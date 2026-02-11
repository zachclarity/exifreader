package com.example.pdfcli;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Base64;

public class PdfApiClient {

    private final String baseUrl;
    private final HttpClient http;
    private final ObjectMapper mapper;
    private final boolean debug;

    public PdfApiClient(String baseUrl) {
        this(baseUrl, false);
    }

    public PdfApiClient(String baseUrl, boolean debug) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.debug = debug;
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
        this.mapper = new ObjectMapper();
        debugLog("PdfApiClient initialized - baseUrl=%s", this.baseUrl);
    }

    public String uploadPdf(String filename, byte[] pdfBytes) throws IOException, InterruptedException {
        String url = baseUrl + "/api/pdf";

        String b64 = Base64.getEncoder().encodeToString(pdfBytes);
        debugLog("Encoded PDF: filename=%s, rawBytes=%d, base64Length=%d", filename, pdfBytes.length, b64.length());

        ObjectNode body = mapper.createObjectNode();
        body.put("pdf", b64);
        body.put("filename", filename);

        String jsonBody = mapper.writeValueAsString(body);
        debugLog("JSON payload size: %d chars", jsonBody.length());

        // NOTE: Java's HttpClient forbids setting certain "restricted" headers:
        //   Connection, Content-Length, Expect, Host, Upgrade,
        //   and (by default) Accept-Encoding.
        // These are managed automatically by the runtime.
        // Setting them manually throws IllegalArgumentException.

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .timeout(Duration.ofSeconds(300))
                .header("Accept", "*/*")
                .header("Content-Type", "application/json")
                .header("User-Agent", "pdf-cli/1.0 (Java HttpClient)")
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                .build();

        debugLog(">> %s %s", request.method(), request.uri());
        if (debug) {
            request.headers().map().forEach((k, v) -> debugLog(">>   %s: %s", k, String.join(", ", v)));
        }

        HttpResponse<String> resp = http.send(request, HttpResponse.BodyHandlers.ofString());

        debugLog("<< HTTP %d", resp.statusCode());
        if (debug) {
            resp.headers().map().forEach((k, v) -> debugLog("<<   %s: %s", k, String.join(", ", v)));
        }
        debugLog("<< Body length: %d chars", resp.body().length());
        debugLog("<< Body (first 500 chars): %.500s", resp.body());

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
