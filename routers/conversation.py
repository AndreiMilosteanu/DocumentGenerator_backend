from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Tuple, List, Optional
import json, logging
import openai
from tortoise.exceptions import DoesNotExist
from tortoise import Tortoise
from config import settings
from templates.structure import DOCUMENT_STRUCTURE, COVER_PAGE_STRUCTURE
from models import Document, SectionData, ChatMessage, ActiveSubsection, ApprovedSubsection, User, Project, CoverPageData
from utils.auth import get_current_active_user, get_admin_user
from utils.file_upload import attach_pending_files_to_thread
from utils.rate_limiter import RateLimiter
from services.openai_client_optimized import get_optimized_client
import re

router = APIRouter()
logger = logging.getLogger("conversation")
logger.setLevel(logging.INFO)

class StartRequest(BaseModel):
    topic: str
    section: Optional[str] = None
    subsection: Optional[str] = None

class SubsectionSelectRequest(BaseModel):
    section: str
    subsection: str

class ReplyRequest(BaseModel):
    message: str

class ConversationResponse(BaseModel):
    data: Dict[str, Any]
    message: str
    section: Optional[str] = None
    subsection: Optional[str] = None

class SubsectionInfo(BaseModel):
    section: str
    subsection: str
    has_conversation: bool

class SubsectionApproval(BaseModel):
    value: str

class SimpleApproval(BaseModel):
    pass  # No fields needed, just use section/subsection from URL

class SectionDataUpdate(BaseModel):
    value: str

class UpdateAndApproveData(BaseModel):
    value: str
    notify_assistant: bool = True

class SubsectionDataStatus(BaseModel):
    section: str
    subsection: str
    has_data: bool
    is_approved: bool
    approved_version: Optional[str] = None

async def _run_thread_and_parse(thread_id: str, topic: str, user: User = None) -> Tuple[Dict[str, Any], str]:
    """
    Executes the assistant run on an existing thread, returns parsed JSON data and human reply.
    """
    # Rate limiting disabled - previously checked rate limit here
    
    # Get the appropriate assistant ID for the topic
    assistant_id = settings.TOPIC_ASSISTANTS.get(topic)
    
    if not assistant_id:
        logger.error(f"No assistant ID available for topic '{topic}'. Please configure at least one assistant.")
        raise ValueError(f"No assistant ID available. Configure ASSISTANT_ID or {topic.upper()}_ASSISTANT_ID in .env file")
    
    # Use the optimized client
    client = get_optimized_client()
    
    # Kick off the assistant run with optimizations
    logger.debug(f"Starting optimized assistant run for thread_id: {thread_id} with assistant_id: {assistant_id}")
    try:
        # Use the optimized run method
        data, human_message = await client.run_assistant_optimized(thread_id, assistant_id)
        
        logger.debug(f"Optimized run completed successfully")
        logger.info(f"Extracted data with {len(data)} keys and human message of length {len(human_message)}")
        
        return data, human_message
        
    except Exception as e:
        logger.error(f"Error during optimized assistant run: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Assistant error: {str(e)}")

async def _analyze_message_format(thread_id: str, message_id: str = None):
    """
    Debug helper to analyze the format of a specific message or the latest message.
    """
    # Get the latest message if no message_id is provided
    if not message_id:
        msgs = openai.beta.threads.messages.list(thread_id=thread_id, limit=1)
        msgs_list = list(msgs)
        if not msgs_list:
            return {"error": "No messages found in thread"}
        message = msgs_list[0]
    else:
        try:
            message = openai.beta.threads.messages.retrieve(
                thread_id=thread_id,
                message_id=message_id
            )
        except Exception as e:
            return {"error": f"Failed to retrieve message: {str(e)}"}
    
    # Extract the content
    raw = ""
    content = message.content
    content_type = type(content).__name__
    
    if isinstance(content, list):
        raw = "".join(block.text.value for block in content if hasattr(block, 'text'))
    else:
        raw = content
    
    # Analyze the format
    parts = raw.split('\n\n', 1)
    json_part = parts[0] if parts else ""
    human_part = parts[1] if len(parts) > 1 else ""
    
    # Check if JSON is in markdown code block
    has_markdown = False
    markdown_extracted_json = ""
    
    if json_part.startswith("```json") or json_part.startswith("```"):
        has_markdown = True
        # Extract content between ``` markers
        lines = json_part.split("\n")
        # Remove the first line with ```json
        lines = lines[1:]
        # Find the closing ``` if it exists
        if "```" in lines:
            closing_index = lines.index("```")
            lines = lines[:closing_index]
        # Join the remaining lines to get the JSON
        markdown_extracted_json = "\n".join(lines)
    
    # Try to parse the JSON part (both original and markdown extracted if applicable)
    json_valid = False
    parsed_json = None
    parse_error = None
    
    # First try the markdown extracted version if it exists
    if has_markdown and markdown_extracted_json:
        try:
            parsed_json = json.loads(markdown_extracted_json)
            json_valid = True
        except json.JSONDecodeError as e:
            parse_error = f"Failed to parse markdown JSON: {str(e)}"
    
    # If that didn't work or there was no markdown, try the original
    if not json_valid:
        try:
            parsed_json = json.loads(json_part)
            json_valid = True
        except json.JSONDecodeError as e:
            if not parse_error:
                parse_error = f"Failed to parse JSON: {str(e)}"
    
    analysis = {
        "message_id": message.id,
        "role": message.role,
        "content_type": content_type,
        "raw_content_length": len(raw),
        "raw_content_preview": raw[:200] + ("..." if len(raw) > 200 else ""),
        "parts_count": len(parts),
        "json_part_length": len(json_part),
        "json_part_preview": json_part[:200] + ("..." if len(json_part) > 200 else ""),
        "has_markdown_code_block": has_markdown,
        "json_valid": json_valid,
        "json_error": parse_error,
        "parsed_json": parsed_json if json_valid else None,
        "human_part_length": len(human_part),
        "human_part_preview": human_part[:200] + ("..." if len(human_part) > 200 else ""),
    }
    
    if has_markdown:
        analysis["markdown_extracted_json"] = markdown_extracted_json[:200] + ("..." if len(markdown_extracted_json) > 200 else "")
    
    return analysis

async def _send_format_correction(thread_id: str, doc_topic: str) -> None:
    """
    Sends a format correction instruction to the thread if the assistant isn't following the format.
    """
    # Get the appropriate assistant ID for the topic
    assistant_id = settings.TOPIC_ASSISTANTS.get(doc_topic)
    
    if not assistant_id:
        logger.error(f"No assistant ID available for topic '{doc_topic}'. Please configure at least one assistant.")
        raise ValueError(f"No assistant ID available. Configure ASSISTANT_ID or {doc_topic.upper()}_ASSISTANT_ID in .env file")
    
    # Use the optimized client
    client = get_optimized_client()
    
    correction_message = (
        "CRITICAL FORMAT CORRECTION: Your last response did not follow the required format. "
        "You MUST structure ALL responses in exactly two parts:\n\n"
        "1) First part: A valid JSON object starting with '{' containing all the information gathered so far\n"
        "2) Second part: Your human-readable message after TWO newlines\n\n"
        f"Example format:\n"
        f"{{\"Section Name\": {{\"Subsection1\": \"Value1\", \"Subsection2\": \"Value2\"}}}}\n\n"
        f"Your normal human response here...\n\n"
        f"Please continue helping with the {doc_topic} document, but ALWAYS follow this exact format."
    )
    
    logger.warning(f"Sending format correction to thread {thread_id}")
    
    # Send correction message using optimized client
    await client.send_message_optimized(thread_id, correction_message)
    
    # Run assistant to get corrected response using optimized method
    try:
        data, message = await client.run_assistant_optimized(thread_id, assistant_id)
        logger.debug(f"Correction run completed successfully")
    except Exception as e:
        logger.error(f"Error in format correction run: {e}")
        raise
    
    return

async def _get_active_subsection(document_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get the currently active subsection for a document
    Returns a tuple of (section, subsection)
    """
    doc = await Document.get(id=document_id)
    active = await ActiveSubsection.filter(document=doc).order_by("-last_accessed").first()
    
    if active:
        return active.section, active.subsection
    return None, None

async def _set_active_subsection(document_id: str, section: str, subsection: str) -> None:
    """
    Set or update the active subsection for a document
    """
    doc = await Document.get(id=document_id)
    
    # Check if this subsection already exists
    existing = await ActiveSubsection.filter(
        document=doc,
        section=section,
        subsection=subsection
    ).first()
    
    if existing:
        # Update the last_accessed timestamp
        existing.last_accessed = None  # This will trigger the auto_now update
        await existing.save()
    else:
        # Create a new active subsection
        await ActiveSubsection.create(
            document=doc,
            section=section,
            subsection=subsection
        )

async def _get_section_data_for_subsection(doc: Document, section: str, subsection: str) -> Dict:
    """
    Get the section data relevant to a specific subsection
    """
    section_data = await SectionData.filter(document=doc, section=section).first()
    
    if section_data:
        data = section_data.data
        if subsection in data:
            return {section: {subsection: data[subsection]}}
    
    # Return empty data structure if subsection not found
    return {section: {subsection: ""}}

async def _check_document_access(document_id: str, user: User) -> Document:
    """
    Check if user has access to the document via a project.
    Admin users have access to all documents.
    Returns the document if access is allowed, otherwise raises HTTPException.
    """
    try:
        doc = await Document.get(id=document_id)
        
        # Admin users have access to all documents
        if user.role == "admin":
            return doc
            
        # For regular users, check if they have a project with this document
        project = await Project.filter(document_id=document_id, user=user).first()
        if not project:
            raise HTTPException(status_code=403, detail="Access denied to this document")
            
        return doc
    except DoesNotExist:
        raise HTTPException(status_code=404, detail="Document not found")

@router.post("/{document_id}/select-subsection")
async def select_subsection(
    document_id: str, 
    request: SubsectionSelectRequest, 
    current_user: User = Depends(get_current_active_user)
):
    """
    Select a specific subsection for the conversation
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Validate section and subsection
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=404, detail=f"Unknown topic '{topic}'")
    
    section_valid = False
    subsection_valid = False
    
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        sec_name = list(sec_obj.keys())[0]
        if sec_name == request.section:
            section_valid = True
            if request.subsection in sec_obj[sec_name]:
                subsection_valid = True
                break
    
    if not section_valid:
        raise HTTPException(status_code=400, detail=f"Invalid section '{request.section}' for topic '{topic}'")
    
    if not subsection_valid:
        raise HTTPException(status_code=400, detail=f"Invalid subsection '{request.subsection}' for section '{request.section}'")
    
    # Set as active subsection
    await _set_active_subsection(document_id, request.section, request.subsection)
    
    # Check if there are previous messages for this subsection
    has_messages = await ChatMessage.filter(
        document=doc,
        section=request.section,
        subsection=request.subsection
    ).exists()
    
    # If no thread exists yet, we'll need to create one when starting the conversation
    thread_exists = doc.thread_id is not None
    
    return {
        "section": request.section,
        "subsection": request.subsection,
        "has_messages": has_messages,
        "thread_exists": thread_exists
    }

@router.get("/{document_id}/subsections", response_model=List[SubsectionInfo])
async def list_subsections(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    List all subsections for a document and their conversation status
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    try:
        doc = await Document.get(id=document_id)
    except Document.DoesNotExist:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get document topic
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=404, detail=f"Unknown topic '{topic}'")
    
    # Get all messages for this document grouped by section/subsection
    messages = await ChatMessage.filter(document=doc).all()
    subsection_msgs = {}
    
    for msg in messages:
        if msg.section and msg.subsection:
            key = f"{msg.section}:{msg.subsection}"
            subsection_msgs[key] = True
    
    # Build list of all subsections
    result = []
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        section = list(sec_obj.keys())[0]
        for subsection in sec_obj[section]:
            key = f"{section}:{subsection}"
            result.append(SubsectionInfo(
                section=section,
                subsection=subsection,
                has_conversation=key in subsection_msgs
            ))
    
    return result

@router.post("/{document_id}/start", response_model=ConversationResponse)
async def start_conversation(
    document_id: str, 
    body: StartRequest,
    current_user: User = Depends(get_current_active_user)
):
    # Rate limiting disabled
    # allowed, error_msg = await RateLimiter.check_rate_limit(current_user)
    # if not allowed:
    #     raise HTTPException(status_code=429, detail=error_msg)
    
    logger.debug(f"Starting conversation for document {document_id} with topic {body.topic}")
    
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Validate topic
    topic = body.topic
    if topic not in DOCUMENT_STRUCTURE:
        logger.error(f"Unknown topic: {topic}")
        raise HTTPException(status_code=404, detail=f"Unknown topic '{topic}'")
    
    # Create or get document record
    doc, created = await Document.get_or_create(id=document_id, defaults={"topic": topic})
    logger.debug(f"Document {'created' if created else 'retrieved'} with ID {doc.id}")
    
    # Handle section and subsection
    section = body.section
    subsection = body.subsection
    
    # If section/subsection not provided, get the first one from the structure
    if not section or not subsection:
        first_section_obj = DOCUMENT_STRUCTURE[topic][0]
        section = list(first_section_obj.keys())[0]
        subsection = first_section_obj[section][0]
        logger.debug(f"Using default section '{section}' and subsection '{subsection}'")
    
    # Set as active subsection
    await _set_active_subsection(document_id, section, subsection)
    
    # Force create a new thread for each document to ensure no context sharing
    # This ensures each project has its own isolated conversation
    create_new_thread = True
    
    # Check if a conversation already exists for this subsection in this document
    existing_messages = await ChatMessage.filter(
        document=doc,
        section=section,
        subsection=subsection
    ).exists()
    
    if existing_messages and doc.thread_id:
        logger.info(f"Conversation already exists for {section}/{subsection}. Returning existing data.")
        # Get the most recent assistant message
        last_message = await ChatMessage.filter(
            document=doc,
            section=section,
            subsection=subsection,
            role="assistant"
        ).order_by("-timestamp").first()
        
        # Get the section data
        section_data = await _get_section_data_for_subsection(doc, section, subsection)
        
        create_new_thread = False
        
        return {
            "data": section_data,
            "message": last_message.content if last_message else "",
            "section": section,
            "subsection": subsection
        }
    
    # Create a new OpenAI thread to ensure isolation between projects
    if create_new_thread or not doc.thread_id:
        # If there was a previous thread, we're intentionally ignoring it to maintain isolation
        if doc.thread_id:
            logger.info(f"Replacing existing thread {doc.thread_id} with a new one for isolation")
        
        # Use optimized client for thread creation
        client = get_optimized_client()
        thread_id = await client.create_thread_optimized()
        doc.thread_id = thread_id
        await doc.save()
        logger.debug(f"Created new optimized thread with ID {thread_id}")
        thread_created = True
    else:
        thread_created = False
        
    thread_id = doc.thread_id
    logger.debug(f"Using thread ID {thread_id}")
    
    # If we just created the thread, attach any pending files
    if thread_created:
        logger.info(f"Attaching any pending files to new thread {thread_id}")
        attached_files = await attach_pending_files_to_thread(doc)
        if attached_files:
            logger.info(f"Attached {len(attached_files)} files to thread {thread_id}")
    
    # Get the appropriate assistant ID for the topic
    assistant_id = settings.TOPIC_ASSISTANTS.get(topic)
    logger.debug(f"Using assistant ID {assistant_id} for topic {topic}")
    
    # Persist system instructions into thread and DB with subsection context
    prompt_lines = [
        f"You are an expert assistant for topic '{topic}'. You need to get relevant data from the user to complete the PDF document for this topic. ",
        "Following sections are needed:"
    ]
    for sec in DOCUMENT_STRUCTURE[topic]:
        title = list(sec.keys())[0]
        subs = sec[title]
        prompt_lines.append(f"- {title}: {', '.join(subs)}")
    
    # Add cover page structure information
    if topic in COVER_PAGE_STRUCTURE:
        prompt_lines.append(f"\nIMPORTANT: This document also has a COVER PAGE (Deckblatt) with the following structure:")
        cover_structure = COVER_PAGE_STRUCTURE[topic]
        for category, fields in cover_structure.items():
            field_names = list(fields.keys())
            prompt_lines.append(f"- {category}: {', '.join(field_names)}")
        
        prompt_lines.append(f"\nCOVER PAGE CAPABILITIES:")
        prompt_lines.append(f"- When files are uploaded, the system automatically extracts cover page data")
        prompt_lines.append(f"- You can reference extracted cover page information in conversations")
        prompt_lines.append(f"- Users can view and edit cover page data through the system")
        prompt_lines.append(f"- Cover page data includes project details, addresses, client information, etc.")
        prompt_lines.append(f"- This cover page data is separate from the main document sections")
    
    # Add context for the specific subsection
    prompt_lines.append(
        f"\nWe are currently working on the subsection '{subsection}' in section '{section}'."
    )
    prompt_lines.append(
        f"Please focus on gathering information ONLY for this specific subsection until instructed otherwise."
    )
    
    # Add isolation instructions to ensure thread-specific context
    prompt_lines.append(
        f"\nIMPORTANT ISOLATION INSTRUCTIONS: This is thread ID {thread_id}. Your responses must be based ONLY on information shared within this specific thread."
    )
    prompt_lines.append(
        f"Do not use or reference any information, files, or data from other threads or conversations."
    )
    prompt_lines.append(
        f"Any files that will be uploaded are specific to this thread only and must not influence your responses in other threads."
    )
    
    prompt_lines.append(
        "IMPORTANT FORMAT INSTRUCTION: For each reply from your side, you MUST output TWO parts in the following format:"
    )
    prompt_lines.append(
        "1) A raw JSON object (starting with '{') containing all extracted information so far,"
    )
    prompt_lines.append(
        "2) Your human-readable response, separated from the JSON by exactly two newlines."
    )
    prompt_lines.append(
        f"Example format:\n{{\"{section}\": {{\"{subsection}\": \"Content gathered for this subsection\"}}}}\n\nYour human response text here..."
    )
    prompt_lines.append(
        "The user will only see the human-readable part, but the JSON is critical for system functioning."
    )
    prompt_lines.append(
        "IMPORTANT: Do NOT use markdown code blocks (```) for the JSON part. Provide the raw JSON starting with '{' character."
    )
    prompt_lines.append(
        "FAILURE TO FOLLOW THIS FORMAT will result in data loss. Always begin your response with a valid JSON object."
    )
    system_prompt = " ".join(prompt_lines)
    
    # send system prompt
    client = get_optimized_client()
    await client.send_message_optimized(thread_id, system_prompt)
    
    # save to DB with section context
    await ChatMessage.create(
        document=doc, 
        role="user", 
        content=system_prompt,
        section=section,
        subsection=subsection
    )
    
    # run assistant and parse
    logger.debug("Running assistant and parsing response...")
    data, question = await _run_thread_and_parse(thread_id, topic, current_user)
    
    # Check if we got valid data - if not, try to send a format correction
    if not data and question:
        logger.warning("No valid JSON data found in assistant's response. Sending format correction.")
        await _send_format_correction(thread_id, doc.topic)
        # Try again after correction
        data, question = await _run_thread_and_parse(thread_id, topic, current_user)
    
    logger.debug(f"Received data with {len(data)} keys and message of length {len(question)}")
    
    # persist section data and assistant message
    await _update_section_data(doc, data)
    
    await ChatMessage.create(
        document=doc, 
        role="assistant", 
        content=question,
        section=section,
        subsection=subsection
    )
    
    return {
        "data": data, 
        "message": question,
        "section": section,
        "subsection": subsection
    }

@router.post("/{document_id}/subsection/start", response_model=ConversationResponse)
async def start_subsection_conversation(
    document_id: str, 
    request: SubsectionSelectRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Start a conversation specifically for a subsection (or switch to a new one)
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    try:
        doc = await Document.get(id=document_id)
    except Document.DoesNotExist:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Validate section and subsection
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=404, detail=f"Unknown topic '{topic}'")
    
    section_valid = False
    subsection_valid = False
    
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        sec_name = list(sec_obj.keys())[0]
        if sec_name == request.section:
            section_valid = True
            if request.subsection in sec_obj[sec_name]:
                subsection_valid = True
                break
    
    if not section_valid:
        raise HTTPException(status_code=400, detail=f"Invalid section '{request.section}' for topic '{topic}'")
    
    if not subsection_valid:
        raise HTTPException(status_code=400, detail=f"Invalid subsection '{request.subsection}' for section '{request.section}'")
    
    # Set as active subsection
    await _set_active_subsection(document_id, request.section, request.subsection)
    
    # We'll use the existing thread if it exists for this document
    # Note: Context isolation is ensured at project creation time in start_conversation
    if not doc.thread_id:
        client = get_optimized_client()
        thread_id = await client.create_thread_optimized()
        doc.thread_id = thread_id
        await doc.save()
        logger.debug(f"Created new optimized thread with ID {thread_id}")
        thread_created = True
    else:
        thread_created = False
    
    thread_id = doc.thread_id
    
    # Get the appropriate assistant ID for the topic
    assistant_id = settings.TOPIC_ASSISTANTS.get(topic)
    
    # Check if we already have conversation for this subsection
    has_messages = await ChatMessage.filter(
        document=doc,
        section=request.section,
        subsection=request.subsection
    ).exists()
    
    if has_messages:
        logger.info(f"Conversation already exists for {request.section}/{request.subsection}. Returning existing data.")
        # Get the last message for this subsection
        last_msg = await ChatMessage.filter(
            document=doc,
            section=request.section,
            subsection=request.subsection,
            role="assistant"
        ).order_by("-timestamp").first()
        
        # Get section data for the subsection
        section_data = await _get_section_data_for_subsection(doc, request.section, request.subsection)
        
        message = ""
        if last_msg:
            message = last_msg.content
        
        return {
            "data": section_data,
            "message": message,
            "section": request.section,
            "subsection": request.subsection
        }
    
    # If this is the first time we're accessing this subsection, tell the assistant about the context switch
    if not has_messages:
        # Create subsection context message
        context_message = (
            f"We are now working on the subsection '{request.subsection}' in section '{request.section}'. "
            f"Please focus on gathering information ONLY for this specific subsection until instructed otherwise. "
            f"All previous information is still valid, but now we need to work on this particular subsection."
        )
        
        # Send to OpenAI thread
        client = get_optimized_client()
        await client.send_message_optimized(thread_id, context_message)
        
        # Save to DB
        await ChatMessage.create(
            document=doc,
            role="user",
            content=context_message,
            section=request.section,
            subsection=request.subsection
        )
        
        # Get response from assistant
        data, message = await _run_thread_and_parse(thread_id, topic, current_user)
        
        # Save assistant response
        await ChatMessage.create(
            document=doc,
            role="assistant",
            content=message,
            section=request.section,
            subsection=request.subsection
        )
        
        # Update section data if any was returned
        await _update_section_data(doc, data)
        
        return {
            "data": data,
            "message": message,
            "section": request.section,
            "subsection": request.subsection
        }

@router.post("/{document_id}/reply", response_model=ConversationResponse)
async def reply_conversation(
    document_id: str, 
    body: ReplyRequest,
    current_user: User = Depends(get_current_active_user)
):
    # Rate limiting disabled
    # allowed, error_msg = await RateLimiter.check_rate_limit(current_user)
    # if not allowed:
    #     raise HTTPException(status_code=429, detail=error_msg)
    
    logger.debug(f"Processing reply for document {document_id}")
    
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    thread_id = doc.thread_id
    if not thread_id:
        logger.error(f"Thread ID not found for document {document_id}")
        raise HTTPException(status_code=400, detail="Thread not initialized. Call start first.")
    
    # Get the active subsection for this document
    active_section, active_subsection = await _get_active_subsection(document_id)
    
    if not active_section or not active_subsection:
        logger.error(f"No active subsection for document {document_id}")
        raise HTTPException(status_code=400, detail="No active subsection selected. Please select a subsection first.")
    
    # Persist user message into thread and DB with section context
    logger.debug(f"Sending user message to OpenAI: {body.message[:50]}...")
    client = get_optimized_client()
    await client.send_message_optimized(thread_id, body.message)
    
    await ChatMessage.create(
        document=doc, 
        role="user", 
        content=body.message,
        section=active_section,
        subsection=active_subsection
    )
    
    # run assistant and parse
    logger.debug("Running assistant and parsing response...")
    data, question = await _run_thread_and_parse(thread_id, doc.topic, current_user)
    
    # Check if we got valid data - if not, try to send a format correction
    if not data and question:
        logger.warning("No valid JSON data found in assistant's response. Sending format correction.")
        await _send_format_correction(thread_id, doc.topic)
        # Try again after correction
        data, question = await _run_thread_and_parse(thread_id, doc.topic, current_user)
    
    logger.debug(f"Received data with {len(data)} keys and message of length {len(question)}")
    
    # persist section data and assistant message
    await _update_section_data(doc, data)
    
    # Save assistant message with section context
    await ChatMessage.create(
        document=doc, 
        role="assistant", 
        content=question,
        section=active_section,
        subsection=active_subsection
    )
    
    return {
        "data": data, 
        "message": question,
        "section": active_section,
        "subsection": active_subsection
    }

@router.get("/{document_id}/messages/{section}/{subsection}")
async def get_subsection_messages(
    document_id: str, 
    section: str, 
    subsection: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all messages for a specific subsection
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    messages = await ChatMessage.filter(
        document=doc,
        section=section,
        subsection=subsection
    ).order_by("timestamp").all()
    
    # Format messages for the response
    formatted_messages = []
    for msg in messages:
        # Skip system messages or prompts for the UI
        if msg.role == "user" and len(msg.content) > 500:  # Likely a system prompt
            continue
            
        formatted_messages.append({
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat()
        })
    
    return {
        "section": section,
        "subsection": subsection,
        "messages": formatted_messages
    }

@router.get("/{document_id}/debug")
async def debug_conversation(
    document_id: str,
    current_user: User = Depends(get_admin_user)  # Only admin can access debug endpoint
):
    """
    Debug endpoint to see all messages and data for a document.
    """
    # Check if user has access to this document (admin only for debug)
    doc = await _check_document_access(document_id, current_user)
    
    # Get all messages
    messages = await ChatMessage.filter(document=doc).order_by("timestamp").all()
    msg_data = [{"role": m.role, "content": m.content, "timestamp": m.timestamp} for m in messages]
    
    # Get all section data
    sections = await SectionData.filter(document=doc).all()
    section_data = {s.section: s.data for s in sections}
    
    # Get OpenAI thread ID
    thread_id = doc.thread_id
    
    # Get raw messages from OpenAI
    openai_messages = []
    if thread_id:
        try:
            raw_msgs = openai.beta.threads.messages.list(thread_id=thread_id)
            openai_messages = [
                {
                    "id": m.id,
                    "role": m.role, 
                    "created_at": m.created_at,
                    "content_type": type(m.content).__name__,
                    "content": str(m.content)[:500] + ("..." if len(str(m.content)) > 500 else "")
                } 
                for m in raw_msgs
            ]
        except Exception as e:
            logger.error(f"Error fetching OpenAI messages: {e}")
            openai_messages = [{"error": str(e)}]
    
    return {
        "document_id": document_id,
        "topic": doc.topic,
        "thread_id": thread_id,
        "messages": msg_data,
        "section_data": section_data,
        "openai_messages": openai_messages
    }

@router.get("/{document_id}/analyze_format")
async def analyze_message_format(
    document_id: str, 
    message_id: str = None,
    current_user: User = Depends(get_admin_user)  # Only admin can access this endpoint
):
    """
    Analyzes the format of a message to debug JSON parsing issues.
    """
    # Check if user has access to this document (admin only for debug)
    doc = await _check_document_access(document_id, current_user)
    
    if not doc.thread_id:
        raise HTTPException(status_code=400, detail="Thread not initialized")
    
    result = await _analyze_message_format(doc.thread_id, message_id)
    return result

@router.post("/{document_id}/extract-and-approve/{section}/{subsection}")
async def extract_and_approve_subsection(
    document_id: str, 
    section: str, 
    subsection: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Extract a subsection value from the conversation and approve it for the PDF.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Validate section and subsection against document structure
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
        
    section_valid = False
    subsection_valid = False
    
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        sec_name = list(sec_obj.keys())[0]
        if sec_name == section:
            section_valid = True
            if subsection in sec_obj[sec_name]:
                subsection_valid = True
                break
    
    if not section_valid:
        raise HTTPException(status_code=400, detail=f"Invalid section '{section}' for topic '{topic}'")
    
    if not subsection_valid:
        raise HTTPException(status_code=400, detail=f"Invalid subsection '{subsection}' for section '{section}'")
    
    # Get the section data
    section_data = await SectionData.filter(document=doc, section=section).first()
    
    if not section_data:
        raise HTTPException(status_code=404, detail=f"No data found for section '{section}'")
            
    data = section_data.data
    
    if subsection not in data:
        raise HTTPException(status_code=404, detail=f"No data found for subsection '{subsection}'")
            
    value = data[subsection]
    
    # Format the value for human readability
    if isinstance(value, dict):
        # Format dictionary into a readable string with each key-value pair on a new line
        formatted_value = ""
        for key, val in value.items():
            formatted_value += f"{key}: {val}\n"
        value = formatted_value.rstrip("\n")  # Remove trailing newline
        logger.info(f"Formatted dictionary value for {section}.{subsection}")
    elif isinstance(value, list):
        # Format list into a bulleted list
        formatted_value = ""
        for item in value:
            formatted_value += f"• {item}\n"
        value = formatted_value.rstrip("\n")  # Remove trailing newline
        logger.info(f"Formatted list value for {section}.{subsection}")
    elif value is None:
        value = ""
    else:
        value = str(value)
    
    # Use direct SQL to avoid datetime issues
    try:
        conn = Tortoise.get_connection("default")
        
        # Check if record exists
        query = """
            SELECT id FROM approved_subsections 
            WHERE document_id = $1 AND section = $2 AND subsection = $3;
        """
        result = await conn.execute_query(query, [str(doc.id), section, subsection])
        
        if result[1]:  # Record exists
            # Update existing record
            update_query = """
                UPDATE approved_subsections 
                SET approved_value = $4 
                WHERE document_id = $1 AND section = $2 AND subsection = $3;
            """
            await conn.execute_query(update_query, [str(doc.id), section, subsection, value])
            logger.debug(f"Updated approval for {section}.{subsection}")
        else:
            # Insert new record
            insert_query = """
                INSERT INTO approved_subsections(document_id, section, subsection, approved_value)
                VALUES($1, $2, $3, $4);
            """
            await conn.execute_query(insert_query, [str(doc.id), section, subsection, value])
            logger.debug(f"Created approval for {section}.{subsection}")
    except Exception as e:
        logger.exception(f"Database error during approval: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Return the result
    return {
        "document_id": document_id,
        "section": section,
        "subsection": subsection,
        "value": value,
        "approved": True
    }

@router.post("/{document_id}/approve/{section}/{subsection}")
async def approve_subsection_value(
    document_id: str, 
    section: str, 
    subsection: str, 
    approval: SubsectionApproval,
    current_user: User = Depends(get_current_active_user)
):
    """
    Approve a specific value for a subsection.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Validate section and subsection against document structure
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
        
    section_valid = False
    subsection_valid = False
    
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        sec_name = list(sec_obj.keys())[0]
        if sec_name == section:
            section_valid = True
            if subsection in sec_obj[sec_name]:
                subsection_valid = True
                break
    
    if not section_valid:
        raise HTTPException(status_code=400, detail=f"Invalid section '{section}' for topic '{topic}'")
    
    if not subsection_valid:
        raise HTTPException(status_code=400, detail=f"Invalid subsection '{subsection}' for section '{section}'")
    
    # Ensure value is a string
    value = approval.value
    if value is None:
        value = ""
    else:
        value = str(value)
    
    # Use direct SQL to avoid datetime issues
    try:
        conn = Tortoise.get_connection("default")
        
        # Check if record exists
        query = """
            SELECT id FROM approved_subsections 
            WHERE document_id = $1 AND section = $2 AND subsection = $3;
        """
        result = await conn.execute_query(query, [str(doc.id), section, subsection])
        
        if result[1]:  # Record exists
            # Update existing record
            update_query = """
                UPDATE approved_subsections 
                SET approved_value = $4 
                WHERE document_id = $1 AND section = $2 AND subsection = $3;
            """
            await conn.execute_query(update_query, [str(doc.id), section, subsection, value])
            logger.debug(f"Updated approval for {section}.{subsection}")
        else:
            # Insert new record
            insert_query = """
                INSERT INTO approved_subsections(document_id, section, subsection, approved_value)
                VALUES($1, $2, $3, $4);
            """
            await conn.execute_query(insert_query, [str(doc.id), section, subsection, value])
            logger.debug(f"Created approval for {section}.{subsection}")
    except Exception as e:
        logger.exception(f"Database error during approval: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Return the result
    return {
        "document_id": document_id,
        "section": section,
        "subsection": subsection,
        "value": value,
        "approved": True
    }

@router.post("/{document_id}/simple-approve/{section}/{subsection}")
async def simple_approve_subsection(
    document_id: str, 
    section: str, 
    subsection: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Simple endpoint to approve a subsection without requiring a value.
    The value is automatically loaded from the section_data.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Validate section and subsection against document structure
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
        
    section_valid = False
    subsection_valid = False
    
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        sec_name = list(sec_obj.keys())[0]
        if sec_name == section:
            section_valid = True
            if subsection in sec_obj[sec_name]:
                subsection_valid = True
                break
    
    if not section_valid:
        raise HTTPException(status_code=400, detail=f"Invalid section '{section}' for topic '{topic}'")
    
    if not subsection_valid:
        raise HTTPException(status_code=400, detail=f"Invalid subsection '{subsection}' for section '{section}'")
    
    # Get the section data
    section_data = await SectionData.filter(document=doc, section=section).first()
    
    if not section_data:
        raise HTTPException(status_code=404, detail=f"No data found for section '{section}'")
            
    data = section_data.data
    
    if subsection not in data:
        raise HTTPException(status_code=404, detail=f"No data found for subsection '{subsection}'")
            
    value = data[subsection]
    
    # Format the value for human readability
    if isinstance(value, dict):
        # Format dictionary into a readable string with each key-value pair on a new line
        formatted_value = ""
        for key, val in value.items():
            formatted_value += f"{key}: {val}\n"
        value = formatted_value.rstrip("\n")  # Remove trailing newline
        logger.info(f"Formatted dictionary value for {section}.{subsection}")
    elif isinstance(value, list):
        # Format list into a bulleted list
        formatted_value = ""
        for item in value:
            formatted_value += f"• {item}\n"
        value = formatted_value.rstrip("\n")  # Remove trailing newline
        logger.info(f"Formatted list value for {section}.{subsection}")
    elif value is None:
        value = ""
    else:
        value = str(value)
    
    # Use direct SQL to avoid datetime issues
    try:
        conn = Tortoise.get_connection("default")
        
        # Check if record exists
        query = """
            SELECT id FROM approved_subsections 
            WHERE document_id = $1 AND section = $2 AND subsection = $3;
        """
        result = await conn.execute_query(query, [str(doc.id), section, subsection])
        
        if result[1]:  # Record exists
            # Update existing record
            update_query = """
                UPDATE approved_subsections 
                SET approved_value = $4 
                WHERE document_id = $1 AND section = $2 AND subsection = $3;
            """
            await conn.execute_query(update_query, [str(doc.id), section, subsection, value])
            logger.debug(f"Updated approval for {section}.{subsection}")
        else:
            # Insert new record
            insert_query = """
                INSERT INTO approved_subsections(document_id, section, subsection, approved_value)
                VALUES($1, $2, $3, $4);
            """
            await conn.execute_query(insert_query, [str(doc.id), section, subsection, value])
            logger.debug(f"Created approval for {section}.{subsection}")
    except Exception as e:
        logger.exception(f"Database error during approval: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Return the result
    return {
        "document_id": document_id,
        "section": section,
        "subsection": subsection,
        "value": value,
        "approved": True
    }

@router.post("/{document_id}/approve-shown-data/{section}/{subsection}")
async def approve_shown_data(
    document_id: str, 
    section: str, 
    subsection: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Approve the data that was explicitly shown to the user for a specific subsection.
    This endpoint is used when the user confirms the data presented by the assistant.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Validate section and subsection against document structure
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
        
    section_valid = False
    subsection_valid = False
    
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        sec_name = list(sec_obj.keys())[0]
        if sec_name == section:
            section_valid = True
            if subsection in sec_obj[sec_name]:
                subsection_valid = True
                break
    
    if not section_valid:
        raise HTTPException(status_code=400, detail=f"Invalid section '{section}' for topic '{topic}'")
    
    if not subsection_valid:
        raise HTTPException(status_code=400, detail=f"Invalid subsection '{subsection}' for section '{section}'")
    
    # Get the section data
    section_data = await SectionData.filter(document=doc, section=section).first()
    
    if not section_data:
        raise HTTPException(status_code=404, detail=f"No data found for section '{section}'")
            
    data = section_data.data
    
    if subsection not in data:
        raise HTTPException(status_code=404, detail=f"No data found for subsection '{subsection}'")
            
    value = data[subsection]
    
    # Format the value for human readability
    if isinstance(value, dict):
        # Format dictionary into a readable string with each key-value pair on a new line
        formatted_value = ""
        for key, val in value.items():
            formatted_value += f"{key}: {val}\n"
        value = formatted_value.rstrip("\n")  # Remove trailing newline
        logger.info(f"Formatted dictionary value for {section}.{subsection}")
    elif isinstance(value, list):
        # Format list into a bulleted list
        formatted_value = ""
        for item in value:
            formatted_value += f"• {item}\n"
        value = formatted_value.rstrip("\n")  # Remove trailing newline
        logger.info(f"Formatted list value for {section}.{subsection}")
    elif value is None:
        value = ""
    else:
        value = str(value)
    
    # Add a confirmation message to the conversation
    thread_id = doc.thread_id
    if thread_id:
        confirmation_message = (
            f"I have approved the data for {section} > {subsection}. "
            f"This information will be included in the final PDF document."
        )
        
        # Add message to conversation history
        await ChatMessage.create(
            document=doc,
            role="user",
            content=confirmation_message,
            section=section,
            subsection=subsection
        )
        
        # Send to OpenAI thread
        try:
            # Use optimized client
            client = get_optimized_client()
            await client.send_message_optimized(doc.thread_id, confirmation_message)
        except Exception as e:
            logger.error(f"Error sending confirmation to OpenAI: {e}")
    
    # Use direct SQL to avoid datetime issues
    try:
        conn = Tortoise.get_connection("default")
        
        # Check if record exists
        query = """
            SELECT id FROM approved_subsections 
            WHERE document_id = $1 AND section = $2 AND subsection = $3;
        """
        result = await conn.execute_query(query, [str(doc.id), section, subsection])
        
        if result[1]:  # Record exists
            # Update existing record
            update_query = """
                UPDATE approved_subsections 
                SET approved_value = $4 
                WHERE document_id = $1 AND section = $2 AND subsection = $3;
            """
            await conn.execute_query(update_query, [str(doc.id), section, subsection, value])
            logger.debug(f"Updated approval for {section}.{subsection}")
        else:
            # Insert new record
            insert_query = """
                INSERT INTO approved_subsections(document_id, section, subsection, approved_value)
                VALUES($1, $2, $3, $4);
            """
            await conn.execute_query(insert_query, [str(doc.id), section, subsection, value])
            logger.debug(f"Created approval for {section}.{subsection}")
    except Exception as e:
        logger.exception(f"Database error during approval: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Return the result
    return {
        "document_id": document_id,
        "section": section,
        "subsection": subsection,
        "value": value,
        "approved": True,
        "message": f"Data for {section} > {subsection} has been approved and will be included in the PDF."
    }

async def _update_section_data(doc: Document, data: Dict[str, Any]) -> None:
    """
    Update section data based on the AI response.
    This is used by both the conversation and file upload routers.
    """
    # Skip if no data provided
    if not data:
        logger.warning("No data to update from AI response")
        return
    
    # Update or create section data records
    for sec_name, sec_data in data.items():
        if isinstance(sec_data, dict):
            existing = await SectionData.filter(document=doc, section=sec_name).first()
            if existing:
                # Merge with existing data rather than overwriting
                merged_data = existing.data
                for subsec, value in sec_data.items():
                    merged_data[subsec] = value
                await SectionData.filter(document=doc, section=sec_name).update(data=merged_data)
            else:
                await SectionData.create(document=doc, section=sec_name, data=sec_data)
        else:
            logger.warning(f"Section '{sec_name}' data is not a dictionary, it's {type(sec_data)}. Skipping.")

@router.get("/{document_id}/limits")
async def get_conversation_limits(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current rate limit status for the user
    """
    return await RateLimiter.get_user_limits(current_user)

@router.get("/{document_id}/section-data/{section}/{subsection}")
async def get_section_subsection_data(
    document_id: str,
    section: str,
    subsection: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current data for a specific section/subsection.
    This is used to populate the modal for user editing.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Validate section and subsection against document structure
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
        
    section_valid = False
    subsection_valid = False
    
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        sec_name = list(sec_obj.keys())[0]
        if sec_name == section:
            section_valid = True
            if subsection in sec_obj[sec_name]:
                subsection_valid = True
                break
    
    if not section_valid:
        raise HTTPException(status_code=400, detail=f"Invalid section '{section}' for topic '{topic}'")
    
    if not subsection_valid:
        raise HTTPException(status_code=400, detail=f"Invalid subsection '{subsection}' for section '{section}'")
    
    # Get the section data
    section_data = await SectionData.filter(document=doc, section=section).first()
    
    if not section_data:
        # Return empty data if not found
        return {
            "document_id": document_id,
            "section": section,
            "subsection": subsection,
            "value": "",
            "approved": False
        }
            
    data = section_data.data
    
    # Get the subsection value
    value = data.get(subsection, "")
    
    # Format the value for human readability
    if isinstance(value, dict):
        # Format dictionary into a readable string with each key-value pair on a new line
        formatted_value = ""
        for key, val in value.items():
            formatted_value += f"{key}: {val}\n"
        value = formatted_value.rstrip("\n")  # Remove trailing newline
        logger.info(f"Formatted dictionary value for {section}.{subsection}")
    elif isinstance(value, list):
        # Format list into a bulleted list
        formatted_value = ""
        for item in value:
            formatted_value += f"• {item}\n"
        value = formatted_value.rstrip("\n")  # Remove trailing newline
        logger.info(f"Formatted list value for {section}.{subsection}")
    elif value is None:
        value = ""
    else:
        value = str(value)
    
    # Check if this subsection is already approved
    is_approved = await ApprovedSubsection.filter(
        document=doc,
        section=section,
        subsection=subsection
    ).exists()
    
    # Get the approved value if it exists
    approved_value = ""
    if is_approved:
        approved_subsection = await ApprovedSubsection.filter(
            document=doc,
            section=section,
            subsection=subsection
        ).first()
        approved_value = approved_subsection.approved_value if approved_subsection else ""
    
    # Return the result
    return {
        "document_id": document_id,
        "section": section,
        "subsection": subsection,
        "value": value,
        "approved": is_approved,
        "approved_value": approved_value
    }

@router.put("/{document_id}/section-data/{section}/{subsection}")
async def update_section_subsection_data(
    document_id: str,
    section: str,
    subsection: str,
    data_update: SectionDataUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update the data for a specific section/subsection based on user edits.
    This is used when the user edits the data in the modal.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Validate section and subsection against document structure
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
        
    section_valid = False
    subsection_valid = False
    
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        sec_name = list(sec_obj.keys())[0]
        if sec_name == section:
            section_valid = True
            if subsection in sec_obj[sec_name]:
                subsection_valid = True
                break
    
    if not section_valid:
        raise HTTPException(status_code=400, detail=f"Invalid section '{section}' for topic '{topic}'")
    
    if not subsection_valid:
        raise HTTPException(status_code=400, detail=f"Invalid subsection '{subsection}' for section '{section}'")
    
    # Get or create the section data
    section_data, created = await SectionData.get_or_create(
        document=doc,
        section=section,
        defaults={"data": {}}
    )
    
    # Update the section data with the new value
    data = section_data.data if isinstance(section_data.data, dict) else {}
    data[subsection] = data_update.value
    section_data.data = data
    await section_data.save()
    
    logger.info(f"Updated section data for {section}.{subsection} with user-edited value")
    
    # Return the result
    return {
        "document_id": document_id,
        "section": section,
        "subsection": subsection,
        "value": data_update.value,
        "updated": True
    }

@router.post("/{document_id}/update-and-approve/{section}/{subsection}")
async def update_and_approve_subsection(
    document_id: str, 
    section: str, 
    subsection: str,
    data: UpdateAndApproveData,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update section data and approve it for the PDF in a single operation.
    This is used when the user edits the data in the modal and approves it.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Validate section and subsection against document structure
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
        
    section_valid = False
    subsection_valid = False
    
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        sec_name = list(sec_obj.keys())[0]
        if sec_name == section:
            section_valid = True
            if subsection in sec_obj[sec_name]:
                subsection_valid = True
                break
    
    if not section_valid:
        raise HTTPException(status_code=400, detail=f"Invalid section '{section}' for topic '{topic}'")
    
    if not subsection_valid:
        raise HTTPException(status_code=400, detail=f"Invalid subsection '{subsection}' for section '{section}'")
    
    # Update the section data first
    section_data, created = await SectionData.get_or_create(
        document=doc,
        section=section,
        defaults={"data": {}}
    )
    
    # Update the data
    section_dict = section_data.data if isinstance(section_data.data, dict) else {}
    section_dict[subsection] = data.value
    section_data.data = section_dict
    await section_data.save()
    
    # Use direct SQL to avoid datetime issues when creating/updating approved subsection
    try:
        conn = Tortoise.get_connection("default")
        
        # Check if record exists
        query = """
            SELECT id FROM approved_subsections 
            WHERE document_id = $1 AND section = $2 AND subsection = $3;
        """
        result = await conn.execute_query(query, [str(doc.id), section, subsection])
        
        if result[1]:  # Record exists
            # Update existing record
            update_query = """
                UPDATE approved_subsections 
                SET approved_value = $4 
                WHERE document_id = $1 AND section = $2 AND subsection = $3;
            """
            await conn.execute_query(update_query, [str(doc.id), section, subsection, data.value])
            logger.debug(f"Updated approval for {section}.{subsection}")
        else:
            # Insert new record
            insert_query = """
                INSERT INTO approved_subsections(document_id, section, subsection, approved_value)
                VALUES($1, $2, $3, $4);
            """
            await conn.execute_query(insert_query, [str(doc.id), section, subsection, data.value])
            logger.debug(f"Created approval for {section}.{subsection}")
    except Exception as e:
        logger.exception(f"Database error during approval: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # Add a confirmation message to the conversation if requested
    if data.notify_assistant and doc.thread_id:
        confirmation_message = (
            f"I have edited and approved the data for {section} > {subsection}. "
            f"This information will be included in the final PDF document."
        )
        
        # Add message to conversation history
        await ChatMessage.create(
            document=doc,
            role="user",
            content=confirmation_message,
            section=section,
            subsection=subsection
        )
        
        # Send to OpenAI thread
        try:
            # Use optimized client
            client = get_optimized_client()
            await client.send_message_optimized(doc.thread_id, confirmation_message)
        except Exception as e:
            logger.error(f"Error sending confirmation to OpenAI: {e}")
    
    # Return the result
    return {
        "document_id": document_id,
        "section": section,
        "subsection": subsection,
        "value": data.value,
        "approved": True,
        "message": f"Data for {section} > {subsection} has been updated and approved for the PDF."
    }

@router.get("/{document_id}/all-section-data")
async def get_all_section_data(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all section data for a document.
    This is used to populate the UI with the current status of all sections/subsections.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Get all section data
    section_data_records = await SectionData.filter(document=doc).all()
    
    # Get all approved subsections
    approved_records = await ApprovedSubsection.filter(document=doc).all()
    approved_map = {f"{a.section}:{a.subsection}": a.approved_value for a in approved_records}
    
    # Prepare the response structure
    topic = doc.topic
    if topic not in DOCUMENT_STRUCTURE:
        raise HTTPException(status_code=400, detail=f"Unknown topic '{topic}'")
    
    # Build a structure with all sections/subsections from the document structure
    result = {}
    
    for sec_obj in DOCUMENT_STRUCTURE[topic]:
        section_name = list(sec_obj.keys())[0]
        subsections = sec_obj[section_name]
        
        section_result = {}
        for subsection in subsections:
            # Initialize with empty values
            section_result[subsection] = {
                "value": "",
                "approved": False,
                "approved_value": ""
            }
        
        result[section_name] = section_result
    
    # Fill in actual values from section data
    for section_record in section_data_records:
        section = section_record.section
        if section not in result:
            # Skip sections not in the document structure
            continue
            
        data = section_record.data
        if not isinstance(data, dict):
            continue
            
        for subsection, value in data.items():
            if subsection in result[section]:
                # Format the value for human readability
                if isinstance(value, dict):
                    # Format dictionary into a readable string
                    formatted_value = ""
                    for key, val in value.items():
                        formatted_value += f"{key}: {val}\n"
                    value = formatted_value.rstrip("\n")
                elif isinstance(value, list):
                    # Format list into a bulleted list
                    formatted_value = ""
                    for item in value:
                        formatted_value += f"• {item}\n"
                    value = formatted_value.rstrip("\n")
                elif value is None:
                    value = ""
                else:
                    value = str(value)
                    
                # Set the value
                result[section][subsection]["value"] = value
                
                # Check if this subsection is approved
                key = f"{section}:{subsection}"
                if key in approved_map:
                    result[section][subsection]["approved"] = True
                    result[section][subsection]["approved_value"] = approved_map[key]
    
    return {
        "document_id": document_id,
        "topic": topic,
        "section_data": result
    }

@router.get("/{document_id}/subsection-status", response_model=List[SubsectionDataStatus])
async def get_subsection_status(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a summary of all subsections and their data status.
    This is used by the UI to show which subsections have data and which are approved.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    # Get all section data
    section_data_records = await SectionData.filter(document=doc).all()
    
    # Build a map of section/subsection -> has_data
    data_map = {}
    for record in section_data_records:
        section = record.section
        data = record.data
        if isinstance(data, dict):
            for subsection, value in data.items():
                # Check if value is not empty
                has_data = False
                if isinstance(value, (dict, list)):
                    has_data = bool(value)  # True if not empty
                else:
                    has_data = bool(value) if value is not None else False
                
                key = f"{section}:{subsection}"
                data_map[key] = has_data
    
    # Get all approved subsections
    approved_records = await ApprovedSubsection.filter(document=doc).all()
    approved_map = {f"{a.section}:{a.subsection}": a.approved_value for a in approved_records}
    
    # Build the result
    result = []
    topic = doc.topic
    
    # Iterate through document structure
    if topic in DOCUMENT_STRUCTURE:
        for sec_obj in DOCUMENT_STRUCTURE[topic]:
            section = list(sec_obj.keys())[0]
            subsections = sec_obj[section]
            
            for subsection in subsections:
                key = f"{section}:{subsection}"
                has_data = key in data_map and data_map[key]
                is_approved = key in approved_map
                
                result.append(SubsectionDataStatus(
                    section=section,
                    subsection=subsection,
                    has_data=has_data,
                    is_approved=is_approved,
                    approved_version=approved_map.get(key) if is_approved else None
                ))
    
    return result

@router.get("/{document_id}/cover-page-data")
async def get_cover_page_data_for_conversation(
    document_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current cover page data for a document.
    This endpoint is used during conversations to access cover page information.
    """
    # Check if user has access to this document
    doc = await _check_document_access(document_id, current_user)
    
    try:
        # Get cover page data from database
        cover_page = await CoverPageData.filter(document=doc).first()
        
        # Get the cover page structure for this topic
        topic = doc.topic
        if topic not in COVER_PAGE_STRUCTURE:
            return {
                "document_id": document_id,
                "topic": topic,
                "cover_page_data": {},
                "message": f"No cover page structure defined for topic '{topic}'"
            }
        
        cover_structure = COVER_PAGE_STRUCTURE[topic]
        
        # Format the response with both structure and current data
        response_data = {}
        
        if cover_page and cover_page.data:
            # Include actual data from database
            response_data = cover_page.data
        else:
            # Initialize empty structure
            for category, fields in cover_structure.items():
                response_data[category] = {field: "" for field in fields.keys()}
        
        return {
            "document_id": document_id,
            "topic": topic,
            "cover_page_data": response_data,
            "cover_page_structure": cover_structure,
            "message": "Cover page data retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error getting cover page data for conversation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving cover page data: {str(e)}")

@router.get("/{document_id}/performance-stats")
async def get_performance_stats(
    document_id: str,
    current_user: User = Depends(get_admin_user)  # Only admin can access performance stats
):
    """
    Get performance statistics for the optimized OpenAI client.
    This helps monitor cache effectiveness and active runs.
    """
    client = get_optimized_client()
    stats = client.get_cache_stats()
    
    return {
        "document_id": document_id,
        "openai_optimization_stats": stats,
        "recommendations": {
            "cache_hit_rate": f"{(stats['valid_entries'] / max(stats['total_entries'], 1)) * 100:.1f}%",
            "active_runs": stats['active_runs'],
            "cache_efficiency": "Good" if stats['valid_entries'] > 0 else "No cache hits yet"
        }
    }
