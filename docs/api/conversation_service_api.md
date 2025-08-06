# ConsolidatedConversationService API Documentation

## Overview

The `ConsolidatedConversationService` is the unified conversation management service that handles all chat interactions, message processing, and conversation lifecycle in the AI Teddy Bear application.

## Table of Contents

- [Service Initialization](#service-initialization)
- [Core Methods](#core-methods)
- [Error Handling](#error-handling)
- [Monitoring & Metrics](#monitoring--metrics)
- [Redis Caching](#redis-caching)
- [Safety & Compliance](#safety--compliance)

---

## Service Initialization

### Constructor Parameters

```python
ConsolidatedConversationService(
    conversation_repository: ConversationRepository,
    message_repository: Optional[MessageRepository] = None,
    notification_service: Optional[NotificationService] = None,
    logger: Optional[Logger] = None,
    max_conversation_length: int = 100,
    context_window_size: int = 10,
    enable_metrics: bool = True,
    metrics_level: MetricLevel = MetricLevel.DETAILED,
    conversation_cache_service: Optional[ConversationCache] = None,
)
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `conversation_repository` | `ConversationRepository` | ✅ | - | Primary repository for conversation persistence |
| `message_repository` | `MessageRepository` | ❌ | `None` | Repository for message persistence |
| `notification_service` | `NotificationService` | ❌ | `None` | Service for sending notifications |
| `logger` | `Logger` | ❌ | `None` | Logging instance |
| `max_conversation_length` | `int` | ❌ | `100` | Maximum messages per conversation |
| `context_window_size` | `int` | ❌ | `10` | Number of recent messages for context |
| `enable_metrics` | `bool` | ❌ | `True` | Enable Prometheus metrics collection |
| `metrics_level` | `MetricLevel` | ❌ | `DETAILED` | Level of metrics collection |
| `conversation_cache_service` | `ConversationCache` | ❌ | `None` | Redis cache for performance optimization |

---

## Core Methods

### 1. start_new_conversation()

Creates a new conversation session for a child.

```python
async def start_new_conversation(
    self,
    child_id: UUID,
    initial_message: str = "Hello! How can I help you today?",
    interaction_type: str = "chat",
    **metadata
) -> Conversation
```

**Parameters:**
- `child_id` (UUID): Unique identifier of the child
- `initial_message` (str): First message to start the conversation
- `interaction_type` (str): Type of interaction ("chat", "game", "story", etc.)
- `**metadata`: Additional conversation metadata

**Returns:** `Conversation` - The newly created conversation object

**Raises:**
- `ValidationError` - Invalid child_id or parameters
- `ServiceUnavailableError` - Service or database unavailable
- `ChildNotFoundError` - Child profile not found

**Example:**
```python
conversation = await service.start_new_conversation(
    child_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
    initial_message="Hi there! Ready for a story?",
    interaction_type="story",
    theme="adventure",
    age_appropriate=True
)
```

### 2. add_message()

Adds a new message to an existing conversation.

```python
async def add_message(
    self,
    conversation_id: UUID,
    message: Message,
    update_context: bool = True
) -> Conversation
```

**Parameters:**
- `conversation_id` (UUID): Target conversation identifier
- `message` (Message): Message object to add
- `update_context` (bool): Whether to update conversation context

**Returns:** `Conversation` - Updated conversation with new message

**Raises:**
- `ConversationNotFoundError` - Conversation doesn't exist
- `ValidationError` - Invalid message format
- `SafetyViolationError` - Message violates safety rules

**Example:**
```python
message = Message(
    content="Tell me a story about dragons",
    role="child",
    child_id=child_id,
    metadata={"emotion": "excited"}
)

updated_conversation = await service.add_message(
    conversation_id=conversation.id,
    message=message
)
```

### 3. get_conversation()

Retrieves a conversation by ID with optional message history.

```python
async def get_conversation(
    self,
    conversation_id: UUID,
    include_messages: bool = True,
    message_limit: int = 50
) -> Optional[Conversation]
```

**Parameters:**
- `conversation_id` (UUID): Conversation identifier
- `include_messages` (bool): Include message history
- `message_limit` (int): Maximum messages to retrieve

**Returns:** `Optional[Conversation]` - Conversation object or None if not found

**Example:**
```python
conversation = await service.get_conversation(
    conversation_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
    include_messages=True,
    message_limit=20
)
```

### 4. archive_conversation()

Archives a completed conversation.

```python
async def archive_conversation(
    self,
    conversation_id: UUID,
    reason: str = "completed"
) -> bool
```

**Parameters:**
- `conversation_id` (UUID): Conversation to archive
- `reason` (str): Reason for archiving

**Returns:** `bool` - Success status

### 5. delete_conversation()

Permanently deletes a conversation (COPPA compliance).

```python
async def delete_conversation(
    self,
    conversation_id: UUID,
    deletion_reason: str = "parent_request"
) -> bool
```

**Parameters:**
- `conversation_id` (UUID): Conversation to delete
- `deletion_reason` (str): Reason for deletion

**Returns:** `bool` - Success status

---

## Error Handling

The service uses a structured error handling approach with custom exceptions:

### Exception Hierarchy

```
AITeddyBearException (base)
├── ConversationNotFoundError
├── ValidationError
├── SafetyViolationError
├── ServiceUnavailableError
└── AuthenticationError
```

### Error Response Format

```python
{
    "error_code": "conversation_not_found",
    "message": "Conversation with ID 123... not found",
    "context": {
        "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
        "timestamp": "2025-08-02T10:30:00Z"
    }
}
```

---

## Monitoring & Metrics

The service provides comprehensive Prometheus metrics:

### Core Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `conversation_operations_total` | Counter | Total conversation operations |
| `conversation_duration_seconds` | Histogram | Conversation duration distribution |
| `active_conversations` | Gauge | Currently active conversations |
| `conversation_messages_total` | Counter | Total messages processed |
| `safety_incidents_total` | Counter | Safety violations detected |
| `service_health_status` | Gauge | Service health (1=healthy, 0=unhealthy) |

### Example Metrics Usage

```python
# Enable metrics during initialization
service = ConsolidatedConversationService(
    conversation_repository=repo,
    enable_metrics=True,
    metrics_level=MetricLevel.DETAILED
)

# Metrics are automatically collected during operations
conversation = await service.start_new_conversation(child_id)
# → Updates conversation_operations_total and active_conversations
```

---

## Redis Caching

The service supports Redis caching for improved performance:

### Cache Operations

- **Conversation Storage**: Active conversations cached for quick access
- **Message History**: Recent messages cached with TTL
- **Context Preservation**: Conversation context cached between sessions

### Cache Configuration

```python
# Initialize with Redis cache
cache_service = ConversationCacheService(redis_client)
service = ConsolidatedConversationService(
    conversation_repository=repo,
    conversation_cache_service=cache_service
)
```

### Cache Behavior

- **Cache Miss**: Falls back to database query
- **Cache Failure**: Graceful degradation to database-only mode
- **TTL**: Configurable cache expiration (default: 1 hour)

---

## Safety & Compliance

### Child Safety Features

- **Age Validation**: Ensures child is within COPPA range (3-13 years)
- **Content Filtering**: All messages checked for appropriate content
- **Safety Scoring**: Real-time safety score calculation
- **Incident Tracking**: Safety violations logged and monitored

### COPPA Compliance

- **Data Encryption**: All child data encrypted at rest
- **Parental Consent**: Verification before conversation start
- **Data Retention**: Configurable retention policies
- **Right to Deletion**: Full conversation deletion support

### Example Safety Check

```python
# Safety validation is automatic
message = Message(content="inappropriate content", role="child")
try:
    await service.add_message(conversation_id, message)
except SafetyViolationError as e:
    print(f"Safety violation: {e.violations}")
    # Handle safety incident
```

---

## Integration Examples

### Basic Usage

```python
from src.services.conversation_service import ConsolidatedConversationService
from src.adapters.database_production import ProductionConversationRepository

# Initialize service
repo = ProductionConversationRepository()
service = ConsolidatedConversationService(conversation_repository=repo)

# Start conversation
child_id = UUID("123e4567-e89b-12d3-a456-426614174000")
conversation = await service.start_new_conversation(
    child_id=child_id,
    interaction_type="story"
)

# Add messages
message = Message(content="Tell me about space", role="child")
updated_conversation = await service.add_message(
    conversation.id, 
    message
)

# Archive when done
await service.archive_conversation(
    conversation.id, 
    reason="story_completed"
)
```

### Advanced Configuration

```python
from src.services.conversation_service import ConsolidatedConversationService, MetricLevel
from src.infrastructure.monitoring.conversation_service_metrics import ConversationServiceMetrics

# Full production setup
service = ConsolidatedConversationService(
    conversation_repository=production_repo,
    message_repository=message_repo,
    notification_service=notification_svc,
    max_conversation_length=200,
    context_window_size=15,
    enable_metrics=True,
    metrics_level=MetricLevel.DETAILED,
    conversation_cache_service=redis_cache
)
```

---

## Performance Considerations

### Optimization Features

1. **Redis Caching**: Reduces database load
2. **Connection Pooling**: Efficient database connections
3. **Async Operations**: Non-blocking I/O
4. **Conversation Locks**: Prevents race conditions
5. **Batch Operations**: Efficient bulk processing

### Recommended Limits

- **Max Conversations per Child**: 10 active
- **Max Messages per Conversation**: 100 (configurable)
- **Cache TTL**: 1 hour for active conversations
- **Context Window**: 10 recent messages

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-08-01 | Initial consolidated service |
| 1.1.0 | 2025-08-02 | Added Redis caching support |
| 1.2.0 | 2025-08-02 | Enhanced metrics and monitoring |

---

For additional support or questions, refer to the [Architecture Documentation](../architecture/) or contact the development team.
