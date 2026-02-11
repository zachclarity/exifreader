package com.example.pdfcli;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Base64;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

public class PdfApiClient {

    private final String baseUrl;
    private final HttpClient http;
    private final ObjectMapper mapper;
    private final boolean debug;

    public PdfApiClient(String baseUrl) {
        this(baseUrl, false);
    }

    public PdfApiClient(String baseUrl, boolean debug) {
        this.baseUrl = normalizeBaseUrl(baseUrl);
        this.debug = debug;
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
        this.mapper = new ObjectMapper();
        debugLog("PdfApiClient initialized - baseUrl=%s", this.baseUrl);
    }

    /**
     * Fixes "URI with undefined scheme" when user passes "localhost:8080". Adds
     * http:// if no scheme is present and trims a trailing slash.
     */
    private static String normalizeBaseUrl(String input) {
        if (input == null) {
            return "http://localhost:8080";
        }
        String s = input.trim();
        if (s.isEmpty()) {
            return "http://localhost:8080";
        }

        boolean hasScheme = s.matches("^[a-zA-Z][a-zA-Z0-9+\\-.]*://.*$");
        if (!hasScheme) {
            s = "http://" + s;
        }
        if (s.endsWith("/")) {
            s = s.substring(0, s.length() - 1);
        }
        return s;
    }

    public String uploadPdf(String filename, byte[] pdfBytes) throws IOException, InterruptedException {
        String url = baseUrl + "/api/pdf";

        String b64 = Base64.getEncoder().encodeToString(pdfBytes);

        ObjectNode body = mapper.createObjectNode();
        body.put("pdf", b64);
        body.put("filename", filename);

        String jsonBody = mapper.writeValueAsString(body);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .timeout(Duration.ofSeconds(300))
                .header("Accept", "*/*")
                .header("Content-Type", "application/json")
                .header("User-Agent", "pdf-cli/1.0 (Java HttpClient)")
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                .build();

        HttpResponse<String> resp = http.send(request, HttpResponse.BodyHandlers.ofString());

        if (resp.statusCode() < 200 || resp.statusCode() >= 300) {
            throw new IOException("HTTP " + resp.statusCode() + ":\n" + resp.body());
        }

        return resp.body();
    }

    private void debugLog(String fmt, Object... args) {
        if (debug) {
            System.err.printf("[DEBUG] " + fmt + "%n", args);
        }
    }
}
