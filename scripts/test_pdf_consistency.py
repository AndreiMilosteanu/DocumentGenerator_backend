#!/usr/bin/env python3
"""
Test script to verify PDF consistency between environments.
This script generates a test PDF and provides information about its characteristics.
"""

import sys
import os
import tempfile
from pathlib import Path

# Add the parent directory to the Python path to import project modules
sys.path.append(str(Path(__file__).parent.parent))

import asyncio
from io import BytesIO
from services.pdf_renderer import render_pdf
from config import settings

async def test_pdf_consistency():
    """Test PDF generation with a standardized document"""
    
    print("PDF Consistency Test")
    print("=" * 50)
    
    # Create test document data
    test_doc_data = {
        "test_doc": {
            "_topic": "Deklarationsanalyse",
            "_section_idx": 2,
            "Stellungnahme": {
                "Probenahmeprotokoll": "Test content for Probenahmeprotokoll section. This should render consistently across environments.",
                "Laborberichte": "Test content for Laborberichte section with some longer text to test font rendering and line spacing.",
                "Auswertung": "Test content for Auswertung section."
            },
            "Anhänge": {
                "Dateien": "Test file listing:\n- test_file_1.pdf\n- test_file_2.docx\n- test_file_3.jpg"
            }
        }
    }
    
    # Test cover page data
    test_cover_data = {
        "PROJEKTBESCHREIBUNG": {
            "project_name": "Test Project Name",
            "project_line2": "Additional project information"
        },
        "AUFTRAGGEBER": {
            "client_company": "Test Company GmbH",
            "client_name": "Max Mustermann",
            "client_street": "Teststraße",
            "client_house_number": "123",
            "client_postal_code": "12345",
            "client_city": "Teststadt"
        }
    }
    
    try:
        # Generate PDF
        print("Generating test PDF...")
        pdf_io = await render_pdf("test_doc", test_doc_data)
        
        if pdf_io and pdf_io.getvalue():
            pdf_size = len(pdf_io.getvalue())
            print(f"✓ PDF generated successfully")
            print(f"  Size: {pdf_size} bytes")
            
            # Save to temporary file for inspection
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(pdf_io.getvalue())
                temp_path = temp_file.name
            
            print(f"  Saved to: {temp_path}")
            print(f"  You can inspect this file to check font rendering and pagination")
            
            # Basic size checks
            if pdf_size < 5000:
                print("⚠ PDF seems unusually small - may be missing content")
            elif pdf_size > 100000:
                print("⚠ PDF seems unusually large - check for issues")
            else:
                print("✓ PDF size appears normal")
            
            # Try to extract some basic info
            try:
                import PyPDF2
                pdf_io.seek(0)
                pdf_reader = PyPDF2.PdfReader(pdf_io)
                num_pages = len(pdf_reader.pages)
                print(f"  Pages: {num_pages}")
                
                if num_pages < 2:
                    print("⚠ Expected at least 2 pages (cover + content)")
                else:
                    print("✓ Page count looks reasonable")
                    
            except Exception as e:
                print(f"? Could not analyze PDF structure: {e}")
            
            return True
            
        else:
            print("✗ PDF generation failed - no output")
            return False
            
    except Exception as e:
        print(f"✗ PDF generation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_configuration():
    """Check current configuration"""
    print("\nConfiguration Check")
    print("-" * 30)
    
    # Check wkhtmltopdf path
    wkhtml_path = getattr(settings, 'WKHTMLTOPDF_PATH', None)
    if wkhtml_path:
        print(f"WKHTMLTOPDF_PATH: {wkhtml_path}")
        if os.path.exists(str(wkhtml_path)):
            print("✓ wkhtmltopdf path exists")
        else:
            print("✗ wkhtmltopdf path does not exist")
    else:
        print("WKHTMLTOPDF_PATH: Not set (will use system PATH)")
    
    # Check environment variables
    env_vars = ["QT_QPA_PLATFORM", "DISPLAY", "FONTCONFIG_PATH"]
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            print(f"{var}: {value}")
        else:
            print(f"{var}: Not set")

async def main():
    """Run the consistency test"""
    check_configuration()
    success = await test_pdf_consistency()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ PDF consistency test completed successfully")
        print("\nTo compare with other environments:")
        print("1. Run this script on both local and deployed environments")
        print("2. Compare the generated PDF files")
        print("3. Check for differences in font rendering, spacing, and pagination")
    else:
        print("✗ PDF consistency test failed")
        print("\nTroubleshooting steps:")
        print("1. Run scripts/check_pdf_environment.py for detailed diagnostics")
        print("2. Ensure wkhtmltopdf is properly installed")
        print("3. Check that all required fonts are available")
        print("4. Verify environment variables are set correctly")

if __name__ == "__main__":
    asyncio.run(main()) 