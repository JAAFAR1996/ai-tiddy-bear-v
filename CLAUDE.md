# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

AI Teddy Bear - A child-safe AI companion system with ESP32 hardware integration, real-time audio processing, and comprehensive parent monitoring capabilities.

## Critical Commands

### Running the Application

```bash
# Development server
uvicorn src.main:app --reload --port 8000

# Production server (on Render)
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT

# With specific environment
ENVIRONMENT=production uvicorn src.main:app --port 8000
```

### Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest -m unit          # Fast unit tests
pytest -m integration   # Integration tests  
pytest -m e2e          # End-to-end tests
pytest -m security     # Security validation

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Run mutation testing
mutmut run --paths-to-mutate=src/

# Run all quality gates (must pass for production)
make all
```

### Database Operations

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Check current revision
alembic current

# Production migration (requires DATABASE_URL)
DATABASE_URL=postgresql://... alembic upgrade head
```

### Linting and Code Quality

```bash
# Python linting
ruff check src/
black src/ --check
mypy src/ --strict

# Security scanning
bandit -r src/
safety check

# Full quality check
make quality
```

### ESP32 Testing

```bash
# Test ESP32 authentication
python test_esp32_auth.py

# Test claim endpoint with actual HMAC
python production_esp32_integration_test.py
```

## Architecture Overview

### Clean Architecture Layers

The codebase follows Clean Architecture with strict layer separation:

1. **Core Domain (`src/core/`)**: Business entities and rules
   - Child safety validation
   - COPPA compliance logic
   - Device-child relationships

2. **Application Layer (`src/application/`)**: Use cases and services
   - `ConsolidatedAIService`: Multi-provider AI orchestration with failover
   - `ChildSafetyService`: Real-time content filtering and monitoring
   - Business logic orchestration

3. **Infrastructure (`src/infrastructure/`)**: External integrations
   - Database adapters (PostgreSQL with SQLAlchemy)
   - Redis for caching and rate limiting
   - Audio processing (Whisper STT, ElevenLabs TTS)
   - Security implementations (JWT, HMAC)

4. **Adapters/Presentation (`src/adapters/`, `src/presentation/`)**: API layer
   - FastAPI routers with WebSocket support
   - ESP32 device endpoints
   - Parent dashboard APIs

### Critical Services and Their Interactions

**ESP32 Authentication Flow**:
```
ESP32 → HMAC-SHA256(device_id, child_id, nonce) → /api/v1/pair/claim
Server validates → Generates JWT → Returns token
ESP32 uses JWT → WebSocket connection → Real-time audio streaming
```

**Audio Processing Pipeline**:
```
ESP32 mic → Base64 audio → WebSocket → Whisper STT → Text
Text → Child Safety Filter → AI Service → Response text
Response → ElevenLabs TTS → Base64 audio → ESP32 speaker
```

**Multi-Provider AI Failover**:
- Primary: OpenAI GPT-4
- Fallback: Anthropic Claude
- Emergency: Local safety responses
- All responses filtered through ChildSafetyService

### Key Configuration Points

**Environment Variables (Required in Production)**:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection for caching/rate limiting
- `ESP32_SHARED_SECRET`: HMAC key for device authentication (64 hex chars)
- `JWT_SECRET_KEY`: JWT signing key
- `OPENAI_API_KEY`: Primary AI provider
- `ANTHROPIC_API_KEY`: Fallback AI provider
- `ELEVENLABS_API_KEY`: Text-to-speech service

**ESP32 Integration Points**:
- WebSocket: `/api/v1/esp32/private/chat` (requires JWT)
- Config: `/api/v1/esp32/config` (public)
- Firmware: `/api/v1/esp32/firmware` (public)
- Claim: `/api/v1/pair/claim` (HMAC auth)

### Database Schema Key Relationships

The system uses PostgreSQL with these core relationships:
- `devices` ← → `children` (many-to-many through `device_child_links`)
- `children` → `parents` (many-to-one)
- `conversations` → `messages` (one-to-many)
- `safety_reports` tracks all safety incidents

Migrations must preserve child data integrity and maintain audit logs.

### Security Architecture

1. **Device Authentication**: HMAC-SHA256 with per-device OOB secrets
2. **API Authentication**: JWT tokens with role-based access
3. **Parent Access**: Separate authentication with MFA support
4. **Child Safety**: Multiple layers of content filtering
5. **Data Privacy**: COPPA/GDPR compliant with encryption at rest

### WebSocket Protocol

ESP32 WebSocket messages follow this structure:
```json
{
  "type": "audio_chunk|audio_start|audio_end|heartbeat",
  "audio_data": "base64_encoded_audio",
  "chunk_id": "uuid",
  "audio_session_id": "uuid",
  "is_final": false
}
```

Server responses:
```json
{
  "type": "audio_response|error|system",
  "audio_data": "base64_encoded_mp3",
  "text": "AI response text",
  "format": "mp3",
  "safety_score": 0.98
}
```

### Testing Strategy

All new features must include:
1. Unit tests for business logic
2. Integration tests for service interactions
3. E2E tests for critical user paths
4. Security tests for authentication/authorization
5. Performance tests for audio processing

Minimum requirements:
- 80% code coverage
- 70% mutation score
- All tests < 180s timeout
- No skipped/fake tests

### Deployment Notes

The application deploys automatically to Render.com on push to main branch:
- Uses Dockerfile for containerization
- Runs database migrations automatically
- Health checks on `/health` endpoint
- WebSocket support enabled
- Auto-scaling based on load

ESP32 devices can auto-register on first connection if `claim_api_auto_register.py` is enabled.

### Common Development Patterns

When implementing new features:
1. Start with core domain entities
2. Add application service layer
3. Implement infrastructure adapters
4. Create API endpoints last
5. Always include comprehensive tests
6. Update OpenAPI documentation

For ESP32 communication:
1. Use HMAC for initial authentication
2. JWT for session management
3. WebSocket for real-time data
4. Implement reconnection logic
5. Handle offline scenarios