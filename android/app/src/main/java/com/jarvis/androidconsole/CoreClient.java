package com.jarvis.androidconsole;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

public class CoreClient {
    private final String baseUrl;
    private final int timeoutMs;

    public CoreClient(String baseUrl, int timeoutMs) {
        this.baseUrl = sanitizeBaseUrl(baseUrl);
        this.timeoutMs = timeoutMs;
    }

    public JSONObject getHealth() throws IOException, JSONException {
        return getJson("/health");
    }

    public JSONObject getVersion() throws IOException, JSONException {
        return getJson("/version");
    }

    public JSONObject command(String text, String deviceId, String location) throws IOException, JSONException {
        JSONObject requestBody = new JSONObject()
                .put("text", text)
                .put("device_id", deviceId)
                .put("location", location);
        return postJson("/command", requestBody);
    }

    public JSONObject transcribe(byte[] wavBytes, String filename) throws IOException, JSONException {
        HttpURLConnection connection = openConnection("/transcribe", "POST");
        String boundary = "----JarvisBoundary" + UUID.randomUUID();
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
        return executeMultipart(connection, boundary, wavBytes, filename);
    }

    public byte[] tts(String text) throws IOException, JSONException {
        JSONObject requestBody = new JSONObject().put("text", text);
        HttpURLConnection connection = openConnection("/tts", "POST");
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        return executeBytes(connection, requestBody.toString());
    }

    private JSONObject getJson(String path) throws IOException, JSONException {
        HttpURLConnection connection = openConnection(path, "GET");
        return execute(connection, null);
    }

    private JSONObject postJson(String path, JSONObject body) throws IOException, JSONException {
        HttpURLConnection connection = openConnection(path, "POST");
        connection.setDoOutput(true);
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        return execute(connection, body.toString());
    }

    private HttpURLConnection openConnection(String path, String method) throws IOException {
        URL url = new URL(baseUrl + path);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(timeoutMs);
        connection.setReadTimeout(timeoutMs);
        connection.setRequestProperty("Accept", "application/json");
        return connection;
    }

    private JSONObject execute(HttpURLConnection connection, String body) throws IOException, JSONException {
        try {
            if (body != null) {
                try (OutputStream os = connection.getOutputStream()) {
                    os.write(body.getBytes(StandardCharsets.UTF_8));
                }
            }

            int statusCode = connection.getResponseCode();
            InputStream stream = statusCode >= 200 && statusCode < 300
                    ? connection.getInputStream()
                    : connection.getErrorStream();

            String payload = readFully(stream);
            if (statusCode < 200 || statusCode >= 300) {
                throw new IOException("HTTP " + statusCode + ": " + payload);
            }

            return new JSONObject(payload);
        } finally {
            connection.disconnect();
        }
    }

    private JSONObject executeMultipart(
            HttpURLConnection connection,
            String boundary,
            byte[] fileBytes,
            String filename
    ) throws IOException, JSONException {
        String safeFilename = (filename == null || filename.trim().isEmpty()) ? "input.wav" : filename.trim();
        String lineBreak = "\r\n";

        try (OutputStream os = connection.getOutputStream()) {
            StringBuilder header = new StringBuilder();
            header.append("--").append(boundary).append(lineBreak);
            header.append("Content-Disposition: form-data; name=\"file\"; filename=\"")
                    .append(safeFilename)
                    .append("\"")
                    .append(lineBreak);
            header.append("Content-Type: audio/wav").append(lineBreak).append(lineBreak);

            os.write(header.toString().getBytes(StandardCharsets.UTF_8));
            os.write(fileBytes);
            os.write(lineBreak.getBytes(StandardCharsets.UTF_8));
            os.write(("--" + boundary + "--" + lineBreak).getBytes(StandardCharsets.UTF_8));
        }

        int statusCode = connection.getResponseCode();
        InputStream stream = statusCode >= 200 && statusCode < 300
                ? connection.getInputStream()
                : connection.getErrorStream();
        String payload = readFully(stream);
        connection.disconnect();

        if (statusCode < 200 || statusCode >= 300) {
            throw new IOException("HTTP " + statusCode + ": " + payload);
        }
        return new JSONObject(payload);
    }

    private byte[] executeBytes(HttpURLConnection connection, String body) throws IOException {
        try {
            if (body != null) {
                try (OutputStream os = connection.getOutputStream()) {
                    os.write(body.getBytes(StandardCharsets.UTF_8));
                }
            }

            int statusCode = connection.getResponseCode();
            InputStream stream = statusCode >= 200 && statusCode < 300
                    ? connection.getInputStream()
                    : connection.getErrorStream();
            byte[] payload = readFullyBytes(stream);

            if (statusCode < 200 || statusCode >= 300) {
                throw new IOException("HTTP " + statusCode + ": " + new String(payload, StandardCharsets.UTF_8));
            }
            return payload;
        } finally {
            connection.disconnect();
        }
    }

    private static String sanitizeBaseUrl(String value) {
        if (value == null) {
            return "";
        }
        String normalized = value.trim();
        while (normalized.endsWith("/")) {
            normalized = normalized.substring(0, normalized.length() - 1);
        }
        return normalized;
    }

    private static String readFully(InputStream stream) throws IOException {
        if (stream == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }

    private static byte[] readFullyBytes(InputStream stream) throws IOException {
        if (stream == null) {
            return new byte[0];
        }
        try (ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = stream.read(buffer)) != -1) {
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }
    }
}
