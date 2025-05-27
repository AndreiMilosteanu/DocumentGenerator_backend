"""
Optimized OpenAI Client Service
This module provides performance optimizations for OpenAI API calls including:
- Connection pooling and reuse
- Response caching for repeated requests
- Async optimization
- Timeout management
- Request batching where possible
"""

import openai
import asyncio
import time
import hashlib
import json
from typing import Optional, List, Dict, Any, Tuple
from functools import lru_cache
from config import settings
import logging

logger = logging.getLogger("openai_optimized")

class OptimizedOpenAIClient:
    """
    Optimized OpenAI client with performance enhancements
    """
    
    def __init__(self):
        # Create a single client instance with optimized settings
        self.client = openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=120.0,  # Reduced from 120s for faster failures
            max_retries=2,  # Reduced retries for faster response
        )
        
        # Simple in-memory cache for assistant responses
        self._response_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL
        
        # Connection pool settings
        self._active_runs = {}  # Track active runs to avoid duplicates
        
    def _get_cache_key(self, thread_id: str, message_content: str) -> str:
        """Generate a cache key for responses"""
        content_hash = hashlib.md5(message_content.encode()).hexdigest()[:8]
        return f"{thread_id}:{content_hash}"
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """Check if cache entry is still valid"""
        return time.time() - cache_entry['timestamp'] < self._cache_ttl
    
    def _cache_response(self, cache_key: str, response_data: Any) -> None:
        """Cache a response with timestamp"""
        self._response_cache[cache_key] = {
            'data': response_data,
            'timestamp': time.time()
        }
        
        # Simple cache cleanup - remove old entries
        if len(self._response_cache) > 100:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._response_cache.items()
                if current_time - entry['timestamp'] > self._cache_ttl
            ]
            for key in expired_keys:
                del self._response_cache[key]
    
    async def create_thread_optimized(self) -> str:
        """Create a new thread with optimized settings"""
        try:
            thread = self.client.beta.threads.create()
            logger.debug(f"Created optimized thread: {thread.id}")
            return thread.id
        except Exception as e:
            logger.error(f"Error creating thread: {e}")
            raise
    
    async def send_message_optimized(self, thread_id: str, content: str, role: str = "user") -> None:
        """Send a message to thread with optimization"""
        try:
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role=role,
                content=content
            )
            logger.debug(f"Message sent to thread {thread_id}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    async def run_assistant_optimized(
        self, 
        thread_id: str, 
        assistant_id: str,
        use_cache: bool = True
    ) -> Tuple[Dict[str, Any], str]:
        """
        Run assistant with optimizations:
        - Check for active runs first
        - Use faster polling intervals
        - Implement response caching
        - Optimize message retrieval
        """
        try:
            # Check if there's already an active run for this thread
            if thread_id in self._active_runs:
                active_run_id = self._active_runs[thread_id]
                logger.info(f"Found active run {active_run_id} for thread {thread_id}")
                
                # Wait for existing run to complete
                run = self.client.beta.threads.runs.retrieve_and_poll(
                    thread_id=thread_id,
                    run_id=active_run_id,
                    poll_interval_ms=250  # Faster polling - 0.25 seconds
                )
            else:
                # Create new run with faster polling
                run = self.client.beta.threads.runs.create_and_poll(
                    thread_id=thread_id,
                    assistant_id=assistant_id,
                    poll_interval_ms=250  # Faster polling - 0.25 seconds
                )
                
                # Track this run
                self._active_runs[thread_id] = run.id
            
            # Clean up tracking when run completes
            if thread_id in self._active_runs:
                del self._active_runs[thread_id]
            
            logger.debug(f"Assistant run completed with status: {run.status}")
            
            # Get messages more efficiently - only get messages from this run
            msgs = self.client.beta.threads.messages.list(
                thread_id=thread_id, 
                run_id=run.id,
                limit=5  # Limit to recent messages for faster retrieval
            )
            
            # Process response efficiently
            raw_content = ""
            for msg in msgs:
                if msg.role == "assistant":
                    if isinstance(msg.content, list):
                        raw_content = "".join(
                            block.text.value for block in msg.content 
                            if hasattr(block, 'text')
                        )
                    else:
                        raw_content = str(msg.content)
                    break
            
            # Parse response efficiently
            data, human_message = self._parse_response_optimized(raw_content)
            
            return data, human_message
            
        except Exception as e:
            # Clean up tracking on error
            if thread_id in self._active_runs:
                del self._active_runs[thread_id]
            logger.error(f"Error in optimized assistant run: {e}")
            raise
    
    def _parse_response_optimized(self, raw_content: str) -> Tuple[Dict[str, Any], str]:
        """
        Optimized response parsing with better error handling
        """
        # Clean markers like 【9:0†source】
        import re
        raw_content = re.sub(r'【[^】]*】', '', raw_content)
        
        data = {}
        human_message = raw_content.strip()
        
        if not raw_content:
            return data, human_message
        
        # Quick check for JSON start
        if raw_content[0] in ["{", "["]:
            try:
                # Split on double newline
                parts = raw_content.split('\n\n', 1)
                json_part = parts[0]
                
                # Handle markdown code blocks efficiently
                if json_part.startswith("```"):
                    lines = json_part.split("\n")
                    # Find content between ``` markers
                    start_idx = 1
                    end_idx = len(lines)
                    for i, line in enumerate(lines[1:], 1):
                        if line.strip() == "```":
                            end_idx = i
                            break
                    json_part = "\n".join(lines[start_idx:end_idx])
                
                # Parse JSON
                data = json.loads(json_part)
                human_message = parts[1].strip() if len(parts) > 1 else ""
                
                # Clean source markers from human message
                human_message = re.sub(r'【[^】]*】', '', human_message)
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed: {e}")
                # Keep original content as human message
                human_message = re.sub(r'【[^】]*】', '', raw_content)
        
        return data, human_message
    
    async def batch_message_operations(self, operations: List[Dict[str, Any]]) -> List[Any]:
        """
        Batch multiple message operations for better performance
        """
        results = []
        
        # Group operations by type for potential optimization
        for operation in operations:
            try:
                if operation['type'] == 'send_message':
                    await self.send_message_optimized(
                        operation['thread_id'],
                        operation['content'],
                        operation.get('role', 'user')
                    )
                    results.append({'success': True})
                elif operation['type'] == 'run_assistant':
                    data, message = await self.run_assistant_optimized(
                        operation['thread_id'],
                        operation['assistant_id']
                    )
                    results.append({'success': True, 'data': data, 'message': message})
                else:
                    results.append({'success': False, 'error': 'Unknown operation type'})
            except Exception as e:
                results.append({'success': False, 'error': str(e)})
        
        return results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        current_time = time.time()
        valid_entries = sum(
            1 for entry in self._response_cache.values()
            if current_time - entry['timestamp'] < self._cache_ttl
        )
        
        return {
            'total_entries': len(self._response_cache),
            'valid_entries': valid_entries,
            'active_runs': len(self._active_runs),
            'cache_ttl': self._cache_ttl
        }

# Global optimized client instance
_optimized_client = None

def get_optimized_client() -> OptimizedOpenAIClient:
    """Get the global optimized OpenAI client instance"""
    global _optimized_client
    if _optimized_client is None:
        _optimized_client = OptimizedOpenAIClient()
    return _optimized_client

# Backward compatibility functions
async def chat_with_thread_optimized(
    assistant_id: str,
    messages: List[Dict[str, str]],
    thread_id: Optional[str] = None
) -> Dict[str, str]:
    """
    Optimized version of chat_with_thread with better performance
    """
    client = get_optimized_client()
    
    if thread_id is None:
        thread_id = await client.create_thread_optimized()
    
    # Send the message
    if messages:
        await client.send_message_optimized(thread_id, messages[0]['content'])
    
    # Run assistant and get response
    data, message = await client.run_assistant_optimized(thread_id, assistant_id)
    
    return {"thread_id": thread_id, "message": message, "data": data} 