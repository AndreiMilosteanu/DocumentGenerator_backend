import os
import uuid
import tempfile
import logging
import mimetypes
from pathlib import Path
from typing import List, Optional, Dict, Any, BinaryIO, Tuple, Union
import openai
from config import settings
from models import FileUpload, Document, User, FileUploadStatus

logger = logging.getLogger("file_upload")

# Supported file types for upload
SUPPORTED_MIME_TYPES = [
    'application/pdf',                                         # PDF
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # DOCX
    'text/plain',                                              # TXT
    'text/csv',                                                # CSV
    'application/json',                                        # JSON
    'image/jpeg',                                              # JPEG
    'image/png',                                               # PNG
]

SUPPORTED_FILE_EXTENSIONS = [
    '.pdf', '.docx', '.txt', '.csv', '.json', '.jpg', '.jpeg', '.png'
]

class FileUploadError(Exception):
    """Exception raised for errors in the file upload process."""
    pass

def is_file_type_supported(filename: str) -> bool:
    """
    Check if the file type is supported based on extension.
    """
    file_ext = os.path.splitext(filename)[1].lower()
    mime_type, _ = mimetypes.guess_type(filename)
    
    return (file_ext in SUPPORTED_FILE_EXTENSIONS or 
            (mime_type and mime_type in SUPPORTED_MIME_TYPES))

def validate_file_size(file_size: int) -> bool:
    """
    Check if the file size is within the allowed limit (20MB for OpenAI).
    """
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB in bytes
    return file_size <= MAX_FILE_SIZE

async def save_temp_file(file_content: bytes, filename: str) -> str:
    """
    Save the uploaded file to a temporary location.
    Returns the path to the temporary file.
    """
    # Create a temporary file
    temp_dir = tempfile.gettempdir()
    file_ext = os.path.splitext(filename)[1]
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = os.path.join(temp_dir, temp_filename)
    
    # Write the file content
    with open(temp_path, 'wb') as f:
        f.write(file_content)
    
    return temp_path

async def upload_file_to_openai(file_path: str, purpose: str = "assistants") -> Dict[str, Any]:
    """
    Upload a file to OpenAI.
    Returns the OpenAI file object.
    """
    try:
        # Create OpenAI client instance
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Ensure the purpose is set to 'assistants' for the file to be available with file_search
        if purpose != "assistants":
            logger.warning(f"Changing file purpose from '{purpose}' to 'assistants' for compatibility with file_search")
            purpose = "assistants"
        
        with open(file_path, 'rb') as file:
            response = client.files.create(
                file=file,
                purpose=purpose
            )
        logger.info(f"File successfully uploaded to OpenAI with ID: {response.id}")
        return response
    except Exception as e:
        logger.error(f"OpenAI file upload error: {str(e)}")
        raise FileUploadError(f"Failed to upload file to OpenAI: {str(e)}")

async def attach_file_to_thread(thread_id: str, file_id: str, topic: str) -> Dict[str, Any]:
    """
    Attach a file to an OpenAI thread by making it available to the assistant.
    
    Args:
        thread_id: The ID of the thread to attach the file to
        file_id: The ID of the file to attach
        topic: The document topic, used to determine which assistant to use
    """
    try:
        # Get the appropriate assistant ID for the topic
        assistant_id = settings.TOPIC_ASSISTANTS.get(topic)
        
        if not assistant_id:
            default_assistant = settings.ASSISTANT_ID
            logger.warning(f"No assistant ID found for topic '{topic}'. Using default: {default_assistant}")
            assistant_id = default_assistant
            
        logger.debug(f"Using assistant ID {assistant_id} for topic {topic}")
        
        # Create OpenAI client instance
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # First, update the Assistant to ensure it has file_search capability
        client.beta.assistants.update(
            assistant_id=assistant_id,
            tools=[{"type": "file_search"}]
        )
        
        # Now attach the file to a message in the thread
        response = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content="I've uploaded a document for reference. Please analyze its contents when I ask questions about it.",
            attachments=[
                {"file_id": file_id, "tools": [{"type": "file_search"}]}
            ]
        )
        
        logger.info(f"Successfully attached file {file_id} to thread {thread_id} with assistant {assistant_id}")
        
        return response
    except Exception as e:
        logger.error(f"Error attaching file to thread: {str(e)}")
        raise FileUploadError(f"Failed to attach file to thread: {str(e)}")

async def get_thread_files(thread_id: str) -> List[Dict[str, Any]]:
    """
    Get all files attached to a thread.
    """
    try:
        # Create OpenAI client instance
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        files = []
        
        for message in messages:
            if hasattr(message, 'file_ids') and message.file_ids:
                for file_id in message.file_ids:
                    file_info = client.files.retrieve(file_id)
                    files.append(file_info)
        
        return files
    except Exception as e:
        logger.error(f"Error retrieving thread files: {str(e)}")
        raise FileUploadError(f"Failed to retrieve thread files: {str(e)}")

async def delete_openai_file(file_id: str) -> bool:
    """
    Delete a file from OpenAI.
    Returns True if successful, False otherwise.
    """
    try:
        # Create OpenAI client instance
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = client.files.delete(file_id)
        return True
    except Exception as e:
        logger.error(f"Error deleting OpenAI file: {str(e)}")
        return False

async def process_file_upload(
    file_content: bytes,
    filename: str,
    document: Document,
    user: User,
    section: Optional[str] = None,
    subsection: Optional[str] = None
) -> FileUpload:
    """
    Process a file upload from end to end.
    1. Validate the file
    2. Save to temporary storage
    3. Upload to OpenAI
    4. Create database record
    5. Attach to thread if available (or store for later attachment)
    6. Clean up temporary file
    
    Returns the created FileUpload record.
    """
    # Check if thread exists - files can only be uploaded after thread initialization
    if not document.thread_id:
        raise FileUploadError(
            "Files can only be uploaded after starting a conversation. "
            "Please start a conversation first to initialize the thread."
        )
    
    # Validate file type
    if not is_file_type_supported(filename):
        raise FileUploadError(f"Unsupported file type: {filename}")
    
    # Validate file size
    file_size = len(file_content)
    if not validate_file_size(file_size):
        raise FileUploadError(f"File too large: {file_size} bytes")
    
    # Create FileUpload record in PENDING state
    file_ext = os.path.splitext(filename)[1].lower()
    mime_type, _ = mimetypes.guess_type(filename)
    
    file_upload = await FileUpload.create(
        id=uuid.uuid4(),
        document=document,
        user=user,
        original_filename=filename,
        openai_file_id="",  # Will be updated after OpenAI upload
        file_size=file_size,
        file_type=mime_type or file_ext,
        status=FileUploadStatus.PENDING,
        section=section,
        subsection=subsection
    )
    
    temp_path = None
    try:
        # Save to temporary storage
        temp_path = await save_temp_file(file_content, filename)
        
        # Update status to PROCESSING
        file_upload.status = FileUploadStatus.PROCESSING
        await file_upload.save()
        
        # Upload to OpenAI
        openai_file = await upload_file_to_openai(temp_path)
        
        # Update record with OpenAI file ID
        file_upload.openai_file_id = openai_file.id
        await file_upload.save()
        
        # Attach to thread
        logger.info(f"Attaching file {openai_file.id} to thread {document.thread_id}")
        await attach_file_to_thread(document.thread_id, openai_file.id, document.topic)
            
        # Update status to READY
        file_upload.status = FileUploadStatus.READY
        await file_upload.save()
        
        logger.info(f"File {filename} uploaded successfully: {openai_file.id}")
        
    except Exception as e:
        # Update status to ERROR and log the error
        file_upload.status = FileUploadStatus.ERROR
        file_upload.error_message = str(e)
        await file_upload.save()
        logger.error(f"File upload error: {str(e)}")
        raise FileUploadError(f"File upload failed: {str(e)}")
    
    finally:
        # Clean up temporary file
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
    
    return file_upload

async def attach_pending_files_to_thread(document: Document) -> List[str]:
    """
    This function is kept for compatibility but no longer needed since files
    can only be uploaded after thread creation.
    
    Returns an empty list as no pending files should exist.
    """
    logger.info(f"attach_pending_files_to_thread called for document {document.id}, but no action needed as files are only uploaded after thread creation")
    return [] 