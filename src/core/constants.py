"""
Unified Constants for AI Teddy Bear
All constants are loaded from environment/config if available, with safe defaults.
Includes validation and clear separation between technical and business constants.
"""

import os
import json
from enum import Enum


# ================= BUSINESS CONSTANTS =================
# Child Safety
MAX_CHILD_AGE = int(os.getenv("MAX_CHILD_AGE", 13))  # COPPA: 13 years max
MIN_CHILD_AGE = int(os.getenv("MIN_CHILD_AGE", 3))  # COPPA: 3 years min
DEFAULT_SAFETY_SCORE = float(os.getenv("DEFAULT_SAFETY_SCORE", 0.95))
MIN_SAFETY_THRESHOLD = float(os.getenv("MIN_SAFETY_THRESHOLD", 0.7))


# ================= TECHNICAL CONSTANTS =================
# Database
DEFAULT_DB_POOL_SIZE = int(os.getenv("DEFAULT_DB_POOL_SIZE", 20))
DEFAULT_DB_MAX_OVERFLOW = int(os.getenv("DEFAULT_DB_MAX_OVERFLOW", 0))
DEFAULT_DB_POOL_RECYCLE = int(os.getenv("DEFAULT_DB_POOL_RECYCLE", 300))
DEFAULT_CONNECTION_TIMEOUT = int(os.getenv("DEFAULT_CONNECTION_TIMEOUT", 30))


# Rate Limiting
DEFAULT_REQUESTS_PER_MINUTE = int(os.getenv("DEFAULT_REQUESTS_PER_MINUTE", 60))
DEFAULT_REQUESTS_PER_HOUR = int(os.getenv("DEFAULT_REQUESTS_PER_HOUR", 600))
DEFAULT_REQUESTS_PER_DAY = int(os.getenv("DEFAULT_REQUESTS_PER_DAY", 5000))
DEFAULT_BURST_LIMIT = int(os.getenv("DEFAULT_BURST_LIMIT", 10))
DEFAULT_BLOCK_DURATION_MINUTES = int(os.getenv("DEFAULT_BLOCK_DURATION_MINUTES", 60))


# AI Response
MAX_AI_RESPONSE_TOKENS = int(os.getenv("MAX_AI_RESPONSE_TOKENS", 200))
MAX_STORY_TOKENS = int(os.getenv("MAX_STORY_TOKENS", 500))
DEFAULT_AI_TIMEOUT = float(os.getenv("DEFAULT_AI_TIMEOUT", 30.0))
MAX_CONVERSATION_HISTORY = int(os.getenv("MAX_CONVERSATION_HISTORY", 10))


# Session Management
DEFAULT_SESSION_TIMEOUT = int(os.getenv("DEFAULT_SESSION_TIMEOUT", 1800))
MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", 100))
SESSION_CLEANUP_INTERVAL = int(os.getenv("SESSION_CLEANUP_INTERVAL", 300))


# File Upload
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 5))
MAX_AUDIO_DURATION_SECONDS = int(os.getenv("MAX_AUDIO_DURATION_SECONDS", 60))
ALLOWED_AUDIO_FORMATS = os.getenv("ALLOWED_AUDIO_FORMATS", "wav,mp3,m4a").split(",")
ALLOWED_IMAGE_FORMATS = os.getenv("ALLOWED_IMAGE_FORMATS", "jpg,jpeg,png").split(",")


# COPPA Compliance
DATA_RETENTION_DAYS = int(os.getenv("DATA_RETENTION_DAYS", 90))
PARENTAL_CONSENT_VALIDITY_DAYS = int(os.getenv("PARENTAL_CONSENT_VALIDITY_DAYS", 365))
AUDIT_LOG_RETENTION_DAYS = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", 2555))
MIN_PARENT_AGE = int(os.getenv("MIN_PARENT_AGE", 18))


# Performance Monitoring
METRICS_COLLECTION_INTERVAL = int(os.getenv("METRICS_COLLECTION_INTERVAL", 30))
PERFORMANCE_ALERT_THRESHOLD = int(os.getenv("PERFORMANCE_ALERT_THRESHOLD", 80))
MAX_MEMORY_USAGE_MB = int(os.getenv("MAX_MEMORY_USAGE_MB", 1000))
MAX_CPU_USAGE_PERCENT = int(os.getenv("MAX_CPU_USAGE_PERCENT", 80))


# Cache Configuration
DEFAULT_CACHE_TTL = int(os.getenv("DEFAULT_CACHE_TTL", 3600))
FREQUENT_DATA_CACHE_TTL = int(os.getenv("FREQUENT_DATA_CACHE_TTL", 300))
REDIS_MAX_CONNECTIONS = int(os.getenv("REDIS_MAX_CONNECTIONS", 100))
CACHE_KEY_PREFIX = os.getenv("CACHE_KEY_PREFIX", "ai_teddy")


# Security
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", 7))
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", 8))
PASSWORD_MAX_ATTEMPTS = int(os.getenv("PASSWORD_MAX_ATTEMPTS", 5))
ACCOUNT_LOCKOUT_MINUTES = int(os.getenv("ACCOUNT_LOCKOUT_MINUTES", 60))


# API Response
MAX_RESPONSE_SIZE_KB = int(os.getenv("MAX_RESPONSE_SIZE_KB", 100))
API_VERSION = os.getenv("API_VERSION", "v1")
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", 20))
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", 100))


# Content Filtering
PROFANITY_FILTER_STRICTNESS = os.getenv("PROFANITY_FILTER_STRICTNESS", "high")
CONTENT_MODERATION_THRESHOLD = float(os.getenv("CONTENT_MODERATION_THRESHOLD", 0.9))
VIOLENCE_DETECTION_THRESHOLD = float(os.getenv("VIOLENCE_DETECTION_THRESHOLD", 0.8))
INAPPROPRIATE_CONTENT_THRESHOLD = float(
    os.getenv("INAPPROPRIATE_CONTENT_THRESHOLD", 0.9)
)


# Logging
LOG_ROTATION_SIZE_MB = int(os.getenv("LOG_ROTATION_SIZE_MB", 100))
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", 30))
LOG_LEVEL_PRODUCTION = os.getenv("LOG_LEVEL", "WARNING")
SENSITIVE_LOG_INTERACTION_KEYS = os.getenv(
    "SENSITIVE_LOG_INTERACTION_KEYS",
    "password,access_token,refresh_token,jwt,session,ssn,credit_card,card_number,cvv,secret,api_key,private_key,child_name,parent_name,email,phone,address,ip_address,child_id,parent_id,social_security_number,medical_record,full_message_content,raw_audio_data",
).split(",")


# Error Handling
MAX_ERROR_MESSAGE_LENGTH = int(os.getenv("MAX_ERROR_MESSAGE_LENGTH", 500))
ERROR_RETRY_ATTEMPTS = int(os.getenv("ERROR_RETRY_ATTEMPTS", 3))
ERROR_RETRY_DELAY_SECONDS = int(os.getenv("ERROR_RETRY_DELAY_SECONDS", 1))
CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(
    os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5)
)


# Event Store
class EventStoreType(Enum):
    KAFKA = "kafka"
    POSTGRES = "postgres"


# Health Check
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", 10))
DEPENDENCY_CHECK_TIMEOUT = int(os.getenv("DEPENDENCY_CHECK_TIMEOUT", 5))
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", 30))


# API Routing
API_PREFIX_ESP32 = os.getenv("API_PREFIX_ESP32", "/api/esp32")
API_TAG_ESP32 = os.getenv("API_TAG_ESP32", "ESP32")
API_PREFIX_DASHBOARD = os.getenv("API_PREFIX_DASHBOARD", "/api/dashboard")
API_TAG_DASHBOARD = os.getenv("API_TAG_DASHBOARD", "Dashboard")
API_PREFIX_HEALTH = os.getenv("API_PREFIX_HEALTH", "/api/health")
API_TAG_HEALTH = os.getenv("API_TAG_HEALTH", "Health")
API_PREFIX_CHATGPT = os.getenv("API_PREFIX_CHATGPT", "/api")
API_TAG_CHATGPT = os.getenv("API_TAG_CHATGPT", "ChatGPT")
API_PREFIX_AUTH = os.getenv("API_PREFIX_AUTH", "/api")
API_TAG_AUTH = os.getenv("API_TAG_AUTH", "Auth")


# Child Safety Endpoints
CHILD_SPECIFIC_API_ENDPOINTS = os.getenv(
    "CHILD_SPECIFIC_API_ENDPOINTS", "/api/v1/conversation,/api/v1/voice"
).split(",")


# OpenAPI Documentation (ثوابت توثيقية فقط)
OPENAPI_TITLE = os.getenv("OPENAPI_TITLE", "AI Teddy Bear API")
OPENAPI_VERSION = os.getenv("OPENAPI_VERSION", "1.0.0")
OPENAPI_DESCRIPTION = os.getenv(
    "OPENAPI_DESCRIPTION", "AI Teddy Bear - Child-Safe AI Companion API"
)

import json

OPENAPI_SERVERS = json.loads(
    os.getenv(
        "OPENAPI_SERVERS",
        '[{"url": "https://api.aiteddybear.com/v1", "description": "Production"}, {"url": "https://staging-api.aiteddybear.com/v1", "description": "Staging"}, {"url": "http://localhost:8000/api/v1", "description": "Development"}]',
    )
)
OPENAPI_TAGS = json.loads(
    os.getenv(
        "OPENAPI_TAGS",
        '[{"name": "Authentication", "description": "User authentication and authorization endpoints"}, {"name": "Children", "description": "Child profile management - Create, read, update, and delete child profiles"}, {"name": "Conversations", "description": "AI chat interactions - Send messages and manage conversations"}, {"name": "COPPA", "description": "COPPA compliance endpoints - Consent management and data privacy"}, {"name": "Safety", "description": "Safety monitoring - Events, alerts, and parental notifications"}, {"name": "Admin", "description": "Administrative endpoints - Health checks and system management"}]',
    )
)
OPENAPI_EXTERNAL_DOCS = json.loads(
    os.getenv(
        "OPENAPI_EXTERNAL_DOCS",
        '{"description": "Full API Documentation", "url": "https://docs.aiteddybear.com/api"}',
    )
)
OPENAPI_LICENSE_INFO = json.loads(
    os.getenv(
        "OPENAPI_LICENSE_INFO",
        '{"name": "Proprietary", "url": "https://aiteddybear.com/license"}',
    )
)
OPENAPI_CONTACT_INFO = json.loads(
    os.getenv(
        "OPENAPI_CONTACT_INFO",
        '{"name": "API Support Team", "url": "https://support.aiteddybear.com", "email": "api-support@aiteddybear.com"}',
    )
)
OPENAPI_COMMON_RESPONSES = json.loads(
    os.getenv(
        "OPENAPI_COMMON_RESPONSES",
        '{"BadRequest": {"description": "Bad request - Invalid input data", "content": {"application/json": {"schema": {"type": "object", "properties": {"error_id": {"type": "string", "format": "uuid"}, "message": {"type": "string"}, "detail": {"type": "string"}, "timestamp": {"type": "string", "format": "date-time"}}}}}}, "Unauthorized": {"description": "Unauthorized - Invalid or missing authentication", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}, "Forbidden": {"description": "Forbidden - Insufficient permissions", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}, "NotFound": {"description": "Not found - Resource does not exist", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}, "TooManyRequests": {"description": "Too many requests - Rate limit exceeded", "headers": {"X-RateLimit-Limit": {"description": "Request limit per minute", "schema": {"type": "integer"}}, "X-RateLimit-Remaining": {"description": "Remaining requests in current window", "schema": {"type": "integer"}}, "X-RateLimit-Reset": {"description": "Time when the rate limit resets (Unix timestamp)", "schema": {"type": "integer"}}}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}}',
    )
)
OPENAPI_BEARER_DESCRIPTION = os.getenv(
    "OPENAPI_BEARER_DESCRIPTION",
    "JWT Authorization header using the Bearer scheme. Example: 'Authorization: Bearer <token>'",
)


# ================= VALIDATION =================
def validate_constants():
    assert (
        3 <= MIN_CHILD_AGE <= MAX_CHILD_AGE <= 18
    ), "Child age limits out of COPPA range"
    assert 0 < DEFAULT_DB_POOL_SIZE < 1000, "DB pool size unreasonable"
    assert 0 < DEFAULT_REQUESTS_PER_MINUTE < 10000, "Rate limit per minute unreasonable"
    assert 0 < MAX_FILE_SIZE_MB <= 100, "File size limit unreasonable"
    assert PASSWORD_MIN_LENGTH >= 6, "Password min length too small"
    assert 0 < MAX_CONCURRENT_SESSIONS < 10000, "Concurrent sessions limit unreasonable"
    assert 0 < MAX_AI_RESPONSE_TOKENS < 10000, "AI response tokens limit unreasonable"
    # Add more as needed for your business rules
