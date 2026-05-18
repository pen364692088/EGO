"""
OpenEmotion Integration - Adapter

Adapts EgoCore events to OpenEmotion events.
"""

from typing import Optional, Dict, Any
from datetime import datetime

from app.integrations.openemotion.types import (
    OpenEmotionEvent,
    OpenEmotionEventMeta,
    EventType,
    EventActor,
)


class EventAdapter:
    """
    Adapts EgoCore events to OpenEmotion events.
    
    Responsible for:
    - Mapping EgoCore message types to OpenEmotion event types
    - Extracting metadata (thread_id, task_id, intent, etc.)
    - Ensuring command messages don't pollute emotion analysis
    """
    
    @staticmethod
    def adapt_user_message(
        text: str,
        chat_id: str,
        user_id: str,
        thread_id: Optional[str] = None,
        task_id: Optional[str] = None,
        intent: Optional[str] = None,
        is_command: bool = False,
    ) -> OpenEmotionEvent:
        """
        Adapt a user message from Telegram.
        
        Args:
            text: User message text
            chat_id: Telegram chat ID
            user_id: Telegram user ID
            thread_id: Optional thread ID
            task_id: Optional task ID
            intent: Message intent (chat, question, new_task, etc.)
            is_command: Whether this is a command message
        
        Returns:
            OpenEmotionEvent
        """
        meta_dict: Dict[str, Any] = {
            "source": "telegram",
            "thread_id": thread_id or f"tg_{chat_id}",
        }
        
        if task_id:
            meta_dict["task_id"] = task_id
        if intent:
            meta_dict["intent"] = intent
        
        # Mark commands to avoid polluting emotion analysis
        if is_command:
            meta_dict["is_command"] = True
        
        return OpenEmotionEvent(
            type=EventType.USER_MESSAGE,
            actor=EventActor.USER,
            target="assistant",
            text=text,
            meta=meta_dict,
        )
    
    @staticmethod
    def adapt_assistant_reply(
        text: str,
        chat_id: str,
        thread_id: Optional[str] = None,
        task_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_status: Optional[str] = None,
    ) -> OpenEmotionEvent:
        """
        Adapt an assistant reply.
        
        Args:
            text: Assistant reply text
            chat_id: Telegram chat ID
            thread_id: Optional thread ID
            task_id: Optional task ID
            tool_name: Optional tool that was used
            tool_status: Optional tool execution status
        
        Returns:
            OpenEmotionEvent
        """
        meta = OpenEmotionEventMeta(
            thread_id=thread_id or f"tg_{chat_id}",
            task_id=task_id,
            source="telegram",
            tool_name=tool_name,
            tool_status=tool_status,
        )
        
        return OpenEmotionEvent(
            type=EventType.ASSISTANT_REPLY,
            actor=EventActor.ASSISTANT,
            target="user",
            text=text,
            meta=meta.to_dict(),
        )
    
    @staticmethod
    def adapt_world_event(
        event_type: str,
        description: str,
        chat_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        task_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        tool_status: Optional[str] = None,
    ) -> OpenEmotionEvent:
        """
        Adapt a world event (tool execution, system event, etc.).
        
        Args:
            event_type: Type of world event
            description: Event description
            chat_id: Optional Telegram chat ID
            thread_id: Optional thread ID
            task_id: Optional task ID
            tool_name: Optional tool name
            tool_status: Optional tool status
        
        Returns:
            OpenEmotionEvent
        """
        meta = OpenEmotionEventMeta(
            thread_id=thread_id,
            task_id=task_id,
            source="telegram",
            tool_name=tool_name,
            tool_status=tool_status,
        )
        
        if chat_id and not meta.thread_id:
            meta.thread_id = f"tg_{chat_id}"
        
        meta_dict = meta.to_dict()
        meta_dict["event_type"] = event_type
        
        return OpenEmotionEvent(
            type=EventType.WORLD_EVENT,
            actor=EventActor.SYSTEM,
            target="assistant",
            text=description,
            meta=meta_dict,
        )
    
    @staticmethod
    def adapt_tool_execution(
        tool_name: str,
        status: str,
        chat_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        task_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> OpenEmotionEvent:
        """
        Adapt a tool execution event.
        
        Args:
            tool_name: Name of the tool
            status: Execution status (success, failed, etc.)
            chat_id: Optional Telegram chat ID
            thread_id: Optional thread ID
            task_id: Optional task ID
            error: Optional error message
        
        Returns:
            OpenEmotionEvent
        """
        description = f"Tool {tool_name} {status}"
        if error:
            description += f": {error[:100]}"
        
        return EventAdapter.adapt_world_event(
            event_type="tool_execution",
            description=description,
            chat_id=chat_id,
            thread_id=thread_id,
            task_id=task_id,
            tool_name=tool_name,
            tool_status=status,
        )
