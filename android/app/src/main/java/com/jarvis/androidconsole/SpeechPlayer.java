package com.jarvis.androidconsole;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;

import java.io.IOException;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

public class SpeechPlayer {
    private final AtomicInteger generation = new AtomicInteger(0);
    private final AtomicReference<AudioTrack> activeTrack = new AtomicReference<>(null);

    public void playWav(byte[] wavBytes) throws IOException {
        int currentGeneration = generation.get();
        WavUtils.PcmData pcmData = WavUtils.wavToPcm16Mono(wavBytes);

        int minBuffer = AudioTrack.getMinBufferSize(
                pcmData.sampleRate,
                AudioFormat.CHANNEL_OUT_MONO,
                AudioFormat.ENCODING_PCM_16BIT
        );
        if (minBuffer <= 0) {
            throw new IOException("Failed to initialize audio output");
        }

        AudioTrack track = new AudioTrack.Builder()
                .setAudioAttributes(new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build())
                .setAudioFormat(new AudioFormat.Builder()
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setSampleRate(pcmData.sampleRate)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build())
                .setTransferMode(AudioTrack.MODE_STREAM)
                .setBufferSizeInBytes(Math.max(minBuffer, 4096))
                .build();

        activeTrack.set(track);
        try {
            track.play();
            int offset = 0;
            byte[] pcm = pcmData.pcm16Mono;
            while (offset < pcm.length) {
                if (generation.get() != currentGeneration) {
                    throw new IOException("Speech interrupted");
                }
                int toWrite = Math.min(2048, pcm.length - offset);
                int written = track.write(pcm, offset, toWrite);
                if (written < 0) {
                    throw new IOException("Audio write failed");
                }
                offset += written;
            }
            if (generation.get() != currentGeneration) {
                throw new IOException("Speech interrupted");
            }
        } finally {
            try {
                track.stop();
            } catch (IllegalStateException ignored) {
            }
            track.release();
            activeTrack.compareAndSet(track, null);
        }
    }

    public void stopSpeech() {
        generation.incrementAndGet();
        AudioTrack track = activeTrack.getAndSet(null);
        if (track != null) {
            try {
                track.pause();
            } catch (Exception ignored) {
            }
            try {
                track.flush();
            } catch (Exception ignored) {
            }
            try {
                track.stop();
            } catch (Exception ignored) {
            }
            try {
                track.release();
            } catch (Exception ignored) {
            }
        }
    }
}
