package com.jarvis.androidconsole;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;

import androidx.core.content.ContextCompat;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;

public class VoiceRecorder {
    private final Context appContext;

    public VoiceRecorder(Context context) {
        this.appContext = context.getApplicationContext();
    }

    public static class VoiceCapture {
        public final byte[] wavBytes;
        public final int sampleRate;

        VoiceCapture(byte[] wavBytes, int sampleRate) {
            this.wavBytes = wavBytes;
            this.sampleRate = sampleRate;
        }
    }

    public VoiceCapture recordWithEndpointing() throws IOException {
        ensureMicrophonePermission();

        int sampleRate = AndroidConsoleConfig.SAMPLE_RATE_HZ;
        int frameSamples = AndroidConsoleConfig.CHUNK_SIZE;
        int bytesPerSample = 2;
        int frameBytes = frameSamples * bytesPerSample;

        int minBuffer = AudioRecord.getMinBufferSize(
                sampleRate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT
        );
        if (minBuffer <= 0) {
            throw new IOException("Unable to initialize microphone buffer");
        }
        int recorderBufferSize = Math.max(minBuffer, frameBytes * 4);

        int maxChunks = Math.max(1, (int) (AndroidConsoleConfig.MAX_DURATION_SECONDS * sampleRate / frameSamples));
        int silenceChunksToStop = Math.max(1, (int) (AndroidConsoleConfig.SILENCE_DURATION_SECONDS * sampleRate / frameSamples));
        int minSpeechChunks = Math.max(1, (int) (AndroidConsoleConfig.MIN_SPEECH_DURATION_SECONDS * sampleRate / frameSamples));
        int noSpeechChunks = Math.max(1, (int) (AndroidConsoleConfig.NO_SPEECH_TIMEOUT_SECONDS * sampleRate / frameSamples));

        ArrayDeque<byte[]> preRoll = new ArrayDeque<>(AndroidConsoleConfig.PRE_ROLL_CHUNKS);
        List<byte[]> captured = new ArrayList<>();

        boolean speechStarted = false;
        int speechChunks = 0;
        int silentAfterSpeech = 0;

        AudioRecord audioRecord;
        try {
            audioRecord = new AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    sampleRate,
                    AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT,
                    recorderBufferSize
            );
        } catch (SecurityException exc) {
            throw new IOException("Microphone permission not granted", exc);
        }
        if (audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
            throw new IOException("Microphone is unavailable");
        }

        try {
            try {
                audioRecord.startRecording();
            } catch (SecurityException exc) {
                throw new IOException("Microphone permission not granted", exc);
            }
            byte[] frame = new byte[frameBytes];

            for (int chunkIndex = 0; chunkIndex < maxChunks; chunkIndex++) {
                int read = audioRecord.read(frame, 0, frame.length);
                if (read <= 0) {
                    throw new IOException("Failed to read audio data");
                }

                byte[] chunk = new byte[read];
                System.arraycopy(frame, 0, chunk, 0, read);
                double rms = computeRms(chunk);

                if (!speechStarted) {
                    if (preRoll.size() == AndroidConsoleConfig.PRE_ROLL_CHUNKS) {
                        preRoll.removeFirst();
                    }
                    preRoll.addLast(chunk);

                    if (rms >= AndroidConsoleConfig.SPEECH_THRESHOLD_RMS) {
                        speechStarted = true;
                        captured.addAll(preRoll);
                        speechChunks += 1;
                        silentAfterSpeech = 0;
                    } else if (chunkIndex >= noSpeechChunks) {
                        throw new IOException("No speech detected");
                    }
                    continue;
                }

                captured.add(chunk);
                if (rms >= AndroidConsoleConfig.SPEECH_THRESHOLD_RMS) {
                    speechChunks += 1;
                    silentAfterSpeech = 0;
                } else {
                    silentAfterSpeech += 1;
                }

                if (speechChunks >= minSpeechChunks && silentAfterSpeech >= silenceChunksToStop) {
                    break;
                }
            }
        } finally {
            try {
                audioRecord.stop();
            } catch (IllegalStateException ignored) {
            }
            audioRecord.release();
        }

        if (captured.isEmpty()) {
            throw new IOException("No speech captured");
        }

        byte[] pcm = mergeBytes(captured);
        byte[] wav = WavUtils.pcm16MonoToWav(pcm, sampleRate);
        return new VoiceCapture(wav, sampleRate);
    }

    private void ensureMicrophonePermission() throws IOException {
        if (ContextCompat.checkSelfPermission(appContext, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            throw new IOException("RECORD_AUDIO permission is required");
        }
    }

    private static byte[] mergeBytes(List<byte[]> chunks) throws IOException {
        try (ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            for (byte[] chunk : chunks) {
                output.write(chunk);
            }
            return output.toByteArray();
        }
    }

    private static double computeRms(byte[] pcm16le) {
        if (pcm16le.length < 2) {
            return 0.0;
        }
        int sampleCount = pcm16le.length / 2;
        double sumSquares = 0.0;

        for (int i = 0; i + 1 < pcm16le.length; i += 2) {
            int lo = pcm16le[i] & 0xFF;
            int hi = pcm16le[i + 1];
            short sample = (short) ((hi << 8) | lo);
            float normalized = sample / 32768.0f;
            sumSquares += normalized * normalized;
        }
        return Math.sqrt(sumSquares / sampleCount);
    }
}
