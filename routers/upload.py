from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
import logging
from pydantic import BaseModel, UUID4
from models import Document, User, FileUpload, FileUploadStatus, ChatMessage, SectionData
from utils.auth import get_current_active_user
from utils.file_upload import process_file_upload, FileUploadError, delete_openai_file, extract_file_content, extract_document_data_from_file, extract_cover_page_data_from_file, save_temp_file, upload_file_to_openai, is_file_type_supported, validate_file_size
from utils.rate_limiter import RateLimiter
from utils.auto_pdf_generator import schedule_pdf_generation
from templates.structure import DOCUMENT_STRUCTURE
from services.openai_client_optimized import get_optimized_client
import json
from config import settings

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
    attachment: bool = False  # True if file will be included in PDF attachments (direct upload), False if conversation file

class FileListResponse(BaseModel):
    files: List[FileUploadResponse]
    count: int

async def append_file_to_document_attachments(document: Document, file_upload: FileUpload, file_content: bytes) -> None:
    """
    Append the file information to the document's attachment section.
    This will add the file to either the "Anlage" or "Anhänge" section depending on the document structure.
    The actual file content will be extracted and included in the section.
    """
    topic = document.topic
    if topic not in DOCUMENT_STRUCTURE:
        logger.warning(f"Unknown topic: {topic}, cannot add file to attachments")
        return

    # Find the attachment section name based on the document structure
    attachment_section = None
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        section_name = list(sec_obj.keys())[0]
        if section_name in ["Anlage", "Anhänge", "Anlagen"]:
            attachment_section = section_name
            break

    if not attachment_section:
        logger.warning(f"No attachment section found for topic {topic}")
        return

    # Get or create the section data
    section_data, created = await SectionData.get_or_create(
        document=document,
        section=attachment_section,
        defaults={"data": {}}
    )

    data = section_data.data
    if not isinstance(data, dict):
        data = {}

    # Find subsection for file attachments in the structure
    subsection = None
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        section_name = list(sec_obj.keys())[0]
        if section_name == attachment_section:
            subsections = sec_obj[section_name]
            # Use the first subsection for simplicity - we can refine this later if needed
            if subsections:
                subsection = subsections[0]
                break

    if not subsection:
        logger.warning(f"No subsection found in {attachment_section} section for topic {topic}")
        return

    # Extract content from file
    file_text = await extract_file_content(file_content, file_upload.original_filename)
    
    # Append file content to the subsection
    current_content = data.get(subsection, "")
    if current_content and not current_content.endswith('\n'):
        current_content += "\n\n"
    
    # Format the new file content with a header
    formatted_content = f"--- {file_upload.original_filename} ---\n\n{file_text}\n\n"
    
    # Append to existing content
    if current_content:
        new_content = current_content + formatted_content
    else:
        new_content = formatted_content
    
    # Update the section data
    data[subsection] = new_content
    section_data.data = data
    await section_data.save()
    
    logger.info(f"Added file content from {file_upload.id} to {attachment_section}.{subsection} for document {document.id}")

async def process_assistant_response(document_id: str, thread_id: str, topic: str, section: str, subsection: str):
    """
    Process the assistant's response to a file upload.
    This is run as a background task.
    """
    try:
        import openai
        from routers.conversation import _run_thread_and_parse, _send_format_correction, _update_section_data
        from templates.structure import DOCUMENT_STRUCTURE
        
        # Create a custom client with increased timeout
        client = get_optimized_client()
        
        # Build a structured representation of the full document template
        structure_description = []
        if topic in DOCUMENT_STRUCTURE:
            for section_obj in DOCUMENT_STRUCTURE[topic]:
                section_name = list(section_obj.keys())[0]
                subsections = section_obj[section_name]
                structure_description.append({
                    "section": section_name,
                    "subsections": subsections
                })
        
        # Create a comprehensive file analysis prompt
        file_analysis_prompt = ""
        # file_analysis_prompt = f"""
        # Ich habe eine Datei für Sie zum Analysieren hochgeladen. Bitte untersuchen Sie den Inhalt gründlich und extrahieren Sie ALLE relevanten Informationen, 
        # die zur Befüllung unserer Dokumentstruktur verwendet werden könnten. Beschränken Sie sich nicht auf einen bestimmten Abschnitt - identifizieren Sie 
        # stattdessen Informationen, die überall in unsere Dokumentvorlage passen.

        # Unsere Dokumentstruktur für das Thema '{topic}' ist:
        # {json.dumps(structure_description, indent=2)}

        # Für jeden Abschnitt und Unterabschnitt, in dem Sie relevante Informationen in der Datei finden, extrahieren und strukturieren Sie diese bitte.
        # Ihre Antwort sollte JSON-Daten entsprechend unserer Dokumentstruktur sowie eine Zusammenfassung dessen, was Sie gefunden haben, enthalten.

        # Denken Sie daran, das erforderliche Format einzuhalten, indem Sie gültige JSON-Daten zusammen mit Ihrer menschlichen Antwort zurückgeben.
        # """
        
        # Send the instruction to the thread
        await client.send_message_optimized(thread_id, file_analysis_prompt)
        
        # Run assistant and get response using optimized method
        data, raw = await client.run_assistant_optimized(thread_id, settings.TOPIC_ASSISTANTS.get(topic))
        
        # Get document
        doc = await Document.get(id=document_id)
        
        # Save the instruction message
        await ChatMessage.create(
            document=doc,
            role="user",
            content=file_analysis_prompt,
            section=section,
            subsection=subsection
        )
        
        # Save the assistant's response
        await ChatMessage.create(
            document=doc,
            role="assistant",
            content=raw,
            section=section,
            subsection=subsection
        )
        
        # Update section data
        await _update_section_data(doc, data)
        
        logger.info(f"Processed assistant response for file upload in document {document_id}")
    
    except Exception as e:
        logger.error(f"Error processing assistant response for file upload: {str(e)}")
        logger.exception("Exception details:")

async def update_document_with_extracted_data(document: Document, file_content: bytes, filename: str):
    """
    Extract structured data from the file and update document sections accordingly.
    This function analyzes the file content and populates the document structure with relevant information.
    """
    from routers.conversation import _update_section_data
    
    try:
        # Extract structured data from the file content based on document topic
        logger.info(f"Starting document data extraction for file '{filename}' with topic '{document.topic}'")
        extracted_data = await extract_document_data_from_file(file_content, filename, document.topic)
        
        if not extracted_data:
            logger.warning(f"No structured data could be extracted from file {filename}")
            return
        
        # Log what we extracted
        sections_with_content = 0
        subsections_with_content = 0
        
        for section, subsections in extracted_data.items():
            section_has_content = False
            for subsection, content in subsections.items():
                if content and len(content.strip()) > 0:
                    subsections_with_content += 1
                    section_has_content = True
                    logger.info(f"Extracted content for {section}.{subsection}: {len(content)} characters")
            
            if section_has_content:
                sections_with_content += 1
        
        if sections_with_content == 0:
            logger.warning(f"Document data extraction completed but no actual content was found in any section")
            return
            
        logger.info(f"Document data extraction found content in {sections_with_content} sections and {subsections_with_content} subsections")
            
        # Update the document sections with the extracted data
        await _update_section_data(document, extracted_data)
        
        logger.info(f"Successfully updated document {document.id} with data extracted from {filename}")
    except Exception as e:
        logger.error(f"Error updating document with extracted data: {str(e)}")
        logger.exception("Error details:")

async def update_cover_page_with_extracted_data(document: Document, file_content: bytes, filename: str):
    """
    Extract cover page data from the file and update the document's cover page accordingly.
    This function analyzes the file content and populates the cover page structure with relevant information.
    """
    try:
        # Extract cover page data from the file content based on document topic
        logger.info(f"Starting cover page data extraction for file '{filename}' with topic '{document.topic}'")
        extracted_cover_data = await extract_cover_page_data_from_file(file_content, filename, document.topic)
        
        if not extracted_cover_data:
            logger.warning(f"No cover page data could be extracted from file {filename}")
            return
        
        # Log what we extracted
        categories_with_content = 0
        fields_with_content = 0
        
        for category, fields in extracted_cover_data.items():
            category_has_content = False
            for field_name, content in fields.items():
                if content and len(str(content).strip()) > 0:
                    fields_with_content += 1
                    category_has_content = True
                    logger.info(f"Extracted cover page data for {category}.{field_name}: '{content[:50]}{'...' if len(str(content)) > 50 else ''}'")
            
            if category_has_content:
                categories_with_content += 1
        
        if categories_with_content == 0:
            logger.warning(f"Cover page data extraction completed but no actual content was found in any category")
            return
            
        logger.info(f"Cover page data extraction found content in {categories_with_content} categories and {fields_with_content} fields")
        
        # Get or create the cover page data for the document
        cover_page, created = await CoverPageData.get_or_create(
            document=document,
            defaults={"data": {}}
        )
        
        # Merge the extracted data with existing cover page data
        existing_data = cover_page.data or {}
        
        # For each category in the extracted data
        for category, fields in extracted_cover_data.items():
            if category not in existing_data:
                existing_data[category] = {}
            
            # For each field in the category, only update if it's currently empty or if the extracted value is better
            for field_name, extracted_value in fields.items():
                if extracted_value and len(str(extracted_value).strip()) > 0:
                    current_value = existing_data[category].get(field_name, "")
                    
                    # Update if current value is empty or if extracted value is longer (more detailed)
                    if not current_value or len(str(extracted_value)) > len(str(current_value)):
                        existing_data[category][field_name] = str(extracted_value).strip()
                        logger.info(f"Updated cover page field {category}.{field_name} with extracted value")
                    else:
                        logger.debug(f"Keeping existing value for {category}.{field_name} (current: '{current_value[:30]}...')")
        
        # Save the updated cover page data
        cover_page.data = existing_data
        await cover_page.save()
        
        logger.info(f"Successfully updated cover page for document {document.id} with data extracted from {filename}")
        
    except Exception as e:
        logger.error(f"Error updating cover page with extracted data: {str(e)}")
        logger.exception("Cover page update error details:")

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
    The file will be used as context for the assistant but will NOT automatically update the document.
    """
    # Rate limiting disabled
    # allowed, error_msg = await RateLimiter.check_rate_limit(current_user)
    # if not allowed:
    #     raise HTTPException(status_code=429, detail=error_msg)
    
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
        
        # Keep a copy of the file content for PDF generation
        file_upload.file_data = file_content
        await file_upload.save()
        logger.info(f"Saved file_data for {file_upload.original_filename}: {len(file_content)} bytes")
        
        # Extract data from the file and update both document sections and cover page
        try:
            # Extract document section data
            await update_document_with_extracted_data(doc, file_content, file.filename)
            
            # Extract cover page data
            # await update_cover_page_with_extracted_data(doc, file_content, file.filename)
            
            # logger.info(f"Completed data extraction for file {file.filename} - both document sections and cover page updated")
            logger.info(f"Completed data extraction for file {file.filename} - document sections extracted")

        except Exception as e:
            logger.error(f"Error during data extraction for file {file.filename}: {str(e)}")
            # Don't fail the upload if extraction fails - the file is still uploaded successfully
        
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
            error_message=file_upload.error_message,
            attachment=True  # Direct uploads are included in PDF attachments
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
    The file will be used only as context for the assistant and will NOT automatically modify any document data.
    """
    # Rate limiting disabled
    # allowed, error_msg = await RateLimiter.check_rate_limit(current_user)
    # if not allowed:
    #     raise HTTPException(status_code=429, detail=error_msg)
    
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
        
        # If no message provided, create a default message
        if not message:
            message = f"Ich habe eine Datei hochgeladen: {file.filename}. Bitte analysieren Sie diese."
        
        # Process the upload but WITHOUT attaching to thread yet (we'll do that manually)
        # We need to upload the file to OpenAI first to get the file_id
        from utils.file_upload import save_temp_file, upload_file_to_openai, is_file_type_supported, validate_file_size, FileUploadError
        import uuid
        import os
        import mimetypes
        
        # Validate file
        if not is_file_type_supported(file.filename):
            raise FileUploadError(f"Unsupported file type: {file.filename}")
        
        file_size = len(file_content)
        if not validate_file_size(file_size):
            raise FileUploadError(f"File too large: {file_size} bytes")
        
        # Create FileUpload record
        file_ext = os.path.splitext(file.filename)[1].lower()
        mime_type, _ = mimetypes.guess_type(file.filename)
        
        file_upload = await FileUpload.create(
            id=uuid.uuid4(),
            document=doc,
            user=current_user,
            original_filename=file.filename,
            openai_file_id="",  # Will be updated after OpenAI upload
            file_size=file_size,
            file_type=mime_type or file_ext,
            status=FileUploadStatus.PROCESSING,
            section=section,
            subsection=subsection
        )
        
        # Save file content
        file_upload.file_data = file_content
        await file_upload.save()
        
        try:
            # Save to temporary storage and upload to OpenAI
            temp_path = await save_temp_file(file_content, file.filename)
            
            try:
                # Upload to OpenAI
                openai_file = await upload_file_to_openai(temp_path, thread_id=doc.thread_id)
                
                # Update record with OpenAI file ID
                file_upload.openai_file_id = openai_file.id
                await file_upload.save()
                
                # Now send the user's message with the file attached to the OpenAI thread
                import openai
                client = openai.OpenAI(api_key=settings.OPENAI_API_KEY, timeout=120.0)
                
                # Send the user's message with file attachment to OpenAI thread
                openai_response = client.beta.threads.messages.create(
                    thread_id=doc.thread_id,
                    role="user",
                    content=message,
                    attachments=[
                        {"file_id": openai_file.id, "tools": [{"type": "file_search"}]}
                    ]
                )
                
                # Create the message in our database to match what was sent to OpenAI
                chat_message = await ChatMessage.create(
                    document=doc,
                    role="user",
                    content=message,
                    section=section,
                    subsection=subsection
                )
                
                # Associate the file with the message
                file_upload.associated_message = chat_message
                file_upload.status = FileUploadStatus.READY
                await file_upload.save()
                
                logger.info(f"Successfully sent message with file {openai_file.id} to thread {doc.thread_id}")
                
                # Now run the assistant to get a response to the user's message
                try:
                    from routers.conversation import _update_section_data
                    
                    # Get the appropriate assistant ID for the topic
                    assistant_id = settings.TOPIC_ASSISTANTS.get(doc.topic)
                    if not assistant_id:
                        assistant_id = settings.ASSISTANT_ID
                    
                    # Run the assistant to get a response
                    client = get_optimized_client()
                    data, raw_response = await client.run_assistant_optimized(doc.thread_id, assistant_id)
                    
                    # Save the assistant's response to the database
                    await ChatMessage.create(
                        document=doc,
                        role="assistant",
                        content=raw_response,
                        section=section,
                        subsection=subsection
                    )
                    
                    # Update section data if the assistant provided structured data
                    if data:
                        await _update_section_data(doc, data)
                    
                    logger.info(f"Successfully processed assistant response for message with file")
                    
                except Exception as e:
                    logger.error(f"Error getting assistant response: {str(e)}")
                    # Don't fail the upload if assistant response fails - the message and file were uploaded successfully
                
            finally:
                # Clean up temporary file
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
        
        except Exception as e:
            # Update status to ERROR and log the error
            file_upload.status = FileUploadStatus.ERROR
            file_upload.error_message = str(e)
            await file_upload.save()
            logger.error(f"File upload error: {str(e)}")
            raise FileUploadError(f"File upload failed: {str(e)}")
        
        # Extract data from the file and update both document sections and cover page
        try:
            # Extract document section data
            await update_document_with_extracted_data(doc, file_content, file.filename)
            
            # Extract cover page data
            # await update_cover_page_with_extracted_data(doc, file_content, file.filename)
            
            logger.info(f"Completed data extraction for file {file.filename} - both document sections and cover page updated")
        except Exception as e:
            logger.error(f"Error during data extraction for file {file.filename}: {str(e)}")
            # Don't fail the upload if extraction fails - the file is still uploaded successfully
        
        # Note: We don't schedule the assistant background task for message-file uploads
        # because the user has already sent their own message with the file attached.
        # The assistant will respond naturally to the user's message in the conversation flow.
        
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
            error_message=file_upload.error_message,
            attachment=False  # Conversation uploads are NOT included in PDF attachments
        )
    
    except FileUploadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in file upload with message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@router.get("/{document_id}/files", response_model=FileListResponse)
async def list_document_files(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    List all files uploaded for a document.
    
    Returns:
    - Files uploaded via /upload/{document_id}/file have attachment=True (included in PDF attachments)
    - Files uploaded via /upload/{document_id}/message-file have attachment=False (conversation only)
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
        file_uploads = await FileUpload.filter(document=doc).prefetch_related('associated_message').order_by("-created_at").all()
        
        # Format response
        files = []
        for upload in file_uploads:
            # Calculate attachment status: True if no associated_message_id (direct upload), False if has associated_message_id (conversation upload)
            is_attachment = upload.associated_message_id is None
            
            # Debug logging to help troubleshoot
            logger.debug(f"File {upload.original_filename}: associated_message_id={upload.associated_message_id}, is_attachment={is_attachment}")
            
            files.append(FileUploadResponse(
                id=upload.id,
                document_id=doc.id,
                original_filename=upload.original_filename,
                file_size=upload.file_size,
                file_type=upload.file_type,
                status=upload.status,
                created_at=upload.created_at.isoformat(),
                openai_file_id=upload.openai_file_id,
                error_message=upload.error_message,
                attachment=is_attachment
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
    
    The attachment field indicates whether the file will be included in PDF attachments:
    - True: Direct upload (via /upload/{document_id}/file) - included in PDF
    - False: Conversation upload (via /upload/{document_id}/message-file) - conversation only
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
            error_message=file_upload.error_message,
            attachment=file_upload.associated_message_id is None  # True if direct upload, False if conversation upload
        )
    
    except Exception as e:
        logger.error(f"Error getting file status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get file status: {str(e)}")

@router.get("/{document_id}/attachment-files")
async def get_attachment_files(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the list of files that have been added to the document's attachment section.
    This represents what will appear in the PDF's Anhänge section.
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
        
        # Find the attachment section name based on the document structure
        topic = doc.topic
        attachment_section = None
        attachment_content = ""
        
        for sec_obj in DOCUMENT_STRUCTURE[topic]:
            section_name = list(sec_obj.keys())[0]
            if section_name in ["Anlage", "Anhänge", "Anlagen"]:
                attachment_section = section_name
                break
        
        if attachment_section:
            # Get section data
            section_data = await SectionData.filter(document=doc, section=attachment_section).first()
            if section_data:
                data = section_data.data
                
                # Find the first subsection with content
                for sec_obj in DOCUMENT_STRUCTURE[topic]:
                    section_name = list(sec_obj.keys())[0]
                    if section_name == attachment_section:
                        subsections = sec_obj[section_name]
                        for subsection in subsections:
                            if subsection in data and data[subsection]:
                                attachment_content = data[subsection]
                                break
                        break
        
        # Parse the content to extract filenames
        files = []
        if attachment_content:
            lines = attachment_content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('- '):
                    filename = line[2:].strip()
                    files.append(filename)
        
        return {
            "document_id": document_id,
            "attachment_section": attachment_section,
            "files": files
        }
        
    except Exception as e:
        logger.error(f"Error getting attachment files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get attachment files: {str(e)}")
