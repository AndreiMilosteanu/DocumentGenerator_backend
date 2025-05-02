from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from services.pdf_renderer import render_pdf
from routers.conversation import doc_data   # <-- pull in the in-memory data

router = APIRouter()

@router.get("/{document_id}/pdf")
async def get_pdf(document_id: str):
    # 1. Grab the collected data
    if document_id not in doc_data:
        raise HTTPException(404, detail="No data for this document")
    data = doc_data[document_id]

    # 2. Render the PDF
    try:
        pdf_io: BytesIO = render_pdf(document_id, doc_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 3. Stream it back
    return StreamingResponse(pdf_io, media_type="application/pdf")

@router.get("/{document_id}/download")
async def download_pdf(document_id: str):
    response = await get_pdf(document_id)
    response.headers["Content-Disposition"] = f"attachment; filename=doc_{document_id}.pdf"
    return response

if __name__ == '__main__':
    doc_data["a"] = {
        "_topic": "Deklarationsanalyse",
        "_section_idx": 3,  # indicates all three sections have been completed
        "Projekt Details": {
            "Standort": "Berlin, Deutschland",
            "Auftraggeber": "Erdbaron GmbH"
        },
        "Projekt Objectives": {
            "Ziele": "Erfassung der Bodenwerte vor Baubeginn",
            "Anforderungen": "Detaillierte Dokumentation bestehender Bedingungen"
        },
        "Anhänge": {
            "Dokumente": ["grundgutachten.pdf"],
            "Bilder": ["bohrkern1.png", "bohrkern2.png"]
        }
    }
    pdf_io = render_pdf("a", doc_data)
    response = download_pdf("a")
    print(response)