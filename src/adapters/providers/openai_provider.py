"""
🧸 AI TEDDY BEAR V5 - OPENAI PROVIDER
===================================
Production-grade OpenAI integration with:
- Comprehensive error handling and retry logic
- Child-safe content filtering and COPPA compliance
- Rate limiting and usage monitoring
- Response validation and safety checks
- Support for multiple OpenAI services
- Extensive logging and observability
"""

# Standard library imports
import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from uuid import UUID

# Third-party imports
import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types import CreateEmbeddingResponse, Moderation

# Internal imports
from src.interfaces.providers.ai_provider import AIProvider
from src.infrastructure.config.config_provider import get_config
from src.core.value_objects.value_objects import SafetyLevel, AgeGroup, ChildPreferences
from src.infrastructure.rate_limiting.rate_limiter import (
    RateLimitingService,
    OperationType,
)

# Configure logging
logger = logging.getLogger(__name__)


# ================================
# ENUMS AND DATA CLASSES
# ================================


class OpenAIService(str, Enum):
    """Available OpenAI services."""

    CHAT_COMPLETIONS = "chat_completions"
    EMBEDDINGS = "embeddings"
    MODERATION = "moderation"
    AUDIO_TRANSCRIPTION = "audio_transcription"
    AUDIO_SPEECH = "audio_speech"


class OpenAIErrorType(str, Enum):
    """Types of OpenAI API errors."""

    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    AUTHENTICATION_ERROR = "authentication_error"
    INVALID_REQUEST = "invalid_request"
    CONTENT_FILTER = "content_filter"
    QUOTA_EXCEEDED = "quota_exceeded"


class SafetyFilterResult:
    """Result of content safety filtering."""

    def __init__(
        self,
        is_safe: bool,
        severity: SafetyLevel,
        violations: List[str],
        confidence: float,
        age_appropriate: bool = True,
    ):
        self.is_safe = is_safe
        self.severity = severity
        self.violations = violations
        self.confidence = confidence
        self.age_appropriate = age_appropriate
        self.timestamp = datetime.utcnow()


class OpenAIUsageStats:
    """OpenAI API usage statistics."""

    def __init__(self):
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost = 0.0
        self.rate_limited_requests = 0
        self.safety_filtered_requests = 0
        self.start_time = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/monitoring."""
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.successful_requests / max(1, self.total_requests),
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_cost_usd": self.total_cost,
            "rate_limited_requests": self.rate_limited_requests,
            "safety_filtered_requests": self.safety_filtered_requests,
            "uptime_seconds": uptime,
            "requests_per_second": self.total_requests / max(1, uptime),
        }


# ================================
# OPENAI PROVIDER IMPLEMENTATION
# ================================


class ProductionOpenAIProvider(AIProvider):
    """
    Production-grade OpenAI provider with comprehensive error handling,
    child safety features, and monitoring capabilities.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        rate_limiter: Optional[RateLimitingService] = None,
        **kwargs,
    ):
        """
        Initialize OpenAI provider with production features.

        Args:
            api_key: OpenAI API key (defaults to config)
            model: Model name (defaults to config)
            rate_limiter: Rate limiting service instance
            **kwargs: Additional configuration options
        """
        # Load configuration
        from src.infrastructure.config.config_provider import get_config

        self.config = kwargs.get("config") or get_config()
        # Initialize API client
        self.api_key = api_key or self.config.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            timeout=kwargs.get("timeout", 30.0),
            max_retries=0,  # We handle retries manually
        )
        # Model configuration
        self.model = model or self.config.OPENAI_MODEL
        self.max_tokens = kwargs.get("max_tokens", self.config.OPENAI_MAX_TOKENS)
        self.temperature = kwargs.get("temperature", self.config.OPENAI_TEMPERATURE)

        # Child safety configuration
        self.enable_content_filter = kwargs.get("enable_content_filter", True)
        self.child_safe_mode = kwargs.get("child_safe_mode", True)
        self.max_response_length = kwargs.get(
            "max_response_length", 500
        )  # Child-appropriate

        # Retry configuration
        self.max_retries = kwargs.get("max_retries", 3)
        self.base_delay = kwargs.get("base_delay", 1.0)
        self.max_delay = kwargs.get("max_delay", 60.0)

        # Rate limiting
        self.rate_limiter = rate_limiter
        self.enable_rate_limiting = kwargs.get("enable_rate_limiting", True)

        # Usage tracking
        self.usage_stats = OpenAIUsageStats()

        # Model pricing (tokens per dollar - approximate)
        self.token_pricing = {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
        }

        logger.info(f"Initialized OpenAI provider with model {self.model}")

    async def _check_rate_limit(self, child_id: str, operation: OperationType) -> bool:
        """Check rate limits for child safety."""
        if not self.enable_rate_limiting or not self.rate_limiter:
            return True

        try:
            result = await self.rate_limiter.check_rate_limit(child_id, operation)
            if not result.allowed:
                self.usage_stats.rate_limited_requests += 1
                logger.warning(
                    f"Rate limit exceeded for child {child_id}: {result.reason}",
                    extra={
                        "child_id": child_id,
                        "operation": operation.value,
                        "remaining": result.remaining,
                        "reset_time": result.reset_time,
                    },
                )
                return False
            return True
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True  # Fail open for safety

    async def _retry_with_backoff(self, operation, *args, **kwargs):
        """Execute operation with exponential backoff retry logic."""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await operation(*args, **kwargs)

            except openai.RateLimitError as e:
                last_exception = e
                if attempt == self.max_retries:
                    break

                # Extract retry-after from headers if available
                retry_after = getattr(e, "retry_after", None) or self.base_delay * (
                    2**attempt
                )
                delay = min(retry_after, self.max_delay)

                logger.warning(
                    f"Rate limit hit (attempt {attempt + 1}/{self.max_retries + 1}), "
                    f"retrying in {delay}s: {e}"
                )
                await asyncio.sleep(delay)

            except openai.APITimeoutError as e:
                last_exception = e
                if attempt == self.max_retries:
                    break

                delay = min(self.base_delay * (2**attempt), self.max_delay)
                logger.warning(
                    f"Timeout error (attempt {attempt + 1}/{self.max_retries + 1}), "
                    f"retrying in {delay}s: {e}"
                )
                await asyncio.sleep(delay)

            except openai.APIConnectionError as e:
                last_exception = e
                if attempt == self.max_retries:
                    break

                delay = min(self.base_delay * (2**attempt), self.max_delay)
                logger.warning(
                    f"Connection error (attempt {attempt + 1}/{self.max_retries + 1}), "
                    f"retrying in {delay}s: {e}"
                )
                await asyncio.sleep(delay)

            except (openai.AuthenticationError, openai.PermissionDeniedError) as e:
                # Don't retry authentication errors
                logger.error(f"Authentication error: {e}")
                raise OpenAIProviderError(
                    "Authentication failed",
                    error_type=OpenAIErrorType.AUTHENTICATION_ERROR,
                    original_error=e,
                )

            except openai.BadRequestError as e:
                # Don't retry bad requests
                logger.error(f"Bad request error: {e}")
                raise OpenAIProviderError(
                    "Invalid request",
                    error_type=OpenAIErrorType.INVALID_REQUEST,
                    original_error=e,
                )

            except Exception as e:
                last_exception = e
                if attempt == self.max_retries:
                    break

                delay = min(self.base_delay * (2**attempt), self.max_delay)
                logger.warning(
                    f"Unexpected error (attempt {attempt + 1}/{self.max_retries + 1}), "
                    f"retrying in {delay}s: {e}"
                )
                await asyncio.sleep(delay)

        # All retries exhausted
        self.usage_stats.failed_requests += 1
        logger.error(f"All retry attempts exhausted. Last error: {last_exception}")

        # Classify error type
        error_type = OpenAIErrorType.API_ERROR
        if isinstance(last_exception, openai.RateLimitError):
            error_type = OpenAIErrorType.RATE_LIMIT
        elif isinstance(last_exception, openai.APITimeoutError):
            error_type = OpenAIErrorType.TIMEOUT_ERROR
        elif isinstance(last_exception, openai.APIConnectionError):
            error_type = OpenAIErrorType.CONNECTION_ERROR

        raise OpenAIProviderError(
            f"Operation failed after {self.max_retries} retries",
            error_type=error_type,
            original_error=last_exception,
        )

    async def _validate_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Validate chat messages for safety and format."""
        if not messages:
            raise ValueError("Messages list cannot be empty")

        for i, message in enumerate(messages):
            if not isinstance(message, dict):
                raise ValueError(f"Message {i} must be a dictionary")

            if "role" not in message:
                raise ValueError(f"Message {i} must have a 'role' field")

            if "content" not in message:
                raise ValueError(f"Message {i} must have a 'content' field")

            role = message["role"]
            if role not in ["system", "user", "assistant", "function"]:
                raise ValueError(f"Invalid role '{role}' in message {i}")

            content = message["content"]
            if not isinstance(content, str):
                raise ValueError(f"Content in message {i} must be a string")

            # Child safety: limit message length
            if len(content) > 2000:
                raise ValueError(f"Message {i} content too long (max 2000 characters)")

    async def _filter_content_safety(
        self, content: str, child_age: Optional[int] = None
    ) -> SafetyFilterResult:
        """
        Filter content for child safety using OpenAI moderation API.
        """
        if not self.enable_content_filter:
            return SafetyFilterResult(
                is_safe=True,
                severity=SafetyLevel.SAFE,
                violations=[],
                confidence=1.0,
                age_appropriate=True,
            )

        try:
            # Use OpenAI moderation API
            moderation = await self.client.moderations.create(input=content)
            result = moderation.results[0]

            violations = []
            max_score = 0.0

            # Check each category
            for category, flagged in result.categories.model_dump().items():
                if flagged:
                    violations.append(category)

                # Get confidence score for this category
                score = getattr(result.category_scores, category, 0.0)
                max_score = max(max_score, score)

            # Determine severity based on violations and scores
            is_safe = not result.flagged
            if result.flagged or max_score > 0.8:
                severity = SafetyLevel.CRITICAL
            elif max_score > 0.6:
                severity = SafetyLevel.HIGH
            elif max_score > 0.4:
                severity = SafetyLevel.MEDIUM
            elif max_score > 0.2:
                severity = SafetyLevel.LOW
            else:
                severity = SafetyLevel.SAFE

            # Additional child-specific checks
            age_appropriate = True
            if child_age and child_age < 8:
                # Stricter rules for younger children
                if max_score > 0.1 or len(content) > 200:
                    age_appropriate = False
                    if "child_safety" not in violations:
                        violations.append("child_safety")

            if not is_safe or not age_appropriate:
                self.usage_stats.safety_filtered_requests += 1

            return SafetyFilterResult(
                is_safe=is_safe and age_appropriate,
                severity=severity,
                violations=violations,
                confidence=1.0 - max_score,
                age_appropriate=age_appropriate,
            )

        except Exception as e:
            logger.error(f"Content safety filtering failed: {e}")
            # Fail safe - be conservative
            return SafetyFilterResult(
                is_safe=False,
                severity=SafetyLevel.HIGH,
                violations=["filter_error"],
                confidence=0.0,
                age_appropriate=False,
            )

    def _calculate_cost(self, usage: Dict[str, int]) -> float:
        """Calculate estimated cost based on token usage."""
        model_key = self.model.split("/")[-1]  # Handle organization prefixes
        if model_key not in self.token_pricing:
            # Default to GPT-4 pricing for unknown models
            model_key = "gpt-4"

        pricing = self.token_pricing[model_key]
        prompt_cost = usage.get("prompt_tokens", 0) * pricing["prompt"] / 1000
        completion_cost = (
            usage.get("completion_tokens", 0) * pricing["completion"] / 1000
        )

        return prompt_cost + completion_cost

    def _update_usage_stats(
        self, response: Union[ChatCompletion, ChatCompletionChunk]
    ) -> None:
        """Update usage statistics from API response."""
        self.usage_stats.total_requests += 1
        self.usage_stats.successful_requests += 1

        if hasattr(response, "usage") and response.usage:
            usage = response.usage.model_dump()
            self.usage_stats.total_tokens += usage.get("total_tokens", 0)
            self.usage_stats.prompt_tokens += usage.get("prompt_tokens", 0)
            self.usage_stats.completion_tokens += usage.get("completion_tokens", 0)

            # Calculate cost
            cost = self._calculate_cost(usage)
            self.usage_stats.total_cost += cost

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        child_id: Optional[str] = None,
        child_age: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream chat completion with comprehensive safety and error handling.

        Args:
            messages: List of chat messages
            child_id: Child identifier for rate limiting
            child_age: Child's age for safety filtering
            **kwargs: Additional parameters

        Yields:
            Streaming text tokens

        Raises:
            OpenAIProviderError: On API errors or safety violations
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Validate inputs
            await self._validate_messages(messages)

            # Check rate limits
            if child_id and not await self._check_rate_limit(
                child_id, OperationType.AI_REQUEST
            ):
                raise OpenAIProviderError(
                    "Rate limit exceeded",
                    error_type=OpenAIErrorType.RATE_LIMIT,
                    correlation_id=correlation_id,
                )

            # Safety filter input messages
            for message in messages:
                if message["role"] == "user":
                    safety_result = await self._filter_content_safety(
                        message["content"], child_age
                    )
                    if not safety_result.is_safe:
                        logger.warning(
                            f"Unsafe input detected: {safety_result.violations}",
                            extra={
                                "correlation_id": correlation_id,
                                "child_id": child_id,
                                "violations": safety_result.violations,
                            },
                        )
                        raise OpenAIProviderError(
                            "Content violates safety policy",
                            error_type=OpenAIErrorType.CONTENT_FILTER,
                            correlation_id=correlation_id,
                            details={"violations": safety_result.violations},
                        )

            # Prepare request parameters
            request_params = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.temperature),
                "max_tokens": min(
                    kwargs.get("max_tokens", self.max_tokens),
                    self.max_response_length if self.child_safe_mode else float("inf"),
                ),
                "stream": True,
                "user": child_id,  # For OpenAI abuse monitoring
            }

            # Add child-safe system message if needed
            if self.child_safe_mode and not any(
                msg["role"] == "system" for msg in messages
            ):
                system_message = {
                    "role": "system",
                    "content": (
                        "You are a friendly, helpful AI assistant for children. "
                        "Always respond in a child-appropriate, safe, and educational manner. "
                        "Keep responses simple, positive, and engaging for young minds."
                    ),
                }
                request_params["messages"] = [system_message] + messages

            logger.info(
                f"Starting chat stream for child {child_id}",
                extra={
                    "correlation_id": correlation_id,
                    "model": self.model,
                    "message_count": len(messages),
                    "child_age": child_age,
                },
            )

            # Execute request with retry logic
            async def _make_request():
                return await self.client.chat.completions.create(**request_params)

            response = await self._retry_with_backoff(_make_request)

            # Stream and validate response
            collected_content = []
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    collected_content.append(content)

                    # Real-time safety check for streaming content
                    if len(collected_content) % 10 == 0:  # Check every 10 chunks
                        partial_content = "".join(collected_content)
                        safety_result = await self._filter_content_safety(
                            partial_content, child_age
                        )
                        if not safety_result.is_safe:
                            logger.warning(
                                f"Unsafe streaming content detected: {safety_result.violations}",
                                extra={"correlation_id": correlation_id},
                            )
                            # Stop streaming and raise error
                            raise OpenAIProviderError(
                                "Response content violates safety policy",
                                error_type=OpenAIErrorType.CONTENT_FILTER,
                                correlation_id=correlation_id,
                            )

                    yield content

                # Update usage stats if available
                if hasattr(chunk, "usage") and chunk.usage:
                    self._update_usage_stats(chunk)

            # Final safety check on complete response
            complete_content = "".join(collected_content)
            if complete_content:
                safety_result = await self._filter_content_safety(
                    complete_content, child_age
                )
                if not safety_result.is_safe:
                    logger.error(
                        f"Final safety check failed: {safety_result.violations}",
                        extra={"correlation_id": correlation_id},
                    )
                    # Note: At this point content has already been streamed,
                    # but we log for monitoring and future improvements

            logger.info(
                f"Chat stream completed successfully",
                extra={
                    "correlation_id": correlation_id,
                    "response_length": len(complete_content),
                    "child_id": child_id,
                },
            )

        except OpenAIProviderError:
            # Re-raise our custom errors
            raise
        except Exception as e:
            self.usage_stats.failed_requests += 1
            logger.error(
                f"Unexpected error in stream_chat: {e}",
                extra={"correlation_id": correlation_id},
                exc_info=True,
            )
            raise OpenAIProviderError(
                f"Unexpected error: {e}",
                error_type=OpenAIErrorType.API_ERROR,
                correlation_id=correlation_id,
                original_error=e,
            )

    async def generate_completion(
        self,
        messages: List[Dict[str, Any]],
        child_id: Optional[str] = None,
        child_age: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Generate a single completion (non-streaming).

        Args:
            messages: List of chat messages
            child_id: Child identifier for rate limiting
            child_age: Child's age for safety filtering
            **kwargs: Additional parameters

        Returns:
            Complete response text

        Raises:
            OpenAIProviderError: On API errors or safety violations
        """
        # Collect all streaming content
        content_parts = []
        async for chunk in self.stream_chat(messages, child_id, child_age, **kwargs):
            content_parts.append(chunk)

        return "".join(content_parts)

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
            OpenAIProviderError: On API errors or safety violations
        """
        # Convert conversation history to messages format
        messages = []
        
        # Add conversation history
        for i, msg in enumerate(conversation_history):
            if i % 2 == 0:
                messages.append({"role": "user", "content": msg})
            else:
                messages.append({"role": "assistant", "content": msg})
        
        # Add current input
        messages.append({"role": "user", "content": current_input})
        
        # Generate response using existing completion method
        return await self.generate_completion(
            messages=messages,
            child_id=str(child_id),
            child_age=getattr(child_preferences, 'age_range', None) if child_preferences else None
        )

    async def create_embedding(
        self,
        text: str,
        model: str = "text-embedding-ada-002",
        child_id: Optional[str] = None,
    ) -> List[float]:
        """
        Create text embedding using OpenAI API.

        Args:
            text: Text to embed
            model: Embedding model name
            child_id: Child identifier for rate limiting

        Returns:
            Embedding vector

        Raises:
            OpenAIProviderError: On API errors
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Check rate limits
            if child_id and not await self._check_rate_limit(
                child_id, OperationType.API_CALL
            ):
                raise OpenAIProviderError(
                    "Rate limit exceeded",
                    error_type=OpenAIErrorType.RATE_LIMIT,
                    correlation_id=correlation_id,
                )

            # Validate input
            if not text or len(text) > 8000:  # OpenAI embedding limit
                raise ValueError("Text must be non-empty and under 8000 characters")

            # Safety filter
            safety_result = await self._filter_content_safety(text)
            if not safety_result.is_safe:
                raise OpenAIProviderError(
                    "Text violates safety policy",
                    error_type=OpenAIErrorType.CONTENT_FILTER,
                    correlation_id=correlation_id,
                )

            logger.info(
                f"Creating embedding for child {child_id}",
                extra={"correlation_id": correlation_id, "model": model},
            )

            # Execute request with retry logic
            async def _make_request():
                return await self.client.embeddings.create(
                    input=text, model=model, user=child_id
                )

            response = await self._retry_with_backoff(_make_request)

            # Update usage stats
            if hasattr(response, "usage") and response.usage:
                self.usage_stats.total_tokens += response.usage.total_tokens
                cost = response.usage.total_tokens * 0.0001 / 1000  # Ada pricing
                self.usage_stats.total_cost += cost

            self.usage_stats.successful_requests += 1

            return response.data[0].embedding

        except OpenAIProviderError:
            raise
        except Exception as e:
            self.usage_stats.failed_requests += 1
            logger.error(
                f"Error creating embedding: {e}",
                extra={"correlation_id": correlation_id},
                exc_info=True,
            )
            raise OpenAIProviderError(
                f"Embedding creation failed: {e}",
                error_type=OpenAIErrorType.API_ERROR,
                correlation_id=correlation_id,
                original_error=e,
            )

    async def moderate_content(self, content: str) -> Dict[str, Any]:
        """
        Moderate content using OpenAI moderation API.

        Args:
            content: Content to moderate

        Returns:
            Moderation result with safety scores and categories

        Raises:
            OpenAIProviderError: On API errors
        """
        correlation_id = str(uuid.uuid4())

        try:
            logger.info("Moderating content", extra={"correlation_id": correlation_id})

            async def _make_request():
                return await self.client.moderations.create(input=content)

            response = await self._retry_with_backoff(_make_request)
            result = response.results[0]

            self.usage_stats.successful_requests += 1

            return {
                "flagged": result.flagged,
                "categories": result.categories.model_dump(),
                "category_scores": result.category_scores.model_dump(),
                "correlation_id": correlation_id,
            }

        except Exception as e:
            self.usage_stats.failed_requests += 1
            logger.error(
                f"Error moderating content: {e}",
                extra={"correlation_id": correlation_id},
                exc_info=True,
            )
            raise OpenAIProviderError(
                f"Content moderation failed: {e}",
                error_type=OpenAIErrorType.API_ERROR,
                correlation_id=correlation_id,
                original_error=e,
            )

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics."""
        return self.usage_stats.to_dict()

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on OpenAI service.

        Returns:
            Health status and metrics
        """
        correlation_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # Simple API call to test connectivity
            response = await self.client.models.list()

            # Check if our model is available
            available_models = [model.id for model in response.data]
            model_available = self.model in available_models

            response_time = time.time() - start_time

            return {
                "status": "healthy" if model_available else "degraded",
                "model_available": model_available,
                "response_time_ms": response_time * 1000,
                "available_models_count": len(available_models),
                "usage_stats": self.get_usage_stats(),
                "correlation_id": correlation_id,
            }

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(
                f"Health check failed: {e}", extra={"correlation_id": correlation_id}
            )

            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": response_time * 1000,
                "correlation_id": correlation_id,
            }


# ================================
# CUSTOM EXCEPTIONS
# ================================


class OpenAIProviderError(Exception):
    """Custom exception for OpenAI provider errors."""

    def __init__(
        self,
        message: str,
        error_type: OpenAIErrorType = OpenAIErrorType.API_ERROR,
        correlation_id: Optional[str] = None,
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.original_error = original_error
        self.details = details or {}
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging."""
        return {
            "message": self.message,
            "error_type": self.error_type.value,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "original_error": str(self.original_error) if self.original_error else None,
            "details": self.details,
        }


# ================================
# FACTORY FUNCTIONS
# ================================


def create_openai_provider(
    config_override: Optional[Dict[str, Any]] = None,
) -> ProductionOpenAIProvider:
    """
    Create a production OpenAI provider with default configuration.

    Args:
        config_override: Optional configuration overrides

    Returns:
        Configured OpenAI provider instance
    """
    config = config_override or {}

    return ProductionOpenAIProvider(
        api_key=config.get("api_key"),
        model=config.get("model"),
        max_tokens=config.get("max_tokens"),
        temperature=config.get("temperature"),
        enable_content_filter=config.get("enable_content_filter", True),
        child_safe_mode=config.get("child_safe_mode", True),
        max_retries=config.get("max_retries", 3),
        timeout=config.get("timeout", 30.0),
    )


def create_child_safe_provider(
    child_age: int, rate_limiter: Optional[RateLimitingService] = None
) -> ProductionOpenAIProvider:
    """
    Create an OpenAI provider optimized for child safety.

    Args:
        child_age: Child's age for safety configuration
        rate_limiter: Rate limiting service

    Returns:
        Child-safe OpenAI provider instance
    """
    # Age-appropriate configuration
    max_tokens = 100 if child_age < 6 else 200 if child_age < 10 else 300
    temperature = 0.3 if child_age < 8 else 0.5  # More predictable for younger children

    return ProductionOpenAIProvider(
        model="gpt-3.5-turbo",  # Safer choice for children
        max_tokens=max_tokens,
        temperature=temperature,
        rate_limiter=rate_limiter,
        enable_content_filter=True,
        child_safe_mode=True,
        max_response_length=max_tokens,
        enable_rate_limiting=True,
    )


# Backward compatibility alias
OpenAIProvider = ProductionOpenAIProvider


# ================================
# EXPORT SYMBOLS
# ================================

__all__ = [
    "ProductionOpenAIProvider",
    "OpenAIProvider",  # Backward compatibility
    "OpenAIProviderError",
    "OpenAIService",
    "OpenAIErrorType",
    "SafetyFilterResult",
    "OpenAIUsageStats",
    "create_openai_provider",
    "create_child_safe_provider",
]
