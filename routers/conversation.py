from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
import logging
import openai
from config import settings

router = APIRouter()

# In-memory store: document_id -> thread_id
session_data: Dict[str, str] = {}
logger = logging.getLogger("conversation")

class StartRequest(BaseModel):
    topic: str

class ReplyRequest(BaseModel):
    message: str

class ConversationResponse(BaseModel):
    thread_id: str
    message: str

@router.post("/{document_id}/start", response_model=ConversationResponse)
async def start_conversation(document_id: str, body: StartRequest):
    """
    Initialize a new thread for this document with topic context.
    """
    if document_id not in session_data:
        # 1. Create a new thread container for the assistant
        thread = openai.beta.threads.create()
        logger.info(f"Created new thread container {thread.id} for document {document_id}")

        # 2. Inject the topic instructions as a user message
        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=(
                f"Unser Thema ist '{body.topic}'. "
                "Du hilfst dem User, ein Dokument mit den folgenden Sektionen zu erstellen: "
                "Projekt Details mit Grundstücksdaten und Bauvorhaben, "
                "Projekt Objectives mit Bewertung und Empfehlungen, "
                "und falls nötig auch einen Anhang mit Gutachten und Plänen."
                "Du wirst direkt nach relevante infos den User fragen."
                "Man sollte Schritt fur Schritt das durchfuren: Man fragt den User nach dem ersten Kategorie, "
                "pruft den Antwort and setzt fort zu dem nachsten wenn alles ok ist"
            )
        )

        # 3. Run the assistant (pre-configured) to generate first reply
        run = openai.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=settings.ASSISTANT_ID
        )

        # 4. Retrieve the assistant's reply for this run
        msgs = openai.beta.threads.messages.list(thread_id=thread.id, run_id=run.id)
        assistant_msg = ""
        for m in msgs:
            if m.role == "assistant":
                content = m.content
                if isinstance(content, list):
                    assistant_msg = "".join(
                        block.text.value for block in content if hasattr(block, 'text')
                    )
                else:
                    assistant_msg = content
                break

        # 5. Store and return
        session_data[document_id] = thread.id
        return {"thread_id": thread.id, "message": assistant_msg}

    # Thread exists: return stored thread_id with an empty message
    return {"thread_id": session_data[document_id], "message": ""}

@router.post("/{document_id}/reply", response_model=ConversationResponse)
async def reply_conversation(document_id: str, body: ReplyRequest):
    """
    Continue conversation for this document's thread.
    """
    if document_id not in session_data:
        raise HTTPException(status_code=400, detail="Conversation not initialized. Call start first.")
    thread_id = session_data[document_id]
    # Add user message to thread
    openai.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=body.message
    )
    # Run the assistant
    run = openai.beta.threads.runs.create_and_poll(
    thread_id=thread_id,
    assistant_id=settings.ASSISTANT_ID
    )
    # Retrieve messages for this run
    msgs = openai.beta.threads.messages.list(thread_id=thread_id, run_id=run.id)
    assistant_msg = ""
    for m in msgs:
        if m.role == "assistant":
            content = m.content
            if isinstance(content, list):
                # Concatenate text values from content blocks
                assistant_msg = "".join(block.text.value for block in content if hasattr(block, 'text'))
            else:
                assistant_msg = content
            break
    return {"thread_id": thread_id, "message": assistant_msg}