"""
Production Payment Security System
=================================
Enterprise-grade security for Iraqi payment processing.
Handles authentication, authorization, fraud detection, and audit logging.
"""

import hmac
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis
from sqlalchemy.orm import Session
import ipaddress
import re
from dataclasses import dataclass

from ..models.database_models import PaymentTransaction, PaymentAuditLog
from src.infrastructure.security.data_encryption_service import DataEncryptionService
from src.infrastructure.security.rate_limiter_advanced import AdvancedRateLimiter


@dataclass
class SecurityContext:
    """Security context for payment operations."""

    user_id: str
    session_id: str
    ip_address: str
    user_agent: str
    api_key: Optional[str] = None
    permissions: List[str] = None
    risk_score: int = 0


class PaymentSecurityManager:
    """
    Centralized security manager for all payment operations.
    Handles authentication, authorization, and audit logging.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        encryption_service: DataEncryptionService,
        rate_limiter: AdvancedRateLimiter,
        jwt_secret: str,
        webhook_secrets: Dict[str, str],
    ):
        self.redis = redis_client
        self.encryption = encryption_service
        self.rate_limiter = rate_limiter
        self.jwt_secret = jwt_secret
        self.webhook_secrets = webhook_secrets
        self.security_scheme = HTTPBearer()

        # Fraud detection thresholds
        self.max_transactions_per_hour = 50
        self.max_amount_per_day = 10000000  # 10M IQD
        self.max_failed_attempts = 5

        # IP whitelist for admin operations
        self.admin_ip_whitelist = {"127.0.0.1", "::1"}

    async def authenticate_user(self, token: str) -> SecurityContext:
        """
        Authenticate user token and return security context.
        """
        # Input validation
        if not token or not isinstance(token, str):
            raise HTTPException(status_code=401, detail="Invalid token format")
        
        # Limit token length
        if len(token) > 2000:
            raise HTTPException(status_code=401, detail="Token too long")
        
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            user_id = payload.get("user_id")
            session_id = payload.get("session_id")
            permissions = payload.get("permissions", [])

            # Validate payload data
            if not user_id or not isinstance(user_id, str):
                raise HTTPException(status_code=401, detail="Invalid user ID in token")
            
            if not session_id or not isinstance(session_id, str):
                raise HTTPException(status_code=401, detail="Invalid session ID in token")
            
            if not isinstance(permissions, list):
                permissions = []

            # Check if session is still valid
            session_key = f"session:{session_id}"
            session_data = await self.redis.get(session_key)
            if not session_data:
                raise HTTPException(status_code=401, detail="Session expired")

            return SecurityContext(
                user_id=user_id,
                session_id=session_id,
                ip_address="",  # Will be set by middleware
                user_agent="",  # Will be set by middleware
                permissions=permissions,
            )

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    async def authenticate_api_key(self, api_key: str) -> SecurityContext:
        """
        Authenticate API key for merchant/system integration.
        """
        # Input validation
        if not api_key or not isinstance(api_key, str):
            raise HTTPException(status_code=401, detail="Invalid API key format")
        
        # Validate API key length and format
        if len(api_key) < 32 or len(api_key) > 128:
            raise HTTPException(status_code=401, detail="Invalid API key length")
        
        # Check for valid characters (alphanumeric and some special chars)
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', api_key):
            raise HTTPException(status_code=401, detail="Invalid API key format")
        
        # Hash the API key for lookup
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Check in Redis cache first
        cache_key = f"api_key:{api_key_hash}"
        cached_data = await self.redis.get(cache_key)

        if cached_data:
            import json

            data = json.loads(cached_data)
            return SecurityContext(
                user_id=data["user_id"],
                session_id=f"api_session_{secrets.token_hex(16)}",
                ip_address="",
                user_agent="API_CLIENT",
                api_key=api_key,
                permissions=data["permissions"],
            )

        raise HTTPException(status_code=401, detail="Invalid API key")

    async def authorize_payment_operation(
        self, context: SecurityContext, operation: str, amount: Optional[int] = None
    ) -> bool:
        """
        Check if user is authorized for specific payment operation.
        """
        # Check basic permissions
        required_permissions = {
            "initiate_payment": ["payment:create"],
            "refund_payment": ["payment:refund"],
            "cancel_payment": ["payment:cancel"],
            "view_payment": ["payment:read"],
            "create_subscription": ["subscription:create"],
            "cancel_subscription": ["subscription:cancel"],
        }

        required = required_permissions.get(operation, [])
        if not all(perm in context.permissions for perm in required):
            return False

        # Check amount limits for user
        if amount and operation in ["initiate_payment", "refund_payment"]:
            user_limit = await self._get_user_payment_limit(context.user_id)
            if amount > user_limit:
                return False

        return True

    async def verify_webhook_signature(
        self, provider: str, payload: bytes, signature: str
    ) -> bool:
        """
        Verify webhook signature from payment provider.
        """
        if provider not in self.webhook_secrets:
            return False

        secret = self.webhook_secrets[provider]
        expected_signature = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected_signature)

    async def check_rate_limits(self, context: SecurityContext, operation: str) -> bool:
        """
        Check rate limits for user and IP address.
        """
        user_key = f"rate_limit:user:{context.user_id}:{operation}"
        ip_key = f"rate_limit:ip:{context.ip_address}:{operation}"

        # Define rate limits per operation
        limits = {
            "initiate_payment": {"per_minute": 10, "per_hour": 100},
            "refund_payment": {"per_minute": 5, "per_hour": 50},
            "webhook": {"per_minute": 1000, "per_hour": 10000},
        }

        operation_limits = limits.get(operation, {"per_minute": 60, "per_hour": 1000})

        # Check user rate limits
        user_count_minute = await self.redis.incr(f"{user_key}:minute")
        if user_count_minute == 1:
            await self.redis.expire(f"{user_key}:minute", 60)

        user_count_hour = await self.redis.incr(f"{user_key}:hour")
        if user_count_hour == 1:
            await self.redis.expire(f"{user_key}:hour", 3600)

        # Check IP rate limits
        ip_count_minute = await self.redis.incr(f"{ip_key}:minute")
        if ip_count_minute == 1:
            await self.redis.expire(f"{ip_key}:minute", 60)

        if (
            user_count_minute > operation_limits["per_minute"]
            or user_count_hour > operation_limits["per_hour"]
            or ip_count_minute > operation_limits["per_minute"] * 5
        ):  # Higher limit for IP
            return False

        return True

    async def perform_fraud_check(
        self,
        context: SecurityContext,
        amount: int,
        payment_method: str,
        customer_phone: str,
        db_session: Session,
    ) -> Dict[str, Any]:
        """
        Comprehensive fraud detection for payment transactions.
        """
        risk_score = 0
        risk_factors = []

        # 1. Velocity checks
        user_transactions_24h = await self._count_user_transactions_24h(
            context.user_id, db_session
        )
        if user_transactions_24h > self.max_transactions_per_hour:
            risk_score += 30
            risk_factors.append("high_transaction_velocity")

        # 2. Amount checks
        user_volume_24h = await self._get_user_volume_24h(context.user_id, db_session)
        if user_volume_24h + amount > self.max_amount_per_day:
            risk_score += 25
            risk_factors.append("high_transaction_volume")

        # 3. Unusual amount patterns
        if amount > 1000000:  # 1M IQD
            risk_score += 20
            risk_factors.append("large_amount")

        # 4. IP geolocation check (if outside Iraq)
        ip_risk = await self._check_ip_geolocation(context.ip_address)
        risk_score += ip_risk
        if ip_risk > 0:
            risk_factors.append("suspicious_ip")

        # 5. Device/browser fingerprinting
        device_risk = await self._check_device_fingerprint(
            context.user_agent, context.session_id
        )
        risk_score += device_risk
        if device_risk > 0:
            risk_factors.append("suspicious_device")

        # 6. Phone number validation
        phone_risk = self._validate_iraqi_phone(customer_phone)
        risk_score += phone_risk
        if phone_risk > 0:
            risk_factors.append("invalid_phone")

        # 7. Time-based checks (unusual hours)
        hour = datetime.utcnow().hour
        if hour < 6 or hour > 23:  # Outside normal business hours
            risk_score += 10
            risk_factors.append("unusual_time")

        # Determine risk level and decision
        if risk_score >= 70:
            risk_level = "critical"
            is_approved = False
        elif risk_score >= 50:
            risk_level = "high"
            is_approved = False
        elif risk_score >= 30:
            risk_level = "medium"
            is_approved = True  # Require additional verification
        else:
            risk_level = "low"
            is_approved = True

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "is_approved": is_approved,
            "requires_verification": risk_level in ["medium", "high"],
        }

    async def log_security_event(
        self,
        context: SecurityContext,
        event_type: str,
        event_description: str,
        transaction_id: Optional[str] = None,
        additional_data: Optional[Dict] = None,
        db_session: Session = None,
    ):
        """
        Log security events for audit and compliance.
        """
        # Create audit log entry
        if db_session and transaction_id:
            audit_log = PaymentAuditLog(
                transaction_id=transaction_id,
                event_type=event_type,
                event_description=event_description,
                user_id=context.user_id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                changes=additional_data or {},
            )
            db_session.add(audit_log)

        # Also log to security monitoring system
        security_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "description": event_description,
            "user_id": context.user_id,
            "session_id": context.session_id,
            "ip_address": context.ip_address,
            "user_agent": context.user_agent,
            "transaction_id": transaction_id,
            "additional_data": additional_data,
        }

        # Store in Redis for real-time monitoring
        await self.redis.lpush("security_events", str(security_log))
        await self.redis.expire("security_events", 86400)  # Keep for 24 hours

    def encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive customer data."""
        return self.encryption.encrypt(data)

    def decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive customer data."""
        return self.encryption.decrypt(encrypted_data)

    async def _count_user_transactions_24h(
        self, user_id: str, db_session: Session
    ) -> int:
        """Count user transactions in last 24 hours."""
        from sqlalchemy import func

        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        count = (
            db_session.query(func.count(PaymentTransaction.id))
            .filter(PaymentTransaction.customer_id == user_id)
            .filter(PaymentTransaction.created_at >= cutoff_time)
            .scalar()
        )

        return count or 0

    async def _get_user_volume_24h(self, user_id: str, db_session: Session) -> int:
        """Get total transaction volume for user in last 24 hours."""
        from sqlalchemy import func

        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        volume = (
            db_session.query(func.sum(PaymentTransaction.amount))
            .filter(PaymentTransaction.customer_id == user_id)
            .filter(PaymentTransaction.created_at >= cutoff_time)
            .filter(PaymentTransaction.status.in_(["completed", "processing"]))
            .scalar()
        )

        return int(volume or 0)

    async def _get_user_payment_limit(self, user_id: str) -> int:
        """Get payment limit for user."""
        # Check user tier in Redis cache
        user_data = await self.redis.get(f"user_limits:{user_id}")
        if user_data:
            import json

            data = json.loads(user_data)
            return data.get("payment_limit", 1000000)  # Default 1M IQD

        return 1000000  # Default limit

    async def _check_ip_geolocation(self, ip_address: str) -> int:
        """Check if IP is from Iraq or suspicious location."""
        try:
            # Skip private/local IPs
            ip_obj = ipaddress.ip_address(ip_address)
            if ip_obj.is_private or ip_obj.is_loopback:
                return 0

            # In production, integrate with IP geolocation service
            # For now, basic check for known suspicious ranges
            risk_score = 0

            # Check against known VPN/proxy ranges (simplified)
            suspicious_ranges = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]

            for range_str in suspicious_ranges:
                network = ipaddress.ip_network(range_str)
                if ip_obj in network:
                    risk_score += 15
                    break

            return risk_score

        except ValueError:
            return 20  # Invalid IP format

    async def _check_device_fingerprint(self, user_agent: str, session_id: str) -> int:
        """Check device fingerprint for suspicious patterns."""
        risk_score = 0

        # Check for suspicious user agents
        suspicious_patterns = [
            r"bot",
            r"crawler",
            r"scanner",
            r"curl",
            r"wget",
            r"python-requests",
        ]

        user_agent_lower = user_agent.lower()
        for pattern in suspicious_patterns:
            if re.search(pattern, user_agent_lower):
                risk_score += 25
                break

        # Check session consistency
        session_devices = await self.redis.get(f"session_device:{session_id}")
        if session_devices:
            import json

            devices = json.loads(session_devices)
            if user_agent not in devices:
                risk_score += 15  # Device changed during session
        else:
            # Store device for session
            await self.redis.setex(
                f"session_device:{session_id}", 3600, json.dumps([user_agent])
            )

        return risk_score

    def _validate_iraqi_phone(self, phone: str) -> int:
        """Validate Iraqi phone number format."""
        # Input validation
        if not phone or not isinstance(phone, str):
            return 20
        
        # Limit phone length
        if len(phone) > 20:
            return 15
        
        # Iraqi mobile number patterns
        iraqi_patterns = [
            r"^07[3-9]\d{8}$",  # Iraqi mobile format
            r"^964[0-9]{10}$",  # International format
            r"^\+964[0-9]{10}$",  # International with +
        ]

        # Sanitize phone number
        phone_clean = re.sub(r"[^\d+]", "", phone[:20])

        for pattern in iraqi_patterns:
            if re.match(pattern, phone_clean):
                return 0  # Valid Iraqi number

        return 15  # Invalid format


# FastAPI Dependencies
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None,
    security_manager: PaymentSecurityManager = Depends(),
) -> SecurityContext:
    """FastAPI dependency to get current authenticated user."""
    context = await security_manager.authenticate_user(credentials.credentials)

    # Add request context
    if request:
        context.ip_address = request.client.host
        context.user_agent = request.headers.get("user-agent", "")

    return context


async def get_api_key_user(
    request: Request, security_manager: PaymentSecurityManager = Depends()
) -> SecurityContext:
    """FastAPI dependency for API key authentication."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    context = await security_manager.authenticate_api_key(api_key)
    context.ip_address = request.client.host
    context.user_agent = request.headers.get("user-agent", "")

    return context


async def require_payment_permission(operation: str):
    """FastAPI dependency factory for permission checking."""

    async def check_permission(
        context: SecurityContext = Depends(get_current_user),
        security_manager: PaymentSecurityManager = Depends(),
    ):
        authorized = await security_manager.authorize_payment_operation(
            context, operation
        )
        if not authorized:
            raise HTTPException(
                status_code=403, detail=f"Not authorized for {operation}"
            )
        return context

    return check_permission


class PaymentSecurityMiddleware:
    """
    FastAPI middleware for payment security.
    """

    def __init__(self, security_manager: PaymentSecurityManager):
        self.security_manager = security_manager

    async def __call__(self, request: Request, call_next):
        """Process security checks for payment endpoints."""

        # Skip security for health checks and public endpoints
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Enhanced security for payment endpoints
        if request.url.path.startswith("/api/v1/payments"):
            # Rate limiting
            user_id = getattr(request.state, "user_id", request.client.host)
            operation = self._extract_operation(request.url.path, request.method)

            context = SecurityContext(
                user_id=user_id,
                session_id="",
                ip_address=request.client.host,
                user_agent=request.headers.get("user-agent", ""),
            )

            rate_limit_ok = await self.security_manager.check_rate_limits(
                context, operation
            )
            if not rate_limit_ok:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")

            # Log access attempt
            await self.security_manager.log_security_event(
                context,
                "api_access",
                f"Access attempt to {request.url.path}",
                additional_data={
                    "method": request.method,
                    "path": request.url.path,
                    "headers": dict(request.headers),
                },
            )

        response = await call_next(request)
        return response

    def _extract_operation(self, path: str, method: str) -> str:
        """Extract operation type from request path and method."""
        if "initiate" in path:
            return "initiate_payment"
        elif "refund" in path:
            return "refund_payment"
        elif "cancel" in path:
            return "cancel_payment"
        elif "subscriptions" in path and method == "POST":
            return "create_subscription"
        elif "webhook" in path:
            return "webhook"
        else:
            return "general"
