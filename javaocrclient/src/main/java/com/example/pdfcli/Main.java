package com.example.pdfcli;

import java.nio.file.Files;
import java.nio.file.Path;

public class Main {

    public static void main(String[] args) {
        boolean debug = false;

        // Check for --debug flag anywhere in args
        int argCount = 0;
        String[] cleanArgs = new String[args.length];
        for (String arg : args) {
            if ("--debug".equalsIgnoreCase(arg) || "-d".equalsIgnoreCase(arg)) {
                debug = true;
            } else {
                cleanArgs[argCount++] = arg;
            }
        }

        if (argCount < 1) {
            System.err.println("""
                Usage:
                  java -jar pdf-cli.jar <path-to-pdf> [baseUrl] [--debug]

                Options:
                  --debug, -d   Enable verbose debug logging to stderr

                Examples:
                  java -jar pdf-cli.jar ./sample.pdf
                  java -jar pdf-cli.jar ./sample.pdf http://localhost:8080
                  java -jar pdf-cli.jar ./sample.pdf http://localhost:8080 --debug
                """);
            System.exit(2);
        }

        Path pdfPath = Path.of(cleanArgs[0]);
        if (!Files.exists(pdfPath) || !Files.isRegularFile(pdfPath)) {
            System.err.println("File not found or not a regular file: " + pdfPath.toAbsolutePath());
            System.exit(2);
        }

        String baseUrl = (argCount >= 2) ? cleanArgs[1] : "http://localhost:8080";

        if (debug) {
            System.err.println("[DEBUG] PDF path : " + pdfPath.toAbsolutePath());
            System.err.println("[DEBUG] Base URL : " + baseUrl);
            System.err.println("[DEBUG] Java     : " + System.getProperty("java.version"));
        }

        try {
            byte[] pdfBytes = Files.readAllBytes(pdfPath);
            if (debug) {
                System.err.println("[DEBUG] Read " + pdfBytes.length + " bytes from " + pdfPath.getFileName());
            }

            PdfApiClient client = new PdfApiClient(baseUrl, debug);
            String jsonResponse = client.uploadPdf(pdfPath.getFileName().toString(), pdfBytes);

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
}
