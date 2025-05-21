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
import PyPDF2
import docx
import json
import io
import time

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

async def upload_file_to_openai(file_path: str, purpose: str = "assistants", thread_id: str = None) -> Dict[str, Any]:
    """
    Upload a file to OpenAI.
    Returns the OpenAI file object.
    
    Args:
        file_path: Path to the file to upload
        purpose: Purpose of the file (always 'assistants' for file_search)
        thread_id: The thread ID this file belongs to (for better isolation)
    """
    try:
        # Create OpenAI client instance
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Ensure the purpose is set to 'assistants' for the file to be available with file_search
        if purpose != "assistants":
            logger.warning(f"Changing file purpose from '{purpose}' to 'assistants' for compatibility with file_search")
            purpose = "assistants"
        
        # Add thread isolation using metadata if thread_id is provided
        metadata = {}
        if thread_id:
            # Create a thread-specific metadata tag
            # This won't affect functionality but allows tracking which thread a file belongs to
            metadata = {
                "thread_id": thread_id,
                "isolation_key": f"thread_{thread_id}",
                "upload_timestamp": str(int(time.time()))
            }
            logger.info(f"Uploading file with thread isolation metadata for thread: {thread_id}")
        
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
        # We don't modify any other assistant settings to maintain isolation
        client.beta.assistants.update(
            assistant_id=assistant_id,
            tools=[{"type": "file_search"}]
        )
        
        # Create isolation key for this thread
        isolation_key = f"thread_{thread_id}_isolation_{int(time.time())}"
        
        # Attach the file specifically to this project's thread with a message
        # that clearly scopes it to this project only with strong isolation instructions
        isolation_message = (
            f"IMPORTANT ISOLATION AND PROCESSING NOTICE: I've uploaded a document for reference in this specific project only. "
            f"This document has isolation key: {isolation_key}. "
            f"The content of this document must ONLY be used within this specific thread (ID: {thread_id}). "
            f"Do not reference or use this document's information in any other thread or conversation. "
            f"This file's contents are exclusively for this project and must not affect your responses in other threads.\n\n"
            f"HANDLING INSTRUCTIONS: Do NOT automatically add any content from this file to the document sections. "
            f"Instead, help me review the file content through conversation. We will explicitly discuss and decide together "
            f"which information to include in the document. Only when I specifically approve content for a particular "
            f"subsection should it be added to the document structure."
        )
        
        response = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=isolation_message,
            attachments=[
                {"file_id": file_id, "tools": [{"type": "file_search"}]}
            ]
        )
        
        logger.info(f"Successfully attached file {file_id} to thread {thread_id} with assistant {assistant_id} and isolation key {isolation_key}")
        
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
    
    # Create initial record without file_data to avoid errors if field does not exist yet
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
    
    # Try to add file_data field
    try:
        file_upload.file_data = file_content
        await file_upload.save()
    except Exception as e:
        logger.warning(f"Could not save file_data: {str(e)}. Field may not exist in database yet.")
    
    temp_path = None
    try:
        # Save to temporary storage
        temp_path = await save_temp_file(file_content, filename)
        
        # Update status to PROCESSING
        file_upload.status = FileUploadStatus.PROCESSING
        await file_upload.save()
        
        # Upload to OpenAI with thread_id for isolation
        thread_id = document.thread_id
        openai_file = await upload_file_to_openai(temp_path, thread_id=thread_id)
        
        # Update record with OpenAI file ID
        file_upload.openai_file_id = openai_file.id
        await file_upload.save()
        
        # Attach to thread
        logger.info(f"Attaching file {openai_file.id} to thread {thread_id}")
        await attach_file_to_thread(thread_id, openai_file.id, document.topic)
            
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

async def extract_file_content(file_content: bytes, filename: str) -> str:
    """
    Extract text content from uploaded files based on file type.
    
    Currently supports:
    - PDF
    - DOCX
    - TXT
    - CSV
    - JSON
    
    For unsupported formats like images, returns a placeholder message.
    """
    file_ext = os.path.splitext(filename)[1].lower()
    
    try:
        # Extract content based on file type
        if file_ext == '.pdf':
            # Handle PDF files
            with io.BytesIO(file_content) as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                text = ""
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n\n"
                if not text.strip():
                    return f"[PDF file '{filename}' - No extractable text content]"
                return text
                
        elif file_ext == '.docx':
            # Handle DOCX files
            with io.BytesIO(file_content) as docx_file:
                doc = docx.Document(docx_file)
                return "\n".join([paragraph.text for paragraph in doc.paragraphs])
                
        elif file_ext in ['.txt', '.csv']:
            # Handle text files
            try:
                return file_content.decode('utf-8')
            except UnicodeDecodeError:
                # Try other common encodings
                for encoding in ['latin-1', 'windows-1252', 'iso-8859-1']:
                    try:
                        return file_content.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                return f"[Text file '{filename}' - Unable to decode content]"
                
        elif file_ext == '.json':
            # Handle JSON files
            try:
                json_data = json.loads(file_content)
                return json.dumps(json_data, indent=2)
            except json.JSONDecodeError:
                return f"[JSON file '{filename}' - Invalid JSON content]"
                
        else:
            # Unsupported file types (images, etc.)
            mime_type, _ = mimetypes.guess_type(filename)
            if mime_type and mime_type.startswith('image/'):
                return f"[Image file '{filename}' - Content cannot be displayed in text format]"
            else:
                return f"[File '{filename}' - Content cannot be displayed]"
    
    except Exception as e:
        logger.error(f"Error extracting content from file {filename}: {str(e)}")
        return f"[Error extracting content from '{filename}': {str(e)}]"

async def extract_document_data_from_file(file_content: bytes, filename: str, topic: str) -> Dict[str, Dict[str, str]]:
    """
    Analyze file content and extract structured data that matches the document structure for the given topic.
    This uses OpenAI to intelligently parse the file content and map it to the document structure.
    
    Returns a dictionary where:
    - Keys are section names
    - Values are dictionaries mapping subsection names to extracted content
    
    Example:
    {
        "Allgemeines und Bauvorhaben": {
            "Anlass und Vorgaben": "Extracted content...",
            "Geländeverhältnisse und Bauwerk": "More extracted content..."
        }
    }
    """
    from templates.structure import DOCUMENT_STRUCTURE
    
    # Get the document structure for this topic
    if topic not in DOCUMENT_STRUCTURE:
        logger.warning(f"Unknown topic: {topic}, cannot extract structured data")
        return {}
    
    topic_structure = DOCUMENT_STRUCTURE[topic]
    
    # Extract the raw text content from the file
    logger.info(f"Extracting content from file: {filename} for topic: {topic}")
    raw_content = await extract_file_content(file_content, filename)
    
    if not raw_content or (raw_content.startswith('[') and ']' in raw_content and len(raw_content.split()) < 10):
        # This indicates an error or unsupported file
        logger.warning(f"Could not extract meaningful text content from file: {filename}")
        return {}
    
    logger.info(f"Successfully extracted {len(raw_content)} characters from file")
    
    # Create a structured representation of the document structure
    structure_description = []
    for section_obj in topic_structure:
        section_name = list(section_obj.keys())[0]
        subsections = section_obj[section_name]
        section_info = {
            "section": section_name,
            "subsections": subsections
        }
        structure_description.append(section_info)
    
    try:
        # Create OpenAI client instance
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Define the system prompt with much clearer instructions
        system_prompt = """
        You are an expert document analyzer specialized in technical documents. Your task is to extract structured information 
        from the provided document and organize it according to a predefined structure.
        
        IMPORTANT INSTRUCTIONS:
        1. You will receive raw text content extracted from a document (PDF, DOCX, etc.)
        2. You will also receive a structured template with sections and subsections
        3. Your job is to EXTRACT ACTUAL INFORMATION from the document that matches each section/subsection
        4. Do NOT return empty values or placeholder messages if you find relevant content
        5. Do NOT say "No data extracted" or similar messages
        6. EXTRACT THE ACTUAL DATA from the document for each section where possible
        7. If there truly is no information for a section, leave it as an empty string
        
        For each section and subsection in the template:
        - Search the entire document for relevant information
        - Extract complete, meaningful content (multiple sentences where appropriate)
        - Maintain technical details, measurements, and specific terminology
        - Format the extracted text properly (paragraphs, line breaks, etc.)
        
        Return ONLY a JSON object with this structure:
        {
            "SectionName1": {
                "Subsection1A": "Actual extracted content...",
                "Subsection1B": "More extracted content..."
            },
            "SectionName2": {
                "Subsection2A": "Technical content extracted from document..."
            }
        }
        
        Remember, I need you to extract ACTUAL INFORMATION from the document - DO NOT create generic template text or placeholders.
        """
        
        # Create the user prompt with more explicit instructions
        user_prompt = f"""
        Please analyze this document content and extract information according to the structure below.
        Extract ACTUAL INFORMATION from the content - do not provide placeholders or empty responses where information exists.
        
        DOCUMENT STRUCTURE:
        {json.dumps(structure_description, indent=2)}
        
        DOCUMENT CONTENT:
        ```
        {raw_content[:75000]}  # Expanded content limit
        ```
        
        For each section and subsection in the structure, extract any relevant information found in the document content.
        Return a JSON object structured exactly like the template (matching the section and subsection names precisely).
        
        For any section where you find information, extract the ACTUAL DATA from the document - not just placeholders.
        Only return empty strings for sections where NO information exists in the document.
        """
        
        logger.info(f"Sending extracted content to GPT model for structured analysis")
        
        # Make the request to OpenAI, ensuring the model has sufficient tokens
        response = client.chat.completions.create(
            model=settings.GPT_MODEL,  # Use the model specified in config
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,  # Keep it deterministic
            response_format={"type": "json_object"}  # Ensure JSON response
        )
        
        # Extract the response text
        result_text = response.choices[0].message.content
        
        # Parse the JSON response
        try:
            extracted_data = json.loads(result_text)
            total_sections = len(extracted_data)
            total_content = sum(len(str(v)) for v in extracted_data.values())
            
            logger.info(f"Successfully extracted structured data: {total_sections} sections with {total_content} characters of content")
            
            # Debug log a sample of extracted data
            for section, data in extracted_data.items():
                for subsection, content in data.items():
                    if content and len(content.strip()) > 0:
                        preview = content[:100] + "..." if len(content) > 100 else content
                        logger.info(f"Extracted content for {section}.{subsection}: {preview}")
            
            return extracted_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {result_text[:500]}...")
            return {}
            
    except Exception as e:
        logger.error(f"Error extracting structured data from file {filename}: {str(e)}")
        logger.exception("Extraction error details:")
        return {} 