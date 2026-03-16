package com.jarvis.androidconsole;

import java.io.ByteArrayOutputStream;
import java.io.IOException;

public final class WavUtils {
    private WavUtils() {}

    public static byte[] pcm16MonoToWav(byte[] pcm16Mono, int sampleRate) throws IOException {
        int channels = 1;
        int bitsPerSample = 16;
        int byteRate = sampleRate * channels * bitsPerSample / 8;
        int blockAlign = channels * bitsPerSample / 8;
        int dataSize = pcm16Mono.length;
        int riffChunkSize = 36 + dataSize;

        try (ByteArrayOutputStream out = new ByteArrayOutputStream(44 + dataSize)) {
            writeAscii(out, "RIFF");
            writeIntLE(out, riffChunkSize);
            writeAscii(out, "WAVE");

            writeAscii(out, "fmt ");
            writeIntLE(out, 16);
            writeShortLE(out, (short) 1);
            writeShortLE(out, (short) channels);
            writeIntLE(out, sampleRate);
            writeIntLE(out, byteRate);
            writeShortLE(out, (short) blockAlign);
            writeShortLE(out, (short) bitsPerSample);

            writeAscii(out, "data");
            writeIntLE(out, dataSize);
            out.write(pcm16Mono);
            return out.toByteArray();
        }
    }

    public static PcmData wavToPcm16Mono(byte[] wavBytes) throws IOException {
        if (wavBytes == null || wavBytes.length < 44) {
            throw new IOException("Invalid WAV payload");
        }
        if (!isAscii(wavBytes, 0, "RIFF") || !isAscii(wavBytes, 8, "WAVE")) {
            throw new IOException("WAV header missing RIFF/WAVE");
        }

        int offset = 12;
        int sampleRate = 0;
        int channels = 0;
        int bitsPerSample = 0;
        int dataOffset = -1;
        int dataSize = -1;

        while (offset + 8 <= wavBytes.length) {
            String chunkId = readAscii(wavBytes, offset, 4);
            int chunkSize = readIntLE(wavBytes, offset + 4);
            int payloadOffset = offset + 8;
            if (payloadOffset + chunkSize > wavBytes.length) {
                break;
            }

            if ("fmt ".equals(chunkId) && chunkSize >= 16) {
                int audioFormat = readShortLE(wavBytes, payloadOffset) & 0xFFFF;
                channels = readShortLE(wavBytes, payloadOffset + 2) & 0xFFFF;
                sampleRate = readIntLE(wavBytes, payloadOffset + 4);
                bitsPerSample = readShortLE(wavBytes, payloadOffset + 14) & 0xFFFF;
                if (audioFormat != 1) {
                    throw new IOException("Unsupported WAV format: " + audioFormat);
                }
            } else if ("data".equals(chunkId)) {
                dataOffset = payloadOffset;
                dataSize = chunkSize;
                break;
            }

            offset = payloadOffset + chunkSize + (chunkSize % 2);
        }

        if (dataOffset < 0 || dataSize <= 0) {
            throw new IOException("WAV data chunk not found");
        }
        if (channels != 1 || bitsPerSample != 16) {
            throw new IOException("Only PCM 16-bit mono WAV is supported");
        }

        byte[] pcm = new byte[dataSize];
        System.arraycopy(wavBytes, dataOffset, pcm, 0, dataSize);
        return new PcmData(pcm, sampleRate);
    }

    public static final class PcmData {
        public final byte[] pcm16Mono;
        public final int sampleRate;

        PcmData(byte[] pcm16Mono, int sampleRate) {
            this.pcm16Mono = pcm16Mono;
            this.sampleRate = sampleRate;
        }
    }

    private static void writeAscii(ByteArrayOutputStream out, String value) {
        for (int i = 0; i < value.length(); i++) {
            out.write((byte) value.charAt(i));
        }
    }

    private static void writeShortLE(ByteArrayOutputStream out, short value) {
        out.write(value & 0xFF);
        out.write((value >> 8) & 0xFF);
    }

    private static void writeIntLE(ByteArrayOutputStream out, int value) {
        out.write(value & 0xFF);
        out.write((value >> 8) & 0xFF);
        out.write((value >> 16) & 0xFF);
        out.write((value >> 24) & 0xFF);
    }

    private static boolean isAscii(byte[] data, int offset, String value) {
        if (offset + value.length() > data.length) {
            return false;
        }
        for (int i = 0; i < value.length(); i++) {
            if ((byte) value.charAt(i) != data[offset + i]) {
                return false;
            }
        }
        return true;
    }

    private static String readAscii(byte[] data, int offset, int length) {
        StringBuilder builder = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            builder.append((char) data[offset + i]);
        }
        return builder.toString();
    }

    private static short readShortLE(byte[] data, int offset) {
        int lo = data[offset] & 0xFF;
        int hi = data[offset + 1] & 0xFF;
        return (short) ((hi << 8) | lo);
    }

    private static int readIntLE(byte[] data, int offset) {
        int b0 = data[offset] & 0xFF;
        int b1 = data[offset + 1] & 0xFF;
        int b2 = data[offset + 2] & 0xFF;
        int b3 = data[offset + 3] & 0xFF;
        return b0 | (b1 << 8) | (b2 << 16) | (b3 << 24);
    }
}
