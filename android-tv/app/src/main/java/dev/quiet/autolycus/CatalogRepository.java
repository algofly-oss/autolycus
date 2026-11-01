package dev.quiet.autolycus;

import android.net.Uri;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

/** Catalogue reads and bounded metadata enrichment; never continuously polls the server. */
public final class CatalogRepository {
    private static final int MAX_DISCOVERY_SHELVES = 16;
    private static final int MAX_DISCOVERY_ITEMS = 48;
    private final AutolycusApi api;
    private volatile JSONArray library = new JSONArray();
    private volatile JSONArray cachedDiscovery = new JSONArray();
    private final Map<String, JSONObject> details =
            new LinkedHashMap<String, JSONObject>(32, .75f, true) {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, JSONObject> eldest) {
                    return size() > 128;
                }
            };

    public CatalogRepository(AutolycusApi api) {
        this.api = api;
    }

    /**
     * Compatibility full load. Native home can render loadLibrary() before requesting discovery.
     */
    public JSONObject load() throws IOException {
        JSONObject result = loadLibrary();
        try {
            put(result, "shelves", loadDiscovery());
        } catch (AutolycusApi.ApiException exception) {
            if (exception.statusCode == 401 || exception.statusCode == 403) throw exception;
            put(
                    result,
                    "discovery_error",
                    "Discovery is unavailable. Your library is ready to play.");
        } catch (IOException exception) {
            put(
                    result,
                    "discovery_error",
                    "Discovery is unavailable. Your library is ready to play.");
        }
        return result;
    }

    /**
     * First-party library/profile reads only; external discovery never blocks this first result.
     */
    public JSONObject loadLibrary() throws IOException {
        JSONObject user = api.get("/api/auth/me");
        JSONArray profiles = new JSONArray();
        try {
            profiles = api.get("/api/auth/profiles").optJSONArray("profiles");
            if (profiles == null) profiles = new JSONArray();
            boolean found = false;
            for (int index = 0; index < profiles.length(); index++) {
                if (api.getProfile().equals(profiles.optJSONObject(index).optString("id")))
                    found = true;
            }
            if (!found && profiles.length() > 0)
                api.setProfile(profiles.optJSONObject(0).optString("id", "default"));
        } catch (AutolycusApi.ApiException exception) {
            if (exception.statusCode == 401 || exception.statusCode == 403) throw exception;
        } catch (IOException ignored) {
            // A catalogue read can still work when profile management is temporarily unavailable.
        }
        JSONObject activeProfile = null;
        for (int index = 0; index < profiles.length(); index++) {
            JSONObject candidate = profiles.optJSONObject(index);
            if (candidate != null && api.getProfile().equals(candidate.optString("id")))
                activeProfile = candidate;
        }
        if (activeProfile != null && activeProfile.optJSONObject("preferences") != null) {
            JSONObject mergedPreferences = copy(user.optJSONObject("preferences"));
            JSONObject selectedPreferences = activeProfile.optJSONObject("preferences");
            for (String key :
                    new String[] {
                        "home_view_mode",
                        "search_view_mode",
                        "video_quality",
                        "video_subtitles",
                        "video_audio_language"
                    }) {
                if (selectedPreferences.has(key))
                    put(mergedPreferences, key, selectedPreferences.opt(key));
            }
            put(user, "preferences", mergedPreferences);
        }
        JSONObject local = api.get("/api/files/cinema");
        JSONArray source = local.optJSONArray("items");
        library = source == null ? new JSONArray() : copy(source);
        for (int index = 0; index < library.length(); index++)
            put(library.optJSONObject(index), "owned", true);
        enrichHome();
        JSONObject result = new JSONObject();
        put(result, "library", library);
        put(result, "shelves", matchDiscovery(cachedDiscovery));
        put(result, "user", user);
        put(result, "profiles", profiles);
        put(result, "profile", api.getProfile());
        put(result, "active_profile", activeProfile);
        put(result, "limited", local.optBoolean("limited"));
        put(result, "discovery_error", "");
        return result;
    }

    /** Optional slower external catalogue. A failed refresh retains the last successful shelves. */
    public JSONArray loadDiscovery() throws IOException {
        JSONArray response = api.get("/api/files/cinema/discover").optJSONArray("shelves");
        JSONArray bounded = new JSONArray();
        if (response != null) {
            for (int index = 0;
                    index < Math.min(response.length(), MAX_DISCOVERY_SHELVES);
                    index++) {
                JSONObject original = response.optJSONObject(index);
                if (original == null) continue;
                JSONObject shelf = copy(original);
                JSONArray sourceItems = original.optJSONArray("items");
                JSONArray items = new JSONArray();
                if (sourceItems != null) {
                    for (int item = 0;
                            item < Math.min(sourceItems.length(), MAX_DISCOVERY_ITEMS);
                            item++) {
                        JSONObject value = sourceItems.optJSONObject(item);
                        if (value != null) items.put(copy(value));
                    }
                }
                put(shelf, "items", items);
                bounded.put(shelf);
            }
        }
        // Cache public metadata, not profile-specific progress/ownership merged into an old result.
        cachedDiscovery = bounded;
        return matchDiscovery(bounded);
    }

    private JSONArray matchDiscovery(JSONArray metadata) {
        JSONArray result = new JSONArray();
        for (int index = 0; index < metadata.length(); index++) {
            JSONObject source = metadata.optJSONObject(index);
            if (source == null) continue;
            JSONObject shelf = copy(source);
            JSONArray sourceItems = source.optJSONArray("items");
            JSONArray matched = new JSONArray();
            if (sourceItems != null) {
                for (int item = 0; item < sourceItems.length(); item++) {
                    matched.put(matchOwned(sourceItems.optJSONObject(item)));
                }
            }
            put(shelf, "items", matched);
            result.put(shelf);
        }
        return result;
    }

    /** At most two known titles and one second per optional server-cache lookup. */
    private void enrichHome() {
        JSONArray snapshot = library;
        if (snapshot.length() == 0) return;
        int continuing = 0;
        double latest = 0;
        for (int index = 0; index < snapshot.length(); index++) {
            JSONObject progress = snapshot.optJSONObject(index).optJSONObject("progress");
            if (progress != null
                    && (!progress.optBoolean("completed")
                            || snapshot.optJSONObject(index).optBoolean("next_episode"))
                    && progress.optDouble("updated") > latest) {
                continuing = index;
                latest = progress.optDouble("updated");
            }
        }
        int[] selected = continuing == 0 ? new int[] {0} : new int[] {0, continuing};
        for (int index : selected) {
            JSONObject item = snapshot.optJSONObject(index);
            String imdb = item.optString("imdb_id", "");
            if (imdb.isEmpty()) continue;
            String kind = "series".equals(item.optString("kind")) ? "series" : "movie";
            String key = kind + ":" + imdb;
            try {
                JSONObject rich;
                synchronized (details) {
                    rich = details.get(key);
                }
                if (rich == null) {
                    rich =
                            api.get(
                                            "/api/files/cinema/title/"
                                                    + Uri.encode(imdb)
                                                    + "?kind="
                                                    + kind,
                                            1000)
                                    .optJSONObject("item");
                    if (rich != null)
                        synchronized (details) {
                            details.put(key, copy(rich));
                        }
                }
                if (rich != null) snapshot.put(index, merge(rich, item));
            } catch (IOException | JSONException ignored) {
                // Catalogue browsing never waits indefinitely for artwork or external metadata.
            }
        }
    }

    public JSONArray search(String query) throws IOException {
        String text = query == null ? "" : query.trim();
        String normalized = normalize(text);
        LinkedHashMap<String, JSONObject> found = new LinkedHashMap<>();
        JSONArray snapshot = library;
        for (int index = 0; index < snapshot.length(); index++) {
            JSONObject item = snapshot.optJSONObject(index);
            if (normalize(item.optString("title")).contains(normalized))
                found.put(identity(item), copy(item));
        }
        if (text.length() >= 2) {
            try {
                JSONArray remote =
                        api.get("/api/files/cinema/search?q=" + Uri.encode(text))
                                .optJSONArray("items");
                if (remote != null)
                    for (int index = 0; index < remote.length(); index++) {
                        JSONObject item = matchOwned(remote.optJSONObject(index));
                        found.putIfAbsent(identity(item), item);
                    }
            } catch (IOException exception) {
                if (found.isEmpty()) throw exception;
            }
        }
        JSONArray result = new JSONArray();
        for (JSONObject item : found.values()) result.put(item);
        return result;
    }

    public JSONObject detail(JSONObject item) throws IOException {
        if (item == null) return new JSONObject();
        String imdb = item.optString("imdb_id", "");
        if (imdb.isEmpty() && item.optString("id").matches("tt[0-9]{5,12}"))
            imdb = item.optString("id");
        String kind = "series".equals(item.optString("kind")) ? "series" : "movie";
        JSONObject remote = null;
        if (imdb.isEmpty()) {
            JSONArray candidates =
                    api.get("/api/files/cinema/search?q=" + Uri.encode(item.optString("title")))
                            .optJSONArray("items");
            if (candidates != null)
                for (int index = 0; index < candidates.length(); index++) {
                    JSONObject candidate = candidates.optJSONObject(index);
                    if (kind.equals(candidate.optString("kind"))
                            && normalize(item.optString("title"))
                                    .equals(normalize(candidate.optString("title")))
                            && compatibleYear(item, candidate)) {
                        remote = candidate;
                        imdb = candidate.optString("imdb_id", "");
                        break;
                    }
                }
        }
        if (!imdb.isEmpty()) {
            String key = kind + ":" + imdb;
            synchronized (details) {
                remote = details.get(key);
            }
            if (remote == null) {
                remote =
                        api.get("/api/files/cinema/title/" + Uri.encode(imdb) + "?kind=" + kind)
                                .optJSONObject("item");
                if (remote != null)
                    synchronized (details) {
                        details.put(key, copy(remote));
                    }
            }
        }
        JSONObject result = merge(remote, item);
        if (item.optBoolean("owned")) {
            for (int index = 0; index < library.length(); index++) {
                JSONObject local = library.optJSONObject(index);
                if (item.optString("id").equals(local.optString("id"))) {
                    try {
                        library.put(index, result);
                    } catch (JSONException ignored) {
                    }
                    break;
                }
            }
        }
        return matchOwned(result);
    }

    private JSONObject matchOwned(JSONObject item) {
        if (item == null) return new JSONObject();
        JSONArray snapshot = library;
        for (int index = 0; index < snapshot.length(); index++) {
            JSONObject local = snapshot.optJSONObject(index);
            boolean sameImdb =
                    !item.optString("imdb_id").isEmpty()
                            && item.optString("imdb_id").equals(local.optString("imdb_id"));
            boolean sameTitle =
                    normalize(item.optString("title")).equals(normalize(local.optString("title")))
                            && compatibleYear(item, local);
            if (item.optString("kind").equals(local.optString("kind")) && (sameImdb || sameTitle))
                return merge(item, local);
        }
        return copy(item);
    }

    private static boolean compatibleYear(JSONObject first, JSONObject second) {
        int a = first.optInt("year"), b = second.optInt("year");
        return a == 0 || b == 0 || Math.abs(a - b) <= 1;
    }

    private static JSONObject merge(JSONObject rich, JSONObject local) {
        JSONObject result = copy(rich);
        if (local == null) return result;
        for (Iterator<String> keys = local.keys(); keys.hasNext(); ) {
            String key = keys.next();
            Object value = local.opt(key);
            if (value == null
                    || value == JSONObject.NULL
                    || value instanceof String && ((String) value).isBlank()) continue;
            if (value instanceof JSONArray
                    && ((JSONArray) value).length() == 0
                    && result.optJSONArray(key) != null) continue;
            put(result, key, value);
        }
        return result;
    }

    private static String identity(JSONObject item) {
        String imdb = item.optString("imdb_id", "");
        return imdb.isEmpty()
                ? normalize(item.optString("title"))
                        + ':'
                        + item.optString("kind")
                        + ':'
                        + item.optInt("year")
                : imdb;
    }

    private static String normalize(String value) {
        return value.toLowerCase(Locale.ROOT).replaceAll("[^\\p{L}\\p{N}]+", "");
    }

    private static JSONObject copy(JSONObject value) {
        if (value == null) return new JSONObject();
        try {
            return new JSONObject(value.toString());
        } catch (JSONException ignored) {
            return new JSONObject();
        }
    }

    private static JSONArray copy(JSONArray value) {
        try {
            return new JSONArray(value.toString());
        } catch (JSONException ignored) {
            return new JSONArray();
        }
    }

    private static void put(JSONObject target, String key, Object value) {
        if (target == null) return;
        try {
            target.put(key, value);
        } catch (JSONException ignored) {
        }
    }
}
