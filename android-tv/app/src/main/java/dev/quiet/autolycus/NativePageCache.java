package dev.quiet.autolycus;

import java.util.LinkedHashMap;

/** Bounded detached-page ownership. Taking a page transfers it back to the live viewport. */
final class NativePageCache<T> {
    private final int maxEntries, maxWeight;
    private final LinkedHashMap<String, Entry<T>> pages = new LinkedHashMap<>();
    private int weight;

    NativePageCache(int maxEntries, int maxWeight) {
        if (maxEntries < 1 || maxWeight < 1)
            throw new IllegalArgumentException("Positive cache bounds required");
        this.maxEntries = maxEntries;
        this.maxWeight = maxWeight;
    }

    void put(String key, T value, int cost) {
        if (cost < 0) throw new IllegalArgumentException("Negative page weight");
        take(key);
        if (cost > maxWeight) return;
        pages.put(key, new Entry<>(value, cost));
        weight += cost;
        while (pages.size() > maxEntries || weight > maxWeight)
            take(pages.keySet().iterator().next());
    }

    T take(String key) {
        Entry<T> entry = pages.remove(key);
        if (entry == null) return null;
        weight -= entry.weight;
        return entry.value;
    }

    boolean contains(String key) {
        return pages.containsKey(key);
    }

    int size() {
        return pages.size();
    }

    void clear() {
        pages.clear();
        weight = 0;
    }

    private static final class Entry<T> {
        final T value;
        final int weight;

        Entry(T value, int weight) {
            this.value = value;
            this.weight = weight;
        }
    }
}
