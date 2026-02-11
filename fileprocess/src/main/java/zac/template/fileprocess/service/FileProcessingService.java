package zac.template.fileprocess.service;

import java.io.IOException;
import java.net.URLConnection;

import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import zac.template.fileprocess.dto.FileInfo;

@Service
public class FileProcessingService {

    /**
     * Processes an uploaded file and extracts metadata.
     *
     * @param file the uploaded MultipartFile
     * @return FileInfo containing file type, size, and other metadata
     * @throws IOException if the file cannot be read
     */
    public FileInfo processFile(MultipartFile file) throws IOException {

        String originalName = file.getOriginalFilename();
        long sizeInBytes = file.getSize();

        // Determine MIME type — prefer content type from the upload, fall back to probing
        String mimeType = file.getContentType();
        if (mimeType == null || mimeType.equals("application/octet-stream")) {
            mimeType = URLConnection.guessContentTypeFromName(originalName);
        }
        if (mimeType == null) {
            mimeType = "unknown";
        }

        // Extract extension
        String extension = "";
        if (originalName != null && originalName.contains(".")) {
            extension = originalName.substring(originalName.lastIndexOf(".") + 1).toLowerCase();
        }

        // Format size to human-readable string
        String formattedSize = formatFileSize(sizeInBytes);

        return new FileInfo(
                originalName,
                mimeType,
                sizeInBytes,
                formattedSize,
                extension,
                "File processed successfully"
        );
    }

    /**
     * Converts bytes to a human-readable size string.
     */
    private String formatFileSize(long bytes) {
        if (bytes < 1024) {
            return bytes + " B";
        } else if (bytes < 1024 * 1024) {
            return String.format("%.2f KB", bytes / 1024.0);
        } else if (bytes < 1024 * 1024 * 1024) {
            return String.format("%.2f MB", bytes / (1024.0 * 1024));
        } else {
            return String.format("%.2f GB", bytes / (1024.0 * 1024 * 1024));
        }
    }
}
