package dev.quiet.autolycus;

import android.media.AudioFormat;
import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.os.SystemClock;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

/** Decodes at most two short audio windows per file, never a whole movie or video frames. */
final class NativeAudioAlignment {
    private NativeAudioAlignment() {}

    static double[] align(
            AutolycusApi api,
            String mainUrl,
            String donorUrl,
            int mainTrack,
            int donorTrack,
            double duration,
            AtomicBoolean cancelled)
            throws IOException {
        long deadline = SystemClock.elapsedRealtime() + 55000;
        double first = Math.max(0, Math.min(60, duration / 8));
        double second = Math.max(first, Math.min(first + 300, duration - 45));
        List<double[]> anchors = new ArrayList<>();
        for (double start : new double[] {first, second}) {
            if (start == second && second == first && !anchors.isEmpty()) break;
            check(cancelled, deadline);
            double[] a = envelope(api, mainUrl, mainTrack, start, 40, cancelled, deadline);
            double[] b = envelope(api, donorUrl, donorTrack, start, 40, cancelled, deadline);
            double[] match = NativeAudioCorrelation.match(a, b, 20, 15);
            if (match != null) anchors.add(new double[] {start, match[0]});
            if (first == second) break;
        }
        if (anchors.isEmpty())
            throw new IOException(
                    "No reliable match found. Different edits or dubbed audio may need manual"
                            + " sync.");
        double rate = 1, delay = anchors.get(0)[1];
        if (anchors.size() == 2 && anchors.get(1)[0] - anchors.get(0)[0] > 60) {
            double[] a = anchors.get(0), b = anchors.get(1);
            rate = 1 - (b[1] - a[1]) / (b[0] - a[0]);
            if (rate < .94 || rate > 1.06)
                throw new IOException(
                        "The recordings differ too much for reliable automatic sync. Manual sync is"
                                + " available.");
            delay = a[0] - (a[0] - a[1]) / rate;
        }
        return new double[] {Math.round(delay * 100) / 100d, Math.round(rate * 100000) / 100000d};
    }

    private static double[] envelope(
            AutolycusApi api,
            String url,
            int ordinal,
            double start,
            int seconds,
            AtomicBoolean cancelled,
            long deadline)
            throws IOException {
        if (!NativePlayerDataSource.sameOrigin(api.getServer(), url))
            throw new IOException("Invalid soundtrack source");
        MediaExtractor extractor = new MediaExtractor();
        MediaCodec codec = null;
        int frequency = 20;
        double[] energy = new double[seconds * frequency];
        int[] counts = new int[energy.length];
        try {
            extractor.setDataSource(url, api.headersFor(url));
            List<Integer> audio = new ArrayList<>();
            for (int i = 0; i < extractor.getTrackCount(); i++) {
                String mime = extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME);
                if (mime != null && mime.startsWith("audio/")) audio.add(i);
            }
            if (audio.isEmpty()) throw new IOException("No audio track can be matched");
            int track = audio.get(Math.max(0, Math.min(audio.size() - 1, ordinal)));
            MediaFormat format = extractor.getTrackFormat(track);
            String mime = format.getString(MediaFormat.KEY_MIME);
            extractor.selectTrack(track);
            long beginUs = (long) (start * 1_000_000), endUs = beginUs + seconds * 1_000_000L;
            extractor.seekTo(beginUs, MediaExtractor.SEEK_TO_PREVIOUS_SYNC);
            codec = MediaCodec.createDecoderByType(mime);
            codec.configure(format, null, null, 0);
            codec.start();
            int sampleRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE),
                    channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
            int encoding = AudioFormat.ENCODING_PCM_16BIT;
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            boolean inputEnded = false, ended = false;
            while (!ended) {
                check(cancelled, deadline);
                if (!inputEnded) {
                    int input = codec.dequeueInputBuffer(10000);
                    if (input >= 0) {
                        ByteBuffer buffer = codec.getInputBuffer(input);
                        int size = extractor.readSampleData(buffer, 0);
                        long time = extractor.getSampleTime();
                        if (size < 0 || time >= endUs) {
                            codec.queueInputBuffer(
                                    input, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputEnded = true;
                        } else {
                            codec.queueInputBuffer(input, 0, size, time, 0);
                            extractor.advance();
                        }
                    }
                }
                int output = codec.dequeueOutputBuffer(info, 10000);
                if (output == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    MediaFormat pcm = codec.getOutputFormat();
                    sampleRate = pcm.getInteger(MediaFormat.KEY_SAMPLE_RATE);
                    channels = pcm.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
                    encoding =
                            pcm.containsKey(MediaFormat.KEY_PCM_ENCODING)
                                    ? pcm.getInteger(MediaFormat.KEY_PCM_ENCODING)
                                    : AudioFormat.ENCODING_PCM_16BIT;
                    if (encoding != AudioFormat.ENCODING_PCM_16BIT
                            && encoding != AudioFormat.ENCODING_PCM_FLOAT)
                        throw new IOException(
                                "This decoded audio format cannot be matched automatically. Manual"
                                        + " sync is available.");
                } else if (output >= 0) {
                    ByteBuffer pcm = codec.getOutputBuffer(output);
                    if (pcm != null && info.size > 0) {
                        pcm = pcm.duplicate().order(ByteOrder.LITTLE_ENDIAN);
                        int bytes = encoding == AudioFormat.ENCODING_PCM_FLOAT ? 4 : 2,
                                frameBytes = bytes * Math.max(1, channels);
                        for (int at = 0; at + frameBytes <= info.size; at += frameBytes * 16) {
                            double time =
                                    info.presentationTimeUs / 1_000_000d
                                            + (at / (double) frameBytes) / sampleRate;
                            int bin = (int) Math.floor((time - start) * frequency);
                            if (bin < 0 || bin >= energy.length) continue;
                            int offset = info.offset + at;
                            double value =
                                    encoding == AudioFormat.ENCODING_PCM_FLOAT
                                            ? pcm.getFloat(offset)
                                            : pcm.getShort(offset) / 32768d;
                            energy[bin] += value * value;
                            counts[bin]++;
                        }
                    }
                    ended =
                            (info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0
                                    || info.presentationTimeUs >= endUs;
                    codec.releaseOutputBuffer(output, false);
                }
            }
        } catch (IOException error) {
            throw error;
        } catch (Exception unsupported) {
            throw new IOException(
                    "Audio alignment is unavailable for this codec. Manual sync is available.");
        } finally {
            if (codec != null) {
                try {
                    codec.stop();
                } catch (Exception ignored) {
                }
                codec.release();
            }
            extractor.release();
        }
        for (int i = 0; i < energy.length; i++)
            energy[i] = counts[i] > 0 ? Math.sqrt(energy[i] / counts[i]) : 0;
        return energy;
    }

    private static void check(AtomicBoolean cancelled, long deadline) throws IOException {
        if (cancelled.get())
            throw new IOException("Audio alignment stopped. Manual sync is available.");
        if (SystemClock.elapsedRealtime() > deadline)
            throw new IOException("Audio alignment timed out. Manual sync is available.");
    }
}
