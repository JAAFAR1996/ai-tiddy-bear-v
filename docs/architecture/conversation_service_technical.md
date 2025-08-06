# Conversation Service Technical Architecture

## Overview

The ConsolidatedConversationService is the central orchestrator for all conversation-related functionality in the AI Teddy Bear platform. This document provides detailed technical insights for developers and DevOps teams.

## Architecture Components

### Core Service Layer
```
┌─────────────────────────────────────────────────────────┐
│                ConsolidatedConversationService           │
├─────────────────────────────────────────────────────────┤
│  • Conversation Lifecycle Management                     │
│  • Message Processing & Validation                       │
│  • Safety Monitoring & Incident Response                 │
│  • Caching Strategy & Performance Optimization           │
│  • Metrics Collection & Health Monitoring                │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Repository  │    │    Cache    │    │ Monitoring  │
│   Layer     │    │   Layer     │    │    Layer    │
│             │    │             │    │             │
│ PostgreSQL  │    │   Redis     │    │ Prometheus  │
│ Persistence │    │ Performance │    │   Metrics   │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Data Flow Architecture

```
Child Request → Authentication → Rate Limiting → Conversation Service
                                                        │
                                                        ▼
Safety Validation ← AI Processing ← Context Retrieval ← Message Processing
        │                                              
        ▼                                              
Response Generation → Caching → Metrics → Database Persistence
        │
        ▼
Child Response + Parent Notification (if needed)
```

## Technical Specifications

### Service Configuration

#### Core Parameters
| Parameter | Type | Default | Production | Description |
|-----------|------|---------|------------|-------------|
| `max_conversation_length` | int | 100 | 200 | Maximum messages per conversation |
| `context_window_size` | int | 10 | 15 | Recent messages for AI context |
| `cache_ttl` | int | 3600 | 1800 | Redis cache TTL in seconds |
| `safety_threshold` | float | 0.7 | 0.8 | Minimum safety score |
| `rate_limit_per_child` | int | 30 | 50 | Messages per minute per child |

#### Database Configuration
```yaml
database:
  connection_pool_size: 20
  max_overflow: 30
  pool_timeout: 30
  pool_recycle: 3600
  echo: false  # Set to true for SQL debugging
```

#### Redis Configuration
```yaml
redis:
  host: redis-cluster.internal
  port: 6379
  db: 2  # Dedicated DB for conversations
  connection_pool_size: 50
  socket_timeout: 5
  socket_connect_timeout: 5
  retry_on_timeout: true
```

### Performance Characteristics

#### Throughput Targets
- **Normal Load**: 100 conversations/second
- **Peak Load**: 500 conversations/second  
- **Burst Capacity**: 1000 conversations/second (5 minutes)

#### Latency Targets
- **p50**: < 200ms
- **p95**: < 500ms
- **p99**: < 1s
- **Timeout**: 10s

#### Resource Requirements
- **CPU**: 2-4 cores per instance
- **Memory**: 2-4GB per instance
- **Network**: 1Gbps
- **Storage**: SSD for database

### Error Handling Strategy

#### Exception Hierarchy
```python
AITeddyBearException
├── ConversationNotFoundError      # 404 - Conversation doesn't exist
├── ValidationError                # 400 - Invalid input data
├── SafetyViolationError          # 403 - Content safety violation
├── ServiceUnavailableError       # 503 - Service temporarily down
├── RateLimitExceededError        # 429 - Too many requests
└── AuthenticationError           # 401 - Invalid authentication
```

#### Error Response Format
```json
{
  "error": {
    "code": "conversation_not_found",
    "message": "Conversation with ID abc123 not found",
    "details": {
      "conversation_id": "abc123",
      "child_id": "def456",
      "timestamp": "2025-08-02T10:30:00Z"
    },
    "trace_id": "trace-789"
  }
}
```

#### Retry Strategy
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
async def database_operation():
    # Database operations with automatic retry
    pass
```

### Caching Strategy

#### Cache Layers
1. **L1 - Application Cache**: In-memory conversation objects
2. **L2 - Redis Cache**: Serialized conversation data
3. **L3 - Database**: Persistent storage

#### Cache Keys
```python
# Conversation cache
f"conversation:{conversation_id}"
f"child_conversations:{child_id}"
f"active_conversations:{child_id}"

# Message cache  
f"messages:{conversation_id}:recent"
f"context:{conversation_id}"

# Safety cache
f"safety_profile:{child_id}"
```

#### Cache Invalidation
```python
# Invalidation triggers
conversation_updated → invalidate(f"conversation:{id}")
message_added → invalidate(f"messages:{conv_id}:recent")
safety_incident → invalidate(f"safety_profile:{child_id}")
```

### Safety & Security

#### Content Safety Pipeline
```
User Input → Profanity Filter → AI Safety Check → Content Analysis → Response
                  │                  │               │
                  ▼                  ▼               ▼
            Block/Warning      Safety Score    Incident Logging
```

#### Safety Scores
- **1.0**: Completely safe content
- **0.8-0.99**: Safe with minor concerns
- **0.5-0.79**: Potentially concerning (flagged)
- **0.0-0.49**: Unsafe (blocked)

#### Data Encryption
```python
# Child data encryption
@encrypt_field(key="COPPA_ENCRYPTION_KEY")
class ConversationModel:
    child_id: UUID
    content: str  # Encrypted in database
    metadata: dict  # Encrypted if contains PII
```

### Monitoring & Observability

#### Key Metrics
```python
# Business Metrics
conversation_operations_total{operation="create|add_message|archive"}
conversation_duration_seconds{interaction_type="chat|story|game"}
active_conversations{age_group="3-6|7-10|11-13"}

# Performance Metrics  
conversation_service_latency_seconds{operation, percentile}
database_operation_duration_seconds{operation}
cache_hit_ratio{cache_type="redis|application"}

# Safety Metrics
safety_incidents_total{severity="low|medium|high|critical"}
safety_score_distribution{score_range}
content_blocks_total{reason}

# Infrastructure Metrics
memory_usage_bytes
cpu_usage_percent
active_database_connections
redis_connection_pool_usage
```

#### Health Checks
```python
async def comprehensive_health_check():
    checks = {
        "database": await check_database_connectivity(),
        "redis": await check_redis_connectivity(),
        "ai_service": await check_ai_service_health(),
        "safety_service": await check_safety_service_health(),
        "memory": check_memory_usage(),
        "cpu": check_cpu_usage()
    }
    
    overall_health = all(checks.values())
    
    return {
        "status": "healthy" if overall_health else "unhealthy",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Deployment Strategy

#### Blue-Green Deployment
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: conversation-service-blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: conversation-service
      version: blue
  template:
    spec:
      containers:
      - name: conversation-service
        image: ai-teddy-bear/conversation-service:v1.2.0
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"  
            cpu: "2000m"
```

#### Rolling Update Strategy
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 1
    maxSurge: 1
```

#### Database Migrations
```python
# Alembic migration pattern
def upgrade():
    """Add conversation metadata column."""
    op.add_column('conversations',
        sa.Column('metadata', postgresql.JSONB(), nullable=True)
    )
    
    # Create index for performance
    op.create_index(
        'ix_conversations_metadata_gin',
        'conversations',
        ['metadata'],
        postgresql_using='gin'
    )

def downgrade():
    """Remove conversation metadata column."""
    op.drop_index('ix_conversations_metadata_gin')
    op.drop_column('conversations', 'metadata')
```

### Testing Strategy

#### Unit Tests
```python
@pytest.mark.asyncio
async def test_conversation_creation_with_safety_validation():
    """Test conversation creation includes safety validation."""
    
    # Setup
    mock_safety_service = AsyncMock()
    mock_safety_service.validate_content.return_value = SafetyResult(
        is_safe=True, 
        score=0.95
    )
    
    service = ConsolidatedConversationService(
        conversation_repository=mock_repo,
        safety_service=mock_safety_service
    )
    
    # Test
    conversation = await service.start_new_conversation(
        child_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        initial_message="Hello!"
    )
    
    # Verify
    assert conversation is not None
    mock_safety_service.validate_content.assert_called_once()
```

#### Integration Tests
```python
@pytest.mark.integration
async def test_full_conversation_flow():
    """Test complete conversation lifecycle."""
    
    # Test conversation creation → message addition → archival
    conversation = await service.start_new_conversation(child_id)
    
    message = Message(content="Tell me a story", role="child")
    updated_conv = await service.add_message(conversation.id, message)
    
    archived = await service.archive_conversation(conversation.id)
    
    assert archived is True
```

#### Performance Tests
```python
@pytest.mark.performance
async def test_concurrent_conversations():
    """Test handling multiple concurrent conversations."""
    
    tasks = []
    for i in range(100):
        task = service.start_new_conversation(
            child_id=UUID(f"child-{i:04d}")
        )
        tasks.append(task)
    
    # All should complete within timeout
    conversations = await asyncio.wait_for(
        asyncio.gather(*tasks), 
        timeout=10.0
    )
    
    assert len(conversations) == 100
```

### Troubleshooting Guide

#### Common Issues

**High Latency**
```bash
# Check database performance
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;

# Check Redis performance  
redis-cli --latency-history -i 1

# Check application metrics
curl http://service:8000/metrics | grep duration
```

**Memory Leaks**
```python
# Memory profiling
import tracemalloc
tracemalloc.start()

# Run operations
await service.process_many_conversations()

# Check memory usage
current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024:.1f} MB")
print(f"Peak: {peak / 1024 / 1024:.1f} MB")
```

**Database Connection Issues**
```python
# Check connection pool
pool_status = await service.conversation_repo.get_pool_status()
print(f"Active connections: {pool_status.active}")
print(f"Pool size: {pool_status.pool_size}")
print(f"Checked out: {pool_status.checked_out}")
```

### Development Workflow

#### Local Development Setup
```bash
# Start dependencies
docker-compose up postgres redis

# Install dependencies
pip install -r requirements-dev.txt

# Run migrations
alembic upgrade head

# Start service
uvicorn src.main:app --reload --port 8000
```

#### Testing Workflow
```bash
# Run unit tests
pytest tests_consolidated/test_conversation_service.py -v

# Run integration tests  
pytest tests_consolidated/test_database_production.py -v

# Run Redis failover tests
pytest tests_consolidated/test_conversation_redis_failover.py -v

# Generate coverage report
pytest --cov=src.services.conversation_service --cov-report=html
```

#### Code Quality Checks
```bash
# Type checking
mypy src/services/conversation_service.py

# Code formatting
black src/services/conversation_service.py

# Linting
pylint src/services/conversation_service.py

# Security scanning
bandit -r src/services/conversation_service.py
```

---

## Future Enhancements

### Planned Features
- [ ] Multi-language conversation support
- [ ] Advanced conversation analytics
- [ ] Real-time conversation summaries
- [ ] Enhanced safety ML models
- [ ] Voice conversation integration

### Technical Debt
- [ ] Refactor legacy conversation adapters
- [ ] Optimize database query patterns
- [ ] Implement conversation sharding
- [ ] Add circuit breaker patterns
- [ ] Improve error recovery mechanisms

---

For additional technical details, see:
- [API Documentation](../api/conversation_service_api.md)
- [Database Schema](../database/conversation_schema.md)
- [Monitoring Setup](../monitoring/setup.md)
