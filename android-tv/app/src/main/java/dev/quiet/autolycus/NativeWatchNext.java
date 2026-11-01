package dev.quiet.autolycus;

import android.content.ContentUris;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.media.tv.TvContract;
import android.net.Uri;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

/** On-demand Watch Next publication. Private resume snapshots never enter the TV provider. */
final class NativeWatchNext {
    static final String ACTION_RESUME = "dev.quiet.autolycus.RESUME";
    private static final String PREFIX = "autolycus:";
    private static final ThreadPoolExecutor WORKER =
            new ThreadPoolExecutor(
                    1,
                    1,
                    0,
                    TimeUnit.MILLISECONDS,
                    new ArrayBlockingQueue<>(8),
                    new ThreadPoolExecutor.DiscardOldestPolicy());

    static void progress(
            Context context,
            AutolycusApi api,
            JSONObject item,
            String path,
            long position,
            long duration,
            boolean completed) {
        Context app = context.getApplicationContext();
        String server = api.getServer(), profile = api.getProfile(), encoded = item.toString();
        publish(
                app,
                server,
                profile,
                encoded,
                path,
                position,
                duration,
                completed,
                System.currentTimeMillis());
    }

    private static void publish(
            Context app,
            String server,
            String profile,
            String encoded,
            String path,
            long position,
            long duration,
            boolean completed,
            long engagement) {
        WORKER.execute(
                () -> {
                    try {
                        JSONObject copy = new JSONObject(encoded);
                        if (id(copy).isEmpty()) return;
                        String key = WatchNextPolicy.key(server, profile, id(copy));
                        if (!WatchNextPolicy.continuing(position, duration, completed)) {
                            if (completed) remove(app, key);
                            return;
                        }
                        JSONObject snapshot =
                                new JSONObject()
                                        .put("server", server)
                                        .put("profile", profile)
                                        .put("id", id(copy))
                                        .put("path", path)
                                        .put("position", position)
                                        .put("updated", engagement);
                        preferences(app).edit().putString(key, snapshot.toString()).apply();
                        ContentValues values = new ContentValues();
                        values.put(
                                TvContract.WatchNextPrograms.COLUMN_INTERNAL_PROVIDER_ID,
                                PREFIX + key);
                        values.put(TvContract.WatchNextPrograms.COLUMN_CONTENT_ID, key);
                        values.put(
                                TvContract.WatchNextPrograms.COLUMN_TITLE,
                                copy.optString("title", "Autolycus"));
                        values.put(
                                TvContract.WatchNextPrograms.COLUMN_SHORT_DESCRIPTION,
                                "Continue watching on Autolycus");
                        values.put(
                                TvContract.WatchNextPrograms.COLUMN_TYPE,
                                "series".equals(copy.optString("kind"))
                                        ? TvContract.WatchNextPrograms.TYPE_TV_EPISODE
                                        : TvContract.WatchNextPrograms.TYPE_MOVIE);
                        values.put(
                                TvContract.WatchNextPrograms.COLUMN_WATCH_NEXT_TYPE,
                                TvContract.WatchNextPrograms.WATCH_NEXT_TYPE_CONTINUE);
                        values.put(
                                TvContract.WatchNextPrograms.COLUMN_LAST_PLAYBACK_POSITION_MILLIS,
                                position);
                        values.put(TvContract.WatchNextPrograms.COLUMN_DURATION_MILLIS, duration);
                        values.put(
                                TvContract.WatchNextPrograms.COLUMN_LAST_ENGAGEMENT_TIME_UTC_MILLIS,
                                engagement);
                        String art = WatchNextPolicy.publicArtwork(copy.optString("background"));
                        if (art.isEmpty())
                            art = WatchNextPolicy.publicArtwork(copy.optString("poster"));
                        if (!art.isEmpty()) {
                            values.put(TvContract.WatchNextPrograms.COLUMN_POSTER_ART_URI, art);
                            values.put(
                                    TvContract.WatchNextPrograms.COLUMN_POSTER_ART_ASPECT_RATIO,
                                    art.equals(copy.optString("background"))
                                            ? TvContract.WatchNextPrograms.ASPECT_RATIO_16_9
                                            : TvContract.WatchNextPrograms.ASPECT_RATIO_2_3);
                        }
                        Intent resume =
                                new Intent(app, TvActivity.class)
                                        .setAction(ACTION_RESUME)
                                        .setData(
                                                new Uri.Builder()
                                                        .scheme("autolycus")
                                                        .authority("resume")
                                                        .appendPath(key)
                                                        .build())
                                        .addFlags(
                                                Intent.FLAG_ACTIVITY_NEW_TASK
                                                        | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                        values.put(
                                TvContract.WatchNextPrograms.COLUMN_INTENT_URI,
                                resume.toUri(Intent.URI_INTENT_SCHEME));
                        long row = row(app, key);
                        if (row >= 0)
                            app.getContentResolver()
                                    .update(
                                            ContentUris.withAppendedId(
                                                    TvContract.WatchNextPrograms.CONTENT_URI, row),
                                            values,
                                            null,
                                            null);
                        else
                            app.getContentResolver()
                                    .insert(TvContract.WatchNextPrograms.CONTENT_URI, values);
                        preferences(app).edit().putString("publication", "Published").apply();
                        trim(app);
                    } catch (Exception unavailable) {
                        preferences(app)
                                .edit()
                                .putString("publication", "TV provider unavailable")
                                .apply();
                    }
                });
    }

    static void reconcile(Context context, AutolycusApi api, JSONArray library) {
        Context app = context.getApplicationContext();
        String server = api.getServer(), profile = api.getProfile(), encoded = library.toString();
        WORKER.execute(
                () -> {
                    try {
                        JSONArray items = new JSONArray(encoded);
                        Set<String> keep = new HashSet<>();
                        JSONObject latestItem = null;
                        double latest = -1;
                        for (int i = 0; i < items.length(); i++) {
                            JSONObject item = items.optJSONObject(i);
                            if (item == null) continue;
                            JSONObject progress = item.optJSONObject("progress");
                            if (progress == null || !progress.optBoolean("completed"))
                                keep.add(WatchNextPolicy.key(server, profile, id(item)));
                            if (progress != null
                                    && !progress.optString("path").isEmpty()
                                    && WatchNextPolicy.continuing(
                                            (long) (progress.optDouble("position") * 1000),
                                            (long) (progress.optDouble("duration") * 1000),
                                            progress.optBoolean("completed"))
                                    && progress.optDouble("updated") > latest) {
                                latest = progress.optDouble("updated");
                                latestItem = item;
                            }
                        }
                        for (String key : preferences(app).getAll().keySet())
                            if (key.matches("[0-9a-f]{64}") && !keep.contains(key))
                                remove(app, key);
                        if (latestItem != null
                                && !preferences(app)
                                        .contains(
                                                WatchNextPolicy.key(
                                                        server, profile, id(latestItem)))) {
                            JSONObject progress = latestItem.optJSONObject("progress");
                            long engagement =
                                    latest > 1e12 ? (long) latest : (long) (latest * 1000);
                            publish(
                                    app,
                                    server,
                                    profile,
                                    latestItem.toString(),
                                    progress.optString("path"),
                                    (long) (progress.optDouble("position") * 1000),
                                    (long) (progress.optDouble("duration") * 1000),
                                    false,
                                    Math.min(System.currentTimeMillis(), Math.max(0, engagement)));
                        }
                    } catch (Exception unavailable) {
                        // A failed refresh must not clear authenticated sessions or bookmarks.
                    }
                });
    }

    static JSONObject resume(
            Context context, Intent intent, String server, String profile, JSONArray library) {
        if (!ACTION_RESUME.equals(intent.getAction())
                || intent.getData() == null
                || !"autolycus".equals(intent.getData().getScheme())
                || !"resume".equals(intent.getData().getHost())) return null;
        String key = intent.getData().getLastPathSegment();
        if (key == null || !key.matches("[0-9a-f]{64}")) return null;
        try {
            JSONObject saved = new JSONObject(preferences(context).getString(key, ""));
            if (!server.equals(saved.optString("server"))
                    || !profile.equals(saved.optString("profile"))) return null;
            for (int i = 0; i < library.length(); i++) {
                JSONObject item = library.optJSONObject(i);
                if (item != null && id(item).equals(saved.optString("id"))) {
                    JSONObject resumed = new JSONObject(item.toString());
                    resumed.put(
                            "progress",
                            new JSONObject()
                                    .put("path", saved.getString("path"))
                                    .put("position", saved.optLong("position") / 1000d)
                                    .put("completed", false));
                    return new JSONObject()
                            .put("item", resumed)
                            .put("path", saved.getString("path"));
                }
            }
        } catch (Exception unavailable) {
        }
        return null;
    }

    private static String id(JSONObject item) {
        String id = item.optString("id");
        if (id.isEmpty()) id = item.optString("imdb_id");
        if (id.isEmpty()) id = item.optString("title");
        return id;
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences("watch-next", Context.MODE_PRIVATE);
    }

    private static long row(Context context, String key) {
        try (Cursor cursor =
                context.getContentResolver()
                        .query(
                                TvContract.WatchNextPrograms.CONTENT_URI,
                                new String[] {
                                    "_id", TvContract.WatchNextPrograms.COLUMN_INTERNAL_PROVIDER_ID
                                },
                                null,
                                null,
                                null)) {
            if (cursor != null)
                while (cursor.moveToNext())
                    if ((PREFIX + key).equals(cursor.getString(1))) return cursor.getLong(0);
        }
        return -1;
    }

    private static void remove(Context context, String key) {
        long row = row(context, key);
        if (row >= 0)
            context.getContentResolver()
                    .delete(
                            ContentUris.withAppendedId(
                                    TvContract.WatchNextPrograms.CONTENT_URI, row),
                            null,
                            null);
        preferences(context).edit().remove(key).apply();
    }

    private static void trim(Context context) throws Exception {
        while (preferences(context).getAll().size() > 33) {
            String oldest = null;
            long time = Long.MAX_VALUE;
            for (String key : preferences(context).getAll().keySet()) {
                if (!key.matches("[0-9a-f]{64}")) continue;
                long updated =
                        new JSONObject(preferences(context).getString(key, "{}"))
                                .optLong("updated");
                if (updated < time) {
                    time = updated;
                    oldest = key;
                }
            }
            if (oldest == null) return;
            remove(context, oldest);
        }
    }
}
