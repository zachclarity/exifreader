package zac.template.fileprocess.service;

import java.io.IOException;
import java.net.URLConnection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import zac.template.fileprocess.dto.FileInfo;

@Service
public class FileProcessingService {

    /**
     * Map of file extensions to their programming language names.
     * Covers mainstream languages, scripting, markup/config,
     * database, mobile, systems, and emerging languages.
     */
    private static final Map<String, String> LANGUAGE_MAP;

    static {
        Map<String, String> map = new LinkedHashMap<>();

        // --- JVM Languages ---
        map.put("java",    "Java");
        map.put("kt",      "Kotlin");
        map.put("kts",     "Kotlin Script");
        map.put("scala",   "Scala");
        map.put("groovy",  "Groovy");
        map.put("clj",     "Clojure");
        map.put("cljs",    "ClojureScript");

        // --- C Family ---
        map.put("c",       "C");
        map.put("h",       "C/C++ Header");
        map.put("cpp",     "C++");
        map.put("cxx",     "C++");
        map.put("cc",      "C++");
        map.put("hpp",     "C++ Header");
        map.put("hxx",     "C++ Header");
        map.put("cs",      "C#");
        map.put("csx",     "C# Script");

        // --- Web / JavaScript Ecosystem ---
        map.put("js",      "JavaScript");
        map.put("mjs",     "JavaScript (ES Module)");
        map.put("cjs",     "JavaScript (CommonJS)");
        map.put("jsx",     "React JSX");
        map.put("ts",      "TypeScript");
        map.put("tsx",     "React TSX");
        map.put("vue",     "Vue");
        map.put("svelte",  "Svelte");
        map.put("astro",   "Astro");

        // --- Python ---
        map.put("py",      "Python");
        map.put("pyw",     "Python");
        map.put("pyx",     "Cython");
        map.put("pyi",     "Python Stub");
        map.put("ipynb",   "Jupyter Notebook");

        // --- Ruby ---
        map.put("rb",      "Ruby");
        map.put("erb",     "Embedded Ruby");
        map.put("rake",    "Ruby (Rake)");
        map.put("gemspec", "Ruby (Gemspec)");

        // --- PHP ---
        map.put("php",     "PHP");
        map.put("phtml",   "PHP");

        // --- Go ---
        map.put("go",      "Go");

        // --- Rust ---
        map.put("rs",      "Rust");

        // --- Swift / Objective-C ---
        map.put("swift",   "Swift");
        map.put("m",       "Objective-C");
        map.put("mm",      "Objective-C++");

        // --- Dart / Flutter ---
        map.put("dart",    "Dart");

        // --- Functional Languages ---
        map.put("hs",      "Haskell");
        map.put("lhs",     "Haskell (Literate)");
        map.put("erl",     "Erlang");
        map.put("hrl",     "Erlang Header");
        map.put("ex",      "Elixir");
        map.put("exs",     "Elixir Script");
        map.put("ml",      "OCaml");
        map.put("mli",     "OCaml Interface");
        map.put("fs",      "F#");
        map.put("fsx",     "F# Script");
        map.put("elm",     "Elm");

        // --- Shell / Scripting ---
        map.put("sh",      "Shell (Bash)");
        map.put("bash",    "Bash");
        map.put("zsh",     "Zsh");
        map.put("fish",    "Fish");
        map.put("ps1",     "PowerShell");
        map.put("psm1",    "PowerShell Module");
        map.put("bat",     "Batch");
        map.put("cmd",     "Batch");

        // --- Perl / Lua ---
        map.put("pl",      "Perl");
        map.put("pm",      "Perl Module");
        map.put("lua",     "Lua");

        // --- R / Julia / MATLAB ---
        map.put("r",       "R");
        map.put("rmd",     "R Markdown");
        map.put("jl",      "Julia");
        map.put("mat",     "MATLAB");

        // --- Systems / Low-Level ---
        map.put("asm",     "Assembly");
        map.put("s",       "Assembly");
        map.put("zig",     "Zig");
        map.put("nim",     "Nim");
        map.put("v",       "V");
        map.put("d",       "D");
        map.put("ada",     "Ada");
        map.put("adb",     "Ada");
        map.put("ads",     "Ada");
        map.put("f90",     "Fortran");
        map.put("f95",     "Fortran");
        map.put("f03",     "Fortran");
        map.put("cob",     "COBOL");
        map.put("cbl",     "COBOL");

        // --- Database / Query ---
        map.put("sql",     "SQL");
        map.put("plsql",   "PL/SQL");
        map.put("psql",    "PostgreSQL");
        map.put("hql",     "HQL");

        // --- Markup / Templating ---
        map.put("html",    "HTML");
        map.put("htm",     "HTML");
        map.put("css",     "CSS");
        map.put("scss",    "SCSS");
        map.put("sass",    "Sass");
        map.put("less",    "Less");
        map.put("xml",     "XML");
        map.put("xsl",     "XSLT");
        map.put("xslt",    "XSLT");
        map.put("xhtml",   "XHTML");
        map.put("jsp",     "JSP");
        map.put("ejs",     "EJS");
        map.put("hbs",     "Handlebars");
        map.put("mustache","Mustache");
        map.put("pug",     "Pug");
        map.put("haml",    "Haml");
        map.put("twig",    "Twig");
        map.put("jinja",   "Jinja2");
        map.put("j2",      "Jinja2");

        // --- Config / Data ---
        map.put("json",    "JSON");
        map.put("yaml",    "YAML");
        map.put("yml",     "YAML");
        map.put("toml",    "TOML");
        map.put("ini",     "INI");
        map.put("cfg",     "Config");
        map.put("properties", "Properties");
        map.put("env",     "Environment Config");
        map.put("proto",   "Protocol Buffers");
        map.put("graphql", "GraphQL");
        map.put("gql",     "GraphQL");

        // --- Build / DevOps ---
        map.put("gradle",  "Gradle");
        map.put("cmake",   "CMake");
        map.put("make",    "Makefile");
        map.put("tf",      "Terraform");
        map.put("tfvars",  "Terraform");

        // --- Misc ---
        map.put("wasm",    "WebAssembly");
        map.put("wat",     "WebAssembly Text");
        map.put("sol",     "Solidity");
        map.put("vy",      "Vyper");
        map.put("tex",     "LaTeX");
        map.put("ltx",     "LaTeX");
        map.put("md",      "Markdown");
        map.put("mdx",     "MDX");
        map.put("rst",     "reStructuredText");

        LANGUAGE_MAP = Collections.unmodifiableMap(map);
    }

    /**
     * Processes an uploaded file and extracts metadata including
     * programming language detection.
     *
     * @param file the uploaded MultipartFile
     * @return FileInfo containing file type, size, language, and other metadata
     * @throws IOException if the file cannot be read
     */
    public FileInfo processFile(MultipartFile file) throws IOException {

        String originalName = file.getOriginalFilename();
        long sizeInBytes = file.getSize();

        // Determine MIME type
        String mimeType = file.getContentType();
        if (mimeType == null || mimeType.equals("application/octet-stream")) {
            mimeType = URLConnection.guessContentTypeFromName(originalName);
        }
        if (mimeType == null) {
            mimeType = "unknown";
        }

        // Extract extension
        String extension = extractExtension(originalName);

        // Detect programming language
        String programmingLanguage = LANGUAGE_MAP.get(extension);
        boolean isSourceCode = programmingLanguage != null;

        // Format size
        String formattedSize = formatFileSize(sizeInBytes);

        return new FileInfo(
                originalName,
                mimeType,
                sizeInBytes,
                formattedSize,
                extension,
                programmingLanguage,
                isSourceCode,
                "File processed successfully"
        );
    }

    /**
     * Returns an unmodifiable view of all supported programming extensions.
     */
    public Map<String, String> getSupportedLanguages() {
        return LANGUAGE_MAP;
    }

    private String extractExtension(String fileName) {
        if (fileName == null || !fileName.contains(".")) {
            return "";
        }
        return fileName.substring(fileName.lastIndexOf(".") + 1).toLowerCase();
    }

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
