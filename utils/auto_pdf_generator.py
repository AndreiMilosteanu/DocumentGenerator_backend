"""
Utility for automatically generating PDFs when files are uploaded.
This module is responsible for extracting data from uploaded files,
populating document sections, and generating PDFs.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import httpx
from models import Document, FileUpload, FileUploadStatus
from utils.file_upload import extract_document_data_from_file

logger = logging.getLogger("auto_pdf_generator")

async def generate_pdf_from_file_upload(file_upload_id: str) -> bool:
    """
    Generate a PDF based on an uploaded file.
    
    Args:
        file_upload_id: The ID of the file upload record
        
    Returns:
        bool: True if PDF generation was successful, False otherwise
    """
    try:
        # Get the file upload record
        file_upload = await FileUpload.get(id=file_upload_id).prefetch_related('document')
        document = file_upload.document
        
        # Skip if file doesn't have binary data
        if not file_upload.file_data:
            logger.warning(f"File upload {file_upload_id} has no binary data, skipping PDF generation")
            return False
        
        # Skip if file is not in READY status
        if file_upload.status != FileUploadStatus.READY:
            logger.warning(f"File upload {file_upload_id} is not in READY status, skipping PDF generation")
            return False
            
        # Call the PDF generation API
        logger.info(f"Generating PDF for document {document.id} based on file upload {file_upload_id}")
        
        try:
            # Use httpx to call the PDF generation endpoint
            async with httpx.AsyncClient() as client:
                # Make a request to our own API to generate the PDF
                base_url = "http://localhost:8000"  # Adjust if your server runs on a different port
                response = await client.get(
                    f"{base_url}/documents/{document.id}/pdf",
                    params={"approved_only": False, "include_attachments": True}
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to generate PDF via API: {response.status_code} - {response.text}")
                    return False
                
                logger.info(f"Successfully generated PDF for document {document.id}")
                return True
                
        except Exception as e:
            logger.error(f"Error calling PDF generation API: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error generating PDF from file upload {file_upload_id}: {str(e)}")
        return False

async def schedule_pdf_generation_for_document(document_id: str, delay_seconds: int = 5) -> None:
    """
    Schedule PDF generation for a document after a short delay.
    This allows time for the file content extraction and section data updates to complete.
    
    Args:
        document_id: The ID of the document to generate a PDF for
        delay_seconds: The number of seconds to wait before generating the PDF
    """
    try:
        # Get the document
        document = await Document.get(id=document_id)
        
        # Get the most recent file upload
        file_upload = await FileUpload.filter(document=document).order_by("-created_at").first()
        
        if not file_upload:
            logger.warning(f"No file uploads found for document {document_id}, skipping PDF generation")
            return
        
        # Wait for the specified delay to allow file processing to complete
        await asyncio.sleep(delay_seconds)
        
        # Generate the PDF
        success = await generate_pdf_from_file_upload(str(file_upload.id))
        
        if success:
            logger.info(f"Scheduled PDF generation completed for document {document_id}")
        else:
            logger.warning(f"Scheduled PDF generation failed for document {document_id}")
            
    except Exception as e:
        logger.error(f"Error scheduling PDF generation for document {document_id}: {str(e)}")

def schedule_pdf_generation(document_id: str) -> None:
    """
    Schedule PDF generation in a non-blocking way.
    This function creates a background task that will run independently.
    
    Args:
        document_id: The ID of the document to generate a PDF for
    """
    try:
        # Create an asyncio task
        loop = asyncio.get_event_loop()
        task = loop.create_task(schedule_pdf_generation_for_document(document_id))
        
        # Add a callback to handle any exceptions
        def handle_task_result(task):
            try:
                task.result()
            except Exception as e:
                logger.error(f"Unhandled exception in PDF generation task: {str(e)}")
                
        task.add_done_callback(handle_task_result)
        
        logger.info(f"Scheduled PDF generation task for document {document_id}")
        
    except Exception as e:
        logger.error(f"Error creating PDF generation task: {str(e)}") 