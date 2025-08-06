"""Consolidated Conversation Service - Unified Chat and Interaction Management

This consolidated service replaces 4+ fragmented conversation services:
- core/conversation_service.py (ConversationService)
- core/interaction_service.py (InteractionService)
- core/notification_service.py (NotificationService)
- core/incident_service.py (IncidentService)

Provides unified interface for:
- Complete conversation lifecycle management
- Real-time interaction handling and coordination
- Message history and context preservation
- Conversation analytics and insights
- Notification management and delivery
- Incident tracking and safety monitoring
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from enum import Enum
from weakref import WeakValueDictionary

from src.core.entities import Conversation, Message
from src.core.repositories import IConversationRepository as ConversationRepository
from src.interfaces.services import IConversationService
from src.core.exceptions import (
    ConversationNotFoundError,
    InvalidInputError,
    ServiceUnavailableError,
)
from src.infrastructure.monitoring.conversation_service_metrics import (
    create_conversation_metrics,
    MetricLevel,
)
from src.infrastructure.database.models import Interaction as InteractionModel
from src.infrastructure.database.database_manager import get_db


class MessageType(Enum):
    """Types of messages in conversations."""

    USER_INPUT = "user_input"
    AI_RESPONSE = "ai_response"
    SYSTEM_MESSAGE = "system_message"
    SAFETY_ALERT = "safety_alert"
    NOTIFICATION = "notification"


class ConversationStatus(Enum):
    """Conversation status types."""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    UNDER_REVIEW = "under_review"


class InteractionType(Enum):
    """Types of interactions."""

    CHAT = "chat"
    VOICE = "voice"
    GAME = "game"
    STORY = "story"
    LEARNING = "learning"


class IncidentSeverity(Enum):
    """Incident severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConsolidatedConversationService(IConversationService):
    """Unified conversation service consolidating all chat and interaction functionality.

    This service replaces multiple scattered conversation services and provides:
    - Complete conversation lifecycle management
    - Real-time message handling and history
    - Interaction coordination and analytics
    - Safety monitoring and incident management
    - Notification delivery and management
    - Context preservation and conversation insights
    """

    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository=None,
        notification_service=None,
        logger=None,
        max_conversation_length: int = 100,
        context_window_size: int = 10,
        enable_metrics: bool = True,
        metrics_level: MetricLevel = MetricLevel.DETAILED,
        conversation_cache_service=None,
    ) -> None:
        """Initialize consolidated conversation service.

        Args:
            conversation_repository: Repository for conversation persistence
            message_repository: Repository for message persistence
            notification_service: External notification service
            max_conversation_length: Maximum messages per conversation
            context_window_size: Number of recent messages to include in context
            enable_metrics: Enable production monitoring and metrics
            metrics_level: Level of metrics collection
            conversation_cache_service: Redis cache service for conversations
        """
        self.conversation_repo = conversation_repository
        self.message_repo = message_repository
        self.notification_service = notification_service
        self.max_conversation_length = max_conversation_length
        self.context_window_size = context_window_size

        # Redis Cache Service for enhanced performance
        self.conversation_cache = conversation_cache_service

        # Active conversations cache (fallback for when Redis cache is unavailable)
        self._active_conversations: Dict[UUID, "Conversation"] = {}

        # Optimized lock management - use WeakValueDictionary to auto-cleanup
        self._conversation_locks: WeakValueDictionary[UUID, asyncio.Lock] = (
            WeakValueDictionary()
        )
        self._lock_creation_lock = (
            asyncio.Lock()
        )  # Only for lock creation, not conversation access

        # Analytics tracking
        self.conversation_count = 0
        self.message_count = 0
        self.safety_incidents = 0
        self.notification_count = 0

        # Safety monitoring
        self.safety_keywords = [
            "personal information",
            "address",
            "phone",
            "email",
            "scared",
            "uncomfortable",
            "inappropriate",
            "unsafe",
        ]

        self.logger = logger

        # Initialize production monitoring
        self.metrics = None
        if enable_metrics:
            self.metrics = create_conversation_metrics(
                service_name="consolidated_conversation_service",
                metric_level=metrics_level,
            )
            # Update service health
            self.metrics.update_service_health(
                healthy=True,
                dependencies={
                    "conversation_repository": self.conversation_repo is not None,
                    "message_repository": self.message_repo is not None,
                    "notification_service": self.notification_service is not None,
                },
            )

        if self.logger:
            self.logger.info(
                "Consolidated Conversation Service initialized successfully",
                extra={
                    "metrics_enabled": enable_metrics,
                    "metrics_level": metrics_level.value if enable_metrics else None,
                },
            )

    # CONVERSATION LIFECYCLE METHODS

    async def start_new_conversation(
        self,
        child_id: UUID,
        initial_message: str,
        interaction_type: InteractionType = InteractionType.CHAT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Conversation:
        """Start a new conversation for a child.

        Args:
            child_id: Child's unique identifier
            initial_message: First message in the conversation
            interaction_type: Type of interaction (chat, voice, etc.)
            metadata: Additional conversation metadata

        Returns:
            Created conversation entity
        """
        try:
            # Create new conversation
            conversation = Conversation(
                id=uuid4(),
                child_id=child_id,
                status=ConversationStatus.ACTIVE.value,
                interaction_type=interaction_type.value,
                started_at=datetime.now(),
                metadata=metadata or {},
                message_count=0,
                context_summary="",
            )

            # Save conversation
            await self.conversation_repo.create(conversation)

            # Add initial message
            if initial_message.strip():
                await self.add_message_internal(
                    conversation_id=conversation.id,
                    message_type=MessageType.USER_INPUT,
                    content=initial_message,
                    sender_id=child_id,
                )

            # Cache active conversation in both local and Redis cache
            self._active_conversations[conversation.id] = conversation
            self._conversation_locks[conversation.id] = asyncio.Lock()

            # Cache in Redis for enhanced performance
            if self.conversation_cache:
                try:
                    await self.conversation_cache.cache_conversation(conversation)
                    if self.logger:
                        safe_conv_id = (
                            str(conversation.id)
                            .replace("\n", "")
                            .replace("\r", "")[:50]
                        )
                        self.logger.debug(
                            f"Conversation {safe_conv_id} cached in Redis successfully"
                        )
                except Exception as e:
                    if self.logger:
                        safe_conv_id = (
                            str(conversation.id)
                            .replace("\n", "")
                            .replace("\r", "")[:50]
                        )
                        safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                        self.logger.warning(
                            f"Failed to cache new conversation {safe_conv_id} in Redis: {safe_error}"
                        )

            self.conversation_count += 1

            # Track metrics
            if self.metrics:
                self.metrics.conversation_started(
                    conversation_id=str(conversation.id),
                    child_id=str(child_id),
                    interaction_type=interaction_type.value,
                )

            if self.logger:
                # Sanitize IDs for logging
                safe_conv_id = str(conversation.id).replace("\n", "").replace("\r", "")
                safe_child_id = str(child_id).replace("\n", "").replace("\r", "")
                self.logger.info(
                    f"Started new conversation {safe_conv_id} for child {safe_child_id}",
                    extra={
                        "conversation_id": safe_conv_id,
                        "interaction_type": interaction_type.value,
                    },
                )
            return conversation

        except (ValueError, ServiceUnavailableError) as e:
            if self.logger:
                # Sanitize child_id for logging
                safe_child_id = str(child_id).replace("\n", "").replace("\r", "")[:50]
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.error(
                    f"Failed to start conversation for child {safe_child_id}: {safe_error}",
                    exc_info=True,
                )
            raise
        except (
            Exception
        ) as e:  # noqa: BLE001 - Catching broad exception here for audit logging
            if self.logger:
                self.logger.error(
                    f"Unexpected error in start_new_conversation for child {child_id}",
                    exc_info=True,
                )
            raise ServiceUnavailableError(f"Failed to start conversation: {e}")

    async def get_conversation_internal(self, conversation_id: UUID) -> Conversation:
        """Get conversation by ID with Redis Cache optimization.

        Args:
            conversation_id: Conversation's unique identifier

        Returns:
            Conversation entity
        """
        # Try Redis Cache first (if available)
        if self.conversation_cache:
            try:
                cached_data = await self.conversation_cache.get_conversation(
                    conversation_id
                )
                if cached_data:
                    # Convert cached data back to Conversation entity
                    conversation_dict = cached_data.to_conversation()
                    conversation = Conversation(
                        id=UUID(conversation_dict["id"]),
                        child_id=UUID(conversation_dict["child_id"]),
                        status=conversation_dict["status"],
                        interaction_type=conversation_dict["interaction_type"],
                        message_count=conversation_dict["message_count"],
                        last_message_at=(
                            datetime.fromisoformat(conversation_dict["last_message_at"])
                            if conversation_dict["last_message_at"]
                            else None
                        ),
                        context_summary=conversation_dict["context_summary"],
                        metadata=conversation_dict["metadata"],
                    )

                    # Also update local cache
                    self._active_conversations[conversation_id] = conversation
                    if conversation_id not in self._conversation_locks:
                        self._conversation_locks[conversation_id] = asyncio.Lock()

                    return conversation
            except Exception as e:
                if self.logger:
                    safe_conv_id = (
                        str(conversation_id).replace("\n", "").replace("\r", "")[:50]
                    )
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.warning(
                    f"Redis cache error for conversation {safe_conv_id}: {safe_error}"
                )

        # Check local cache
        if conversation_id in self._active_conversations:
            return self._active_conversations[conversation_id]

        # Load from repository
        conversation = await self.conversation_repo.get_by_id(conversation_id)
        if not conversation:
            raise ConversationNotFoundError(
                f"Conversation not found: {conversation_id}"
            )

        # Cache in both Redis and local cache if active
        if conversation.status == ConversationStatus.ACTIVE.value:
            self._active_conversations[conversation_id] = conversation
            self._conversation_locks[conversation_id] = asyncio.Lock()

            # Also cache in Redis
            if self.conversation_cache:
                try:
                    await self.conversation_cache.cache_conversation(conversation)
                except Exception as e:
                    if self.logger:
                        self.logger.warning(
                            f"Failed to cache conversation {conversation_id} in Redis: {e}"
                        )

        return conversation

    async def get_conversations_for_child(
        self,
        child_id: UUID,
        limit: int = 10,
        include_completed: bool = False,
    ) -> List[Conversation]:
        """Get conversations for a child.

        Args:
            child_id: Child's unique identifier
            limit: Maximum number of conversations to return
            include_completed: Include completed conversations

        Returns:
            List of conversation entities
        """
        try:
            conversations = await self.conversation_repo.get_by_child_id(
                child_id=child_id,
                limit=limit,
                include_completed=include_completed,
            )

            return conversations or []

        except (ValueError, ServiceUnavailableError) as e:
            if self.logger:
                # Sanitize child_id for logging
                safe_child_id = str(child_id).replace("\n", "").replace("\r", "")[:50]
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.error(
                    f"Failed to get conversations for child {safe_child_id}: {safe_error}",
                    exc_info=True,
                )
            return []
        except (
            Exception
        ) as e:  # noqa: BLE001 - Catching broad exception here for audit logging
            if self.logger:
                self.logger.error(
                    f"Unexpected error in get_conversations_for_child for child {child_id}",
                    exc_info=True,
                )
            return []

    async def end_conversation(
        self,
        conversation_id: UUID,
        reason: str = "completed",
        summary: Optional[str] = None,
    ) -> Conversation:
        """End an active conversation.

        Args:
            conversation_id: Conversation's unique identifier
            reason: Reason for ending conversation
            summary: Optional conversation summary

        Returns:
            Updated conversation entity
        """
        async with self._get_conversation_lock(conversation_id):
            conversation = await self.get_conversation_internal(conversation_id)

            # Update conversation status
            conversation.status = ConversationStatus.COMPLETED.value
            conversation.ended_at = datetime.now()

            # Track metrics
            if self.metrics:
                self.metrics.conversation_ended(
                    conversation_id=str(conversation_id),
                    reason=reason,
                    final_message_count=conversation.message_count,
                )
            conversation.metadata["end_reason"] = reason

            if summary:
                conversation.context_summary = summary
            else:
                # Generate automatic summary
                conversation.context_summary = (
                    await self._generate_conversation_summary(conversation_id)
                )

            # Save updated conversation
            await self.conversation_repo.update(conversation)

            # Remove from both local and Redis caches
            self._active_conversations.pop(conversation_id, None)
            self._conversation_locks.pop(conversation_id, None)

            # Remove from Redis cache
            if self.conversation_cache:
                try:
                    await self.conversation_cache.remove_conversation(conversation_id)
                    if self.logger:
                        safe_conv_id = (
                            str(conversation_id)
                            .replace("\n", "")
                            .replace("\r", "")[:50]
                        )
                        self.logger.debug(
                            f"Conversation {safe_conv_id} removed from Redis cache"
                        )
                except Exception as e:
                    if self.logger:
                        safe_conv_id = (
                            str(conversation_id)
                            .replace("\n", "")
                            .replace("\r", "")[:50]
                        )
                        safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                        self.logger.warning(
                            f"Failed to remove conversation {safe_conv_id} from Redis cache: {safe_error}"
                        )

            if self.logger:
                # Sanitize IDs and reason for logging
                safe_conv_id = str(conversation_id).replace("\n", "").replace("\r", "")
                safe_reason = reason.replace("\n", "").replace("\r", "")[:100]
                self.logger.info(f"Ended conversation {safe_conv_id}: {safe_reason}")
            return conversation

    # MESSAGE HANDLING METHODS

    async def add_message_internal(
        self,
        conversation_id: UUID,
        message_type: MessageType,
        content: str,
        sender_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """Add a message to a conversation.

        Args:
            conversation_id: Conversation's unique identifier
            message_type: Type of message
            content: Message content
            sender_id: ID of message sender
            metadata: Additional message metadata

        Returns:
            Created message entity
        """
        import time

        start_time = time.time()

        async with self._get_conversation_lock(conversation_id):
            # Validate conversation exists and is active
            conversation = await self.get_conversation_internal(conversation_id)

            if conversation.status not in [ConversationStatus.ACTIVE.value]:
                raise InvalidInputError(
                    f"Cannot add message to {conversation.status} conversation"
                )

            # Check conversation length limits
            if conversation.message_count >= self.max_conversation_length:
                await self._handle_conversation_overflow(conversation_id)

            # Create message
            message = Message(
                id=uuid4(),
                conversation_id=conversation_id,
                message_type=message_type.value,
                content=content,
                sender_id=sender_id,
                timestamp=datetime.now(),
                metadata=metadata or {},
            )

            # Enhanced real-time safety monitoring for user messages
            if message_type == MessageType.USER_INPUT:
                # Use enhanced safety service if available
                if hasattr(self, 'safety_service') and hasattr(self.safety_service, 'monitor_conversation_real_time'):
                    try:
                        # Get child age from conversation context
                        child_age = conversation.metadata.get('child_age', 8)
                        child_id = conversation.metadata.get('child_id')
                        
                        if child_id:
                            from uuid import UUID
                            safety_result = await self.safety_service.monitor_conversation_real_time(
                                conversation_id=UUID(str(conversation_id)),
                                child_id=UUID(child_id),
                                message_content=content,
                                child_age=child_age
                            )
                            
                            # Handle safety actions
                            for action in safety_result.get('monitoring_actions', []):
                                if action['action'] == 'BLOCK_CONVERSATION':
                                    await self._handle_conversation_block(conversation_id, action['reason'])
                                    return message  # Block further processing
                                elif action['action'] == 'EMERGENCY_ALERT':
                                    await self._handle_emergency_alert(conversation_id, safety_result)
                                elif action['action'] == 'NOTIFY_PARENT':
                                    await self._schedule_parent_notification(conversation_id, safety_result)
                        else:
                            # Fallback to basic safety check
                            safety_result = await self._check_message_safety(content)
                    except Exception as e:
                        self.logger.error(f"Enhanced safety monitoring failed: {e}")
                        # Fallback to basic safety check
                        safety_result = await self._check_message_safety(content)
                else:
                    # Basic safety check
                    safety_result = await self._check_message_safety(content)
                
                # Handle safety incidents if needed
                if not safety_result.get("is_safe", True):
                    await self._handle_safety_incident(
                        conversation_id=conversation_id,
                        message=message,
                        safety_result=safety_result,
                    )

            # Save message
            if self.message_repo:
                await self.message_repo.create(message)

            # Update conversation
            conversation.message_count += 1
            conversation.last_message_at = message.timestamp
            conversation.updated_at = datetime.now()
            await self.conversation_repo.update(conversation)

            # Update caches (both local and Redis)
            self._active_conversations[conversation_id] = conversation

            # Cache message in Redis
            if self.conversation_cache:
                try:
                    await self.conversation_cache.cache_message(
                        message, conversation_id
                    )
                    # Update conversation in Redis cache
                    await self.conversation_cache.update_conversation(
                        conversation_id,
                        {
                            "message_count": conversation.message_count,
                            "last_message_at": conversation.last_message_at.isoformat(),
                        },
                    )
                except Exception as e:
                    if self.logger:
                        safe_msg_id = (
                            str(message.id).replace("\n", "").replace("\r", "")[:50]
                        )
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.warning(
                    f"Failed to cache message {safe_msg_id} in Redis: {safe_error}"
                )

            self.message_count += 1

            # Track metrics
            processing_time_ms = (time.time() - start_time) * 1000
            if self.metrics:
                self.metrics.message_processed(
                    conversation_id=str(conversation_id),
                    message_type=message_type.value,
                    processing_time_ms=processing_time_ms,
                    safety_status="safe",  # Assumed safe if we got here
                    success=True,
                )

            if self.logger:
                # Sanitize conversation_id for logging
                safe_conv_id = str(conversation_id).replace("\n", "").replace("\r", "")
                self.logger.debug(
                    f"Added {message_type.value} message to conversation {safe_conv_id}",
                    extra={
                        "processing_time_ms": processing_time_ms,
                        "message_type": message_type.value,
                    },
                )
            return message

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        limit: Optional[int] = None,
        include_system_messages: bool = False,
    ) -> List[Message]:
        """Get messages for a conversation with Redis Cache optimization.

        Args:
            conversation_id: Conversation's unique identifier
            limit: Maximum number of messages to return
            include_system_messages: Include system messages

        Returns:
            List of message entities
        """
        # Try Redis Cache first (if available)
        if self.conversation_cache:
            try:
                cached_messages = (
                    await self.conversation_cache.get_conversation_messages(
                        conversation_id,
                        limit=limit or 50,
                        include_flagged=include_system_messages,
                    )
                )

                if cached_messages:
                    # Convert cached messages back to Message entities
                    messages = []
                    for cached_msg in cached_messages:
                        message_dict = cached_msg.to_message()
                        message = Message(
                            id=UUID(message_dict["id"]),
                            conversation_id=UUID(message_dict["conversation_id"]),
                            message_type=message_dict["message_type"],
                            content=message_dict["content"],
                            sender_id=(
                                UUID(message_dict["sender_id"])
                                if message_dict["sender_id"]
                                else None
                            ),
                            timestamp=datetime.fromisoformat(message_dict["timestamp"]),
                            metadata=message_dict["metadata"],
                        )
                        messages.append(message)

                    return messages
            except Exception as e:
                if self.logger:
                    safe_conv_id = (
                        str(conversation_id).replace("\n", "").replace("\r", "")[:50]
                    )
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.warning(
                    f"Redis cache error for messages {safe_conv_id}: {safe_error}"
                )

        # Fallback to repository
        if not self.message_repo:
            return []

        try:
            messages = await self.message_repo.get_by_conversation_id(
                conversation_id=conversation_id,
                limit=limit,
                include_system_messages=include_system_messages,
            )

            return messages or []

        except (ValueError, ServiceUnavailableError) as e:
            if self.logger:
                self.logger.error(
                    f"Failed to get messages for conversation {conversation_id}: {e}",
                    exc_info=True,
                )
            return []
        except (
            Exception
        ) as e:  # noqa: BLE001 - Catching broad exception here for audit logging
            if self.logger:
                self.logger.error(
                    f"Unexpected error in get_conversation_messages for conversation {conversation_id}",
                    exc_info=True,
                )
            return []

    async def get_conversation_context(
        self,
        conversation_id: UUID,
        window_size: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent conversation context for AI processing with Redis Cache optimization.

        Args:
            conversation_id: Conversation's unique identifier
            window_size: Number of recent messages to include

        Returns:
            List of recent messages formatted for AI context
        """
        window_size = window_size or self.context_window_size

        # Try to get smart context from Redis Cache
        if self.conversation_cache:
            try:
                cached_context = await self.conversation_cache.get_conversation_context(
                    conversation_id, context_size=window_size
                )

                if cached_context and cached_context.recent_messages:
                    # Convert cached context to AI format
                    context = []
                    for cached_msg in cached_context.recent_messages[-window_size:]:
                        context.append(
                            {
                                "role": (
                                    "user"
                                    if cached_msg.message_type
                                    == MessageType.USER_INPUT.value
                                    else "assistant"
                                ),
                                "content": cached_msg.content,
                                "timestamp": cached_msg.timestamp,
                                "safety_score": cached_msg.safety_score,
                                "topics": cached_context.topics,
                                "sentiment": cached_context.sentiment,
                                "engagement_level": cached_context.engagement_level,
                            }
                        )

                    return context
            except Exception as e:
                if self.logger:
                    safe_conv_id = (
                        str(conversation_id).replace("\n", "").replace("\r", "")[:50]
                    )
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.warning(
                    f"Redis context cache error for {safe_conv_id}: {safe_error}"
                )

        # Fallback to standard message retrieval
        messages = await self.get_conversation_messages(
            conversation_id=conversation_id,
            limit=window_size,
            include_system_messages=False,
        )

        # Format messages for AI context
        context = []
        for message in messages[-window_size:]:  # Get most recent
            context.append(
                {
                    "role": (
                        "user"
                        if message.message_type == MessageType.USER_INPUT.value
                        else "assistant"
                    ),
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat(),
                }
            )

        return context

    # INTERACTION MANAGEMENT METHODS

    async def record_interaction_event(
        self,
        conversation_id: UUID,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> None:
        """Record an interaction event for analytics.

        Args:
            conversation_id: Conversation's unique identifier
            event_type: Type of interaction event
            event_data: Event data and metadata
        """
        interaction_event = {
            "event_id": str(uuid4()),
            "conversation_id": str(conversation_id),
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": event_data,
        }

        if self.logger:
            # Sanitize event data for logging
            safe_event_type = event_type.replace("\n", "").replace("\r", "")[:50]
            # Create safe version of interaction_event
            safe_event = {
                "event_id": interaction_event["event_id"],
                "conversation_id": interaction_event["conversation_id"],
                "event_type": safe_event_type,
                "timestamp": interaction_event["timestamp"],
            }
            self.logger.info(f"Interaction event [{safe_event_type}]: {safe_event}")

    async def get_conversation_analytics(
        self,
        conversation_id: UUID,
    ) -> Dict[str, Any]:
        """Get analytics for a specific conversation.

        Args:
            conversation_id: Conversation's unique identifier

        Returns:
            Conversation analytics data
        """
        conversation = await self.get_conversation_internal(conversation_id)
        messages = await self.get_conversation_messages(conversation_id)

        # Calculate analytics
        user_messages = [
            m for m in messages if m.message_type == MessageType.USER_INPUT.value
        ]
        ai_messages = [
            m for m in messages if m.message_type == MessageType.AI_RESPONSE.value
        ]

        duration = None
        if conversation.started_at and conversation.ended_at:
            duration = (conversation.ended_at - conversation.started_at).total_seconds()
        elif conversation.started_at:
            duration = (datetime.now() - conversation.started_at).total_seconds()

        analytics = {
            "conversation_id": str(conversation_id),
            "child_id": str(conversation.child_id),
            "status": conversation.status,
            "interaction_type": conversation.interaction_type,
            "started_at": conversation.started_at.isoformat(),
            "duration_seconds": duration,
            "total_messages": len(messages),
            "user_messages": len(user_messages),
            "ai_responses": len(ai_messages),
            "average_response_time": 0,  # Would calculate from actual data
            "safety_flags": 0,  # Would count from actual safety incidents
            "engagement_score": min(100, len(messages) * 5),  # Simple engagement metric
        }

        return analytics

    # NOTIFICATION METHODS

    async def send_notification(
        self,
        recipient_id: UUID,
        notification_type: str,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send a notification to a user.

        Args:
            recipient_id: Recipient's unique identifier
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            metadata: Additional notification metadata

        Returns:
            Success status
        """
        try:
            notification = {
                "id": str(uuid4()),
                "recipient_id": str(recipient_id),
                "type": notification_type,
                "title": title,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }

            # Send through notification service if available
            if self.notification_service:
                await self.notification_service.send_notification(notification)
            else:
                # Log notification for demo purposes
                if self.logger:
                    # Sanitize notification data for logging
                    safe_type = notification_type.replace("\n", "").replace("\r", "")[
                        :50
                    ]
                    safe_title = title.replace("\n", "").replace("\r", "")[:100]
                    safe_message = message.replace("\n", "").replace("\r", "")[:200]
                    self.logger.info(
                        f"Notification [{safe_type}]: {safe_title} - {safe_message}"
                    )

            self.notification_count += 1
            return True

        except (ValueError, ServiceUnavailableError) as e:
            if self.logger:
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.error(
                    f"Failed to send notification: {safe_error}", exc_info=True
                )
            return False
        except (
            Exception
        ) as e:  # noqa: BLE001 - Catching broad exception here for audit logging
            if self.logger:
                self.logger.error(
                    f"Unexpected error in send_notification: {e}", exc_info=True
                )
            return False

    # SAFETY AND INCIDENT METHODS

    async def report_safety_incident(
        self,
        conversation_id: UUID,
        incident_type: str,
        severity: IncidentSeverity,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Report a safety incident.

        Args:
            conversation_id: Related conversation ID
            incident_type: Type of safety incident
            severity: Incident severity level
            description: Incident description
            metadata: Additional incident metadata

        Returns:
            Incident ID
        """
        incident_id = str(uuid4())
        incident = {
            "incident_id": incident_id,
            "conversation_id": str(conversation_id),
            "incident_type": incident_type,
            "severity": severity.value,
            "description": description,
            "reported_at": datetime.now().isoformat(),
            "status": "open",
            "metadata": metadata or {},
        }

        if self.logger:
            # Sanitize incident data for logging
            safe_severity = severity.value.replace("\n", "").replace("\r", "")
            safe_incident = {
                "incident_id": incident["incident_id"],
                "conversation_id": incident["conversation_id"],
                "incident_type": incident["incident_type"]
                .replace("\n", "")
                .replace("\r", "")[:50],
                "severity": safe_severity,
                "reported_at": incident["reported_at"],
            }
            self.logger.warning(
                f"Safety incident reported [{safe_severity}]: {safe_incident}"
            )

        if severity in [IncidentSeverity.HIGH, IncidentSeverity.CRITICAL]:
            conversation = await self.get_conversation_internal(conversation_id)
            await self.send_notification(
                recipient_id=conversation.child_id,  # Would send to parent in production
                notification_type="safety_alert",
                title="Safety Alert",
                message=f"A {severity.value} safety incident has been reported.",
                metadata={"incident_id": incident_id},
            )

        self.safety_incidents += 1

        # Track metrics
        if self.metrics:
            self.metrics.safety_violation_detected(
                conversation_id=str(conversation_id),
                violation_type=incident_type,
                severity=severity.value,
            )

        return incident_id

    # INTERNAL METHODS

    async def _get_conversation_lock(self, conversation_id: UUID) -> asyncio.Lock:
        """Get or create lock for conversation with optimized creation."""
        # Check if lock exists first (without global lock)
        if conversation_id in self._conversation_locks:
            return self._conversation_locks[conversation_id]

        # Only use global lock for creation to minimize contention
        async with self._lock_creation_lock:
            # Double-check pattern to avoid race conditions
            if conversation_id not in self._conversation_locks:
                self._conversation_locks[conversation_id] = asyncio.Lock()
            return self._conversation_locks[conversation_id]

    async def _check_message_safety(self, content: str) -> Dict[str, Any]:
        """Check message content for safety issues."""
        content_lower = content.lower()
        flagged_keywords = []

        for keyword in self.safety_keywords:
            if keyword in content_lower:
                flagged_keywords.append(keyword)

        is_safe = len(flagged_keywords) == 0

        return {
            "is_safe": is_safe,
            "flagged_keywords": flagged_keywords,
            "confidence": 0.8 if is_safe else 0.3,
            "checked_at": datetime.now().isoformat(),
        }

    async def _handle_safety_incident(
        self,
        conversation_id: UUID,
        message: Message,
        safety_result: Dict[str, Any],
    ) -> None:
        """Handle a safety incident in conversation."""
        await self.report_safety_incident(
            conversation_id=conversation_id,
            incident_type="inappropriate_content",
            severity=IncidentSeverity.MEDIUM,
            description=f"Safety flags detected in message: {safety_result['flagged_keywords']}",
            metadata={
                "message_id": str(message.id),
                "safety_result": safety_result,
            },
        )

    async def _handle_conversation_overflow(self, conversation_id: UUID) -> None:
        """Handle conversation that has reached maximum length."""
        # End current conversation and suggest starting a new one
        await self.end_conversation(
            conversation_id=conversation_id,
            reason="max_length_reached",
            summary="Conversation ended due to length limit. User can start a new conversation.",
        )

    async def _generate_conversation_summary(self, conversation_id: UUID) -> str:
        """Generate automatic summary for conversation."""
        messages = await self.get_conversation_messages(conversation_id, limit=10)

        if not messages:
            return "No messages in conversation"

        # Simple summary generation (would use AI in production)
        user_message_count = len(
            [m for m in messages if m.message_type == MessageType.USER_INPUT.value]
        )
        topics = ["general chat"]  # Would extract actual topics

        return f"Conversation with {user_message_count} user messages covering topics: {', '.join(topics)}"

    # =========================================================================
    # ICONVERSATIONSERVICE INTERFACE COMPLIANCE METHODS
    # =========================================================================

    async def create_conversation(self, child_id: str, metadata: Dict[str, Any]) -> str:
        """Create new conversation (IConversationService interface compliance).

        Args:
            child_id: Child's unique identifier as string
            metadata: Additional conversation metadata

        Returns:
            Conversation ID as string
        """
        try:
            # Convert string child_id to UUID for internal use
            child_uuid = UUID(child_id) if isinstance(child_id, str) else child_id

            # Use existing start_new_conversation method
            conversation = await self.start_new_conversation(
                child_id=child_uuid,
                initial_message=metadata.get("initial_message", ""),
                interaction_type=InteractionType(
                    metadata.get("interaction_type", "chat")
                ),
                metadata=metadata,
            )

            # Return conversation ID as string for interface compliance
            return str(conversation.id)

        except Exception as e:
            if self.logger:
                safe_child_id = str(child_id).replace("\n", "").replace("\r", "")[:50]
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.error(
                    f"Failed to create conversation for child {safe_child_id}: {safe_error}"
                )
            raise ServiceUnavailableError(f"Failed to create conversation: {e}")
    
    async def _handle_conversation_block(self, conversation_id: UUID, reason: str) -> None:
        """Handle conversation blocking due to safety violations."""
        try:
            conversation = await self.get_conversation_internal(conversation_id)
            if conversation:
                conversation.status = ConversationStatus.TERMINATED.value
                conversation.metadata["blocked"] = True
                conversation.metadata["block_reason"] = reason
                conversation.metadata["blocked_at"] = datetime.now().isoformat()
                
                await self.report_safety_incident(
                    conversation_id=conversation_id,
                    incident_type="conversation_blocked",
                    severity=IncidentSeverity.HIGH,
                    description=f"Conversation blocked: {reason}",
                    metadata={"block_reason": reason}
                )
                
                self.logger.warning(f"Conversation {conversation_id} blocked: {reason}")
        except Exception as e:
            self.logger.error(f"Failed to block conversation {conversation_id}: {e}")
    
    async def _handle_emergency_alert(self, conversation_id: UUID, safety_result: Dict[str, Any]) -> None:
        """Handle emergency safety alerts with unified notification system."""
        try:
            await self.report_safety_incident(
                conversation_id=conversation_id,
                incident_type="emergency_alert",
                severity=IncidentSeverity.CRITICAL,
                description=f"Emergency safety alert: Risk score {safety_result.get('risk_score', 0):.2f}",
                metadata={
                    "safety_result": safety_result,
                    "triggered_rules": safety_result.get("triggered_rules", []),
                    "pii_detected": safety_result.get("pii_detected", False)
                }
            )
            
            # Set conversation to under review
            conversation = await self.get_conversation_internal(conversation_id)
            if conversation:
                conversation.status = ConversationStatus.UNDER_REVIEW.value
                conversation.metadata["emergency_alert"] = True
                conversation.metadata["alert_time"] = datetime.now().isoformat()
                
                # Get parent ID for emergency notification
                parent_id = conversation.metadata.get("parent_id")
                child_id = conversation.metadata.get("child_id", str(conversation.child_id))
                
                if parent_id:
                    # Send emergency alert via unified notification orchestrator
                    try:
                        from src.application.services.realtime.unified_notification_orchestrator import get_notification_orchestrator
                        orchestrator = get_notification_orchestrator()
                        
                        emergency_data = {
                            "conversation_id": str(conversation_id),
                            "message": f"Emergency safety alert: Risk score {safety_result.get('risk_score', 0):.2f}",
                            "emergency_type": "safety_violation",
                            "triggered_rules": safety_result.get("triggered_rules", []),
                            "detected_issues": safety_result.get("detected_issues", []),
                            "pii_detected": safety_result.get("pii_detected", False),
                            "immediate_actions": ["Review conversation immediately", "Contact child if needed"],
                            "alert_id": f"emergency_{int(datetime.now().timestamp())}"
                        }
                        
                        await orchestrator.send_emergency_alert(
                            child_id=child_id,
                            parent_id=parent_id,
                            emergency_data=emergency_data
                        )
                        
                        self.logger.info(f"Emergency notification sent to parent {parent_id} for conversation {conversation_id}")
                        
                    except Exception as notif_error:
                        self.logger.error(f"Failed to send emergency notification: {notif_error}")
            
            self.logger.critical(f"Emergency alert triggered for conversation {conversation_id}")
        except Exception as e:
            self.logger.error(f"Failed to handle emergency alert for {conversation_id}: {e}")
    
    async def _schedule_parent_notification(self, conversation_id: UUID, safety_result: Dict[str, Any]) -> None:
        """Schedule parent notification for concerning content with unified notification system."""
        try:
            await self.report_safety_incident(
                conversation_id=conversation_id,
                incident_type="parent_notification_scheduled",
                severity=IncidentSeverity.MEDIUM,
                description=f"Parent notification scheduled: Risk score {safety_result.get('risk_score', 0):.2f}",
                metadata={
                    "safety_result": safety_result,
                    "notification_type": "safety_concern"
                }
            )
            
            # Add to conversation metadata for parent review
            conversation = await self.get_conversation_internal(conversation_id)
            if conversation:
                if "parent_notifications" not in conversation.metadata:
                    conversation.metadata["parent_notifications"] = []
                
                conversation.metadata["parent_notifications"].append({
                    "type": "safety_concern",
                    "scheduled_at": datetime.now().isoformat(),
                    "risk_score": safety_result.get('risk_score', 0),
                    "issues": safety_result.get('issues', [])
                })
                
                # Get parent and child IDs for notification
                parent_id = conversation.metadata.get("parent_id")
                child_id = conversation.metadata.get("child_id", str(conversation.child_id))
                
                if parent_id:
                    # Send safety alert via unified notification orchestrator
                    try:
                        from src.application.services.realtime.unified_notification_orchestrator import get_notification_orchestrator
                        orchestrator = get_notification_orchestrator()
                        
                        # Prepare safety alert data
                        alert_data = {
                            "conversation_id": str(conversation_id),
                            "safety_score": safety_result.get('safety_score', 100),
                            "event_type": "safety_concern",
                            "detected_issues": safety_result.get('detected_issues', []),
                            "triggered_rules": safety_result.get('triggered_rules', []),
                            "child_age": safety_result.get('child_age', 8),
                            "recommendations": [
                                "Review the conversation with your child",
                                "Discuss appropriate online behavior",
                                "Monitor future interactions"
                            ]
                        }
                        
                        await orchestrator.send_safety_alert(
                            child_id=child_id,
                            parent_id=parent_id,
                            safety_result=alert_data
                        )
                        
                        self.logger.info(f"Safety notification sent to parent {parent_id} for conversation {conversation_id}")
                        
                    except Exception as notif_error:
                        self.logger.error(f"Failed to send safety notification: {notif_error}")
            
            self.logger.info(f"Parent notification scheduled for conversation {conversation_id}")
        except Exception as e:
            self.logger.error(f"Failed to schedule parent notification for {conversation_id}: {e}")

    async def add_message(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        """Add message to conversation (IConversationService interface compliance).

        Args:
            conversation_id: Conversation ID as string
            message: Message data dictionary

        Returns:
            True if message added successfully
        """
        try:
            # Convert string conversation_id to UUID
            conv_uuid = UUID(conversation_id)

            # Extract message components
            message_type = MessageType(message.get("type", "user_input"))
            content = message.get("content", "")
            sender_id = message.get("sender_id")

            # Convert sender_id to UUID if provided as string
            sender_uuid = (
                UUID(sender_id)
                if sender_id and isinstance(sender_id, str)
                else sender_id
            )

            # Use existing add_message_internal method
            await self.add_message_internal(
                conversation_id=conv_uuid,
                message_type=message_type,
                content=content,
                sender_id=sender_uuid,
                metadata=message.get("metadata", {}),
            )

            return True

        except Exception as e:
            if self.logger:
                safe_conv_id = (
                    str(conversation_id).replace("\n", "").replace("\r", "")[:50]
                )
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.error(
                    f"Failed to add message to conversation {safe_conv_id}: {safe_error}"
                )
            return False

    async def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation details (IConversationService interface compliance).

        Args:
            conversation_id: Conversation ID as string

        Returns:
            Conversation data as dictionary
        """
        try:
            # Convert string conversation_id to UUID
            conv_uuid = UUID(conversation_id)

            # Use existing get_conversation method
            conversation = await self.get_conversation_internal(conv_uuid)

            # Convert to dict for interface compliance
            return {
                "id": str(conversation.id),
                "child_id": str(conversation.child_id),
                "status": conversation.status,
                "interaction_type": conversation.interaction_type,
                "started_at": (
                    conversation.started_at.isoformat()
                    if conversation.started_at
                    else None
                ),
                "ended_at": (
                    conversation.ended_at.isoformat() if conversation.ended_at else None
                ),
                "message_count": conversation.message_count,
                "context_summary": conversation.context_summary,
                "metadata": conversation.metadata or {},
            }

        except ConversationNotFoundError:
            return {}
        except Exception as e:
            if self.logger:
                safe_conv_id = (
                    str(conversation_id).replace("\n", "").replace("\r", "")[:50]
                )
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.error(
                    f"Failed to get conversation {safe_conv_id}: {safe_error}"
                )
            return {}

    async def archive_conversation(self, conversation_id: str) -> bool:
        """Archive conversation (IConversationService interface compliance).

        Args:
            conversation_id: Conversation ID as string

        Returns:
            True if conversation archived successfully
        """
        try:
            # Convert string conversation_id to UUID
            conv_uuid = UUID(conversation_id)

            # End conversation with archive reason
            await self.end_conversation(
                conversation_id=conv_uuid,
                reason="archived",
                summary="Conversation archived by user request",
            )

            # Remove from active conversations cache
            if conv_uuid in self._active_conversations:
                del self._active_conversations[conv_uuid]
            if conv_uuid in self._conversation_locks:
                del self._conversation_locks[conv_uuid]

            return True

        except Exception as e:
            if self.logger:
                safe_conv_id = (
                    str(conversation_id).replace("\n", "").replace("\r", "")[:50]
                )
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.error(
                    f"Failed to archive conversation {safe_conv_id}: {safe_error}"
                )
            return False

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete conversation permanently (IConversationService interface compliance).

        Args:
            conversation_id: Conversation ID as string

        Returns:
            True if conversation deleted successfully
        """
        try:
            # Convert string conversation_id to UUID
            conv_uuid = UUID(conversation_id)

            # Safety check - ensure conversation exists
            conversation = await self.get_conversation_internal(conv_uuid)
            if not conversation:
                return False

            # Remove from repository (if repository supports deletion)
            if hasattr(self.conversation_repo, "delete"):
                await self.conversation_repo.delete(conv_uuid)

            # Remove from active conversations cache
            if conv_uuid in self._active_conversations:
                del self._active_conversations[conv_uuid]
            if conv_uuid in self._conversation_locks:
                del self._conversation_locks[conv_uuid]

            if self.logger:
                self.logger.warning(
                    f"Conversation {conversation_id} permanently deleted"
                )

            return True

        except Exception as e:
            if self.logger:
                safe_conv_id = (
                    str(conversation_id).replace("\n", "").replace("\r", "")[:50]
                )
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.error(
                    f"Failed to delete conversation {safe_conv_id}: {safe_error}"
                )
            return False

    async def get_service_health(self) -> Dict[str, Any]:
        """Get service health status and metrics."""
        active_conversations = len(self._active_conversations)
        active_locks = len(self._conversation_locks)

        # Update metrics if available
        if self.metrics:
            import psutil
            import os

            # Get memory usage
            process = psutil.Process(os.getpid())
            memory_bytes = process.memory_info().rss

            # Update resource metrics
            self.metrics.update_resource_usage(memory_bytes, active_locks)

            # Update service health
            healthy = active_conversations < 5000  # Reasonable threshold
            self.metrics.update_service_health(
                healthy=healthy,
                dependencies={
                    "conversation_repo": self.conversation_repo is not None,
                    "message_repo": self.message_repo is not None,
                    "notification_service": self.notification_service is not None,
                },
            )

        health_data = {
            "status": "healthy",
            "total_conversations": self.conversation_count,
            "active_conversations": active_conversations,
            "active_locks": active_locks,
            "total_messages": self.message_count,
            "safety_incidents": self.safety_incidents,
            "notifications_sent": self.notification_count,
            "configuration": {
                "max_conversation_length": self.max_conversation_length,
                "context_window_size": self.context_window_size,
                "safety_keywords_count": len(self.safety_keywords),
                "metrics_enabled": self.metrics is not None,
            },
            "repository_status": {
                "conversation_repo": self.conversation_repo is not None,
                "message_repo": self.message_repo is not None,
                "notification_service": self.notification_service is not None,
            },
        }

        # Add metrics data if available
        if self.metrics:
            try:
                analytics = self.metrics.get_conversation_analytics()
                health_data["analytics"] = analytics
            except Exception as e:
                health_data["analytics_error"] = str(e)

        return health_data

    # INTERACTION TRACKING METHODS FOR PRODUCTION DATABASE

    async def create_interaction_record(
        self,
        conversation_id: UUID,
        user_message: str,
        ai_response: str,
        safety_score: float = 100.0,
        flagged: bool = False,
        flag_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Create interaction record in the interactions table for dashboard display.
        
        This method bridges the gap between Message entities and the interactions
        table used by dashboard_routes.py for parent dashboard display.
        
        Args:
            conversation_id: UUID of the conversation
            user_message: User's message content
            ai_response: AI's response content
            safety_score: Safety score (0-100)
            flagged: Whether interaction is flagged
            flag_reason: Reason for flagging
            metadata: Additional metadata
            
        Returns:
            True if interaction created successfully
        """
        try:
            # Get database session (we need to handle this differently)
            from src.infrastructure.database.database_manager import database_manager
            
            async with database_manager.get_session() as db_session:
                # Create interaction record
                interaction = InteractionModel(
                    conversation_id=conversation_id,
                    message=user_message.strip(),
                    ai_response=ai_response.strip(),
                    timestamp=datetime.utcnow(),
                    safety_score=safety_score,
                    flagged=flagged,
                    flag_reason=flag_reason if flagged else None,
                    content_metadata=metadata or {},
                    created_by=None,  # Could be set to child_id if needed
                    retention_status='active'
                )
                
                # Save to database
                db_session.add(interaction)
                await db_session.commit()
                
                if self.logger:
                    safe_conv_id = str(conversation_id).replace("\n", "").replace("\r", "")[:50]
                    self.logger.info(
                        f"Interaction record created for conversation {safe_conv_id}",
                        extra={
                            "conversation_id": safe_conv_id,
                            "safety_score": safety_score,
                            "flagged": flagged
                        }
                    )
                
                return True
                
        except Exception as e:
            if self.logger:
                safe_conv_id = str(conversation_id).replace("\n", "").replace("\r", "")[:50]
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.error(
                    f"Failed to create interaction record for {safe_conv_id}: {safe_error}",
                    exc_info=True
                )
            return False

    async def store_chat_interaction(
        self,
        conversation_id: str,
        user_message: str,
        ai_response: str,
        safety_score: float = 100.0
    ) -> bool:
        """Convenience method to store chat interactions from the chat endpoint.
        
        Args:
            conversation_id: Conversation ID as string
            user_message: User's message content
            ai_response: AI's response content
            safety_score: Safety score from AI processing
            
        Returns:
            True if interaction stored successfully
        """
        try:
            # Convert string ID to UUID
            conv_uuid = UUID(conversation_id)
            
            # Determine if content should be flagged
            flagged = safety_score < 80.0
            flag_reason = "Low safety score detected" if flagged else None
            
            # Store interaction with metadata
            success = await self.create_interaction_record(
                conversation_id=conv_uuid,
                user_message=user_message,
                ai_response=ai_response,
                safety_score=safety_score,
                flagged=flagged,
                flag_reason=flag_reason,
                metadata={
                    "stored_via": "chat_endpoint",
                    "processing_timestamp": datetime.utcnow().isoformat(),
                    "ai_model": "production_model"
                }
            )
            
            return success
            
        except Exception as e:
            if self.logger:
                safe_conv_id = str(conversation_id).replace("\n", "").replace("\r", "")[:50]
                safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
                self.logger.error(
                    f"Failed to store chat interaction for {safe_conv_id}: {safe_error}"
                )
            return False
