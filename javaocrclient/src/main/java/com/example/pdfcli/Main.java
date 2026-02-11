package com.example.pdfcli;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Base64;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

public class Main {

    public static void main(String[] args) {
        boolean debug = false;
        boolean ocr = false;

        // Collect positional args after stripping flags
        int argCount = 0;
        String[] positional = new String[args.length];

        for (String arg : args) {
            String a = arg == null ? "" : arg.trim();

            // Accept: --ocr, -o, -ocr (your current usage)
            if ("--ocr".equalsIgnoreCase(a) || "-o".equalsIgnoreCase(a) || "-ocr".equalsIgnoreCase(a)) {
                ocr = true;
                continue;
            }

            if ("--debug".equalsIgnoreCase(a) || "-d".equalsIgnoreCase(a)) {
                debug = true;
                continue;
            }

            positional[argCount++] = a;
        }

        if (argCount < 1) {
            System.err.println("""
                Usage:
                  java -jar pdf-cli.jar <path-to-pdf> [baseUrl] [--ocr|-o|-ocr] [--debug|-d]

                Notes:
                  - You can pass flags anywhere.
                  - If baseUrl is omitted, defaults to http://localhost:8080
                  - baseUrl must be like http://host:port (or host:port)

                Examples:
                  java -jar pdf-cli.jar ./sample.pdf
                  java -jar pdf-cli.jar ./sample.pdf localhost:8080
                  java -jar pdf-cli.jar ./sample.pdf localhost:8080 --ocr
                  java -jar pdf-cli.jar ./sample.pdf -ocr
                  java -jar pdf-cli.jar ./sample.pdf --ocr --debug http://localhost:8080
                """);
            System.exit(2);
        }

        Path pdfPath = Path.of(positional[0]);
        if (!Files.exists(pdfPath) || !Files.isRegularFile(pdfPath)) {
            System.err.println("File not found or not a regular file: " + pdfPath.toAbsolutePath());
            System.exit(2);
        }

        // baseUrl is optional positional[1], but ONLY if it doesn't look like a flag
        String baseUrlRaw;
        if (argCount >= 2 && positional[1] != null && !positional[1].isBlank() && !positional[1].startsWith("-")) {
            baseUrlRaw = positional[1];
        } else {
            baseUrlRaw = "http://localhost:8080";
        }

        String baseUrl = normalizeBaseUrl(baseUrlRaw);

        if (debug) {
            System.err.println("[DEBUG] PDF path : " + pdfPath.toAbsolutePath());
            System.err.println("[DEBUG] Base URL : " + baseUrl + " (from: " + baseUrlRaw + ")");
            System.err.println("[DEBUG] Mode     : " + (ocr ? "OCR (/api/pdf-ocr)" : "UPLOAD (/api/pdf)"));
        }

        try {
            byte[] pdfBytes = Files.readAllBytes(pdfPath);

            String jsonResponse;
            if (ocr) {
                OcrApiClient ocrClient = new OcrApiClient(baseUrl, debug);
                jsonResponse = ocrClient.ocrPdf(pdfPath.getFileName().toString(), pdfBytes);
            } else {
                PdfApiClient client = new PdfApiClient(baseUrl, debug);
                jsonResponse = client.uploadPdf(pdfPath.getFileName().toString(), pdfBytes);
            }

            System.out.println(jsonResponse);

        } catch (Exception e) {
            System.err.println("ERROR: " + e.getClass().getSimpleName() + ": " + e.getMessage());
            if (debug) {
                System.err.println("\n--- Full Stack Trace ---");
                e.printStackTrace(System.err);
            }
            System.exit(1);
        }
    }

    private static String normalizeBaseUrl(String input) {
        if (input == null) {
            return "http://localhost:8080";
        }
        String s = input.trim();
        if (s.isEmpty()) {
            return "http://localhost:8080";
        }

        // If user accidentally passes a flag as baseUrl, fail early with a clear message
        if (s.startsWith("-")) {
            throw new IllegalArgumentException("Base URL looks like a flag: " + s + " (did you mean to pass --ocr?)");
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

    static final class OcrApiClient {

        private final String baseUrl;
        private final boolean debug;
        private final HttpClient http;
        private final ObjectMapper mapper;

        OcrApiClient(String baseUrl, boolean debug) {
            this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
            this.debug = debug;
            this.http = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(10))
                    .followRedirects(HttpClient.Redirect.NORMAL)
                    .build();
            this.mapper = new ObjectMapper();
        }

        String ocrPdf(String filename, byte[] pdfBytes) throws IOException, InterruptedException {
            String url = baseUrl + "/api/pdf-ocr";

            String b64 = Base64.getEncoder().encodeToString(pdfBytes);
            String dataUri = "data:application/pdf;base64," + b64;

            ObjectNode body = mapper.createObjectNode();
            body.put("pdf", dataUri);
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
    }
}
