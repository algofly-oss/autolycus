package dev.quiet.autolycus;

/** Container track IDs are not track-list ordinals. Zero means default track. */
final class NativePlayerTrackIds {
    private NativePlayerTrackIds() {}

    static Integer containerId(String value) {
        if (value == null || !value.matches("[0-9]{1,10}")) return null;
        try {
            long parsed = Long.parseLong(value);
            return parsed > 0 && parsed <= Integer.MAX_VALUE ? (int) parsed : null;
        } catch (NumberFormatException invalid) {
            return null;
        }
    }
}
