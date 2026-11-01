package dev.quiet.autolycus;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Rect;
import android.net.Uri;
import android.os.SystemClock;
import android.view.View;

import androidx.media3.common.C;
import androidx.media3.datasource.DataSpec;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;

/** Bounded, on-demand server sprite previews; no video decoder or polling loop. */
@androidx.annotation.OptIn(markerClass = androidx.media3.common.util.UnstableApi.class)
final class NativePlayerPreview extends View {
    private final AutolycusApi api;
    private final ExecutorService worker;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private String path;
    private Bitmap sprite;
    private JSONObject metadata;
    private boolean attempted, closed, active;
    private long attemptedAt;
    private long position;
    private int generation;

    NativePlayerPreview(Context context, AutolycusApi api, ExecutorService worker) {
        super(context);
        this.api = api;
        this.worker = worker;
        setFocusable(false);
    }

    void setPath(String path) {
        generation++;
        this.path = path;
        sprite = null;
        metadata = null;
        attempted = false;
        setVisibility(GONE);
    }

    void showPosition(long milliseconds) {
        active = true;
        position = milliseconds;
        if (sprite != null) {
            setVisibility(VISIBLE);
            invalidate();
            return;
        }
        if (attempted && SystemClock.elapsedRealtime() - attemptedAt < 5000
                || path == null
                || closed
                || worker.isShutdown()) return;
        attempted = true;
        attemptedAt = SystemClock.elapsedRealtime();
        int request = generation;
        String source = path;
        worker.execute(
                () -> {
                    NativePlayerDataSource stream = null;
                    try {
                        JSONObject info =
                                api.get(
                                        "/api/files/playback/preview?path="
                                                + URLEncoder.encode(
                                                        source, StandardCharsets.UTF_8));
                        if (!"ready".equals(info.optString("status"))) return;
                        String image = api.absolute(info.optString("image"));
                        stream = new NativePlayerDataSource(api);
                        long length = stream.open(new DataSpec(Uri.parse(image)));
                        if (length > 8 * 1024 * 1024) return;
                        ByteArrayOutputStream output = new ByteArrayOutputStream();
                        byte[] data = new byte[16384];
                        while (output.size() <= 8 * 1024 * 1024) {
                            int count = stream.read(data, 0, data.length);
                            if (count == C.RESULT_END_OF_INPUT) break;
                            output.write(data, 0, count);
                        }
                        if (output.size() > 8 * 1024 * 1024) return;
                        byte[] bytes = output.toByteArray();
                        BitmapFactory.Options bounds = new BitmapFactory.Options();
                        bounds.inJustDecodeBounds = true;
                        BitmapFactory.decodeByteArray(bytes, 0, bytes.length, bounds);
                        if (bounds.outWidth <= 0
                                || bounds.outHeight <= 0
                                || (long) bounds.outWidth * bounds.outHeight > 16_000_000) return;
                        Bitmap decoded = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                        post(
                                () -> {
                                    if (closed || request != generation || decoded == null) return;
                                    metadata = info;
                                    sprite = decoded;
                                    if (active) setVisibility(VISIBLE);
                                    invalidate();
                                });
                    } catch (Exception ignored) {
                        // A missing sprite never blocks seeking or playback.
                    } finally {
                        if (stream != null)
                            try {
                                stream.close();
                            } catch (Exception ignored) {
                            }
                    }
                });
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (sprite == null || metadata == null) return;
        int columns = Math.max(1, metadata.optInt("columns", 1));
        int rows = Math.max(1, metadata.optInt("rows", 1));
        int count = Math.max(1, metadata.optInt("count", columns * rows));
        double duration = Math.max(.001, metadata.optDouble("duration", 1));
        int index = Math.max(0, Math.min(count - 1, (int) (position / 1000d / duration * count)));
        int width = sprite.getWidth() / columns, height = sprite.getHeight() / rows;
        Rect source =
                new Rect(
                        index % columns * width,
                        index / columns * height,
                        (index % columns + 1) * width,
                        (index / columns + 1) * height);
        canvas.drawBitmap(sprite, source, new Rect(0, 0, getWidth(), getHeight()), paint);
    }

    void close() {
        closed = true;
        generation++;
        sprite = null;
        metadata = null;
    }

    void hide() {
        active = false;
        setVisibility(GONE);
    }
}
