package dev.quiet.autolycus;

import java.util.Random;

/** Rejects misleading automatic soundtrack matches as well as testing a known offset. */
final class NativeAudioCorrelationCheck {
    public static void main(String[] args) {
        Random random = new Random(7493);
        double[] reference = new double[800];
        double[] donor = new double[800];
        double[] unrelated = new double[800];
        for (int i = 0; i < reference.length; i++) {
            reference[i] = random.nextDouble();
            donor[i] = random.nextDouble();
            unrelated[i] = random.nextDouble();
        }
        for (int i = 0; i < 760; i++) donor[i + 40] = reference[i];
        double[] match = NativeAudioCorrelation.match(reference, donor, 20, 15);
        if (match == null || Math.abs(match[0] + 2) > 1e-6)
            throw new AssertionError("Known offset was not recovered");
        if (NativeAudioCorrelation.match(reference, unrelated, 20, 15) != null)
            throw new AssertionError("Unrelated audio falsely matched");
        if (NativeAudioCorrelation.match(new double[800], new double[800], 20, 15) != null)
            throw new AssertionError("Silence falsely matched");
        double[] repeated = new double[800];
        for (int i = 0; i < repeated.length; i++) repeated[i] = Math.sin(i * .3);
        if (NativeAudioCorrelation.match(repeated, repeated, 20, 15) != null)
            throw new AssertionError("Ambiguous repetition falsely matched");
        System.out.println("Native audio correlation: offset and false-match rejection PASS");
    }
}
