# AI Teddy Bear - Copilot Instructions

## Architecture Overview

This is a **child-safe AI companion** built with FastAPI, following **Clean Architecture** principles with strict **COPPA compliance**. The system prioritizes safety through multi-layered content filtering, rate limiting, and age-appropriate interactions.

### Core Structure
- **`src/core/`** - Domain entities (`Child`, `Message`, `Conversation`) and consolidated services
- **`src/adapters/`** - FastAPI web layer (`web.py`) and database adapters
- **`src/infrastructure/`** - Configuration, DI container, monitoring, and cross-cutting concerns
- **`src/services/`** - Consolidated service implementations with registry pattern
- **`tests_consolidated/`** - All tests consolidated from 25+ original test files

### Service Architecture
Uses **ServiceRegistry pattern** (`src/services/service_registry.py`) for dependency management:
```python
# Get services through registry
ai_service = await get_ai_service()
safety_service = await get_child_safety_service()
```

## Configuration System

**Unified configuration** through `src/infrastructure/config/loader.py`:
- Singleton pattern with startup validation
- Fails fast with detailed error messages if required vars missing
- Access via: `from src.infrastructure.config.loader import get_config`

### Required Environment Variables
```bash
SECRET_KEY                 # 32+ chars, cryptographically secure
JWT_SECRET_KEY            # 32+ chars, unique from SECRET_KEY
COPPA_ENCRYPTION_KEY      # 32+ chars for child data encryption
DATABASE_URL              # postgresql://...
REDIS_URL                 # redis://...
OPENAI_API_KEY           # sk-...
CORS_ALLOWED_ORIGINS     # JSON array of exact origins
PARENT_NOTIFICATION_EMAIL # valid email for compliance
```

## Child Safety & COPPA Compliance

**Critical**: All child interactions must pass safety checks:
- Age validation: 3-13 years only
- Content filtering through `ChildSafetyService`
- Rate limiting via `slowapi` 
- Parent consent tracking
- Encrypted PII storage

Example safety pattern:
```python
# Always validate child age first
if not 3 <= child_age <= 13:
    raise HTTPException(400, "COPPA compliance violation")

# Safety check required before AI response
safety_result = await safety_service.check_content(message)
if not safety_result.is_safe:
    return filtered_response
```

## Development Workflow

### Local Development
```bash
# Start infrastructure
docker-compose up postgres redis

# Install dependencies  
pip install -r requirements.txt

# Run with auto-reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing Strategy
- **Consolidated tests** in `tests_consolidated/` (combined from 25+ files)
- Run with: `pytest tests_consolidated/`
- Focus areas: AI safety, COPPA compliance, authentication
- Mock external services (OpenAI, Redis) in tests

### Database Operations
- **Alembic migrations** in `migrations/versions/`
- Production schema in `sql/init-production.sql`
- Always use async database operations
- Connection pooling configured in `database_production.py`

## Key Patterns & Conventions

### Error Handling
- Centralized in `src/infrastructure/error_handler.py`
- Custom exceptions in `src/infrastructure/exceptions.py`
- Always include safety context in error responses

### API Endpoints
- All routes in `src/adapters/web.py` 
- Request/response models defined inline
- Authentication via `get_current_user` dependency
- Rate limiting on all child-facing endpoints

### Service Dependencies
Use dependency injection through `ApplicationContainer`:
```python
# Prefer interface-based dependencies
from src.interfaces.services import IAIService

# Access through registry for runtime resolution
service = await get_service_registry().get_ai_service()
```

## Production Deployment

### Docker Deployment
- Multi-service with `docker-compose.yml`
- Health checks for postgres/redis dependencies
- Production scripts in `scripts/production/`

### Key Commands
```bash
# Production deployment
./scripts/production/deploy.sh production v1.0.0

# Database migration
./scripts/production/migrate.sh

# Health monitoring
./scripts/production/health_check.sh
```

### Monitoring & Observability
- Structured logging with `structlog`
- Health endpoints for all services
- Redis for session/cache management
- Backup scripts for data protection

## AI Integration Specifics

### OpenAI Integration
- Async client in production AI service
- Age-appropriate prompt engineering
- Emotion detection and response modulation
- Content safety validation before/after AI generation

### Response Pipeline
1. Input validation (age, content safety)
2. Conversation context retrieval
3. AI generation with safety prompts
4. Safety re-validation of response
5. Conversation persistence with encryption

## Critical Files to Understand
- `src/main.py` - Application bootstrap and middleware
- `src/core/entities.py` - Domain models with safety constraints
- `src/adapters/web.py` - All API endpoints
- `src/infrastructure/config/loader.py` - Configuration management
- `src/services/service_registry.py` - Service discovery
- `tests_consolidated/test_ai.py` - AI safety test patterns

When making changes, always consider COPPA compliance and child safety implications first.
