package zac.template.fileprocess.dto;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "File processing result containing metadata about the uploaded file")
public class FileInfo {

    @Schema(description = "Original file name", example = "report.pdf")
    private String fileName;

    @Schema(description = "MIME type of the file", example = "application/pdf")
    private String fileType;

    @Schema(description = "File size in bytes", example = "204800")
    private long sizeInBytes;

    @Schema(description = "Human-readable file size", example = "200.00 KB")
    private String formattedSize;

    @Schema(description = "File extension", example = "pdf")
    private String extension;

    @Schema(description = "Processing status message", example = "File processed successfully")
    private String message;

    public FileInfo() {
    }

    public FileInfo(String fileName, String fileType, long sizeInBytes, String formattedSize, String extension, String message) {
        this.fileName = fileName;
        this.fileType = fileType;
        this.sizeInBytes = sizeInBytes;
        this.formattedSize = formattedSize;
        this.extension = extension;
        this.message = message;
    }

    public String getFileName() {
        return fileName;
    }

    public void setFileName(String fileName) {
        this.fileName = fileName;
    }

    public String getFileType() {
        return fileType;
    }

    public void setFileType(String fileType) {
        this.fileType = fileType;
    }

    public long getSizeInBytes() {
        return sizeInBytes;
    }

    public void setSizeInBytes(long sizeInBytes) {
        this.sizeInBytes = sizeInBytes;
    }

    public String getFormattedSize() {
        return formattedSize;
    }

    public void setFormattedSize(String formattedSize) {
        this.formattedSize = formattedSize;
    }

    public String getExtension() {
        return extension;
    }

    public void setExtension(String extension) {
        this.extension = extension;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }
}
