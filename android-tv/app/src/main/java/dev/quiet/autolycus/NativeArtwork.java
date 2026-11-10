package dev.quiet.autolycus;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Handler;
import android.os.Looper;
import android.util.LruCache;
import android.widget.ImageView;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.lang.ref.WeakReference;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

/** Bounded artwork loading shared by native catalogue and detail surfaces. */
final class NativeArtwork {
    private static final Map<String, Request> REQUESTS = new HashMap<>();
    private static final ThreadPoolExecutor WORKERS =
            new ThreadPoolExecutor(
                    3,
                    3,
                    0,
                    TimeUnit.MILLISECONDS,
                    new ArrayBlockingQueue<>(128),
                    task ->
                            new Thread(
                                    () -> {
                                        android.os.Process.setThreadPriority(
                                                android.os.Process.THREAD_PRIORITY_BACKGROUND);
                                        task.run();
                                    },
                                    "AutolycusArtwork"),
                    (task, executor) -> {
                        Runnable oldest = executor.getQueue().poll();
                        if (oldest instanceof Request) ((Request) oldest).discard();
                        if (!executor.isShutdown()) executor.execute(task);
                        else if (task instanceof Request) ((Request) task).discard();
                    });
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
        cancel(target);
        target.setTag(key);
        Bitmap ready = CACHE.get(key);
        if (ready != null) {
            target.animate().cancel();
            target.setImageBitmap(ready);
            target.setAlpha(1f);
            if (shown != null) shown.run();
            return;
        }
        Request request;
        synchronized (REQUESTS) {
            request = REQUESTS.get(key);
            if (request != null) {
                request.targets.add(new Target(target, shown));
                return;
            }
            request = new Request(this, key, url, width, height);
            request.targets.add(new Target(target, shown));
            REQUESTS.put(key, request);
        }
        WORKERS.execute(request);
    }

    /** Detach a hidden image and remove work that has not started; running reads stay bounded. */
    static void cancel(ImageView target) {
        Object previous = target.getTag();
        target.setTag(null);
        target.animate().cancel();
        synchronized (REQUESTS) {
            Request request = REQUESTS.get(previous);
            if (request == null) return;
            request.targets.removeIf(t -> t.view.get() == null || t.view.get() == target);
            if (request.targets.isEmpty() && !request.started && WORKERS.remove(request)) {
                REQUESTS.remove(request.key);
            }
        }
    }

    private static final class Target {
        final WeakReference<ImageView> view;
        final Runnable shown;

        Target(ImageView view, Runnable shown) {
            this.view = new WeakReference<>(view);
            this.shown = shown;
        }
    }

    private static final class Request implements Runnable {
        final NativeArtwork loader;
        final String key, url;
        final int width, height;
        final List<Target> targets = new ArrayList<>();
        boolean started;

        Request(NativeArtwork loader, String key, String url, int width, int height) {
            this.loader = loader;
            this.key = key;
            this.url = url;
            this.width = width;
            this.height = height;
        }

        void discard() {
            synchronized (REQUESTS) {
                if (REQUESTS.get(key) == this) REQUESTS.remove(key);
                targets.clear();
            }
        }

        @Override
        public void run() {
            synchronized (REQUESTS) {
                started = true;
            }
            try {
                byte[] bytes = loader.read(url);
                BitmapFactory.Options bounds = new BitmapFactory.Options();
                bounds.inJustDecodeBounds = true;
                BitmapFactory.decodeByteArray(bytes, 0, bytes.length, bounds);
                if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return;
                BitmapFactory.Options options = new BitmapFactory.Options();
                options.inSampleSize = 1;
                while (bounds.outWidth / (options.inSampleSize * 2) >= Math.max(1, width)
                        && bounds.outHeight / (options.inSampleSize * 2) >= Math.max(1, height))
                    options.inSampleSize *= 2;
                options.inPreferredConfig = Bitmap.Config.ARGB_8888;
                Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length, options);
                if (bitmap == null) return;
                bitmap.prepareToDraw();
                CACHE.put(key, bitmap);
                List<Target> listeners;
                synchronized (REQUESTS) {
                    listeners = new ArrayList<>(targets);
                    discard();
                }
                MAIN.post(
                        () -> {
                            for (Target listener : listeners) {
                                ImageView target = listener.view.get();
                                if (target == null || !key.equals(target.getTag())) continue;
                                target.animate().cancel();
                                boolean replacing = target.getDrawable() != null;
                                target.setImageBitmap(bitmap);
                                target.setAlpha(replacing || listener.shown != null ? 1f : 0f);
                                if (listener.shown != null) listener.shown.run();
                                else if (!replacing)
                                    target.animate().alpha(1f).setDuration(180).start();
                            }
                        });
            } catch (Exception ignored) {
                // Missing artwork keeps its native placeholder, without repeated retries.
            } finally {
                discard();
            }
        }
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
