from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Tuple
import json, logging
import openai
from config import settings
from templates.structure import DOCUMENT_STRUCTURE
from models import Document, SectionData, ChatMessage

router = APIRouter()
logger = logging.getLogger("conversation")
logger.setLevel(logging.DEBUG)

class StartRequest(BaseModel):
    topic: str

class ReplyRequest(BaseModel):
    message: str

class ConversationResponse(BaseModel):
    data: Dict[str, Any]
    message: str

async def _run_thread_and_parse(thread_id: str) -> Tuple[Dict[str, Any], str]:
    """
    Executes the assistant run on an existing thread, returns parsed JSON data and human reply.
    """
    # Kick off the assistant run
    logger.debug(f"Starting assistant run for thread_id: {thread_id}")
    run = openai.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=settings.ASSISTANT_ID
    )
    logger.debug(f"Run completed with status: {run.status}")
    
    # Retrieve messages for that run
    msgs = openai.beta.threads.messages.list(thread_id=thread_id, run_id=run.id)
    logger.debug(f"Retrieved {len(list(msgs))} messages for the run")
    
    # Combine assistant content
    raw = ""
    for m in msgs:
        if m.role == "assistant":
            content = m.content
            logger.debug(f"Found assistant message with content type: {type(content)}")
            if isinstance(content, list):
                raw = "".join(block.text.value for block in content if hasattr(block, 'text'))
            else:
                raw = content
            logger.debug(f"Raw assistant content: {raw[:100]}...")
            break
    
    # Initialize variables
    data = {}
    human = raw.strip()  # Default to using full content as human message if no JSON detected
    
    # Check if content might start with JSON by checking first character
    first_char = raw[0] if raw else ""
    if first_char in ["{", "["]:  # Likely starts with JSON
        # Split JSON and human part
        parts = raw.split('\n\n', 1)
        logger.debug(f"Split raw content into {len(parts)} parts")
        
        # Extract JSON part (handle Markdown code blocks if present)
        json_part = parts[0] if parts else ""
        
        # Check if JSON is wrapped in markdown code blocks and extract it
        if json_part.startswith("```json") or json_part.startswith("```"):
            # Extract content between ``` markers
            lines = json_part.split("\n")
            # Remove the first line with ```json
            lines = lines[1:]
            # Find the closing ``` if it exists
            if "```" in lines:
                closing_index = lines.index("```")
                lines = lines[:closing_index]
            # Join the remaining lines to get the JSON
            json_part = "\n".join(lines)
            logger.debug(f"Extracted JSON from markdown code block: {json_part[:100]}...")
        
        # Parse the JSON
        try:
            data = json.loads(json_part)
            logger.debug(f"Successfully parsed JSON data: {json.dumps(data, indent=2)}")
            # If we got valid JSON, set human part to second part (if exists)
            human = parts[1].strip() if len(parts) > 1 else ''
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Raw content that failed to parse: {json_part[:200]}...")
            # Keep default human = raw
    else:
        logger.warning(f"Response does not begin with a JSON object. First character: '{first_char}'")
        logger.warning("Using entire response as human message and returning empty data")
    
    logger.debug(f"Human part (first 100 chars): {human[:100]}...")
    logger.info(f"Extracted data with {len(data)} keys and human message of length {len(human)}")
    
    return data, human

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
    correction_message = (
        "CRITICAL FORMAT CORRECTION: Your last response did not follow the required format. "
        "You MUST structure ALL responses in exactly two parts:\n\n"
        "1) First part: A valid JSON object starting with '{' containing all the information gathered so far\n"
        "2) Second part: Your human-readable message after TWO newlines\n\n"
        f"For example:\n"
        f"{{\"Section Name\": {{\"Subsection1\": \"Value1\", \"Subsection2\": \"Value2\"}}}}\n\n"
        f"Your normal human response here...\n\n"
        f"Please continue helping with the {doc_topic} document, but ALWAYS follow this exact format."
    )
    
    logger.warning(f"Sending format correction to thread {thread_id}")
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=correction_message
    )
    
    # Run the assistant to get a corrected response
    run = openai.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=settings.ASSISTANT_ID
    )
    logger.debug(f"Correction run completed with status: {run.status}")
    
    return

@router.post("/{document_id}/start", response_model=ConversationResponse)
async def start_conversation(document_id: str, body: StartRequest):
    logger.debug(f"Starting conversation for document {document_id} with topic {body.topic}")
    # Validate topic
    topic = body.topic
    if topic not in DOCUMENT_STRUCTURE:
        logger.error(f"Unknown topic: {topic}")
        raise HTTPException(status_code=404, detail=f"Unknown topic '{topic}'")
    
    # Create or get document record
    doc, created = await Document.get_or_create(id=document_id, defaults={"topic": topic})
    logger.debug(f"Document {'created' if created else 'retrieved'} with ID {doc.id}")
    
    # If new or no thread, create OpenAI thread
    if created or not doc.thread_id:
        thread = openai.beta.threads.create()
        doc.thread_id = thread.id
        await doc.save()
        logger.debug(f"Created new thread with ID {thread.id}")
    thread_id = doc.thread_id
    logger.debug(f"Using thread ID {thread_id}")
    
    # Persist system instructions into thread and DB
    prompt_lines = [
        f"You are an expert assistant for topic '{topic}'. You need to get relevant data from the user to complete the PDF document for this topic. ",
        "Following sections are needed:"
    ]
    for sec in DOCUMENT_STRUCTURE[topic]:
        title = list(sec.keys())[0]
        subs = sec[title]
        prompt_lines.append(f"- {title}: {', '.join(subs)}")
    prompt_lines.append(
        "Go through the sections one by one and ask the user for information for that section until you consider you have enough."
    )
    prompt_lines.append(
        "When one section is completed or the user requests to move on, start with the next section."
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
        "Example format:\n{\"Section Name\": {\"Subsection1\": \"Content\", \"Subsection2\": \"Content\"}}\n\nYour human response text here..."
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
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=system_prompt
    )
    # save to DB
    await ChatMessage.create(document=doc, role="user", content=system_prompt)
    logger.debug(f"System prompt saved to DB with length {len(system_prompt)}")
    
    # run assistant and parse
    logger.debug("Running assistant and parsing response...")
    data, question = await _run_thread_and_parse(thread_id)
    
    # Check if we got valid data - if not, try to send a format correction
    if not data and question:
        logger.warning("No valid JSON data found in assistant's response. Sending format correction.")
        await _send_format_correction(thread_id, doc.topic)
        # Try again after correction
        data, question = await _run_thread_and_parse(thread_id)
    
    logger.debug(f"Received data with {len(data)} keys and message of length {len(question)}")
    
    # persist section data and assistant message
    for section, vals in data.items():
        await SectionData.get_or_create(document=doc, section=section, defaults={"data": vals})
        await SectionData.filter(document=doc, section=section).update(data=vals)
    logger.debug(f"Saved {len(data)} section data items to DB")
    
    await ChatMessage.create(document=doc, role="assistant", content=question)
    logger.debug(f"Saved assistant message to DB with length {len(question)}")
    
    return {"data": data, "message": question}

@router.post("/{document_id}/reply", response_model=ConversationResponse)
async def reply_conversation(document_id: str, body: ReplyRequest):
    logger.debug(f"Processing reply for document {document_id}")
    # Fetch document
    try:
        doc = await Document.get(id=document_id)
        logger.debug(f"Found document with thread_id {doc.thread_id}")
    except Document.DoesNotExist:
        logger.error(f"Document not found: {document_id}")
        raise HTTPException(status_code=404, detail="Conversation not initialized. Call start first.")
    
    thread_id = doc.thread_id
    if not thread_id:
        logger.error(f"Thread ID not found for document {document_id}")
        raise HTTPException(status_code=400, detail="Thread not initialized. Call start first.")
    
    # Persist user into thread and DB
    logger.debug(f"Sending user message to OpenAI: {body.message[:50]}...")
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=body.message
    )
    await ChatMessage.create(document=doc, role="user", content=body.message)
    logger.debug("User message saved to DB")
    
    # run assistant and parse
    logger.debug("Running assistant and parsing response...")
    data, question = await _run_thread_and_parse(thread_id)
    
    # Check if we got valid data - if not, try to send a format correction
    if not data and question:
        logger.warning("No valid JSON data found in assistant's response. Sending format correction.")
        await _send_format_correction(thread_id, doc.topic)
        # Try again after correction
        data, question = await _run_thread_and_parse(thread_id)
    
    logger.debug(f"Received data with {len(data)} keys and message of length {len(question)}")
    
    # persist section data and assistant message
    sections_updated = 0
    for section, vals in data.items():
        await SectionData.get_or_create(document=doc, section=section, defaults={"data": vals})
        await SectionData.filter(document=doc, section=section).update(data=vals)
        sections_updated += 1
    logger.debug(f"Updated {sections_updated} sections in DB")
    
    await ChatMessage.create(document=doc, role="assistant", content=question)
    logger.debug(f"Saved assistant message to DB with length {len(question)}")
    
    return {"data": data, "message": question}

@router.get("/{document_id}/debug")
async def debug_conversation(document_id: str):
    """
    Debug endpoint to see all messages and data for a document.
    """
    try:
        doc = await Document.get(id=document_id)
    except Document.DoesNotExist:
        raise HTTPException(status_code=404, detail="Document not found")
    
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
async def analyze_message_format(document_id: str, message_id: str = None):
    """
    Analyzes the format of a message to debug JSON parsing issues.
    """
    try:
        doc = await Document.get(id=document_id)
    except Document.DoesNotExist:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.thread_id:
        raise HTTPException(status_code=400, detail="Thread not initialized")
    
    result = await _analyze_message_format(doc.thread_id, message_id)
    return result
