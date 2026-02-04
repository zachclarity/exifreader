#!/usr/bin/env python3
"""Generate sample PDFs with custom metadata stored as JSON object."""

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from pypdf import PdfReader, PdfWriter
import json
import os

OUTPUT_DIR = "./samples"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_pdf_content(filename, title, content_paragraphs):
    """Create a PDF with reportlab."""
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=30
    )
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 12))
    
    for para in content_paragraphs:
        story.append(Paragraph(para, styles['Normal']))
        story.append(Spacer(1, 12))
    
    doc.build(story)

def add_custom_metadata(input_path, output_path, standard_meta, custom_fields):
    """Add metadata to PDF with custom fields as JSON object."""
    reader = PdfReader(input_path)
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)
    
    # Combine standard metadata with custom fields as JSON
    metadata = {**standard_meta}
    metadata["/CustomFields"] = json.dumps(custom_fields)
    
    writer.add_metadata(metadata)
    
    with open(output_path, "wb") as f:
        writer.write(f)

# Sample PDFs with different classifications
samples = [
    {
        "filename": "quarterly_report_q4_2024.pdf",
        "title": "Q4 2024 Financial Report",
        "content": [
            "This document contains the quarterly financial results for Q4 2024.",
            "Revenue increased by 15% compared to the previous quarter.",
            "Operating expenses remained stable at $2.3 million.",
            "Net profit margin improved to 12.5% from 10.2% in Q3.",
        ],
        "standard": {
            "/Title": "Q4 2024 Financial Report",
            "/Author": "Finance Department",
            "/Subject": "Quarterly Financial Results",
            "/Keywords": "finance, quarterly, report, Q4, 2024, revenue",
            "/Creator": "Acme Corp Financial System",
            "/Producer": "ReportLab + PyPDF",
        },
        "custom": {
            "classification": "CONFIDENTIAL",
            "securityLevel": 3,
            "department": "Finance",
            "documentType": "Financial Report",
            "retentionPeriod": "7 years",
            "compliance": {
                "category": "SOX",
                "audited": True,
                "lastAuditDate": "2024-11-01"
            },
            "accessControl": {
                "allowedGroups": ["Finance Team", "Executive", "Audit"],
                "allowedUsers": ["cfo@acme.com", "controller@acme.com"],
                "restrictedCountries": ["CN", "RU"]
            },
            "dataSensitivity": "HIGH",
            "projectCode": "FIN-2024-Q4",
            "workflow": {
                "status": "Approved",
                "approvedBy": "Jane Smith",
                "approvedDate": "2024-12-15",
                "reviewers": ["john.doe@acme.com", "mary.jane@acme.com"]
            },
            "tags": ["quarterly", "financial", "2024", "Q4"]
        }
    },
    {
        "filename": "employee_handbook_2024.pdf",
        "title": "Employee Handbook 2024",
        "content": [
            "Welcome to Acme Corporation! This handbook outlines company policies.",
            "Chapter 1: Code of Conduct - All employees must maintain professional behavior.",
            "Chapter 2: Benefits - Health insurance, 401k, and PTO policies.",
            "Chapter 3: Remote Work Policy - Guidelines for working from home.",
        ],
        "standard": {
            "/Title": "Employee Handbook 2024",
            "/Author": "Human Resources",
            "/Subject": "Company Policies and Procedures",
            "/Keywords": "HR, handbook, policies, employee, benefits",
            "/Creator": "HR Documentation System",
            "/Producer": "ReportLab + PyPDF",
        },
        "custom": {
            "classification": "INTERNAL",
            "securityLevel": 1,
            "department": "Human Resources",
            "documentType": "Policy Document",
            "retentionPeriod": "Current + 1 year",
            "compliance": {
                "category": "HR Compliance",
                "audited": False
            },
            "accessControl": {
                "allowedGroups": ["All Employees"],
                "public": False
            },
            "dataSensitivity": "LOW",
            "projectCode": "HR-HANDBOOK-2024",
            "workflow": {
                "status": "Published",
                "version": "3.2",
                "effectiveDate": "2024-01-01",
                "nextReviewDate": "2025-01-01"
            },
            "tags": ["HR", "policy", "handbook", "onboarding"],
            "languages": ["en", "es", "fr"]
        }
    },
    {
        "filename": "product_roadmap_2025.pdf",
        "title": "Product Roadmap 2025",
        "content": [
            "Strategic product development plan for fiscal year 2025.",
            "Q1: Launch of AI-powered analytics dashboard.",
            "Q2: Mobile app redesign with new UX patterns.",
            "Q3: Integration with third-party platforms.",
            "Q4: Enterprise features and security enhancements.",
        ],
        "standard": {
            "/Title": "Product Roadmap 2025",
            "/Author": "Product Management",
            "/Subject": "Strategic Product Planning",
            "/Keywords": "roadmap, product, strategy, 2025, planning",
            "/Creator": "Product Planning Tool",
            "/Producer": "ReportLab + PyPDF",
        },
        "custom": {
            "classification": "TOP SECRET",
            "securityLevel": 5,
            "department": "Product",
            "documentType": "Strategic Plan",
            "retentionPeriod": "5 years",
            "compliance": {
                "category": "Trade Secret",
                "ndaRequired": True,
                "exportControlled": True
            },
            "accessControl": {
                "allowedGroups": ["Executive Team", "Product Leadership"],
                "allowedUsers": ["ceo@acme.com", "cpo@acme.com", "vp-product@acme.com"],
                "mfaRequired": True,
                "watermarkOnView": True
            },
            "dataSensitivity": "CRITICAL",
            "projectCode": "PROD-ROADMAP-2025",
            "workflow": {
                "status": "Draft",
                "expirationDate": "2025-12-31",
                "distributionList": ["C-Suite", "VP Product", "Directors"]
            },
            "tags": ["roadmap", "strategy", "confidential", "2025"],
            "competitors": {
                "mentionsCompetitors": True,
                "competitorAnalysis": True
            }
        }
    },
    {
        "filename": "research_findings_ai_ml.pdf",
        "title": "AI/ML Research Findings",
        "content": [
            "Summary of machine learning research conducted in 2024.",
            "Key Finding 1: Transformer models showed 23% improvement in accuracy.",
            "Key Finding 2: Training time reduced by 40% with new optimization.",
            "Key Finding 3: Energy consumption decreased through efficient batching.",
            "Recommendations for future research directions included.",
        ],
        "standard": {
            "/Title": "AI/ML Research Findings 2024",
            "/Author": "Dr. Jane Smith, Research Team",
            "/Subject": "Machine Learning Research Results",
            "/Keywords": "AI, ML, research, machine learning, transformers",
            "/Creator": "Research Documentation System",
            "/Producer": "ReportLab + PyPDF",
        },
        "custom": {
            "classification": "RESTRICTED",
            "securityLevel": 4,
            "department": "Research & Development",
            "documentType": "Research Paper",
            "retentionPeriod": "10 years",
            "compliance": {
                "category": "IP Protection",
                "exportControlled": False
            },
            "accessControl": {
                "allowedGroups": ["R&D Team", "Patent Office"],
                "allowedUsers": ["dr.smith@acme.com", "patent@acme.com"]
            },
            "dataSensitivity": "HIGH",
            "projectCode": "RND-AI-2024-047",
            "workflow": {
                "status": "Peer Reviewed",
                "peerReviewDate": "2024-11-20",
                "reviewers": ["dr.jones@acme.com", "dr.lee@acme.com"]
            },
            "intellectualProperty": {
                "patentStatus": "Pending",
                "patentNumber": "US-2024-12345",
                "publicationStatus": "Embargoed",
                "embargoUntil": "2025-06-01"
            },
            "tags": ["AI", "ML", "research", "transformers", "optimization"]
        }
    },
    {
        "filename": "meeting_notes_public.pdf",
        "title": "All-Hands Meeting Notes",
        "content": [
            "Notes from the company all-hands meeting held on December 1, 2024.",
            "CEO presented annual achievements and thanked all teams.",
            "New office locations announced for 2025 expansion.",
            "Q&A session addressed employee questions about benefits.",
        ],
        "standard": {
            "/Title": "All-Hands Meeting Notes - December 2024",
            "/Author": "Communications Team",
            "/Subject": "Company Meeting Summary",
            "/Keywords": "meeting, all-hands, company, notes",
            "/Creator": "Meeting Notes App",
            "/Producer": "ReportLab + PyPDF",
        },
        "custom": {
            "classification": "PUBLIC",
            "securityLevel": 0,
            "department": "Communications",
            "documentType": "Meeting Notes",
            "retentionPeriod": "2 years",
            "compliance": {
                "category": "None",
                "audited": False
            },
            "accessControl": {
                "allowedGroups": ["Public"],
                "public": True,
                "shareable": True
            },
            "dataSensitivity": "NONE",
            "projectCode": "COMM-MTG-2024-12",
            "workflow": {
                "status": "Approved for Distribution",
                "approvedBy": "Communications Director"
            },
            "meeting": {
                "date": "2024-12-01",
                "attendees": "All Employees",
                "location": "Main Auditorium",
                "recordingAvailable": True,
                "recordingUrl": "https://intranet.acme.com/recordings/allhands-dec2024"
            },
            "tags": ["meeting", "all-hands", "company-wide", "december"]
        }
    },
]

if __name__ == "__main__":
    print("Creating sample PDFs with JSON custom metadata...")
    print()

    for sample in samples:
        temp_path = os.path.join(OUTPUT_DIR, f"temp_{sample['filename']}")
        final_path = os.path.join(OUTPUT_DIR, sample['filename'])
        
        # Create PDF content
        create_pdf_content(temp_path, sample['title'], sample['content'])
        
        # Add metadata with custom fields as JSON
        add_custom_metadata(temp_path, final_path, sample['standard'], sample['custom'])
        
        # Remove temp file
        os.remove(temp_path)
        
        print(f"Created: {sample['filename']}")
        print(f"  Classification: {sample['custom']['classification']}")
        print(f"  Security Level: {sample['custom']['securityLevel']}")
        print(f"  Custom Fields: {len(sample['custom'])} top-level fields")
        print()

    print(f"All PDFs created in: {OUTPUT_DIR}")

    # Verify metadata of one file
    print()
    print("--- Verification: quarterly_report_q4_2024.pdf ---")
    print()
    reader = PdfReader(os.path.join(OUTPUT_DIR, "quarterly_report_q4_2024.pdf"))
    meta = reader.metadata

    print("Standard Metadata:")
    for key, value in meta.items():
        if key != "/CustomFields":
            print(f"  {key}: {value}")

    print()
    print("Custom Fields (JSON):")
    if "/CustomFields" in meta:
        custom = json.loads(meta["/CustomFields"])
        print(json.dumps(custom, indent=2))
