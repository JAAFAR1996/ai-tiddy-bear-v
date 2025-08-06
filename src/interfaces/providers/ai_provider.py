"""
AIProvider interface for all AI chat/generation providers.
Depends on: nothing (pure interface)
Security: All implementations must enforce child safety and COPPA compliance at the service layer.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, List
from uuid import UUID
from src.core.value_objects.value_objects import ChildPreferences


class AIProvider(ABC):
    @abstractmethod
    async def generate_response(
        self,
        child_id: UUID,
        conversation_history: List[str],
        current_input: str,
        child_preferences: Optional[ChildPreferences] = None,
    ) -> str:
        """
        Generate a child-safe AI response based on conversation context.
        
        Args:
            child_id: Unique identifier for the child user
            conversation_history: List of previous conversation messages
            current_input: Current user input to respond to
            child_preferences: Optional child preferences for personalization
            
        Returns:
            Generated AI response content
            
        Raises:
            ServiceUnavailableError: When AI provider is unavailable
            AITimeoutError: When response generation times out
            InvalidInputError: When input is invalid or unsafe
        """
        pass

    @abstractmethod
    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        """
        Stream chat completions from the provider (legacy method).
        
        Args:
            messages: List of message dictionaries with role/content
            
        Yields:
            Streaming response chunks
        """
        pass
