package dev.quiet.autolycus;

/** Bounded normalized energy correlation. Ambiguous or silent audio is not a match. */
final class NativeAudioCorrelation {
    private NativeAudioCorrelation() {}

    static double[] match(double[] reference, double[] donor, int frequency, int maxOffset) {
        int limit = maxOffset * frequency;
        double[] scores = new double[limit * 2 + 1];
        java.util.Arrays.fill(scores, -2);
        int bestLag = 0;
        double best = -2;
        for (int lag = -limit; lag <= limit; lag++) {
            int begin = Math.max(0, -lag), end = Math.min(reference.length, donor.length - lag);
            if (end - begin < frequency * 4) continue;
            double a = 0, b = 0, aa = 0, bb = 0, ab = 0;
            for (int i = begin; i < end; i++) {
                double x = reference[i], y = donor[i + lag];
                a += x;
                b += y;
                aa += x * x;
                bb += y * y;
                ab += x * y;
            }
            int n = end - begin;
            double variance = (aa - a * a / n) * (bb - b * b / n);
            if (variance <= 1e-10) continue;
            double score = (ab - a * b / n) / Math.sqrt(variance);
            scores[lag + limit] = score;
            if (score > best) {
                best = score;
                bestLag = lag;
            }
        }
        double rival = -2;
        for (int lag = -limit; lag <= limit; lag++)
            if (Math.abs(lag - bestLag) > frequency) rival = Math.max(rival, scores[lag + limit]);
        return best < .72 || rival > -2 && best - rival < .08
                ? null
                : new double[] {-bestLag / (double) frequency, best};
    }
}
