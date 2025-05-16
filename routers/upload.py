from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
import logging
from pydantic import BaseModel, UUID4
from models import Document, User, FileUpload, FileUploadStatus, ChatMessage
from utils.auth import get_current_active_user
from utils.file_upload import process_file_upload, FileUploadError, delete_openai_file

router = APIRouter()
logger = logging.getLogger("upload")

class FileUploadResponse(BaseModel):
    id: UUID4
    document_id: UUID4
    original_filename: str
    file_size: int
    file_type: str
    status: str
    created_at: str
    openai_file_id: Optional[str] = None
    error_message: Optional[str] = None

class FileListResponse(BaseModel):
    files: List[FileUploadResponse]
    count: int

@router.post("/{document_id}/file", response_model=FileUploadResponse)
async def upload_file(
    document_id: str,
    file: UploadFile = File(...),
    section: Optional[str] = Form(None),
    subsection: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a file to be associated with a document and attached to its OpenAI thread.
    """
    try:
        # Get document
        try:
            doc = await Document.get(id=document_id)
        except Document.DoesNotExist:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Check user access to document
        if current_user.role != "admin":
            # For regular users, check if they have a project with this document
            project = await doc.project.filter(user=current_user).first()
            if not project:
                raise HTTPException(status_code=403, detail="Access denied to this document")
        
        # Read file content
        file_content = await file.read()
        
        # Process the upload
        file_upload = await process_file_upload(
            file_content=file_content,
            filename=file.filename,
            document=doc,
            user=current_user,
            section=section,
            subsection=subsection
        )
        
        # Create response
        return FileUploadResponse(
            id=file_upload.id,
            document_id=doc.id,
            original_filename=file_upload.original_filename,
            file_size=file_upload.file_size,
            file_type=file_upload.file_type,
            status=file_upload.status,
            created_at=file_upload.created_at.isoformat(),
            openai_file_id=file_upload.openai_file_id,
            error_message=file_upload.error_message
        )
    
    except FileUploadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in file upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@router.post("/{document_id}/message-file", response_model=FileUploadResponse)
async def upload_file_to_message(
    document_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    message: str = Form(""),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a file and create a message in the conversation referencing it.
    This is for adding files mid-conversation.
    """
    try:
        # Get document
        try:
            doc = await Document.get(id=document_id)
        except Document.DoesNotExist:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Check user access to document
        if current_user.role != "admin":
            # For regular users, check if they have a project with this document
            project = await doc.project.filter(user=current_user).first()
            if not project:
                raise HTTPException(status_code=403, detail="Access denied to this document")
        
        # Ensure thread exists
        if not doc.thread_id:
            raise HTTPException(status_code=400, detail="Conversation not initialized for this document")
        
        # Get active section/subsection
        from routers.conversation import _get_active_subsection
        section, subsection = await _get_active_subsection(document_id)
        
        if not section or not subsection:
            raise HTTPException(status_code=400, detail="No active subsection. Select a subsection first.")
        
        # Read file content
        file_content = await file.read()
        
        # Create the message first
        chat_message = await ChatMessage.create(
            document=doc,
            role="user",
            content=message or f"Uploaded file: {file.filename}",
            section=section,
            subsection=subsection
        )
        
        # Process the upload and associate with the message
        file_upload = await process_file_upload(
            file_content=file_content,
            filename=file.filename,
            document=doc,
            user=current_user,
            section=section,
            subsection=subsection
        )
        
        # Associate the file with the message
        file_upload.associated_message = chat_message
        await file_upload.save()
        
        # Schedule the assistant to process the file in the background
        background_tasks.add_task(process_assistant_response, doc.id, doc.thread_id, doc.topic, section, subsection)
        
        # Create response
        return FileUploadResponse(
            id=file_upload.id,
            document_id=doc.id,
            original_filename=file_upload.original_filename,
            file_size=file_upload.file_size,
            file_type=file_upload.file_type,
            status=file_upload.status,
            created_at=file_upload.created_at.isoformat(),
            openai_file_id=file_upload.openai_file_id,
            error_message=file_upload.error_message
        )
    
    except FileUploadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in file upload with message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

async def process_assistant_response(document_id: str, thread_id: str, topic: str, section: str, subsection: str):
    """
    Process the assistant's response to a file upload.
    This is run as a background task.
    """
    try:
        from routers.conversation import _run_thread_and_parse, _send_format_correction, _update_section_data
        
        # Run the assistant to process the file
        data, message = await _run_thread_and_parse(thread_id, topic)
        
        # If no data was returned, try sending a format correction
        if not data and message:
            await _send_format_correction(thread_id, topic)
            data, message = await _run_thread_and_parse(thread_id, topic)
        
        # Get document
        doc = await Document.get(id=document_id)
        
        # Save the assistant's response
        await ChatMessage.create(
            document=doc,
            role="assistant",
            content=message,
            section=section,
            subsection=subsection
        )
        
        # Update section data
        await _update_section_data(doc, data)
        
        logger.info(f"Processed assistant response for file upload in document {document_id}")
    
    except Exception as e:
        logger.error(f"Error processing assistant response for file upload: {str(e)}")

@router.get("/{document_id}/files", response_model=FileListResponse)
async def list_document_files(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    List all files uploaded for a document.
    """
    try:
        # Get document
        try:
            doc = await Document.get(id=document_id)
        except Document.DoesNotExist:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Check user access to document
        if current_user.role != "admin":
            # For regular users, check if they have a project with this document
            project = await doc.project.filter(user=current_user).first()
            if not project:
                raise HTTPException(status_code=403, detail="Access denied to this document")
        
        # Get all file uploads for this document
        file_uploads = await FileUpload.filter(document=doc).order_by("-created_at").all()
        
        # Format response
        files = []
        for upload in file_uploads:
            files.append(FileUploadResponse(
                id=upload.id,
                document_id=doc.id,
                original_filename=upload.original_filename,
                file_size=upload.file_size,
                file_type=upload.file_type,
                status=upload.status,
                created_at=upload.created_at.isoformat(),
                openai_file_id=upload.openai_file_id,
                error_message=upload.error_message
            ))
        
        return FileListResponse(
            files=files,
            count=len(files)
        )
    
    except Exception as e:
        logger.error(f"Error listing document files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@router.delete("/{document_id}/files/{file_id}")
async def delete_file(
    document_id: str,
    file_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a file from OpenAI and remove it from the database.
    """
    try:
        # Get document
        try:
            doc = await Document.get(id=document_id)
        except Document.DoesNotExist:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Check user access to document
        if current_user.role != "admin":
            # For regular users, check if they have a project with this document
            project = await doc.project.filter(user=current_user).first()
            if not project:
                raise HTTPException(status_code=403, detail="Access denied to this document")
        
        # Get file upload
        try:
            file_upload = await FileUpload.get(id=file_id, document=doc)
        except FileUpload.DoesNotExist:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Delete from OpenAI if it was uploaded successfully
        if file_upload.openai_file_id and file_upload.status == FileUploadStatus.READY:
            deleted = await delete_openai_file(file_upload.openai_file_id)
            if not deleted:
                logger.warning(f"Failed to delete file {file_upload.openai_file_id} from OpenAI")
        
        # Delete from database
        await file_upload.delete()
        
        return {"success": True, "message": "File deleted successfully"}
    
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

@router.get("/files/status/{file_id}", response_model=FileUploadResponse)
async def get_file_status(
    file_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the status of a file upload.
    """
    try:
        # Get file upload
        try:
            file_upload = await FileUpload.get(id=file_id).prefetch_related('document')
        except FileUpload.DoesNotExist:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check user access to document
        doc = file_upload.document
        if current_user.role != "admin":
            # For regular users, check if they have a project with this document
            project = await doc.project.filter(user=current_user).first()
            if not project:
                raise HTTPException(status_code=403, detail="Access denied to this file")
        
        # Format response
        return FileUploadResponse(
            id=file_upload.id,
            document_id=doc.id,
            original_filename=file_upload.original_filename,
            file_size=file_upload.file_size,
            file_type=file_upload.file_type,
            status=file_upload.status,
            created_at=file_upload.created_at.isoformat(),
            openai_file_id=file_upload.openai_file_id,
            error_message=file_upload.error_message
        )
    
    except Exception as e:
        logger.error(f"Error getting file status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get file status: {str(e)}")
