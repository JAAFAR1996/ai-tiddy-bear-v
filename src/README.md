# AI Teddy Bear - Source Code Documentation
## دليل الكود المصدري لدمية الدب الذكية

### 📋 نظرة عامة / Overview

This repository contains the source code for an enterprise-grade AI Teddy Bear application designed for safe child interactions. The system implements COPPA compliance, advanced safety monitoring, and a clean architecture pattern.

يحتوي هذا المستودع على الكود المصدري لتطبيق دمية الدب الذكية المصمم للتفاعل الآمن مع الأطفال. يطبق النظام امتثال COPPA ومراقبة الأمان المتقدمة ونمط العمارة النظيفة.

### 🏗️ معمارية النظام / System Architecture

The application follows **Clean Architecture** principles with clear separation of concerns:

```
src/
├── core/                    # Core business logic and entities
├── application/             # Application services and use cases  
├── infrastructure/          # External concerns (database, config, etc.)
├── interfaces/              # Interface definitions and contracts
├── adapters/                # External adapters (web, database)
├── shared/                  # Shared DTOs and utilities
└── main.py                  # Application entry point
```

### 📂 تفصيل المجلدات الرئيسية / Main Directory Structure

#### 🎯 `/core` - الطبقة الأساسية
Contains the core business logic that is independent of external concerns:

- **`models.py`** - Core entities (`ConversationEntity`, `MessageEntity`)
- **`entities.py`** - Business entities and domain models
- **`value_objects/`** - Value objects for type safety
- **`exceptions.py`** - Domain-specific exceptions
- **`services.py`** - Core business services
- **`repositories.py`** - Repository interfaces
- **`security_service.py`** - Core security functionality

#### 🚀 `/application` - طبقة التطبيق
Application-specific business logic and orchestration:

- **`services/`** - Application services
  - `ai_service.py` - AI interaction and safety filtering
  - `audio_service.py` - Audio processing and streaming
  - `child_safety_service.py` - COPPA compliance and safety
  - `user_service.py` - User management
  - `streaming/` - Real-time audio processing

- **`use_cases/`** - Business use case implementations
  - `generate_ai_response.py` - AI response generation
  - `manage_child_profile.py` - Child profile management
  - `process_esp32_audio.py` - ESP32 audio handling

- **`content/`** - Content management and filtering
  - `content_manager.py` - Content creation and management
  - `age_filter.py` - Age-appropriate content filtering
  - `educational_content.py` - Educational content generation

- **`templates/`** - Response templates
  - `responses/` - Age-specific response templates
  - `stories/` - Story templates and educational content

#### 🏢 `/infrastructure` - طبقة البنية التحتية
External concerns and technical implementation:

- **`config/`** - Configuration management
  - `loader.py` - Configuration loading and validation
  - `production_config.py` - Production-specific settings
  - `validator.py` - Configuration validation

- **`security/`** - Security infrastructure
  - `auth.py` - Authentication and authorization
  - Rate limiting and security headers

- **`monitoring/`** - System monitoring
  - `health.py` - Health checks
  - `metrics.py` - Performance metrics
  - `audit.py` - Audit logging

- **`device/`** - IoT device management
  - `esp32_protocol.py` - ESP32 communication
  - `wifi_manager.py` - WiFi connectivity
  - `audio_streamer.py` - Real-time audio streaming

#### 🔌 `/interfaces` - واجهات النظام
Interface definitions and contracts:

- **`providers/`** - External service providers
  - `ai_provider.py` - AI service provider interface
  - `tts_provider.py` - Text-to-speech provider interface
  - `speech_to_text_provider.py` - Speech recognition interface

- **`repositories/`** - Data access interfaces
- **`services/`** - Service interface definitions

#### 🌐 `/adapters` - محولات النظام
External adapters implementing interfaces:

- **`web.py`** - FastAPI web adapter with REST endpoints
- **`api_routes.py`** - API route definitions
- **`database_production.py`** - Database implementation
- **`dashboard/`** - Parent dashboard implementation
  - `parent_dashboard.py` - Dashboard backend
  - `child_monitor.py` - Real-time monitoring
  - `safety_controls.py` - Safety control panel
  - `templates/` - Dashboard HTML templates

#### 📦 `/shared` - المشتركة
Shared components and DTOs:

- **`dto/`** - Data Transfer Objects
  - `ai_response.py` - AI response structure
  - `child_data.py` - Child data models
  - `esp32/` - ESP32 communication DTOs

#### 🛠️ `/utils` - الأدوات المساعدة
Utility functions and helpers:

- **`crypto_utils.py`** - Encryption and security utilities
- **`validation_utils.py`** - Input validation helpers
- **`text_utils.py`** - Text processing utilities
- **`date_utils.py`** - Date and time utilities

### 🔧 الميزات الرئيسية / Key Features

#### 🛡️ الأمان وامتثال COPPA
- **Content Filtering**: Advanced age-appropriate content filtering
- **Safety Monitoring**: Real-time safety analysis and blocking
- **Data Protection**: Encrypted storage and COPPA-compliant data handling
- **Audit Logging**: Comprehensive audit trails for compliance

#### 🤖 الذكاء الاصطناعي
- **Multi-Provider Support**: OpenAI GPT integration with failover
- **Age-Appropriate Responses**: Tailored responses based on child's age (3-13)
- **Context Awareness**: Conversation history and personalization
- **Safety Post-Processing**: AI response filtering and validation

#### 🎵 معالجة الصوت
- **Real-time Streaming**: ESP32 audio streaming with low latency
- **Speech-to-Text**: Voice input processing
- **Text-to-Speech**: Natural voice responses
- **Audio Buffer Management**: Efficient audio processing pipeline

#### 📊 المراقبة والتحليلات
- **Health Monitoring**: System health checks and metrics
- **Performance Tracking**: Response times and service availability
- **Usage Analytics**: Child interaction patterns (privacy-preserving)
- **Error Tracking**: Comprehensive error logging and alerting

### 🚦 كيفية تشغيل النظام / Running the System

#### المتطلبات الأساسية / Prerequisites
```bash
# Python dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Configure your API keys and settings in .env
```

#### تشغيل التطبيق / Starting the Application
```bash
# Development mode
python src/main.py

# Production mode
ENVIRONMENT=production python src/main.py

# Using uvicorn directly
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

#### نقاط النهاية الرئيسية / Main Endpoints
- **`GET /`** - Root endpoint with system information
- **`GET /health`** - Health check endpoint
- **`POST /api/v1/conversation`** - AI conversation endpoint
- **`POST /api/v1/audio/stream`** - Audio streaming endpoint
- **`GET /api/v1/dashboard`** - Parent dashboard
- **`GET /docs`** - API documentation (development only)

### 🔒 الأمان والامتثال / Security & Compliance

#### COPPA Compliance
- Age verification (3-13 years)
- Parental consent management
- Data minimization and retention
- Safe content filtering

#### Security Features
- JWT authentication
- Rate limiting and DDoS protection
- Content Security Policy headers
- Input validation and sanitization
- Encrypted data storage

#### Safety Monitoring
- Real-time content analysis
- Inappropriate content blocking
- Incident reporting and alerts
- Comprehensive audit logging

### 📈 الأداء والتحسين / Performance & Optimization

#### Caching Strategy
- Redis-based response caching
- Memory fallback for development
- TTL-based cache invalidation
- Smart cache key generation

#### Scalability Features
- Async/await throughout the application
- Connection pooling for databases
- Horizontal scaling support
- Load balancing ready

#### Monitoring
- Prometheus metrics integration
- Health check endpoints
- Performance tracking
- Error rate monitoring

### 🧪 الاختبار / Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/safety/
```

### 🔄 النشر / Deployment

#### Docker Support
```bash
# Build image
docker build -t ai-teddy-bear .

# Run container
docker run -p 8000:8000 ai-teddy-bear
```

#### Environment Configuration
- **Development**: Full debugging and documentation
- **Staging**: Production-like with additional logging
- **Production**: Optimized for performance and security

### 📚 التوثيق الإضافي / Additional Documentation

- **API Documentation**: Available at `/docs` in development mode
- **Configuration Guide**: See `infrastructure/config/` for detailed configuration options
- **Safety Guidelines**: Comprehensive safety implementation in `application/services/child_safety_service.py`
- **Architecture Decisions**: Check individual audit reports in each module

### 🤝 المساهمة / Contributing

1. Follow the Clean Architecture principles
2. Ensure all safety tests pass
3. Add comprehensive logging for audit trails
4. Update documentation for any API changes
5. Test with multiple age groups (3-5, 6-9, 10-13)

### 📞 الدعم / Support

For technical support or security concerns:
- **Email**: support@ai-teddy-bear.com
- **Documentation**: Check module-specific README files
- **Security Issues**: Report immediately through secure channels

---

### 🏷️ الكود المميز / Key Code Components

#### Main Application Entry Point
**File**: `main.py`
- FastAPI application setup
- Security middleware configuration
- Rate limiting and CORS
- Health check endpoints

#### AI Service (Enterprise Grade)
**File**: `application/services/ai_service.py`
- Advanced content filtering engine
- Multi-model AI provider support
- Comprehensive retry mechanisms
- Performance metrics and caching

#### Child Safety Service
**File**: `application/services/child_safety_service.py`
- COPPA compliance implementation
- Age-appropriate content filtering
- Safety incident reporting
- Parental control integration

#### Audio Processing Pipeline
**File**: `application/services/audio_service.py`
- Real-time audio streaming
- ESP32 device communication
- Speech-to-text and text-to-speech integration
- Latency optimization

---

*This documentation is regularly updated to reflect the current system architecture and implementation.*

*يتم تحديث هذا التوثيق بانتظام ليعكس معمارية النظام والتنفيذ الحالي.*