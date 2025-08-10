from src.core.exceptions import *  # re-export كل شيء من المصدر الموحّد

# ✅ Alias خلفي للحفاظ على التوافق مع الكود القديم
AIServiceError = (
    ExternalServiceError  # إذا كان عندك صنف آخر باسم AIServiceError في السابق
)
ServiceError = ExternalServiceError  # ← للتوافق مع parent_dashboard.py

# ✅ AIContentFilterError alias للتوافق مع core.services
AIContentFilterError = SafetyViolationError  # استخدام SafetyViolationError الموجود

# ✅ map_exception المطلوبة من error_handler
from typing import Tuple, Dict, Any


def map_exception(exc: Exception) -> Tuple[int, Dict[str, Any]]:
    try:
        from fastapi import status
    except Exception:
        # fallback أكواد ثابتة لو fastapi مش متاح وقت الاستيراد
        class status:
            HTTP_401_UNAUTHORIZED = 401
            HTTP_403_FORBIDDEN = 403
            HTTP_404_NOT_FOUND = 404
            HTTP_422_UNPROCESSABLE_ENTITY = 422
            HTTP_429_TOO_MANY_REQUESTS = 429
            HTTP_500_INTERNAL_SERVER_ERROR = 500
            HTTP_502_BAD_GATEWAY = 502
            HTTP_503_SERVICE_UNAVAILABLE = 503

    if isinstance(exc, AuthenticationError):
        code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, AuthorizationError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, ResourceNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ValidationError):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, RateLimitExceeded):
        code = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(exc, ServiceUnavailableError):
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, ExternalServiceError):
        code = status.HTTP_502_BAD_GATEWAY
    elif isinstance(exc, DatabaseError):
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR

    body = ExceptionHandler.format_for_api(exc, include_debug=False)
    return code, body


__all__ = [name for name in dir() if not name.startswith("_")]
