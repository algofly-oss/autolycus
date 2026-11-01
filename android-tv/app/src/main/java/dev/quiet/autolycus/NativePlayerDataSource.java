package dev.quiet.autolycus;

import android.net.Uri;

import androidx.media3.common.C;
import androidx.media3.datasource.BaseDataSource;
import androidx.media3.datasource.DataSpec;

import java.io.BufferedInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

/** Range streaming without forwarding a signed-in session to a redirected third party. */
@androidx.annotation.OptIn(markerClass = androidx.media3.common.util.UnstableApi.class)
final class NativePlayerDataSource extends BaseDataSource {
    private final AutolycusApi api;
    private final Stats stats;
    private HttpURLConnection connection;
    private InputStream input;
    private Uri resolved;
    private long remaining;
    private boolean opened;

    NativePlayerDataSource(AutolycusApi api) {
        this(api, null);
    }

    NativePlayerDataSource(AutolycusApi api, Stats stats) {
        super(true);
        this.api = api;
        this.stats = stats;
    }

    @Override
    public long open(DataSpec spec) throws IOException {
        transferInitializing(spec);
        if (stats != null) {
            stats.requests.incrementAndGet();
            stats.lastRequestedPosition.set(spec.position);
        }
        URL target = new URL(spec.uri.toString());
        for (int redirects = 0; redirects <= 4; redirects++) {
            if (!sameOrigin(api.getServer(), target.toString()))
                throw new IOException("Playback source must remain on the configured server");
            connection = (HttpURLConnection) target.openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(12000);
            connection.setReadTimeout(20000);
            connection.setRequestProperty("Accept-Encoding", "identity");
            connection.setRequestProperty("User-Agent", "AutolycusTV/2 NativePlayer");
            for (Map.Entry<String, String> entry : api.headersFor(target.toString()).entrySet())
                connection.setRequestProperty(entry.getKey(), entry.getValue());
            if (spec.position != 0 || spec.length != C.LENGTH_UNSET) {
                String range = "bytes=" + spec.position + "-";
                if (spec.length != C.LENGTH_UNSET) range += spec.position + spec.length - 1;
                connection.setRequestProperty("Range", range);
            }
            int code = connection.getResponseCode();
            if (code >= 300 && code < 400) {
                String location = connection.getHeaderField("Location");
                connection.disconnect();
                connection = null;
                if (location == null) throw new IOException("Invalid playback redirect");
                target = new URL(target, location);
                continue;
            }
            if (code != 200 && code != 206) {
                connection.disconnect();
                connection = null;
                throw new IOException("Media request failed (HTTP " + code + ")");
            }
            input = new BufferedInputStream(connection.getInputStream(), 128 * 1024);
            long skipped = code == 200 ? spec.position : 0;
            while (skipped > 0) {
                long count = input.skip(skipped);
                if (count == 0) {
                    if (input.read() < 0)
                        throw new IOException("Media seek is past the available data");
                    count = 1;
                }
                skipped -= count;
            }
            remaining = spec.length;
            if (remaining == C.LENGTH_UNSET) {
                long length = connection.getContentLengthLong();
                remaining =
                        length < 0
                                ? C.LENGTH_UNSET
                                : Math.max(0, length - (code == 200 ? spec.position : 0));
            }
            resolved = Uri.parse(target.toString());
            opened = true;
            transferStarted(spec);
            return remaining;
        }
        throw new IOException("Too many media redirects");
    }

    @Override
    public int read(byte[] buffer, int offset, int length) throws IOException {
        if (length == 0) return 0;
        if (remaining == 0) return C.RESULT_END_OF_INPUT;
        int read =
                input.read(
                        buffer,
                        offset,
                        remaining == C.LENGTH_UNSET ? length : (int) Math.min(length, remaining));
        if (read < 0) return C.RESULT_END_OF_INPUT;
        if (remaining != C.LENGTH_UNSET) remaining -= read;
        bytesTransferred(read);
        if (stats != null) {
            stats.bytes.addAndGet(read);
            stats.lastReadAt.set(android.os.SystemClock.elapsedRealtime());
        }
        return read;
    }

    @Override
    public Uri getUri() {
        return resolved;
    }

    @Override
    public Map<String, List<String>> getResponseHeaders() {
        return connection == null ? Collections.emptyMap() : connection.getHeaderFields();
    }

    @Override
    public void close() throws IOException {
        try {
            if (input != null) input.close();
        } finally {
            input = null;
            if (connection != null) connection.disconnect();
            connection = null;
            resolved = null;
            if (opened) {
                opened = false;
                transferEnded();
            }
        }
    }

    static boolean sameOrigin(String first, String second) {
        try {
            URI a = URI.create(first), b = URI.create(second);
            return a.getScheme().equalsIgnoreCase(b.getScheme())
                    && a.getHost().equalsIgnoreCase(b.getHost())
                    && port(a) == port(b)
                    && b.getUserInfo() == null;
        } catch (RuntimeException failure) {
            return false;
        }
    }

    private static int port(URI uri) {
        return uri.getPort() >= 0
                ? uri.getPort()
                : "https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80;
    }

    static final class Stats {
        final AtomicLong bytes = new AtomicLong();
        final AtomicLong requests = new AtomicLong();
        final AtomicLong lastRequestedPosition = new AtomicLong();
        final AtomicLong lastReadAt = new AtomicLong();
    }
}
