package dev.quiet.autolycus;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.CookiePolicy;
import java.net.HttpCookie;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URISyntaxException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Blocking first-party API client. Call requests from a bounded worker executor. */
public final class AutolycusApi {
    private static final int MAX_JSON_BYTES = 8 * 1024 * 1024;
    private static final String KEY_ALIAS = "autolycus.native.session.v1";
    private static final String USER_AGENT = "AutolycusNativeTV/1.0 (Android TV)";
    private final String server;
    private final URI origin;
    private final SharedPreferences preferences;
    private final String storageKey;
    private final java.net.CookieManager cookies =
            new java.net.CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER);
    private volatile String profile;

    public AutolycusApi(Context context, String server) {
        try {
            URI parsed = new URI(server.trim());
            if (!("https".equalsIgnoreCase(parsed.getScheme())
                            || "http".equalsIgnoreCase(parsed.getScheme()))
                    || parsed.getHost() == null
                    || parsed.getUserInfo() != null) {
                throw new IllegalArgumentException("Enter an http:// or https:// server address");
            }
            origin =
                    new URI(
                            parsed.getScheme().toLowerCase(Locale.ROOT),
                            null,
                            parsed.getHost().toLowerCase(Locale.ROOT),
                            parsed.getPort(),
                            "/",
                            null,
                            null);
            this.server = origin.toString();
            storageKey =
                    hex(
                            MessageDigest.getInstance("SHA-256")
                                    .digest(this.server.getBytes(StandardCharsets.UTF_8)));
        } catch (IllegalArgumentException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new IllegalArgumentException("Invalid server address");
        }
        preferences =
                context.getApplicationContext()
                        .getSharedPreferences("native-api", Context.MODE_PRIVATE);
        profile = preferences.getString(storageKey + ".profile", "default");
        loadCookies();
        migrateOwnWebSession();
    }

    public String getServer() {
        return server;
    }

    public String getProfile() {
        return profile;
    }

    public void setProfile(String value) {
        profile = value == null || value.isEmpty() ? "default" : value;
        preferences.edit().putString(storageKey + ".profile", profile).apply();
    }

    /** Resolves artwork URLs too; authentication is attached only to this server's origin. */
    public String absolute(String value) {
        try {
            URI target = origin.resolve(value == null ? "" : value);
            if (!("http".equalsIgnoreCase(target.getScheme())
                            || "https".equalsIgnoreCase(target.getScheme()))
                    || target.getHost() == null
                    || target.getUserInfo() != null) {
                throw new IllegalArgumentException("Unsupported URL");
            }
            return target.toASCIIString();
        } catch (IllegalArgumentException exception) {
            throw new IllegalArgumentException("Unsupported URL");
        }
    }

    public boolean isFirstParty(String value) {
        try {
            URI target = new URI(absolute(value));
            return sameOrigin(origin, target);
        } catch (Exception ignored) {
            return false;
        }
    }

    public Map<String, String> headersFor(String value) {
        LinkedHashMap<String, String> headers = new LinkedHashMap<>();
        headers.put("User-Agent", USER_AGENT);
        if (!isFirstParty(value)) return headers;
        headers.put("X-Profile-ID", profile);
        try {
            synchronized (cookies) {
                Map<String, List<String>> selected =
                        cookies.get(new URI(absolute(value)), Collections.emptyMap());
                for (Map.Entry<String, List<String>> entry : selected.entrySet()) {
                    if ("Cookie".equalsIgnoreCase(entry.getKey()) && !entry.getValue().isEmpty()) {
                        headers.put("Cookie", String.join("; ", entry.getValue()));
                    }
                }
            }
        } catch (IOException | URISyntaxException ignored) {
            // An invalid target must never receive a session header.
        }
        return headers;
    }

    public JSONObject get(String path) throws IOException {
        return request("GET", path, null, 20000);
    }

    /** A bounded optional metadata read; a timeout never clears authentication. */
    public JSONObject get(String path, int timeoutMillis) throws IOException {
        return request("GET", path, null, Math.max(250, Math.min(timeoutMillis, 20000)));
    }

    public JSONObject post(String path, JSONObject body) throws IOException {
        return request("POST", path, body, 20000);
    }

    public JSONObject put(String path, JSONObject body) throws IOException {
        return request("PUT", path, body, 20000);
    }

    public JSONObject patch(String path, JSONObject body) throws IOException {
        return request("PATCH", path, body, 20000);
    }

    public JSONObject delete(String path) throws IOException {
        return request("DELETE", path, null, 20000);
    }

    private JSONObject request(String method, String path, JSONObject body, int timeoutMillis)
            throws IOException {
        String target;
        try {
            target = absolute(path);
        } catch (IllegalArgumentException exception) {
            throw new IOException("Invalid API address");
        }
        if (!isFirstParty(target))
            throw new IOException("API requests must use the configured server");
        for (int redirects = 0; redirects <= 3; redirects++) {
            HttpURLConnection connection = (HttpURLConnection) new URL(target).openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(Math.min(8000, timeoutMillis));
            connection.setReadTimeout(timeoutMillis);
            connection.setRequestMethod(method);
            connection.setRequestProperty("Accept", "application/json");
            for (Map.Entry<String, String> header : headersFor(target).entrySet()) {
                connection.setRequestProperty(header.getKey(), header.getValue());
            }
            try {
                if (body != null) {
                    byte[] encoded = body.toString().getBytes(StandardCharsets.UTF_8);
                    connection.setRequestProperty(
                            "Content-Type", "application/json; charset=utf-8");
                    connection.setDoOutput(true);
                    connection.setFixedLengthStreamingMode(encoded.length);
                    try (OutputStream output = connection.getOutputStream()) {
                        output.write(encoded);
                    }
                }
                int status = connection.getResponseCode();
                synchronized (cookies) {
                    cookies.put(URI.create(target), connection.getHeaderFields());
                    saveCookies();
                }
                if (status == 301
                        || status == 302
                        || status == 303
                        || status == 307
                        || status == 308) {
                    String location = connection.getHeaderField("Location");
                    String next =
                            location == null ? "" : URI.create(target).resolve(location).toString();
                    if (!isFirstParty(next))
                        throw new IOException("The server redirected to another origin");
                    target = next;
                    if (status == 303
                            || ((status == 301 || status == 302) && "POST".equals(method))) {
                        method = "GET";
                        body = null;
                    }
                    continue;
                }
                InputStream stream =
                        status >= 400 ? connection.getErrorStream() : connection.getInputStream();
                String text =
                        stream == null ? "" : read(stream, status >= 400 ? 16384 : MAX_JSON_BYTES);
                JSONObject result;
                try {
                    result = text.isBlank() ? new JSONObject() : new JSONObject(text);
                } catch (JSONException exception) {
                    if (status >= 400)
                        throw new ApiException(status, "Server request failed (" + status + ")");
                    throw new IOException("The server returned an unexpected response");
                }
                if (status >= 400) {
                    String detail =
                            result.optString("detail", "Server request failed (" + status + ")");
                    if (detail.length() > 240 || detail.indexOf('\n') >= 0)
                        detail = "Server request failed (" + status + ")";
                    throw new ApiException(status, detail);
                }
                return result;
            } finally {
                connection.disconnect();
            }
        }
        throw new IOException("Too many server redirects");
    }

    private static String read(InputStream input, int maximum) throws IOException {
        try (InputStream stream = input;
                ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = stream.read(buffer)) >= 0) {
                if (output.size() + count > maximum)
                    throw new IOException("Server response is too large");
                output.write(buffer, 0, count);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    private void migrateOwnWebSession() {
        String flag = storageKey + ".web-session-migrated";
        if (preferences.getBoolean(flag, false)) return;
        synchronized (cookies) {
            if (cookies.getCookieStore().getCookies().isEmpty()) {
                try {
                    String ownSession =
                            android.webkit.CookieManager.getInstance().getCookie(server);
                    if (ownSession != null) {
                        for (String pair : ownSession.split(";")) {
                            int separator = pair.indexOf('=');
                            if (separator <= 0) continue;
                            HttpCookie cookie =
                                    new HttpCookie(
                                            pair.substring(0, separator).trim(),
                                            pair.substring(separator + 1).trim());
                            cookie.setDomain(origin.getHost());
                            cookie.setPath("/");
                            cookie.setHttpOnly(true);
                            cookie.setSecure("https".equals(origin.getScheme()));
                            // The server remains authoritative about expiration and revocation.
                            cookie.setMaxAge(400L * 24 * 60 * 60);
                            cookies.getCookieStore().add(origin, cookie);
                        }
                        saveCookies();
                    }
                } catch (Exception ignored) {
                    // A missing WebView provider or old session does not prevent native sign-in.
                }
            }
        }
        preferences.edit().putBoolean(flag, true).apply();
    }

    private void saveCookies() throws IOException {
        try {
            JSONArray array = new JSONArray();
            long now = System.currentTimeMillis();
            for (HttpCookie cookie : cookies.getCookieStore().getCookies()) {
                if (cookie.hasExpired()) continue;
                JSONObject entry = new JSONObject();
                entry.put("name", cookie.getName());
                entry.put("value", cookie.getValue());
                entry.put("domain", cookie.getDomain());
                entry.put("path", cookie.getPath());
                entry.put("secure", cookie.getSecure());
                entry.put("httpOnly", cookie.isHttpOnly());
                long seconds = cookie.getMaxAge() < 0 ? 400L * 86400 : cookie.getMaxAge();
                entry.put("expires", now + seconds * 1000);
                array.put(entry);
            }
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, encryptionKey());
            byte[] ciphertext = cipher.doFinal(array.toString().getBytes(StandardCharsets.UTF_8));
            String stored =
                    Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP)
                            + "."
                            + Base64.encodeToString(ciphertext, Base64.NO_WRAP);
            if (!preferences.edit().putString(storageKey + ".cookies", stored).commit()) {
                throw new IOException("Could not retain the login session on this TV");
            }
        } catch (IOException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new IOException("Could not retain the login session on this TV");
        }
    }

    private void loadCookies() {
        String stored = preferences.getString(storageKey + ".cookies", "");
        if (stored.isEmpty()) return;
        try {
            String[] parts = stored.split("\\.", 2);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(
                    Cipher.DECRYPT_MODE,
                    encryptionKey(),
                    new GCMParameterSpec(128, Base64.decode(parts[0], Base64.NO_WRAP)));
            JSONArray array =
                    new JSONArray(
                            new String(
                                    cipher.doFinal(Base64.decode(parts[1], Base64.NO_WRAP)),
                                    StandardCharsets.UTF_8));
            long now = System.currentTimeMillis();
            for (int index = 0; index < array.length(); index++) {
                JSONObject entry = array.getJSONObject(index);
                long remaining = (entry.optLong("expires") - now) / 1000;
                if (remaining <= 0) continue;
                HttpCookie cookie =
                        new HttpCookie(entry.getString("name"), entry.getString("value"));
                cookie.setDomain(entry.optString("domain", origin.getHost()));
                cookie.setPath(entry.optString("path", "/"));
                cookie.setSecure(entry.optBoolean("secure"));
                cookie.setHttpOnly(entry.optBoolean("httpOnly"));
                cookie.setMaxAge(remaining);
                cookies.getCookieStore().add(origin, cookie);
            }
        } catch (Exception ignored) {
            // Keep the encrypted record in place; never erase a login on transient failures.
        }
    }

    private static synchronized SecretKey encryptionKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(KEY_ALIAS)) return (SecretKey) store.getKey(KEY_ALIAS, null);
        KeyGenerator generator =
                KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(
                new KeyGenParameterSpec.Builder(
                                KEY_ALIAS,
                                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                        .build());
        return generator.generateKey();
    }

    private static boolean sameOrigin(URI first, URI second) {
        return first.getScheme().equalsIgnoreCase(second.getScheme())
                && first.getHost().equalsIgnoreCase(second.getHost())
                && effectivePort(first) == effectivePort(second);
    }

    private static int effectivePort(URI uri) {
        return uri.getPort() >= 0
                ? uri.getPort()
                : "https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80;
    }

    private static String hex(byte[] bytes) {
        StringBuilder value = new StringBuilder();
        for (byte item : bytes) value.append(String.format(Locale.ROOT, "%02x", item));
        return value.toString();
    }

    public static final class ApiException extends IOException {
        public final int statusCode;

        ApiException(int statusCode, String message) {
            super(message);
            this.statusCode = statusCode;
        }
    }
}
