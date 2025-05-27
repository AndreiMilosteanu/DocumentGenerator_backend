from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
import logging
from pydantic import BaseModel, UUID4
from models import Document, User, FileUpload, FileUploadStatus, ChatMessage, SectionData
from utils.auth import get_current_active_user
from utils.file_upload import process_file_upload, FileUploadError, delete_openai_file, extract_file_content, extract_document_data_from_file, extract_cover_page_data_from_file
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
        file_analysis_prompt = f"""
        I've uploaded a file for you to analyze. Please examine the content thoroughly and extract ALL relevant information 
        that could be used to populate our document structure. Don't limit yourself to any specific section - instead,
        identify information that fits anywhere in our document template.

        IMPORTANT: The system has also automatically extracted cover page (Deckblatt) information from this file and 
        populated the cover page fields with relevant project details, addresses, client information, and other data.
        You can reference this extracted cover page information in our conversation.

        Our document structure for topic '{topic}' is:
        {json.dumps(structure_description, indent=2)}

        For each section and subsection where you find relevant information in the file, please extract and structure it.
        Your response should include JSON data organized according to our document structure, along with a summary of 
        what you found.

        Remember to follow the required format by returning valid JSON data along with your human response.
        """
        
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
            await update_cover_page_with_extracted_data(doc, file_content, file.filename)
            
            logger.info(f"Completed data extraction for file {file.filename} - both document sections and cover page updated")
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
        
        # If no message provided, create a default message that encourages the assistant to analyze the file
        if not message:
            message = f"""I've uploaded a file: {file.filename}. 
Please analyze this file and help me understand its content. Let's discuss what information might be relevant for our document.
Do NOT automatically add any content to the document - we'll decide together what should be included after our discussion."""
        
        # Create the message first
        chat_message = await ChatMessage.create(
            document=doc,
            role="user",
            content=message,
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
        
        # Keep a copy of the file content for PDF merging
        file_upload.file_data = file_content
        await file_upload.save()
        logger.info(f"Saved file_data for {file_upload.original_filename}: {len(file_content)} bytes")
        
        # Extract data from the file and update both document sections and cover page
        try:
            # Extract document section data
            await update_document_with_extracted_data(doc, file_content, file.filename)
            
            # Extract cover page data
            await update_cover_page_with_extracted_data(doc, file_content, file.filename)
            
            logger.info(f"Completed data extraction for file {file.filename} - both document sections and cover page updated")
        except Exception as e:
            logger.error(f"Error during data extraction for file {file.filename}: {str(e)}")
            # Don't fail the upload if extraction fails - the file is still uploaded successfully
        
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
