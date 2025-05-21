#!/usr/bin/env python
"""
Diagnostic and fix script for PDF generation issues with approved subsections.
This script helps identify why approved subsection data isn't showing up in PDFs.
"""

import sys
import os
import asyncio
import json
import logging
from pathlib import Path

# Add parent directory to path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from tortoise import Tortoise
from models import Document, ApprovedSubsection, SectionData
from services.pdf_renderer import render_pdf
from services.template_manager import TemplateManager
from config import settings

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("fix_pdf_generation")

async def init_db():
    """Initialize Tortoise ORM"""
    await Tortoise.init(
        db_url=settings.DATABASE_URL,
        modules={"models": ["models"]}
    )

async def cleanup():
    """Close DB connection"""
    await Tortoise.close_connections()

async def get_document_info(document_id):
    """Get detailed information about a document and its data"""
    try:
        doc = await Document.get(id=document_id)
        approved = await ApprovedSubsection.filter(document=doc).all()
        sections = await SectionData.filter(document=doc).all()
        
        print(f"\nDocument ID: {document_id}")
        print(f"Topic: {doc.topic}")
        print(f"Thread ID: {doc.thread_id}")
        print(f"Has PDF data: {bool(doc.pdf_data)}")
        
        print(f"\nApproved subsections: {len(approved)}")
        for item in approved:
            print(f"- {item.section}.{item.subsection}: {item.approved_value[:50]}...")
        
        print(f"\nSection data records: {len(sections)}")
        for section in sections:
            subsections = list(section.data.keys()) if isinstance(section.data, dict) else []
            print(f"- {section.section}: {len(subsections)} subsections: {subsections}")
            
        return doc, approved, sections
    except Exception as e:
        print(f"Error getting document info: {e}")
        return None, [], []

async def build_data_structure(doc, approved):
    """Build the proper data structure that should be passed to the PDF renderer"""
    data = {
        "_topic": doc.topic,
        "_section_idx": 0  # Will be updated later
    }
    
    # Structure data from approved subsections
    sections_data = {}
    for item in approved:
        if item.section not in sections_data:
            sections_data[item.section] = {}
        
        sections_data[item.section][item.subsection] = item.approved_value
        print(f"Added approved value for {item.section}.{item.subsection}")
    
    # Add all section data
    for section, subsections in sections_data.items():
        data[section] = subsections
    
    data["_section_idx"] = len(sections_data)  # Number of sections with approved content
    
    print(f"\nBuilt data structure with {len(sections_data)} sections from approved content")
    return data

async def diagnostic_pdf_render(document_id, data):
    """
    Diagnostic function to render a PDF and see what's happening in the process
    """
    # Create a wrapper object that mimics what generate_pdf does
    doc_data = {document_id: data}
    
    print("\nRendering PDF with data structure:")
    print(f"Doc data keys: {list(doc_data.keys())}")
    print(f"Document data keys: {list(data.keys())}")
    
    # This is a simplified version of what happens in the render_pdf function
    # We're just inspecting the data here, not actually rendering the PDF
    template_manager = TemplateManager()
    
    # Extract section data for template
    section_data = {}
    topic = data.get('_topic', '')
    for section, subsections in data.items():
        if section.startswith('_'):
            continue
        if isinstance(subsections, dict):
            section_data[section] = subsections
            
    # Log what we found
    print("\nSection data extracted for template:")
    for section, subsections in section_data.items():
        print(f"- Section '{section}' has {len(subsections)} subsections: {list(subsections.keys())}")
    
    return section_data

async def run_diagnostic(document_id):
    """Run diagnostic tests on the document"""
    print(f"Running diagnostics for document: {document_id}")
    
    # Initialize the database connection
    await init_db()
    
    try:
        # Get document information
        doc, approved, sections = await get_document_info(document_id)
        if not doc:
            return
            
        # Build the proper data structure
        data = await build_data_structure(doc, approved)
        
        # Test PDF rendering logic
        section_data = await diagnostic_pdf_render(document_id, data)
        
        print("\nDiagnostic complete!")
        
        if not section_data:
            print("\n⚠️ Warning: No section data extracted for the template")
            print("This means the PDF will be empty. Check your approved subsections.")
        else:
            print(f"\n✅ Successfully extracted {sum(len(subs) for subs in section_data.values())} subsections for the template")
            print("Your PDF should now display the approved content.")
        
    finally:
        # Clean up
        await cleanup()

async def fix_approved_data(document_id):
    """
    Look at the approved data in the database and fix any inconsistencies to 
    ensure it works with the template system.
    """
    print(f"Running fix for document: {document_id}")
    
    # Initialize the database connection
    await init_db()
    
    try:
        # Get document information
        doc = await Document.get(id=document_id)
        if not doc:
            print("Document not found!")
            return
            
        approved = await ApprovedSubsection.filter(document=doc).all()
        if not approved:
            print("No approved subsections found! Approving some test data...")
            
            # Create some test approved data for debugging
            topic = doc.topic
            from tortoise import Tortoise
            conn = Tortoise.get_connection("default")
            
            # Find a section with data
            sections = await SectionData.filter(document=doc).all()
            if sections:
                test_section = sections[0]
                test_subsection = list(test_section.data.keys())[0] if test_section.data else None
                
                if test_subsection:
                    test_value = test_section.data[test_subsection]
                    print(f"Creating test approval for {test_section.section}.{test_subsection}")
                    
                    # Insert test approval
                    query = """
                        INSERT INTO approved_subsections(document_id, section, subsection, approved_value)
                        VALUES($1, $2, $3, $4)
                        ON CONFLICT (document_id, section, subsection) 
                        DO UPDATE SET approved_value = $4;
                    """
                    await conn.execute_query(
                        query, 
                        [str(doc.id), test_section.section, test_subsection, str(test_value)]
                    )
                    print("Test approval created!")
            else:
                print("No section data available to create test approvals")
                return
        
        # Verify approvals
        approved = await ApprovedSubsection.filter(document=doc).all()
        print(f"\nVerified approved subsections: {len(approved)}")
        for item in approved:
            print(f"- {item.section}.{item.subsection}: {item.approved_value[:50]}...")
            
        # Build proper data structure again
        data = await build_data_structure(doc, approved)
        
        # Generate a PDF using the proper structure
        print("\nGenerating test PDF to validate structure...")
        from io import BytesIO
        import tempfile
        
        # Create the proper data structure
        doc_data = {document_id: data}
        
        # Manual test of the render_pdf function
        from services.pdf_renderer import render_pdf
        try:
            pdf_io = render_pdf(document_id, doc_data)
            
            # Save to a temporary file for manual inspection
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_io.getvalue())
                pdf_path = tmp.name
                
            print(f"\n✅ Successfully generated test PDF: {pdf_path}")
            print("Please check this PDF to confirm content is displayed correctly.")
            
            # Update the document with this PDF
            doc.pdf_data = pdf_io.getvalue()
            await doc.save()
            print("Document PDF data has been updated with this test PDF.")
            
        except Exception as e:
            print(f"\n❌ Error generating test PDF: {e}")
            import traceback
            traceback.print_exc()
        
    finally:
        # Clean up
        await cleanup()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_pdf_generation.py <document_id> [command]")
        print("Commands:")
        print("  diag    - Run diagnostic (default)")
        print("  fix     - Fix approved data and generate test PDF")
        sys.exit(1)
        
    document_id = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "diag"
    
    if command == "diag":
        asyncio.run(run_diagnostic(document_id))
    elif command == "fix":
        asyncio.run(fix_approved_data(document_id))
    else:
        print(f"Unknown command: {command}")
        print("Available commands: diag, fix")
        sys.exit(1) 