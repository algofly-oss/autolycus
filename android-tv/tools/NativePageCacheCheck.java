package dev.quiet.autolycus;

/** Budget/ownership checks for native tab reuse, independent of Android and UI mirroring. */
public final class NativePageCacheCheck {
    public static void main(String[] args) {
        NativePageCache<Object> pages = new NativePageCache<>(4, 1000);
        Object forYou = new Object();
        pages.put("all", forYou, 900);
        check(pages.take("all") == forYou, "Full For You page must be reusable without rebuilding");
        check(!pages.contains("all"), "Active page leaves the retained-page budget");
        pages.put("all", forYou, 900);
        pages.put("movie", new Object(), 90);
        pages.put("library", new Object(), 90);
        check(
                !pages.contains("all") && pages.contains("movie"),
                "Oldest retained page evicted under memory pressure");
        Object movie = pages.take("movie");
        pages.put("movie", movie, 90);
        pages.put("oversized", new Object(), 1001);
        check(
                pages.contains("movie") && !pages.contains("oversized"),
                "Oversized pages do not flush other useful tabs");
        pages.clear();
        for (int i = 0; i < 5; i++) pages.put("empty" + i, new Object(), 0);
        check(pages.size() == 4 && !pages.contains("empty0"), "Empty pages still obey entry bound");
        pages.clear();
        check(
                pages.take("movie") == null && pages.size() == 0,
                "Data refresh invalidates stale views");
        System.out.println("Native tab cache ownership, eviction and invalidation: PASS");
    }

    private static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
