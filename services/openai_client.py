import openai
from typing import Optional, List, Dict
from config import settings

openai.api_key = settings.OPENAI_API_KEY

async def chat_with_thread(
    assistant_id: str,
    messages: List[Dict[str, str]],
    thread_id: Optional[str] = None
) -> Dict[str, str]:
    """
    Use OpenAI Threads API to start or continue a conversation.
    Returns 'thread_id' and assistant 'message'.
    """
    if thread_id is None:
        response = await openai.chat.threads.create(
            model=assistant_id,
            messages=messages
        )
        thread_id = response.id
        assistant_msg = response.messages[0].content
        return {"thread_id": thread_id, "message": assistant_msg}
    response = await openai.chat.threads.messages.create(
        thread_id=thread_id,
        model=assistant_id,
        message=messages[0]
    )
    assistant_msg = response.message.content
    return {"thread_id": thread_id, "message": assistant_msg}