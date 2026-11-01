package dev.quiet.autolycus;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Handler;
import android.os.Looper;
import android.util.LruCache;
import android.widget.ImageView;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Bounded artwork loading shared by native catalogue and detail surfaces. */
final class NativeArtwork {
    private static final ExecutorService WORKERS = Executors.newFixedThreadPool(3);
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final LruCache<String, Bitmap> CACHE =
            new LruCache<String, Bitmap>(24 * 1024 * 1024) {
                @Override
                protected int sizeOf(String key, Bitmap value) {
                    return value.getAllocationByteCount();
                }
            };
    private final AutolycusApi api;

    NativeArtwork(AutolycusApi api) {
        this.api = api;
    }

    void load(ImageView target, String address, int width, int height) {
        load(target, address, width, height, null);
    }

    void load(ImageView target, String address, int width, int height, Runnable shown) {
        if (address == null || address.isEmpty() || "null".equals(address)) return;
        final String url = api.absolute(address);
        final String key = url + "|" + width + "x" + height;
        target.setTag(key);
        Bitmap ready = CACHE.get(key);
        if (ready != null) {
            target.animate().cancel();
            target.setImageBitmap(ready);
            target.setAlpha(1f);
            if (shown != null) shown.run();
            return;
        }
        WORKERS.execute(
                () -> {
                    try {
                        byte[] bytes = read(url);
                        BitmapFactory.Options bounds = new BitmapFactory.Options();
                        bounds.inJustDecodeBounds = true;
                        BitmapFactory.decodeByteArray(bytes, 0, bytes.length, bounds);
                        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return;
                        BitmapFactory.Options options = new BitmapFactory.Options();
                        options.inSampleSize = 1;
                        while (bounds.outWidth / (options.inSampleSize * 2) >= Math.max(1, width)
                                && bounds.outHeight / (options.inSampleSize * 2)
                                        >= Math.max(1, height)) options.inSampleSize *= 2;
                        options.inPreferredConfig = Bitmap.Config.ARGB_8888;
                        Bitmap bitmap =
                                BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
                        if (bitmap == null) return;
                        CACHE.put(key, bitmap);
                        MAIN.post(
                                () -> {
                                    if (!key.equals(target.getTag())) return;
                                    target.animate().cancel();
                                    boolean replacing = target.getDrawable() != null;
                                    target.setImageBitmap(bitmap);
                                    target.setAlpha(replacing || shown != null ? 1f : 0f);
                                    if (shown != null) shown.run();
                                    else if (!replacing)
                                        target.animate().alpha(1f).setDuration(180).start();
                                });
                    } catch (Exception ignored) {
                        // Missing artwork keeps its native placeholder, without repeated retries.
                    }
                });
    }

    private byte[] read(String initial) throws Exception {
        String address = initial;
        for (int redirects = 0; redirects < 4; redirects++) {
            URL url = new URL(address);
            if (!"http".equals(url.getProtocol()) && !"https".equals(url.getProtocol()))
                throw new IllegalArgumentException("Unsupported artwork address");
            HttpURLConnection connection = (HttpURLConnection) url.openConnection();
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(12000);
            connection.setInstanceFollowRedirects(false);
            for (Map.Entry<String, String> header : api.headersFor(address).entrySet())
                connection.setRequestProperty(header.getKey(), header.getValue());
            try {
                int status = connection.getResponseCode();
                if (status >= 300 && status < 400) {
                    String location = connection.getHeaderField("Location");
                    if (location == null)
                        throw new IllegalStateException("Artwork redirect failed");
                    address = new URI(address).resolve(location).toString();
                    continue;
                }
                if (status != 200) throw new IllegalStateException("Artwork unavailable");
                try (InputStream input = connection.getInputStream();
                        ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                    byte[] buffer = new byte[16384];
                    int count;
                    while ((count = input.read(buffer)) >= 0) {
                        if (output.size() + count > 12 * 1024 * 1024)
                            throw new IllegalStateException("Artwork exceeds cache budget");
                        output.write(buffer, 0, count);
                    }
                    return output.toByteArray();
                }
            } finally {
                connection.disconnect();
            }
        }
        throw new IllegalStateException("Too many artwork redirects");
    }
}
