package dev.quiet.autolycus;

public final class WatchNextPolicyCheck {
    public static void main(String[] args) {
        check(WatchNextPolicy.continuing(1000, 10000, false), "Started title resumes");
        check(!WatchNextPolicy.continuing(0, 10000, false), "Unstarted title omitted");
        check(!WatchNextPolicy.continuing(8000, 10000, false), "Final seconds omitted");
        check(!WatchNextPolicy.continuing(5000, 10000, true), "Completed title removed");
        check(!WatchNextPolicy.continuing(5000, -1, false), "Unknown duration omitted");
        String key = WatchNextPolicy.key("server", "profile", "title");
        check(key.matches("[a-f0-9]{64}"), "Opaque ID contains no address or profile");
        check(key.equals(WatchNextPolicy.key("server", "profile", "title")), "Stable update key");
        check(!key.equals(WatchNextPolicy.key("other", "profile", "title")), "Server isolation");
        check(!key.equals(WatchNextPolicy.key("server", "other", "title")), "Profile isolation");
        check(
                !WatchNextPolicy.publicArtwork("https://image.tmdb.org/t/p/w500/poster.jpg")
                        .isEmpty(),
                "Public CDN art allowed");
        for (String unsafe :
                new String[] {
                    "http://image.tmdb.org/poster",
                    "https://image.tmdb.org/poster?token=private",
                    "https://user:password@image.tmdb.org/poster",
                    "/api/poster/private",
                    "https://server.local/api/private",
                    "content://private/art"
                })
            check(
                    WatchNextPolicy.publicArtwork(unsafe).isEmpty(),
                    "Private/signed/unsupported art rejected");
        System.out.println("Watch Next progress, identity isolation and artwork privacy: PASS");
    }

    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
