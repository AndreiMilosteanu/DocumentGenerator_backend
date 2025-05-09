from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from services.pdf_renderer import render_pdf
from models import Document, SectionData
from typing import Dict, Any

router = APIRouter()

async def get_document_data(document_id: str) -> Dict[str, Any]:
    """
    Retrieves document data from the database and formats it for PDF generation.
    """
    try:
        # Get document record
        doc = await Document.get(id=document_id)
        
        # Get all section data for this document
        sections = await SectionData.filter(document=doc).all()
        
        if not sections:
            raise ValueError(f"No section data found for document {document_id}")
        
        # Format data in the structure expected by PDF generator
        pdf_data = {
            "_topic": doc.topic,
            "_section_idx": len(sections),  # Number of completed sections
        }
        
        # Add all section data
        for section in sections:
            # The data field contains the actual key-value pairs for each subsection
            pdf_data[section.section] = section.data
            
        return pdf_data
    except Document.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving document data: {str(e)}")

@router.get("/{document_id}/pdf")
async def get_pdf(document_id: str):
    # 1. Grab the collected data from database
    doc_data = {}
    pdf_data = await get_document_data(document_id)
    doc_data[document_id] = pdf_data

    # 2. Render the PDF
    try:
        pdf_io: BytesIO = render_pdf(document_id, doc_data)
        
        # Store the PDF in the database
        doc = await Document.get(id=document_id)
        doc.pdf_data = pdf_io.getvalue()
        await doc.save()
        
        # Reset BytesIO position for streaming
        pdf_io.seek(0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 3. Stream it back
    return StreamingResponse(pdf_io, media_type="application/pdf")

@router.get("/{document_id}/download")
async def download_pdf(document_id: str):
    # Try to get PDF from database first
    try:
        doc = await Document.get(id=document_id)
        if doc.pdf_data:
            pdf_io = BytesIO(doc.pdf_data)
            response = StreamingResponse(pdf_io, media_type="application/pdf")
            response.headers["Content-Disposition"] = f"attachment; filename=doc_{document_id}.pdf"
            return response
    except Document.DoesNotExist:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
    # If not in DB, generate it
    response = await get_pdf(document_id)
    response.headers["Content-Disposition"] = f"attachment; filename=doc_{document_id}.pdf"
    return response