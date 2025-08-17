"""
OpenAPI Configuration - Centralized schema generation
"""

from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
import os

# Configuration from environment or defaults
API_TITLE = os.getenv("API_TITLE", "AI Teddy Bear API")
API_VERSION = os.getenv("API_VERSION", "1.0.0")
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.aiteddybear.com")
STAGING_URL = os.getenv("STAGING_URL", "https://staging-api.aiteddybear.com")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "support@aiteddybear.com")

tags_metadata = [
    {
        "name": "Authentication",
        "description": """
        **Parent authentication and session management**
        
        Secure JWT-based authentication with 2FA support. All endpoints require 
        proper authentication except for registration and public health checks.
        
        ### Security Features
        - JWT tokens with short expiration (15 minutes)
        - Refresh token rotation
        - Rate limiting on authentication attempts
        - Account lockout after failed attempts
        """,
        "externalDocs": {
            "description": "Authentication Guide",
            "url": f"{API_BASE_URL}/docs/auth",
        },
    },
    {
        "name": "Children",
        "description": """
        **Child profile management with COPPA compliance**
        
        Create and manage child profiles with comprehensive safety settings.
        All child data is encrypted and stored according to COPPA requirements.
        
        ### Privacy Features
        - No last names stored
        - Data encryption at rest
        - Parental consent required
        - Data deletion on request
        """,
        "externalDocs": {
            "description": "COPPA Compliance Guide",
            "url": f"{API_BASE_URL}/docs/coppa",
        },
    },
    {
        "name": "Conversations",
        "description": """
        **AI conversation endpoints with real-time safety monitoring**
        
        Safe, educational conversations with AI Teddy Bear. All messages
        are filtered for safety and appropriateness before and after AI processing.
        
        ### Safety Features
        - Real-time content moderation
        - Age-appropriate responses
        - Educational content prioritization
        - Parental monitoring
        """,
        "externalDocs": {
            "description": "Conversation Safety Guide",
            "url": f"{API_BASE_URL}/docs/safety",
        },
    },
    {
        "name": "Safety",
        "description": """
        **Content moderation and safety reporting**
        
        Comprehensive safety monitoring with real-time incident reporting.
        Parents receive notifications of any safety events.
        
        ### Monitoring Features
        - 24/7 content filtering
        - Behavioral analysis
        - Safety incident reporting
        - Parental alerts
        """,
    },
    {
        "name": "Health",
        "description": """
        **System health and monitoring endpoints**
        
        Public and authenticated health checks for system monitoring
        and service availability verification.
        """,
    },
    {
        "name": "Admin",
        "description": """
        **Administrative endpoints for system management**
        
        Protected endpoints for system administrators to monitor
        platform health, manage users, and access analytics.
        """,
    },
]


# =============================================================================
# OPENAPI SCHEMA GENERATION
# =============================================================================


def generate_openapi_schema(app: FastAPI) -> Dict[str, Any]:
    """Generate OpenAPI schema with proper error handling

    Args:
        app: FastAPI application instance

    Returns:
        Dict containing OpenAPI schema

    Raises:
        ValueError: If app is invalid or missing required attributes
    """
    if not app:
        raise ValueError("FastAPI app instance is required")

    if app.openapi_schema:
        return app.openapi_schema

    try:
        # Validate environment variables
        if not API_TITLE or not API_VERSION:
            raise ValueError("API_TITLE and API_VERSION must be set")

        openapi_schema = get_openapi(
            title=API_TITLE,
            version=API_VERSION,
            description="🧸 Child-safe AI conversations with COPPA compliance",
            routes=app.routes,
            tags=tags_metadata,
        )

        # Enhanced configuration
        openapi_schema.update(
            {
                "servers": [
                    {"url": API_BASE_URL, "description": "Production"},
                    {"url": STAGING_URL, "description": "Staging"},
                    {"url": "http://localhost:8000", "description": "Development"},
                ],
                "info": {
                    **openapi_schema.get("info", {}),
                    "contact": {"email": SUPPORT_EMAIL, "name": "Support Team"},
                    "termsOfService": f"{API_BASE_URL}/terms",
                    "license": {"name": "Proprietary"},
                },
            }
        )

        # Security configuration
        if "components" not in openapi_schema:
            openapi_schema["components"] = {}
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token from authentication endpoint",
            }
        }
        openapi_schema["security"] = [{"BearerAuth": []}]

        app.openapi_schema = openapi_schema
        return openapi_schema

    except Exception as e:
        # Log error in production
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"OpenAPI schema generation failed: {e}")
        # Return minimal schema instead of empty dict
        return {
            "openapi": "3.0.3",
            "info": {"title": API_TITLE, "version": API_VERSION},
            "paths": {},
        }


def get_openapi_tags() -> List[Dict[str, str]]:
    """Get OpenAPI tags metadata

    Returns:
        List of tag metadata dictionaries
    """
    return tags_metadata


def custom_openapi_schema(app: FastAPI) -> Dict[str, Any]:
    """Generate custom OpenAPI schema for the application

    Args:
        app: FastAPI application instance

    Returns:
        Custom OpenAPI schema with enhanced documentation
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=API_TITLE,
        version=API_VERSION,
        description="""
        🧸 **AI Teddy Bear - Child-Safe AI Companion**
        
        Enterprise-grade API for secure, COPPA-compliant AI interactions designed specifically for children aged 3-13.
        
        ## 🔒 Security & Compliance
        - **COPPA Compliant**: Full adherence to Children's Online Privacy Protection Act
        - **Multi-layer Safety**: Content filtering, age verification, parental controls
        - **Enterprise Security**: JWT authentication, rate limiting, encryption
        
        ## 🎯 Key Features
        - Real-time conversational AI optimized for children
        - Voice interaction with child-safe TTS
        - Educational content and learning assistance
        - Comprehensive parental controls and monitoring
        - Multi-language support with age-appropriate responses
        
        ## 📋 API Usage
        1. **Parent Registration**: Create secure parent account with verification
        2. **Child Profile**: Set up child profile with safety preferences
        3. **Conversations**: Secure AI interactions with safety monitoring
        4. **Monitoring**: Real-time safety reports and conversation logs
        
        ## 🛡️ Safety Guarantees
        - No personal information collection from children
        - Real-time content safety scoring
        - Immediate intervention for inappropriate content
        - Encrypted storage of all child data
        - Automatic parental notifications for safety incidents
        """,
        routes=app.routes,
        tags=tags_metadata,
        servers=[
            {"url": API_BASE_URL, "description": "Production server"},
            {"url": STAGING_URL, "description": "Staging server"},
            {"url": "http://localhost:8000", "description": "Development server"},
        ],
        contact={
            "name": "AI Teddy Bear Support",
            "email": SUPPORT_EMAIL,
            "url": "https://www.aiteddybear.com/support",
        },
        license_info={
            "name": "Proprietary License",
            "url": "https://www.aiteddybear.com/license",
        },
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token obtained from /auth/login endpoint",
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema
