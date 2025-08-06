"""
AI Teddy Bear API - Main module for API definitions and schemas
"""

# Import specific models to avoid namespace pollution
from .docs import (
    # Request/Response Models
    ParentRegistrationRequest, LoginRequest, AuthResponse,
    ChildProfileRequest, ChildProfileResponse, ConversationRequest,
    ConversationResponse, SafetyReport, HealthStatus, ErrorResponse,
    ErrorDetail, ErrorCode, UserRole, ConversationMode,
    # Rate Limiting Models
    RateLimitInfo, RateLimitExceeded,
    # Audit Trail Models
    AuditEventType, AuditEvent, AuditTrail,
    # Token Models
    TokenResponse, RefreshTokenRequest,
    # Pagination Models
    PaginationParams, PaginatedResponse
)

# Import OpenAPI functions from centralized config
from .openapi_config import generate_openapi_schema, get_openapi_tags

# Import configuration
from .config import (
    get_rate_limit_config, get_safety_config,
    ALLOWED_INTERESTS, SUPPORTED_LANGUAGES
)

# Export public API
__all__ = [
    # Request/Response Models
    'ParentRegistrationRequest', 'LoginRequest', 'AuthResponse',
    'ChildProfileRequest', 'ChildProfileResponse', 'ConversationRequest',
    'ConversationResponse', 'SafetyReport', 'HealthStatus', 'ErrorResponse',
    'ErrorDetail', 'ErrorCode', 'UserRole', 'ConversationMode',
    # Rate Limiting Models
    'RateLimitInfo', 'RateLimitExceeded',
    # Audit Trail Models  
    'AuditEventType', 'AuditEvent', 'AuditTrail',
    # Token Models
    'TokenResponse', 'RefreshTokenRequest',
    # Pagination Models
    'PaginationParams', 'PaginatedResponse',
    # Functions
    'generate_openapi_schema', 'get_openapi_tags',
    'get_rate_limit_config', 'get_safety_config',
    # Constants
    'ALLOWED_INTERESTS', 'SUPPORTED_LANGUAGES'
]
