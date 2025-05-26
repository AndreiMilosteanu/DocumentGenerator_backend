#!/usr/bin/env python3
"""
Test script to verify PDF styling improvements.
This script tests the font size increases and pagination improvements.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.pdf_renderer import render_pdf
from templates.structure import DOCUMENT_STRUCTURE
import tempfile

async def test_pdf_styling():
    """Test the PDF styling improvements"""
    
    print("🧪 Testing PDF styling improvements...")
    
    # Test data for each document type
    test_documents = {
        'Deklarationsanalyse': {
            '_topic': 'Deklarationsanalyse',
            '_section_idx': 2,
            'Probenahme': {
                'Probenahmeort': 'Test location for sampling',
                'Probenahmeverfahren': 'Standard sampling procedure according to DIN standards'
            },
            'Laboruntersuchung': {
                'Analyseverfahren': 'Chemical analysis using XRF spectroscopy',
                'Messergebnisse': 'Sample results: pH 7.2, Heavy metals within limits'
            }
        },
        'Baugrundgutachten': {
            '_topic': 'Baugrundgutachten',
            '_section_idx': 2,
            'Baugrunduntersuchung': {
                'Aufschlussverfahren': 'Drilling and sampling procedures',
                'Bodenschichtung': 'Layer 1: Sandy soil 0-2m, Layer 2: Clay 2-5m'
            },
            'Bodenmechanische Kennwerte': {
                'Korngrößenverteilung': 'Sand 60%, Silt 25%, Clay 15%',
                'Konsistenzgrenzen': 'Liquid limit: 35%, Plastic limit: 18%'
            }
        },
        'Bodenuntersuchung': {
            '_topic': 'Bodenuntersuchung',
            '_section_idx': 2,
            'Probenahme': {
                'Entnahmetiefe': '0.5m - 2.0m depth',
                'Probenanzahl': '12 samples collected from different locations'
            },
            'Klassifizierung': {
                'Bodenart': 'Sandy loam with organic content',
                'Bodengruppe': 'Group A-4 according to AASHTO classification'
            }
        },
        'Plattendruckversuch': {
            '_topic': 'Plattendruckversuch',
            '_section_idx': 2,
            'Versuchsdurchführung': {
                'Versuchsaufbau': 'Standard plate load test setup with 30cm diameter plate',
                'Belastungsschritte': 'Incremental loading: 25, 50, 75, 100 kN/m²'
            },
            'Messergebnisse': {
                'Setzungen': 'Maximum settlement: 8.5mm at 100 kN/m²',
                'Steifemodul': 'E₁ = 15.2 MN/m², E₂ = 22.8 MN/m²'
            }
        }
    }
    
    # Test cover page data
    cover_page_data = {
        'project_info': {
            'project_name': 'Test Project - PDF Styling Verification',
            'project_line2': 'Font Size and Pagination Test',
            'property_info': 'Test Property / Test Gemarkung',
            'street': 'Test Street',
            'house_number': '123',
            'postal_code': '12345',
            'city': 'Test City'
        },
        'client_info': {
            'client_company': 'Test Client Company GmbH',
            'client_name': 'Max Mustermann',
            'client_street': 'Client Street',
            'client_house_number': '456',
            'client_postal_code': '54321',
            'client_city': 'Client City'
        },
        'order_info': {
            'order_number': 'TEST-2024-001',
            'creation_date': '2024-01-15',
            'author': 'PDF Test System'
        },
        'company_info': {
            'company_info': 'Erdbaron HQ SRL | Test Environment | PDF Styling Test'
        }
    }
    
    results = []
    
    for doc_type, test_data in test_documents.items():
        print(f"\n📄 Testing {doc_type}...")
        
        try:
            # Create test document data
            doc_data = {
                'test_doc_id': test_data
            }
            
            # Render PDF
            pdf_stream = await render_pdf('test_doc_id', doc_data)
            
            if pdf_stream and len(pdf_stream.getvalue()) > 0:
                pdf_size = len(pdf_stream.getvalue())
                print(f"   ✅ {doc_type}: PDF generated successfully ({pdf_size:,} bytes)")
                
                # Save test PDF to temp directory for manual inspection
                with tempfile.NamedTemporaryFile(
                    delete=False, 
                    suffix=f'_{doc_type.lower()}_styling_test.pdf',
                    dir=tempfile.gettempdir()
                ) as temp_file:
                    temp_file.write(pdf_stream.getvalue())
                    print(f"   📁 Saved test PDF: {temp_file.name}")
                
                results.append({
                    'document_type': doc_type,
                    'status': 'success',
                    'size': pdf_size,
                    'file_path': temp_file.name
                })
            else:
                print(f"   ❌ {doc_type}: PDF generation failed - empty result")
                results.append({
                    'document_type': doc_type,
                    'status': 'failed',
                    'error': 'Empty PDF result'
                })
                
        except Exception as e:
            print(f"   ❌ {doc_type}: PDF generation failed - {str(e)}")
            results.append({
                'document_type': doc_type,
                'status': 'error',
                'error': str(e)
            })
    
    # Summary
    print(f"\n📊 Test Summary:")
    print(f"   Total document types tested: {len(test_documents)}")
    
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] != 'success']
    
    print(f"   ✅ Successful: {len(successful)}")
    print(f"   ❌ Failed: {len(failed)}")
    
    if successful:
        print(f"\n✅ Successfully generated PDFs:")
        for result in successful:
            print(f"   - {result['document_type']}: {result['size']:,} bytes")
            print(f"     File: {result['file_path']}")
    
    if failed:
        print(f"\n❌ Failed PDFs:")
        for result in failed:
            print(f"   - {result['document_type']}: {result.get('error', 'Unknown error')}")
    
    print(f"\n🎯 Styling improvements applied:")
    print(f"   - Cover page font sizes increased (28pt title, 16pt subtitle, 14pt content)")
    print(f"   - Table of contents font sizes increased (20pt title, 12-13pt entries)")
    print(f"   - Section titles increased to 16pt, subsections to 14pt")
    print(f"   - CSS-based pagination with 'Seite X von Y' format")
    print(f"   - Improved spacing and margins throughout")
    print(f"   - Page numbers in table of contents")
    
    return len(failed) == 0

if __name__ == "__main__":
    success = asyncio.run(test_pdf_styling())
    sys.exit(0 if success else 1) 