# PDF Metadata Extractor

A simple web app to upload PDFs and extract their metadata/EXIF information, including custom classification fields.

## Features

- Drag & drop or click to upload PDF files
- Extracts standard metadata: Title, Author, Subject, Keywords, Creator, Producer, Creation Date, Modification Date, PDF Version, Page Count, File Size
- Extracts custom classification fields: Classification, Security Level, Data Sensitivity, Department, Document Type, Access Control, Compliance Category, Retention Period, Project Code, Approval Status
- Color-coded classification badges (PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED, TOP SECRET)

## Quick Start

```bash
# Start the application
docker-compose up -d

# Open in browser
open http://localhost:8080

# Stop the application
docker-compose down
```

## Sample PDFs

The `samples/` folder contains 5 PDFs with different classification levels:

| File | Classification | Security Level | Department |
|------|----------------|----------------|------------|
| quarterly_report_q4_2024.pdf | CONFIDENTIAL | Level 3 | Finance |
| employee_handbook_2024.pdf | INTERNAL | Level 1 | Human Resources |
| product_roadmap_2025.pdf | TOP SECRET | Level 5 | Product |
| research_findings_ai_ml.pdf | RESTRICTED | Level 4 | R&D |
| meeting_notes_public.pdf | PUBLIC | Level 0 | Communications |

## Creating Custom PDFs

Run the Python script to generate new sample PDFs:

```bash
pip install pypdf reportlab
python create_samples.py
```

## Tech Stack

- HTML5 + Tailwind CSS
- PDF.js for metadata extraction
- Nginx (Alpine) for serving
- Docker Compose for orchestration
- Python + pypdf + reportlab for PDF generation
"# exifreader" 
