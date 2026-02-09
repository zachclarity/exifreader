package com.zactonics.ocr;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

public class OcrHandler implements RequestHandler<Map<String, Object>, Map<String, Object>> {

    private static final String TESS_BIN = System.getenv().getOrDefault("TESSERACT_BIN", "/opt/tesseract/bin/tesseract");
    private static final String TESS_LANG = System.getenv().getOrDefault("TESS_LANG", "eng");
    private static final String TESSDATA_PREFIX = System.getenv().getOrDefault("TESSDATA_PREFIX", "/opt/tessdata");
    private static final boolean REAL_OCR = "true".equalsIgnoreCase(System.getenv().getOrDefault("REAL_OCR", "false"));

    private static final String BUCKET = System.getenv().getOrDefault("OCR_BUCKET", "ocr-images");
    private static final String LOCALSTACK_ENDPOINT = System.getenv().getOrDefault("LOCALSTACK_ENDPOINT", "http://localstack:4566");
    private static final String REGION = System.getenv().getOrDefault("AWS_DEFAULT_REGION", "us-east-1");

    // Lazily initialized S3 client (helps cold start).
    private static volatile S3Client s3;

    @Override
    public Map<String, Object> handleRequest(Map<String, Object> event, Context context) {
        long start = System.nanoTime();

        try {
            String filename = str(event.get("filename"));
            String contentType = str(event.get("contentType"));
            String imageBase64 = str(event.get("imageBase64"));
            boolean storeToS3 = bool(event.get("storeToS3"), true);

            if (imageBase64 == null || imageBase64.isBlank()) {
                return error("imageBase64 is required", start);
            }

            byte[] imageBytes = Base64.getDecoder().decode(imageBase64);

            String s3Key = null;
            if (storeToS3) {
                s3Key = "uploads/" + Instant.now().toEpochMilli() + "-" + UUID.randomUUID() + "-" + safeFilename(filename);
                putToS3(s3Key, imageBytes, contentType);
            }

            String text;
            if (REAL_OCR && new File(TESS_BIN).exists()) {
                text = runTesseract(imageBytes);
            } else {
                text = "MOCK OCR RESULT\n" +
                        "filename: " + safe(filename) + "\n" +
                        "contentType: " + safe(contentType) + "\n" +
                        "imageBytes: " + imageBytes.length + "\n\n" +
                        "Real OCR not enabled. Set REAL_OCR=true and include tesseract.";
            }

            long elapsedMs = (System.nanoTime() - start) / 1_000_000;

            Map<String, Object> out = new LinkedHashMap<>();
            out.put("text", text);
            out.put("processingTimeMs", elapsedMs);
            out.put("s3Bucket", BUCKET);
            out.put("s3Key", s3Key);
            out.put("realOcr", REAL_OCR && new File(TESS_BIN).exists());
            return out;

        } catch (Exception e) {
            return error("Exception: " + e.getMessage(), start);
        }
    }

    private static void putToS3(String key, byte[] bytes, String contentType) {
        S3Client client = s3Client();
        PutObjectRequest req = PutObjectRequest.builder()
                .bucket(BUCKET)
                .key(key)
                .contentType(contentType == null ? "application/octet-stream" : contentType)
                .build();
        client.putObject(req, RequestBody.fromBytes(bytes));
    }

    private static S3Client s3Client() {
        if (s3 == null) {
            synchronized (OcrHandler.class) {
                if (s3 == null) {
                    s3 = S3Client.builder()
                            .credentialsProvider(StaticCredentialsProvider.create(AwsBasicCredentials.create("test", "test")))
                            .region(Region.of(REGION))
                            .endpointOverride(URI.create(LOCALSTACK_ENDPOINT))
                            .forcePathStyle(true)
                            .build();
                }
            }
        }
        return s3;
    }

    private static String runTesseract(byte[] imageBytes) throws Exception {
        // Write to /tmp and run tesseract -> stdout
        File in = new File("/tmp/input-image");
        Files.write(in.toPath(), imageBytes);

        ProcessBuilder pb = new ProcessBuilder(
                TESS_BIN,
                in.getAbsolutePath(),
                "stdout",
                "-l", TESS_LANG
        );
        pb.redirectErrorStream(true);
        pb.environment().put("TESSDATA_PREFIX", TESSDATA_PREFIX);

        Process p = pb.start();
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        try (InputStream is = p.getInputStream()) {
            is.transferTo(baos);
        }
        int code = p.waitFor();
        String out = baos.toString(StandardCharsets.UTF_8);
        if (code != 0) {
            throw new RuntimeException("tesseract exited " + code + ": " + out);
        }
        return out.trim();
    }

    private static Map<String, Object> error(String msg, long startNano) {
        long elapsedMs = (System.nanoTime() - startNano) / 1_000_000;
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("text", msg);
        out.put("processingTimeMs", elapsedMs);
        out.put("error", true);
        return out;
    }

    private static String str(Object o) { return o == null ? null : String.valueOf(o); }
    private static boolean bool(Object o, boolean dflt) {
        if (o == null) return dflt;
        if (o instanceof Boolean b) return b;
        return "true".equalsIgnoreCase(String.valueOf(o));
    }
    private static String safe(String s) { return s == null ? "(unknown)" : s; }
    private static String safeFilename(String s) {
        if (s == null || s.isBlank()) return "image";
        return s.replaceAll("[^a-zA-Z0-9._-]+", "_");
    }
}
