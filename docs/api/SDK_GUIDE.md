# AI Teddy Bear API SDK Guide

## 📋 Table of Contents
- [Quick Start](#-quick-start)
- [Authentication](#-authentication)
- [API Endpoints](#-api-endpoints)
- [Enhanced Security Features](#-enhanced-security-features)
- [Security Guardrails](#-security-guardrails)
- [Child Safety Compliance](#-child-safety-compliance)
- [Retry Logic & Error Handling](#-retry-logic--error-handling)
- [Monitoring & Health Checks](#-monitoring--health-checks)
- [Real-time Features](#-real-time-features)
- [Code Examples](#-code-examples)

## 🧸 Quick Start

### Python SDK

```python
from ai_teddy_bear import Client

# Initialize client
client = Client(
    api_key="your-api-key",
    environment="production",  # or "sandbox"
    base_url="https://api.aiteddybear.com"
)

# Register parent
parent = await client.auth.register(
    email="parent@example.com",
    password="SecurePassword123!",
    first_name="John",
    last_name="Doe",
    phone="+1234567890",
    consent_to_coppa=True
)

# Create child profile
child = await client.children.create(
    parent_id=parent.id,
    name="Emma",
    age=7,
    interests=["dinosaurs", "space", "art"],
    safety_level="high"
)

# Start conversation
response = await client.conversations.send_message(
    child_id=child.id,
    message="Hi Teddy! Tell me about dinosaurs!",
    voice_enabled=True
)

print(f"Teddy says: {response.content}")
if response.audio_url:
    print(f"Audio response: {response.audio_url}")
```

### JavaScript SDK

```javascript
import { AITeddyBearClient } from '@ai-teddy-bear/sdk';

// Initialize client
const client = new AITeddyBearClient({
    apiKey: 'your-api-key',
    environment: 'production',
    baseUrl: 'https://api.aiteddybear.com'
});

// Register parent
const parent = await client.auth.register({
    email: 'parent@example.com',
    password: 'SecurePassword123!',
    firstName: 'John',
    lastName: 'Doe',
    phone: '+1234567890',
    consentToCoppa: true
});

// Create child profile
const child = await client.children.create({
    parentId: parent.id,
    name: 'Emma',
    age: 7,
    interests: ['dinosaurs', 'space', 'art'],
    safetyLevel: 'high'
});

// Start conversation
const response = await client.conversations.sendMessage({
    childId: child.id,
    message: 'Hi Teddy! Tell me about dinosaurs!',
    voiceEnabled: true
});
```

## 🌐 API Endpoints

### Authentication Endpoints

| Method | Endpoint | Description | Enhanced Features |
|--------|----------|-------------|-------------------|
| `POST` | `/auth/login` | User authentication | Device tracking, IP monitoring, retry logic |
| `POST` | `/auth/refresh` | Refresh access token | Enhanced security validation, retry logic |
| `POST` | `/auth/revoke` | Revoke specific token | Real-time token blacklisting |
| `POST` | `/auth/revoke-all` | Revoke all user tokens | Security reset functionality |
| `GET` | `/auth/sessions` | Get active sessions | Device and IP tracking |

### Conversation Endpoints

| Method | Endpoint | Description | Enhanced Features |
|--------|----------|-------------|-------------------|
| `POST` | `/chat` | Send message to AI | Safety-focused retry logic, fallback responses |
| `GET` | `/conversations/{child_id}/history` | Get conversation history | Database resilience retry |

### Audio Processing Endpoints

| Method | Endpoint | Description | Enhanced Features |
|--------|----------|-------------|-------------------|
| `POST` | `/esp32/audio` | Process ESP32 audio | Real-time optimized retry, latency tracking |

### Health & Monitoring Endpoints

| Method | Endpoint | Description | Enhanced Features |
|--------|----------|-------------|-------------------|
| `GET` | `/health` | Main health check | Database and Redis retry validation |
| `GET` | `/health/audio` | Audio pipeline health | TTS/STT provider monitoring |
| `GET` | `/health/audio/metrics` | Audio metrics | Performance tracking |
| `GET` | `/health/audio/tts` | TTS provider health | Provider-specific monitoring |
| `GET` | `/metrics/audio` | Prometheus audio metrics | Filtered metrics for monitoring |

### Example API Usage

```python
# Enhanced login with device tracking
login_response = await client.auth.login({
    "email": "parent@example.com",
    "password": "SecurePassword123!",
    "device_info": {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "platform": "macOS",
        "timezone": "America/New_York"
    }
})

# Chat with retry logic and safety fallbacks
chat_response = await client.conversations.send_message({
    "child_id": "child-uuid",
    "message": "Tell me about dinosaurs",
    "child_age": 7,
    "child_name": "Emma"
})

# Process audio with optimized retry
audio_response = await client.esp32.process_audio({
    "child_id": "child-uuid",
    "audio_data": audio_bytes,
    "language_code": "en-US"
})

# Health monitoring with retry reliability
health = await client.health.check()
audio_health = await client.health.audio_pipeline()
```

## 🔐 Authentication

### JWT Token Flow

1. **Register/Login** to get access token
2. **Include token** in Authorization header
3. **Refresh token** before expiration

### Example Headers

```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
X-Child-ID: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json
X-API-Version: 1.0
```

### Enhanced JWT Token Management

```python
# Check token expiration
if client.auth.is_token_expired():
    await client.auth.refresh_token()

# Manual token refresh with enhanced security
new_tokens = await client.auth.refresh_token()

# New enhanced authentication endpoints
# Revoke specific token
await client.auth.revoke_token(
    jti="token-identifier",
    reason="manual_revocation"
)

# Revoke all user tokens (security reset)
await client.auth.revoke_all_tokens(
    reason="security_reset"
)

# Get active sessions with device tracking
sessions = await client.auth.get_sessions()
for session in sessions.sessions:
    print(f"Device: {session.device_id[:8]}...")
    print(f"IP: {session.ip_address}")
    print(f"Last activity: {session.last_activity}")
```

## 🚦 Rate Limiting

| Endpoint Category | Limit | Window | Headers |
|------------------|-------|--------|---------|
| Registration | 3 requests | 1 hour | `X-RateLimit-Remaining: 2` |
| Login | 10 requests | 15 minutes | `X-RateLimit-Reset: 1627846261` |
| Conversations | 30 requests | 1 minute | `Retry-After: 60` |
| AI Generation | 10 requests | 1 minute | |
| Audio Processing | 5 requests | 1 minute | |

### Handling Rate Limits

```python
from ai_teddy_bear.exceptions import RateLimitError

try:
    response = await client.conversations.send_message(...)
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
    await asyncio.sleep(e.retry_after)
```

## 👶 COPPA Compliance

### Child Data Requirements

All child data endpoints require:
- ✅ Valid parental consent on file
- ✅ Age verification (2-13 years)
- ✅ Encrypted data transmission
- ✅ Audit trail logging

### Consent Management

```python
# Check consent status
consent = await client.consent.check_status(child_id=child.id)

# Request new consent for feature
consent_request = await client.consent.request(
    child_id=child.id,
    feature="voice_interaction",
    description="Enable voice conversations with AI Teddy"
)

# Grant consent (parent action)
await client.consent.grant(
    consent_id=consent_request.id,
    parent_verification=True
)
```

### Data Export (COPPA Right)

```python
# Export all child data
export = await client.data.export_child_data(
    child_id=child.id,
    format="json",  # or "csv", "xml"
    include_conversations=True,
    include_audio=False
)

# Download export
with open("child_data.zip", "wb") as f:
    f.write(export.download())
```

## 🔄 Webhooks

### Configure Webhooks

```python
# Register webhook endpoints
await client.webhooks.create(
    url="https://your-app.com/webhooks/safety",
    events=["safety.violation", "safety.warning"],
    secret="your-webhook-secret"
)

await client.webhooks.create(
    url="https://your-app.com/webhooks/consent",
    events=["consent.granted", "consent.revoked"],
    secret="your-webhook-secret"
)
```

### Webhook Events

| Event | Description | Payload |
|-------|-------------|---------|
| `safety.violation` | Content safety violation detected | `child_id`, `severity`, `content_hash` |
| `safety.warning` | Safety warning triggered | `child_id`, `risk_level`, `recommendation` |
| `consent.granted` | Parental consent granted | `child_id`, `feature`, `granted_at` |
| `consent.revoked` | Parental consent revoked | `child_id`, `feature`, `revoked_at` |
| `session.started` | Child conversation session started | `child_id`, `session_id`, `started_at` |
| `session.ended` | Child conversation session ended | `child_id`, `session_id`, `duration` |

### Webhook Validation

```python
import hmac
import hashlib

def validate_webhook(payload, signature, secret):
    """Validate webhook signature"""
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(
        f"sha256={expected_signature}",
        signature
    )
```

## 🌐 WebSocket Integration

### Real-time Conversations

```python
import asyncio
import websockets

async def conversation_stream():
    uri = "wss://api.aiteddybear.com/v1/conversations/stream"
    headers = {"Authorization": "Bearer your-token"}
    
    async with websockets.connect(uri, extra_headers=headers) as websocket:
        # Send message
        await websocket.send(json.dumps({
            "type": "message",
            "child_id": "child-uuid",
            "content": "Hello Teddy!"
        }))
        
        # Receive response
        async for message in websocket:
            data = json.loads(message)
            if data["type"] == "response":
                print(f"Teddy: {data['content']}")
            elif data["type"] == "audio":
                print(f"Audio URL: {data['audio_url']}")
```

### Safety Monitoring Stream

```python
async def safety_monitor():
    uri = "wss://api.aiteddybear.com/v1/safety/monitor"
    headers = {"Authorization": "Bearer your-token"}
    
    async with websockets.connect(uri, extra_headers=headers) as websocket:
        async for message in websocket:
            safety_event = json.loads(message)
            
            if safety_event["severity"] == "high":
                # Handle safety violation
                await handle_safety_violation(safety_event)
```

## 📊 Analytics & Monitoring

### Usage Analytics

```python
# Get conversation analytics
analytics = await client.analytics.get_conversation_stats(
    child_id=child.id,
    date_range="last_30_days"
)

print(f"Total conversations: {analytics.total_conversations}")
print(f"Average session length: {analytics.avg_session_length}")
print(f"Safety score: {analytics.safety_score}")
```

### Health Monitoring

```python
# Check API health
health = await client.health.check()

print(f"Status: {health.status}")
print(f"Response time: {health.response_time}ms")
print(f"Uptime: {health.uptime}")
```

## 🛠️ Error Handling

### Error Types

```python
from ai_teddy_bear.exceptions import (
    AuthenticationError,
    ChildSafetyError,
    RateLimitError,
    ValidationError,
    ServiceUnavailableError
)

try:
    response = await client.conversations.send_message(...)
except AuthenticationError:
    # Handle auth failure - redirect to login
    pass
except ChildSafetyError as e:
    # Handle safety violation
    print(f"Safety violation: {e.violation_type}")
except RateLimitError as e:
    # Handle rate limiting
    await asyncio.sleep(e.retry_after)
except ValidationError as e:
    # Handle validation errors
    print(f"Invalid input: {e.field} - {e.message}")
except ServiceUnavailableError:
    # Handle service downtime
    print("Service temporarily unavailable")
```

### Retry Logic

```python
import backoff

@backoff.on_exception(
    backoff.expo,
    ServiceUnavailableError,
    max_tries=3,
    max_time=30
)
async def robust_api_call():
    return await client.conversations.send_message(...)
```

## 🧪 Testing

### Test Environment

```python
# Use sandbox environment for testing
test_client = Client(
    api_key="test-api-key",
    environment="sandbox",
    base_url="https://sandbox.aiteddybear.com"
)

# Create test child profile
test_child = await test_client.children.create(
    name="Test Child",
    age=8,
    interests=["testing"],
    safety_level="high"
)
```

### Mock Responses

```python
from ai_teddy_bear.testing import MockClient

# Use mock client for unit tests
mock_client = MockClient()
mock_client.conversations.send_message.return_value = {
    "content": "Hello from test Teddy!",
    "safety_score": 1.0,
    "audio_url": None
}
```

## 🛡️ Enhanced Security Features

### Advanced JWT Security

The AI Teddy Bear API now implements advanced JWT security features:

- **RS256 Algorithm**: Public/private key pairs for enhanced security
- **Device Fingerprinting**: Track and validate device-specific sessions
- **IP Address Tracking**: Monitor access patterns for security
- **Token Blacklisting**: Real-time token revocation via Redis
- **Session Management**: Comprehensive session tracking and control

```python
# Login with enhanced security tracking
login_response = await client.auth.login(
    email="parent@example.com",
    password="SecurePassword123!",
    device_info={
        "user_agent": "Mozilla/5.0...",
        "platform": "MacOS",
        "timezone": "America/New_York"
    }
)

# Tokens now include device and IP context
print(f"Session ID: {login_response.session_id}")
print(f"Device registered: {login_response.device_id}")
```

### Automatic Retry Logic

All API endpoints now include intelligent retry logic:

```python
# Automatic retries with exponential backoff
response = await client.conversations.send_message(
    child_id=child.id,
    message="Tell me a story",
    # Retry configuration (optional)
    max_retries=3,
    retry_strategy="exponential_backoff"
)

# The SDK automatically handles:
# - Network timeouts
# - Service unavailable errors
# - Rate limit backoff
# - Circuit breaker patterns
```

### Circuit Breaker Protection

Built-in circuit breaker protection for resilience:

```python
# Circuit breaker status
breaker_status = await client.health.circuit_breaker_status()
for service, status in breaker_status.items():
    print(f"{service}: {status.state}")
    if status.state == "OPEN":
        print(f"  Next retry: {status.next_attempt_time}")
```

## 🔄 Retry Logic & Error Handling

### Intelligent Retry Patterns

The API implements sophisticated retry patterns for different scenarios:

```python
# Chat endpoint - limited retries for child safety
try:
    response = await client.conversations.send_message(
        child_id=child.id,
        message="Hello Teddy!"
    )
    # Max 2 retries with safety score validation
except SafetyViolationError as e:
    # Safety failures use fallback responses
    print(f"Safety fallback used: {e.fallback_response}")
```

### Service-Specific Retry Logic

Different endpoints use optimized retry strategies:

- **Chat Messages**: 2 retries max (child safety priority)
- **Authentication**: 1 retry (prevent brute force)
- **Database Operations**: 3 retries (network resilience)
- **Audio Processing**: 2 retries (real-time performance)
- **Health Checks**: 3 retries (monitoring reliability)

```python
# Monitoring retry metrics
retry_metrics = await client.monitoring.get_retry_metrics()
print(f"Total retries today: {retry_metrics.total_retries}")
print(f"Success rate: {retry_metrics.success_rate}%")
```

## 🛡️ Security Guardrails

### Comprehensive Security Protection

The AI Teddy Bear platform implements multi-layered security guardrails to protect children and ensure COPPA compliance:

#### Security Validation Pipeline

Every request goes through comprehensive security validation:

```python
# Example of security validation response
{
    "security_status": {
        "allowed": true,
        "violations": [],
        "action": "allow",
        "checks_performed": [
            "rate_limiting",
            "ip_reputation",
            "user_agent_validation", 
            "content_filtering",
            "child_safety_validation"
        ]
    }
}
```

#### Rate Limiting Protection

Advanced rate limiting with multiple tiers:

```python
# Rate limits are automatically applied based on user tier
# Anonymous: 20 req/min, 500 req/hour
# Basic: 60 req/min, 2000 req/hour  
# Premium: 120 req/min, 5000 req/hour

# Specific endpoint limits
# /auth/login: 5 req/min (brute force protection)
# /chat: 10 req/min with child safety priority
# /audio: 20 req/min optimized for real-time
```

#### Input Validation & Sanitization

All inputs are validated and sanitized:

```python
# Example validation
validation_result = {
    "is_valid": true,
    "sanitized_content": "Hello Teddy!",
    "security_violations": [],
    "child_safety_violations": [],
    "risk_score": 0.0
}
```

### Security Status Monitoring

Monitor security status in real-time:

```python
# Get security status
security_status = await client.security.get_status()
print(f"Security guardrails: {security_status.active}")
print(f"Rate limiting: {security_status.rate_limiting.active}")
print(f"Input validation: {security_status.input_validation.active}")

# Test security guardrails (admin only)
test_result = await client.security.test_guardrails({
    "message": "Test message",
    "child_age": 7,
    "test_inputs": {
        "suspicious_content": "<script>alert('test')</script>"
    }
})
```

## 👶 Child Safety Compliance

### COPPA Compliance Features

Comprehensive COPPA compliance built-in:

#### Age Verification
- Strict age validation (3-13 years)
- Age-appropriate content filtering
- Automatic compliance checks

#### Content Safety Validation

```python
# Child safety validation example
safety_check = {
    "is_safe": true,
    "coppa_compliant": true,
    "violations": [],
    "risk_score": 0.0,
    "age_appropriate": true
}
```

#### Protected Patterns Detection

The system automatically detects and blocks:
- Personal information requests (address, phone, etc.)
- Meeting solicitation attempts
- Inappropriate content for age group
- Scary or violent content
- Adult-oriented topics

#### Enhanced Safety Features

```python
# Safety validation is applied to all child interactions
child_interaction = {
    "message": "Hi Teddy!",
    "child_age": 7,
    "safety_validation": {
        "content_appropriate": true,
        "no_personal_info": true,
        "age_suitable": true,
        "coppa_compliant": true
    }
}
```

### Safety Monitoring

Real-time safety monitoring:

```python
# Monitor child safety metrics
safety_metrics = await client.monitoring.get_child_safety_metrics()
print(f"Interactions today: {safety_metrics.total_interactions}")
print(f"Safety violations: {safety_metrics.violations_count}")
print(f"COPPA compliance rate: {safety_metrics.coppa_compliance_rate}%")
```

## 📊 Monitoring & Health Checks

### Enhanced Health Endpoints

New comprehensive health monitoring:

```python
# Main health check
health = await client.health.check()
print(f"Overall status: {health.status}")
print(f"Database: {health.database}")
print(f"Redis: {health.redis}")

# Audio pipeline health
audio_health = await client.health.audio_pipeline()
print(f"STT Provider: {audio_health.stt_status}")
print(f"TTS Provider: {audio_health.tts_status}")
print(f"Latency: {audio_health.average_latency}ms")

# Audio metrics for monitoring
audio_metrics = await client.health.audio_metrics()
print(f"Requests today: {audio_metrics.total_requests}")
print(f"Success rate: {audio_metrics.success_rate}%")
print(f"P95 latency: {audio_metrics.p95_latency}ms")
```

### Real-time Metrics

Access real-time performance metrics:

```python
# Prometheus-compatible metrics
metrics = await client.monitoring.get_metrics()
# Returns metrics in Prometheus format for external monitoring

# Audio-specific metrics
audio_metrics = await client.monitoring.get_audio_metrics()
# Filtered metrics for audio pipeline monitoring
```

## 🎵 Real-time Features

### ESP32 Audio Processing

Enhanced ESP32 integration with optimized audio processing:

```python
# Process ESP32 audio with retry logic
audio_response = await client.esp32.process_audio(
    child_id=child.id,
    audio_data=audio_bytes,
    language_code="en-US"
)

# Response includes retry metadata
print(f"Processing attempt: {audio_response.metadata.retry_attempt}")
print(f"Provider used: {audio_response.metadata.stt_provider}")
print(f"Latency: {audio_response.metadata.processing_time}ms")
```

### WebSocket with Retry Support

WebSocket connections now include automatic reconnection:

```python
import asyncio
from ai_teddy_bear.websockets import ConversationWebSocket

async def conversation_stream():
    ws = ConversationWebSocket(
        token="your-jwt-token",
        auto_reconnect=True,
        max_reconnect_attempts=5
    )
    
    try:
        await ws.connect()
        
        # Send message
        await ws.send_message({
            "child_id": child.id,
            "content": "Hello Teddy!"
        })
        
        # Receive with automatic retry
        async for message in ws:
            if message.type == "response":
                print(f"Teddy: {message.content}")
                
    except ConnectionError:
        # Automatic reconnection will be attempted
        print("Connection lost, retrying...")
```

## 📚 Advanced Features

### Batch Operations

```python
# Send multiple messages in batch
messages = [
    {"child_id": child1.id, "message": "Hello!"},
    {"child_id": child2.id, "message": "How are you?"}
]

responses = await client.conversations.send_batch(messages)
```

### Custom Safety Rules

```python
# Configure custom safety rules
await client.safety.configure_rules(
    child_id=child.id,
    rules={
        "block_words": ["custom", "words"],
        "time_limits": {"daily_minutes": 30},
        "content_types": ["educational", "creative"]
    }
)
```

## 🔧 Configuration

### Environment Variables

```bash
# Required
AI_TEDDY_API_KEY=your-api-key-here
AI_TEDDY_ENVIRONMENT=production

# Optional
AI_TEDDY_BASE_URL=https://api.aiteddybear.com
AI_TEDDY_TIMEOUT=30
AI_TEDDY_RETRY_ATTEMPTS=3
```

### Client Configuration

```python
client = Client(
    api_key=os.getenv("AI_TEDDY_API_KEY"),
    environment=os.getenv("AI_TEDDY_ENVIRONMENT", "sandbox"),
    timeout=30,
    retry_attempts=3,
    enable_logging=True,
    log_level="INFO"
)
```

## 💻 Code Examples

### Complete Integration Example

```python
import asyncio
from ai_teddy_bear import Client
from ai_teddy_bear.exceptions import *

async def complete_ai_teddy_integration():
    """Complete example showing all enhanced features"""
    
    # Initialize client with retry configuration
    client = Client(
        api_key=os.getenv("AI_TEDDY_API_KEY"),
        environment="production",
        timeout=30,
        retry_attempts=3,
        enable_logging=True
    )
    
    try:
        # Enhanced authentication with device tracking
        login_response = await client.auth.login(
            email="parent@example.com",
            password="SecurePassword123!",
            device_info={
                "user_agent": "AI-Teddy-App/1.0",
                "platform": "iOS",
                "timezone": "America/New_York"
            }
        )
        print(f"✅ Logged in - Session: {login_response.session_id[:8]}...")
        
        # Create child profile
        child = await client.children.create(
            name="Emma",
            age=7,
            interests=["dinosaurs", "space", "art"],
            safety_level="high"
        )
        print(f"✅ Child profile created: {child.name}")
        
        # Start conversation with retry logic
        conversation_response = await client.conversations.send_message(
            child_id=child.id,
            message="Hi Teddy! Tell me about dinosaurs!",
            child_age=7,
            child_name="Emma"
        )
        print(f"🧸 Teddy: {conversation_response.response}")
        print(f"📊 Safety Score: {conversation_response.safety_score}")
        
        # Process audio if available
        if audio_data:
            audio_response = await client.esp32.process_audio(
                child_id=child.id,
                audio_data=audio_data,
                language_code="en-US"
            )
            print(f"🎵 Audio processed in {audio_response.metadata.processing_time}ms")
        
        # Monitor health
        health = await client.health.check()
        print(f"🏥 System Health: {health.status}")
        
        # Get session information
        sessions = await client.auth.get_sessions()
        print(f"📱 Active Sessions: {sessions.total_sessions}")
        
    except AuthenticationError as e:
        print(f"❌ Auth failed: {e.message}")
    except ChildSafetyError as e:
        print(f"🛡️ Safety violation: {e.violation_type}")
        print(f"🔄 Fallback response: {e.fallback_response}")
    except RateLimitError as e:
        print(f"⏱️ Rate limited. Retry in {e.retry_after}s")
    except ServiceUnavailableError as e:
        print(f"🚫 Service unavailable: {e.message}")
        # Automatic retries will be attempted
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
    finally:
        # Optional: Revoke session on exit
        try:
            await client.auth.revoke_all_tokens(reason="session_end")
            print("🔐 Session revoked successfully")
        except:
            pass

# Run the example
asyncio.run(complete_ai_teddy_integration())
```

### Real-time Conversation Example

```python
import asyncio
from ai_teddy_bear.websockets import ConversationWebSocket

async def real_time_conversation():
    """Example of real-time conversation with retry support"""
    
    ws = ConversationWebSocket(
        token="your-jwt-token",
        child_id="child-uuid",
        auto_reconnect=True,
        max_reconnect_attempts=5,
        reconnect_delay=2.0
    )
    
    try:
        await ws.connect()
        print("🔗 Connected to real-time conversation")
        
        # Send initial message
        await ws.send_message({
            "content": "Hi Teddy! Let's chat!",
            "type": "text"
        })
        
        # Listen for responses with automatic retry
        async for message in ws:
            if message.type == "response":
                print(f"🧸 Teddy: {message.content}")
                
                # Simulate user response
                await asyncio.sleep(2)
                await ws.send_message({
                    "content": "That's interesting! Tell me more!",
                    "type": "text"
                })
                
            elif message.type == "audio":
                print(f"🎵 Audio response: {message.audio_url}")
                
            elif message.type == "safety_alert":
                print(f"🛡️ Safety alert: {message.severity}")
                
    except ConnectionError as e:
        print(f"📡 Connection error: {e}")
        # Auto-reconnection will be attempted
    except Exception as e:
        print(f"💥 Error: {e}")
    finally:
        await ws.close()
        print("🔌 Connection closed")

asyncio.run(real_time_conversation())
```

### Monitoring and Analytics Example

```python
async def monitoring_dashboard():
    """Example of comprehensive monitoring and analytics"""
    
    client = Client(api_key=os.getenv("AI_TEDDY_API_KEY"))
    
    # Health monitoring
    health = await client.health.check()
    audio_health = await client.health.audio_pipeline()
    
    print("🏥 System Health Dashboard")
    print(f"  Overall: {health.status}")
    print(f"  Database: {health.database}")
    print(f"  Redis: {health.redis}")
    print(f"  Audio Pipeline: {audio_health.status}")
    print(f"  Audio Latency: {audio_health.average_latency}ms")
    
    # Retry metrics
    retry_metrics = await client.monitoring.get_retry_metrics()
    print("\n🔄 Retry Statistics")
    print(f"  Total Retries: {retry_metrics.total_retries}")
    print(f"  Success Rate: {retry_metrics.success_rate}%")
    print(f"  Circuit Breakers: {len(retry_metrics.circuit_breaker_details)}")
    
    # Circuit breaker status
    for service, breaker in retry_metrics.circuit_breaker_details.items():
        print(f"    {service}: {breaker.state}")
        if breaker.state == "OPEN":
            print(f"      Failures: {breaker.failure_count}")
    
    # Audio metrics
    audio_metrics = await client.health.audio_metrics()
    print("\n🎵 Audio Pipeline Metrics")
    print(f"  Total Requests: {audio_metrics.total_requests}")
    print(f"  Success Rate: {audio_metrics.success_rate}%")
    print(f"  P95 Latency: {audio_metrics.p95_latency}ms")
    print(f"  P99 Latency: {audio_metrics.p99_latency}ms")

asyncio.run(monitoring_dashboard())
```

## 📞 Support

- **Documentation**: https://docs.aiteddybear.com
- **API Reference**: https://api.aiteddybear.com/docs
- **Support Email**: support@aiteddybear.com
- **Community Forum**: https://community.aiteddybear.com
- **Status Page**: https://status.aiteddybear.com

## 📋 Changelog

### Version 2.1.0 (2025-08-03)
- ✅ **Comprehensive Security Guardrails** - Multi-layered protection system
- ✅ **Enhanced Child Safety Compliance** - COPPA-focused validation
- ✅ **Advanced Rate Limiting** - Tier-based protection with abuse detection
- ✅ **Real-time Security Monitoring** - Live threat detection and response
- ✅ **Input Validation & Sanitization** - SQL injection, XSS, and content filtering
- ✅ **IP Reputation & Bot Detection** - Automated threat intelligence
- ✅ **Security Status Dashboard** - Real-time security metrics
- ✅ **Content Safety Patterns** - Age-appropriate interaction validation

### Version 2.0.0 (2025-08-03)
- ✅ Enhanced JWT security with RS256 and device tracking
- ✅ Intelligent retry logic across all endpoints  
- ✅ Circuit breaker protection for resilience
- ✅ Advanced health monitoring and metrics
- ✅ Real-time audio processing optimizations
- ✅ Comprehensive session management
- ✅ Enhanced error handling and fallback responses

### Version 1.5.0 (2025-07-01)
- Basic retry logic
- Simple health checks
- Standard JWT authentication
