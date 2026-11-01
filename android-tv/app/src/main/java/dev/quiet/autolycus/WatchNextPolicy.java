package dev.quiet.autolycus;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Pure publication rules; no authentication or filesystem paths enter launcher metadata. */
final class WatchNextPolicy {
    static String key(String server, String profile, String id) {
        try {
            byte[] bytes =
                    MessageDigest.getInstance("SHA-256")
                            .digest(
                                    (server + "\n" + profile + "\n" + id)
                                            .getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder();
            for (byte b : bytes)
                result.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
            return result.toString();
        } catch (java.security.NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    static boolean continuing(long position, long duration, boolean completed) {
        return !completed && duration > 2000 && position >= 1000 && position < duration - 2000;
    }

    static String publicArtwork(String address) {
        try {
            URI uri = new URI(address);
            String host = uri.getHost();
            boolean publicCdn =
                    "m.media-amazon.com".equalsIgnoreCase(host)
                            || "image.tmdb.org".equalsIgnoreCase(host)
                            || "images.metahub.space".equalsIgnoreCase(host);
            return "https".equalsIgnoreCase(uri.getScheme())
                            && publicCdn
                            && uri.getRawUserInfo() == null
                            && uri.getRawQuery() == null
                            && uri.getRawFragment() == null
                    ? uri.toString()
                    : "";
        } catch (Exception invalid) {
            return "";
        }
    }
}
