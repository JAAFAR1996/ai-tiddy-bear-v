from src.infrastructure.exceptions import (
    AIServiceError,
    AIContentFilterError,
)
from src.core.exceptions import (
    SafetyViolationError,
)
from src.interfaces.providers.ai_provider import AIProvider


# Core Services - Clean, organized, and PEP8-compliant
# Note: AuthService has been moved to src.infrastructure.security.auth for production use


import structlog
from typing import List, Optional
from src.core.entities import Message, AIResponse

logger = structlog.get_logger(__name__)


# SafetyService has been consolidated into ChildSafetyService
# Import the unified service for backward compatibility
from src.application.services.child_safety_service import (
    ChildSafetyService as SafetyService,
)


# Rate limiting has been moved to unified RateLimitingService
from src.infrastructure.rate_limiting.rate_limiter import (
    RateLimitingService,
    OperationType,
)


class ChatService:
    """Consolidated chat service with AI integration and safety"""

    def __init__(
        self,
        ai_provider: AIProvider = None,
        safety_service: Optional[SafetyService] = None,
        rate_limiter: Optional[RateLimitingService] = None,
        config=None,
    ):
        # Import locally to avoid circular imports during module initialization
        if config is None:
            # Production: config must be passed from caller
            raise ValueError("Config must be passed to AIServiceManager - no global access in production")

        from src.infrastructure.rate_limiting.rate_limiter import (
            create_rate_limiting_service,
        )

        if config is None:
            raise ValueError("get_openai_provider requires config parameter - no global fallback in production")
        if ai_provider is not None:
            self.ai_provider = ai_provider
        else:
            from src.adapters.providers.openai_provider import OpenAIProvider

            self.ai_provider = OpenAIProvider(
                api_key=config.OPENAI_API_KEY,
                model=getattr(config, "OPENAI_MODEL", "gpt-4-turbo-preview"),
                max_tokens=getattr(config, "OPENAI_MAX_TOKENS", 200),
                temperature=getattr(config, "OPENAI_TEMPERATURE", 0.7),
            )
        self.safety_service = safety_service or SafetyService(config)
        self.rate_limiter = rate_limiter or create_rate_limiting_service()
        self.child_safety_rules = getattr(
            config,
            "CHILD_SAFETY_RULES",
            [
                "Always use child-friendly language",
                "Avoid scary or violent content",
                "Keep responses age-appropriate",
                "Encourage learning and creativity",
                "Be supportive and positive",
                "Don't discuss adult topics",
                "Redirect inappropriate questions to safe topics",
            ],
        )

    async def generate_response(
        self,
        user_message: str,
        child_age: int,
        child_name: str = "friend",
        conversation_history: List[Message] = None,
        user_id: str = None,
    ) -> AIResponse:
        """Generate AI response with safety filtering - consolidated implementation"""

        # --- Rate limiting using unified service ---
        rate_result = await self.rate_limiter.check_rate_limit(
            child_id=user_id or "anonymous",
            operation=OperationType.AI_REQUEST,
            child_age=child_age,
        )
        if not rate_result.allowed:
            raise AIServiceError(
                f"Rate limit exceeded: {rate_result.reason}",
                context={
                    "safety": True,
                    "location": "generate_response",
                    "user_id": user_id,
                    "remaining": rate_result.remaining,
                },
            )

        # Pre-filter user message
        safety_result = self.safety_service.analyze_content(user_message, child_age)
        if not safety_result.is_safe:
            raise SafetyViolationError(
                "User message failed safety check",
                violations=safety_result.violations,
                context={
                    "safety": True,
                    "location": "generate_response",
                    "input": user_message,
                },
            )

        # Build system prompt - extracted from existing implementation
        system_prompt = self._build_system_prompt(child_age, child_name)
        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            for msg in conversation_history[-5:]:
                messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_message})
        try:
            # Call AIProvider abstraction
            content_chunks = []
            async for chunk in self.ai_provider.stream_chat(messages):
                content_chunks.append(chunk)
            ai_content = "".join(content_chunks).strip()
            # Post-filter AI response
            ai_safety = self.safety_service.analyze_content(ai_content, child_age)
            if not ai_safety.is_safe:
                raise AIContentFilterError(
                    "AI response failed post-generation safety check",
                    context={
                        "safety": True,
                        "location": "generate_response",
                        "output": ai_content,
                        "violations": ai_safety.violations,
                    },
                )
            return AIResponse(
                content=ai_content,
                safety_score=ai_safety.safety_score,
                age_appropriate=ai_safety.age_appropriate,
            )
        except Exception as e:
            from uuid import uuid4

            correlation_id = str(uuid4())
            logger.error(
                "AI response generation failed",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                user_message=user_message[:100],
                child_age=child_age,
            )
            raise AIServiceError(
                f"AI response generation failed: {str(e)}",
                context={
                    "correlation_id": correlation_id,
                    "location": "generate_response",
                    "user_message": user_message[:100],
                    "child_age": child_age,
                    "safety": True,
                },
            )

    def _build_system_prompt(self, child_age: int, child_name: str) -> str:
        """Build system prompt - extracted from existing implementation"""
        prompt = (
            f"You are a friendly, safe, and supportive AI Teddy Bear for {child_name}, "
            f"who is {child_age} years old. Your primary goal is to provide a positive "
            f"and educational experience. Follow these rules strictly:\n"
        )

        for rule in self.child_safety_rules:
            prompt += f"- {rule}\n"

        prompt += (
            "\nRemember to be gentle, patient, and encouraging in all your responses."
        )
        return prompt

    def _get_safe_redirect_response(self) -> str:
        """Get safe redirect response - extracted from existing implementation"""
        safe_responses = [
            "Let's talk about something fun instead! What's your favorite animal?",
            "How about we discuss your favorite colors or shapes?",
            "Let's explore something exciting like space or nature!",
            "What games do you like to play? I'd love to hear about them!",
            "Tell me about your favorite story or book!",
        ]
        import random

        return random.choice(safe_responses)


# ConversationService has been moved to unified ConsolidatedConversationService
from src.services.conversation_service import (
    ConsolidatedConversationService as ConversationService,
)
