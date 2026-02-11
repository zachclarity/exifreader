package zac.template.fileprocess.controller;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;

import zac.template.fileprocess.dto.FileInfo;
import zac.template.fileprocess.service.FileProcessingService;

@RestController
@RequestMapping("/api/upload")
@CrossOrigin(origins = "*")
@Tag(name = "File Upload", description = "Endpoints for uploading and processing files")
public class FileUploadController {

    private static final String UPLOAD_DIR = "uploads/";

    private final FileProcessingService fileProcessingService;

    public FileUploadController(FileProcessingService fileProcessingService) {
        this.fileProcessingService = fileProcessingService;
    }

    @Operation(
        summary = "Upload and process a file",
        description = "Uploads a file to the server, saves it locally, and returns metadata including file type, size, and extension."
    )
    @ApiResponses(value = {
        @ApiResponse(
            responseCode = "200",
            description = "File uploaded and processed successfully",
            content = @Content(mediaType = "application/json", schema = @Schema(implementation = FileInfo.class))
        ),
        @ApiResponse(
            responseCode = "400",
            description = "No file selected or file is empty",
            content = @Content(mediaType = "application/json", schema = @Schema(implementation = FileInfo.class))
        ),
        @ApiResponse(
            responseCode = "500",
            description = "Internal server error during file upload or processing",
            content = @Content(mediaType = "application/json", schema = @Schema(implementation = FileInfo.class))
        )
    })
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE, produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<FileInfo> uploadFile(
            @Parameter(description = "File to upload", required = true)
            @RequestParam("file") MultipartFile file) {

        // 1. Check if the file is empty
        if (file.isEmpty()) {
            FileInfo errorInfo = new FileInfo();
            errorInfo.setMessage("Please select a file to upload.");
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(errorInfo);
        }

        try {
            // 2. Create the upload directory if it doesn't exist
            File directory = new File(UPLOAD_DIR);
            if (!directory.exists()) {
                directory.mkdirs();
            }

            // 3. Save the file locally
            byte[] bytes = file.getBytes();
            Path path = Paths.get(UPLOAD_DIR + file.getOriginalFilename());
            Files.write(path, bytes);

            // 4. Delegate to service for processing
            FileInfo fileInfo = fileProcessingService.processFile(file);

            return ResponseEntity.ok(fileInfo);

        } catch (IOException e) {
            e.printStackTrace();
            FileInfo errorInfo = new FileInfo();
            errorInfo.setMessage("Could not upload the file: " + e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(errorInfo);
        }
    }
}
