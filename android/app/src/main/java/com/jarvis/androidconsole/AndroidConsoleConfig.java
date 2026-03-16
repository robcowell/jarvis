package com.jarvis.androidconsole;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

public final class AndroidConsoleConfig {
    private AndroidConsoleConfig() {}

    public static final String DEFAULT_CORE_URL = "http://10.0.2.2:8000";
    public static final String DEFAULT_DEVICE_ID = "android-console";
    public static final String DEFAULT_LOCATION = "unknown";
    public static final int CORE_TIMEOUT_MS = 20_000;

    public static final int SAMPLE_RATE_HZ = 16_000;
    public static final int CHUNK_SIZE = 1024;
    public static final double MAX_DURATION_SECONDS = 6.0;
    public static final double SPEECH_THRESHOLD_RMS = 0.012;
    public static final double SILENCE_DURATION_SECONDS = 0.75;
    public static final double MIN_SPEECH_DURATION_SECONDS = 0.35;
    public static final double NO_SPEECH_TIMEOUT_SECONDS = 2.0;
    public static final int PRE_ROLL_CHUNKS = 2;

    public static final boolean WAKE_WORD_ENABLED = true;
    public static final String[] WAKE_WORDS = new String[]{"jarvis"};
    public static final String WAKE_WORD_DISPLAY = WAKE_WORDS[0];

    public static final Set<String> LOCAL_INTERRUPT_PHRASES = new HashSet<>(
            Arrays.asList("stop", "cancel", "thats enough")
    );
}
