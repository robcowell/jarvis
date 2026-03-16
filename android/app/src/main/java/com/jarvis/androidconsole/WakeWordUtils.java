package com.jarvis.androidconsole;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class WakeWordUtils {
    private WakeWordUtils() {}

    public static String normalizePhrase(String text) {
        if (text == null) {
            return "";
        }
        String lowered = text.trim().toLowerCase(Locale.US).replace("'", "");
        String cleaned = lowered.replaceAll("[^a-z0-9\\s]", " ");
        return cleaned.replaceAll("\\s+", " ").trim();
    }

    public static boolean containsWakeWord(String text) {
        if (text == null || text.trim().isEmpty()) {
            return false;
        }
        for (String word : AndroidConsoleConfig.WAKE_WORDS) {
            Pattern pattern = Pattern.compile("\\b" + Pattern.quote(word) + "\\b", Pattern.CASE_INSENSITIVE);
            if (pattern.matcher(text).find()) {
                return true;
            }
        }
        return false;
    }

    public static String stripWakeWord(String text) {
        if (text == null || text.isEmpty()) {
            return "";
        }
        String updated = text;
        for (String word : AndroidConsoleConfig.WAKE_WORDS) {
            Pattern pattern = Pattern.compile("\\b" + Pattern.quote(word) + "\\b", Pattern.CASE_INSENSITIVE);
            Matcher matcher = pattern.matcher(updated);
            if (matcher.find()) {
                updated = matcher.replaceFirst("");
                break;
            }
        }
        updated = updated.replaceAll("\\s+", " ");
        return updated.replaceAll("^[\\s,.;:!?-]+|[\\s,.;:!?-]+$", "");
    }

    public static boolean isLocalInterruptCommand(String text) {
        String normalized = normalizePhrase(text);
        if (normalized.isEmpty()) {
            return false;
        }

        if (AndroidConsoleConfig.LOCAL_INTERRUPT_PHRASES.contains(normalized)) {
            return true;
        }
        if (normalized.startsWith("stop ") || normalized.startsWith("cancel ") || normalized.startsWith("thats enough ")) {
            return true;
        }

        for (String wakeWord : AndroidConsoleConfig.WAKE_WORDS) {
            String wakeNormalized = normalizePhrase(wakeWord);
            if (!wakeNormalized.isEmpty() && normalized.startsWith(wakeNormalized + " ")) {
                String stripped = normalized.substring((wakeNormalized + " ").length()).trim();
                if (AndroidConsoleConfig.LOCAL_INTERRUPT_PHRASES.contains(stripped)) {
                    return true;
                }
                if (stripped.startsWith("stop ") || stripped.startsWith("cancel ") || stripped.startsWith("thats enough ")) {
                    return true;
                }
            }
        }
        return false;
    }
}
