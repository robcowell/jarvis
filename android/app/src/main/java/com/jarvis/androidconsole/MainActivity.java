package com.jarvis.androidconsole;

import android.Manifest;
import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Switch;
import android.widget.TextView;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import org.json.JSONException;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.Executor;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends AppCompatActivity {
    private static final String PREFS_NAME = "jarvis_android_console_prefs";
    private static final String PREF_CORE_URL = "core_url";
    private static final String PREF_DEVICE_ID = "device_id";
    private static final String PREF_LOCATION = "location";
    private static final String PREF_WAKE_WORD_ENABLED = "wake_word_enabled";

    private EditText coreUrlInput;
    private EditText deviceIdInput;
    private EditText locationInput;
    private EditText commandInput;
    private Switch wakeWordSwitch;
    private TextView outputView;
    private TextView statusValueView;
    private TextView statusSubView;
    private TextView heroCaptionView;
    private TextView wakeTopMetricView;
    private Button listenButton;
    private View ringTickView;
    private View loadingView;

    private ExecutorService networkExecutor;
    private Executor mainExecutor;
    private final AtomicBoolean voicePipelineBusy = new AtomicBoolean(false);
    private final SpeechPlayer speechPlayer = new SpeechPlayer();
    private final SimpleDateFormat timestampFormat = new SimpleDateFormat("HH:mm:ss", Locale.US);
    private SharedPreferences preferences;
    private ObjectAnimator ringSpinAnimator;
    private ObjectAnimator listenPulseXAnimator;
    private ObjectAnimator listenPulseYAnimator;

    private final ActivityResultLauncher<String> microphonePermissionLauncher =
            registerForActivityResult(new ActivityResultContracts.RequestPermission(), this::onMicPermissionResult);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        setContentView(R.layout.activity_main);

        networkExecutor = Executors.newSingleThreadExecutor();
        mainExecutor = ContextCompat.getMainExecutor(this);
        preferences = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);

        coreUrlInput = findViewById(R.id.coreUrlInput);
        deviceIdInput = findViewById(R.id.deviceIdInput);
        locationInput = findViewById(R.id.locationInput);
        commandInput = findViewById(R.id.commandInput);
        wakeWordSwitch = findViewById(R.id.wakeWordSwitch);
        outputView = findViewById(R.id.outputView);
        statusValueView = findViewById(R.id.statusValue);
        statusSubView = findViewById(R.id.statusSub);
        heroCaptionView = findViewById(R.id.heroCaption);
        wakeTopMetricView = findViewById(R.id.wakeTopMetric);
        listenButton = findViewById(R.id.listenButton);
        ringTickView = findViewById(R.id.ringTickView);
        loadingView = findViewById(R.id.loadingOverlay);

        coreUrlInput.setText(preferences.getString(PREF_CORE_URL, AndroidConsoleConfig.DEFAULT_CORE_URL));
        deviceIdInput.setText(preferences.getString(PREF_DEVICE_ID, AndroidConsoleConfig.DEFAULT_DEVICE_ID));
        locationInput.setText(preferences.getString(PREF_LOCATION, AndroidConsoleConfig.DEFAULT_LOCATION));
        wakeWordSwitch.setChecked(preferences.getBoolean(PREF_WAKE_WORD_ENABLED, AndroidConsoleConfig.WAKE_WORD_ENABLED));
        wakeTopMetricView.setText(wakeWordSwitch.isChecked() ? "Armed" : "Off");

        Button healthButton = findViewById(R.id.healthButton);
        Button versionButton = findViewById(R.id.versionButton);
        Button sendButton = findViewById(R.id.sendButton);
        Button stopSpeechButton = findViewById(R.id.stopSpeechButton);

        healthButton.setOnClickListener(v -> runHealth());
        versionButton.setOnClickListener(v -> runVersion());
        sendButton.setOnClickListener(v -> runCommand());
        listenButton.setOnClickListener(v -> runListenPipeline());
        stopSpeechButton.setOnClickListener(v -> runStopSpeech());
        wakeWordSwitch.setOnCheckedChangeListener((buttonView, isChecked) -> persistPrefs());

        appendLog("Ready. Native Android console is online.");
        appendLog("Use Listen for voice pipeline: record -> transcribe -> command -> tts.");
        setHudState("Idle", "Touch the core to speak");
        initAnimations();
        enterImmersiveFullscreen();
    }

    @Override
    protected void onResume() {
        super.onResume();
        enterImmersiveFullscreen();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            enterImmersiveFullscreen();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        persistPrefs();
        speechPlayer.stopSpeech();
        stopPulse();
        if (ringSpinAnimator != null) {
            ringSpinAnimator.cancel();
        }
        if (networkExecutor != null) {
            networkExecutor.shutdownNow();
        }
    }

    private void runHealth() {
        String baseUrl = readCoreUrl();
        if (baseUrl == null) {
            return;
        }
        persistPrefs();
        setLoading(true);
        appendLog("GET /health -> " + baseUrl);
        setHudState("Thinking...", "Checking core health");
        networkExecutor.execute(() -> {
            try {
                JSONObject payload = new CoreClient(baseUrl, AndroidConsoleConfig.CORE_TIMEOUT_MS).getHealth();
                postSuccess("/health", payload);
            } catch (Exception ex) {
                postError("/health", ex);
            }
        });
    }

    private void runVersion() {
        String baseUrl = readCoreUrl();
        if (baseUrl == null) {
            return;
        }
        persistPrefs();
        setLoading(true);
        appendLog("GET /version -> " + baseUrl);
        setHudState("Thinking...", "Checking version metadata");
        networkExecutor.execute(() -> {
            try {
                JSONObject payload = new CoreClient(baseUrl, AndroidConsoleConfig.CORE_TIMEOUT_MS).getVersion();
                postSuccess("/version", payload);
            } catch (Exception ex) {
                postError("/version", ex);
            }
        });
    }

    private void runCommand() {
        String baseUrl = readCoreUrl();
        if (baseUrl == null) {
            return;
        }

        String text = commandInput.getText().toString().trim();
        if (TextUtils.isEmpty(text)) {
            appendLog("Command text cannot be empty.");
            return;
        }

        String deviceId = valueOrDefault(deviceIdInput.getText().toString().trim(), AndroidConsoleConfig.DEFAULT_DEVICE_ID);
        String location = valueOrDefault(locationInput.getText().toString().trim(), AndroidConsoleConfig.DEFAULT_LOCATION);
        persistPrefs();

        setLoading(true);
        appendLog("POST /command -> " + text);
        setHudState("Thinking...", "Sending text command");
        networkExecutor.execute(() -> {
            try {
                JSONObject payload = new CoreClient(baseUrl, AndroidConsoleConfig.CORE_TIMEOUT_MS).command(text, deviceId, location);
                postSuccess("/command", payload);
            } catch (Exception ex) {
                postError("/command", ex);
            }
        });
    }

    private void runListenPipeline() {
        if (voicePipelineBusy.get()) {
            appendLog("Voice pipeline is already running.");
            return;
        }
        if (!hasMicrophonePermission()) {
            appendLog("Requesting microphone permission...");
            microphonePermissionLauncher.launch(Manifest.permission.RECORD_AUDIO);
            return;
        }
        startListenPipeline();
    }

    private void startListenPipeline() {
        String baseUrl = readCoreUrl();
        if (baseUrl == null) {
            return;
        }
        String deviceId = valueOrDefault(deviceIdInput.getText().toString().trim(), AndroidConsoleConfig.DEFAULT_DEVICE_ID);
        String location = valueOrDefault(locationInput.getText().toString().trim(), AndroidConsoleConfig.DEFAULT_LOCATION);
        boolean wakeWordEnabled = wakeWordSwitch.isChecked();
        persistPrefs();

        if (!voicePipelineBusy.compareAndSet(false, true)) {
            appendLog("Voice pipeline is already running.");
            return;
        }

        setLoading(true);
        appendLog("Listening...");
        setHudState("Listening...", "Recording request");
        networkExecutor.execute(() -> {
            try {
                CoreClient client = new CoreClient(baseUrl, AndroidConsoleConfig.CORE_TIMEOUT_MS);
                VoiceRecorder.VoiceCapture capture = new VoiceRecorder(this).recordWithEndpointing();
                postLog("Recorded speech (" + capture.wavBytes.length + " bytes WAV)");

                JSONObject transcribePayload = client.transcribe(capture.wavBytes, "input.wav");
                String transcript = transcribePayload.optString("text", "").trim();
                if (transcript.isEmpty()) {
                    throw new IllegalStateException("Core /transcribe returned empty text");
                }
                postLog("Transcript: " + transcript);

                String promptText = transcript;
                if (wakeWordEnabled) {
                    if (!WakeWordUtils.containsWakeWord(transcript)) {
                        throw new IllegalStateException("Say \"" + AndroidConsoleConfig.WAKE_WORD_DISPLAY + "\" to activate.");
                    }
                    promptText = WakeWordUtils.stripWakeWord(transcript);
                    if (promptText.isEmpty()) {
                        throw new IllegalStateException("Wake word heard. Say your command after it.");
                    }
                }

                if (WakeWordUtils.isLocalInterruptCommand(promptText)) {
                    speechPlayer.stopSpeech();
                    postLog("Speech interrupted.");
                    return;
                }

                postLog("Thinking...");
                postState("Thinking...", "Generating response");
                JSONObject commandPayload = client.command(promptText, deviceId, location);
                String response = commandPayload.optString("response", "").trim();
                if (response.isEmpty()) {
                    throw new IllegalStateException("Core /command returned empty response");
                }
                postLog("Response: " + response);

                postLog("Requesting TTS...");
                byte[] wav = client.tts(response);
                if (wav.length == 0) {
                    throw new IllegalStateException("Core /tts returned empty audio");
                }
                postLog("Speaking...");
                postState("Speaking...", "Delivering response");
                speechPlayer.playWav(wav);
                postLog("Done.");
                postState("Idle", "Touch the core to speak");
            } catch (Exception ex) {
                postLog("Listen pipeline failed: " + ex.getMessage());
                postState("Error", ex.getMessage());
            } finally {
                voicePipelineBusy.set(false);
                mainExecutor.execute(() -> setLoading(false));
            }
        });
    }

    private void runStopSpeech() {
        speechPlayer.stopSpeech();
        appendLog("Stop requested.");
    }

    private void postSuccess(String route, JSONObject payload) {
        runOnUiThread(() -> {
            setLoading(false);
            setHudState("Idle", "Touch the core to speak");
            appendLog(route + " OK");
            appendLog(prettyJson(payload));
            if ("/command".equals(route)) {
                commandInput.setText("");
            }
        });
    }

    private void postError(String route, Exception exception) {
        runOnUiThread(() -> {
            setLoading(false);
            setHudState("Error", exception.getMessage());
            appendLog(route + " FAILED: " + exception.getMessage());
        });
    }

    private void setLoading(boolean isLoading) {
        loadingView.setVisibility(isLoading ? View.VISIBLE : View.GONE);
    }

    private String readCoreUrl() {
        String baseUrl = coreUrlInput.getText().toString().trim();
        if (TextUtils.isEmpty(baseUrl)) {
            appendLog("Core URL is required.");
            return null;
        }
        return baseUrl;
    }

    private boolean hasMicrophonePermission() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void onMicPermissionResult(Boolean granted) {
        if (Boolean.TRUE.equals(granted)) {
            appendLog("Microphone permission granted.");
            startListenPipeline();
            return;
        }
        setHudState("Error", "Microphone permission denied");
        appendLog("Microphone permission denied.");
    }

    private void persistPrefs() {
        wakeTopMetricView.setText(wakeWordSwitch.isChecked() ? "Armed" : "Off");
        preferences.edit()
                .putString(PREF_CORE_URL, coreUrlInput.getText().toString().trim())
                .putString(PREF_DEVICE_ID, deviceIdInput.getText().toString().trim())
                .putString(PREF_LOCATION, locationInput.getText().toString().trim())
                .putBoolean(PREF_WAKE_WORD_ENABLED, wakeWordSwitch.isChecked())
                .apply();
    }

    private void postLog(@NonNull String line) {
        mainExecutor.execute(() -> appendLog(line));
    }

    private void postState(@NonNull String state, @NonNull String subtext) {
        mainExecutor.execute(() -> setHudState(state, subtext));
    }

    private void appendLog(String line) {
        String current = outputView.getText().toString();
        String stamped = "[" + timestampFormat.format(new Date()) + "] " + line;
        if (current.isEmpty()) {
            outputView.setText(stamped);
        } else {
            outputView.setText(current + "\n" + stamped);
        }
    }

    private void setHudState(String state, String subtext) {
        statusValueView.setText(state);
        statusSubView.setText(valueOrDefault(subtext, ""));
        if ("Listening...".equals(state)) {
            statusValueView.setTextColor(ContextCompat.getColor(this, R.color.accent));
            heroCaptionView.setText("Capturing audio input");
            startPulse();
            return;
        }
        if ("Thinking...".equals(state)) {
            statusValueView.setTextColor(ContextCompat.getColor(this, R.color.state_warn));
            heroCaptionView.setText("Processing intent");
            startPulse();
            return;
        }
        if ("Speaking...".equals(state)) {
            statusValueView.setTextColor(ContextCompat.getColor(this, R.color.text_primary));
            heroCaptionView.setText("Delivering response");
            startPulse();
            return;
        }
        if ("Error".equals(state)) {
            statusValueView.setTextColor(ContextCompat.getColor(this, R.color.state_bad));
            heroCaptionView.setText("Attention required");
            stopPulse();
            return;
        }
        statusValueView.setTextColor(ContextCompat.getColor(this, R.color.state_good));
        heroCaptionView.setText("Touch interface engaged");
        stopPulse();
    }

    private void initAnimations() {
        ringSpinAnimator = ObjectAnimator.ofFloat(ringTickView, View.ROTATION, 0f, 360f);
        ringSpinAnimator.setDuration(22000);
        ringSpinAnimator.setRepeatCount(ValueAnimator.INFINITE);
        ringSpinAnimator.start();

        listenPulseXAnimator = ObjectAnimator.ofFloat(listenButton, View.SCALE_X, 1.0f, 0.98f, 1.03f, 1.0f);
        listenPulseYAnimator = ObjectAnimator.ofFloat(listenButton, View.SCALE_Y, 1.0f, 0.98f, 1.03f, 1.0f);
        listenPulseXAnimator.setDuration(1250);
        listenPulseYAnimator.setDuration(1250);
        listenPulseXAnimator.setRepeatCount(ValueAnimator.INFINITE);
        listenPulseYAnimator.setRepeatCount(ValueAnimator.INFINITE);
    }

    private void startPulse() {
        if (listenPulseXAnimator != null && !listenPulseXAnimator.isStarted()) {
            listenPulseXAnimator.start();
        }
        if (listenPulseYAnimator != null && !listenPulseYAnimator.isStarted()) {
            listenPulseYAnimator.start();
        }
    }

    private void stopPulse() {
        if (listenPulseXAnimator != null) {
            listenPulseXAnimator.cancel();
        }
        if (listenPulseYAnimator != null) {
            listenPulseYAnimator.cancel();
        }
        listenButton.setScaleX(1.0f);
        listenButton.setScaleY(1.0f);
    }

    private void enterImmersiveFullscreen() {
        WindowInsetsControllerCompat controller =
                WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        if (controller == null) {
            return;
        }
        controller.setSystemBarsBehavior(
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        );
        controller.hide(WindowInsetsCompat.Type.systemBars());
    }

    private static String prettyJson(JSONObject payload) {
        try {
            return payload.toString(2);
        } catch (JSONException ex) {
            return payload.toString();
        }
    }

    private static String valueOrDefault(String value, String fallback) {
        return TextUtils.isEmpty(value) ? fallback : value;
    }
}
