"""
🧸 AI TEDDY BEAR V5 - CORE SECURITY SERVICE
==========================================
Core security service for child protection and system security.
"""

import time
import hashlib
import json
import re
import secrets
import base64
import uuid
from dataclasses import asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.exc import SQLAlchemyError
from collections import defaultdict, deque
from statistics import mean, stdev

import redis.asyncio as aioredis
import jwt

# Cryptography imports
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from src.infrastructure.database.database_manager import initialize_database
from src.infrastructure.persistence.models.production_models import (
    ChildModel,
)
from src.infrastructure.config.production_config import get_config
from src.infrastructure.rate_limiting.rate_limiter import (
    RateLimitingService,
    OperationType,
)

from src.infrastructure.logging.production_logger import get_logger, security_logger
from src.infrastructure.monitoring.audit import coppa_audit


class EncryptionLevel(str, Enum):
    """Levels of encryption based on data sensitivity."""

    NONE = "none"  # Public data
    STANDARD = "standard"  # General user data
    SENSITIVE = "sensitive"  # PII, child data
    HIGHLY_SENSITIVE = "highly_sensitive"  # Payment, medical data


class DataClassification(str, Enum):
    """Data classification levels for audit purposes."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"  # Child data, COPPA protected


class AuditEventType(str, Enum):
    """Types of events to audit."""

    DATA_ACCESS = "data_access"
    DATA_CREATE = "data_create"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    ENCRYPTION_KEY_ROTATION = "key_rotation"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_EXPORT = "data_export"
    COPPA_VIOLATION = "coppa_violation"
    SECURITY_INCIDENT = "security_incident"
    LOGIN_ATTEMPT = "login_attempt"
    PERMISSION_CHANGE = "permission_change"


@dataclass
class AuditLogEntry:
    """Comprehensive audit log entry structure."""

    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    user_id: Optional[str]
    user_type: Optional[str]  # child, parent, admin
    child_id: Optional[str]  # For child-related events
    action_performed: str
    resource_type: str  # user, child, session, etc.
    resource_id: Optional[str]
    data_classification: DataClassification
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    error_message: Optional[str] = None
    data_before: Optional[Dict[str, Any]] = None  # For updates
    data_after: Optional[Dict[str, Any]] = None  # For updates
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data


@dataclass
class SecurityThreat:
    """Security threat detection result."""

    threat_id: str
    threat_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    detected_at: datetime
    source_ip: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class BehaviorFeatures:
    """Features extracted from user behavior for anomaly detection."""

    user_id: str
    timestamp: datetime
    # Temporal features
    hour_of_day: int
    day_of_week: int
    session_duration: float
    # Activity features
    requests_per_minute: float
    content_length_avg: float
    content_length_std: float
    # Interaction features
    unique_endpoints: int
    error_rate: float
    # Child-specific features
    child_safety_violations: int
    age_inappropriate_attempts: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyResult:
    """Result of anomaly detection analysis."""

    is_anomaly: bool
    anomaly_score: float  # 0-1, higher means more anomalous
    confidence: float  # 0-1, confidence in the prediction
    detected_patterns: List[str]
    risk_factors: List[str]
    explanation: str
    threshold_used: float


class MLAnomalyDetector:
    """ML-based anomaly detection for user behavior analysis."""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None, config=None):
        self.logger = get_logger(__name__, "ml_anomaly_detector")
        self.redis = redis_client
        self.config = config or get_config()

        # Behavioral baselines for each user
        self.user_baselines: Dict[str, Dict[str, Any]] = {}

        # Feature tracking windows
        self.feature_windows: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Anomaly detection thresholds
        self.anomaly_thresholds = {
            "temporal_anomaly": 0.7,
            "activity_anomaly": 0.8,
            "content_anomaly": 0.75,
            "child_safety_anomaly": 0.9,
        }

        # Known patterns (could be trained from historical data)
        self.normal_patterns = {
            "typical_hours": set(range(7, 22)),  # 7 AM to 10 PM
            "typical_session_duration": (300, 3600),  # 5 min to 1 hour
            "typical_requests_per_minute": (0.5, 5.0),
            "typical_content_length": (10, 500),
        }

    async def extract_behavior_features(
        self,
        user_id: str,
        session_data: Dict[str, Any],
        historical_window_hours: int = 24,
    ) -> BehaviorFeatures:
        """Extract behavioral features for anomaly detection."""

        now = datetime.utcnow()

        try:
            # Get historical data for this user
            historical_data = await self._get_user_historical_data(
                user_id, historical_window_hours
            )

            # Extract temporal features
            hour_of_day = now.hour
            day_of_week = now.weekday()
            session_duration = session_data.get("session_duration", 0)

            # Extract activity features
            requests_in_session = session_data.get("requests", [])
            if requests_in_session:
                session_minutes = max(1, session_duration / 60)
                requests_per_minute = len(requests_in_session) / session_minutes

                content_lengths = [
                    len(req.get("content", ""))
                    for req in requests_in_session
                    if req.get("content")
                ]
                content_length_avg = mean(content_lengths) if content_lengths else 0
                content_length_std = (
                    stdev(content_lengths) if len(content_lengths) > 1 else 0
                )
            else:
                requests_per_minute = 0
                content_length_avg = 0
                content_length_std = 0

            # Extract interaction features
            unique_endpoints = len(
                set(req.get("endpoint", "") for req in requests_in_session)
            )
            errors = sum(1 for req in requests_in_session if req.get("error", False))
            error_rate = errors / max(1, len(requests_in_session))

            # Extract child safety features
            safety_violations = session_data.get("safety_violations", 0)
            age_inappropriate = session_data.get("age_inappropriate_attempts", 0)

            features = BehaviorFeatures(
                user_id=user_id,
                timestamp=now,
                hour_of_day=hour_of_day,
                day_of_week=day_of_week,
                session_duration=session_duration,
                requests_per_minute=requests_per_minute,
                content_length_avg=content_length_avg,
                content_length_std=content_length_std,
                unique_endpoints=unique_endpoints,
                error_rate=error_rate,
                child_safety_violations=safety_violations,
                age_inappropriate_attempts=age_inappropriate,
                metadata={
                    "total_requests": len(requests_in_session),
                    "historical_sessions": len(historical_data),
                },
            )

            return features

        except (ConnectionError, ValueError, KeyError) as e:
            # Sanitize user_id and error for logging to prevent log injection
            safe_user_id = (
                re.sub(r"[\r\n\x00-\x1f\x7f-\x9f]", "", str(user_id))[:50]
                if user_id
                else "None"
            )
            safe_error = re.sub(r"[\r\n\x00-\x1f\x7f-\x9f]", "", str(e))[:200]
            self.logger.error(
                "Error extracting behavior features for user %s: %s",
                safe_user_id,
                safe_error,
            )
            # Return basic features as fallback
            return BehaviorFeatures(
                user_id=user_id,
                timestamp=now,
                hour_of_day=now.hour,
                day_of_week=now.weekday(),
                session_duration=0,
                requests_per_minute=0,
                content_length_avg=0,
                content_length_std=0,
                unique_endpoints=0,
                error_rate=0,
                child_safety_violations=0,
                age_inappropriate_attempts=0,
            )

    async def detect_behavioral_anomalies(
        self, features: BehaviorFeatures
    ) -> AnomalyResult:
        """Detect anomalies in user behavior using statistical and heuristic methods."""

        try:
            detected_patterns = []
            risk_factors = []
            anomaly_scores = []

            # 1. Temporal Anomaly Detection
            temporal_score = await self._detect_temporal_anomalies(features)
            anomaly_scores.append(temporal_score)
            if temporal_score > self.anomaly_thresholds["temporal_anomaly"]:
                detected_patterns.append("temporal_anomaly")
                risk_factors.append("Unusual access time patterns")

            # 2. Activity Level Anomaly Detection
            activity_score = await self._detect_activity_anomalies(features)
            anomaly_scores.append(activity_score)
            if activity_score > self.anomaly_thresholds["activity_anomaly"]:
                detected_patterns.append("activity_anomaly")
                risk_factors.append("Abnormal activity levels")

            # 3. Content Behavior Anomaly Detection
            content_score = await self._detect_content_anomalies(features)
            anomaly_scores.append(content_score)
            if content_score > self.anomaly_thresholds["content_anomaly"]:
                detected_patterns.append("content_anomaly")
                risk_factors.append("Unusual content interaction patterns")

            # 4. Child Safety Anomaly Detection
            safety_score = await self._detect_child_safety_anomalies(features)
            anomaly_scores.append(safety_score)
            if safety_score > self.anomaly_thresholds["child_safety_anomaly"]:
                detected_patterns.append("child_safety_anomaly")
                risk_factors.append("Child safety violations detected")

            # Calculate overall anomaly score
            overall_score = max(anomaly_scores) if anomaly_scores else 0.0

            # Determine if this is an anomaly
            is_anomaly = overall_score > 0.6  # Overall threshold

            # Calculate confidence based on consistency of scores
            confidence = self._calculate_confidence(anomaly_scores, detected_patterns)

            # Generate explanation
            explanation = self._generate_explanation(
                detected_patterns, risk_factors, overall_score
            )

            result = AnomalyResult(
                is_anomaly=is_anomaly,
                anomaly_score=overall_score,
                confidence=confidence,
                detected_patterns=detected_patterns,
                risk_factors=risk_factors,
                explanation=explanation,
                threshold_used=0.6,
            )

            # Store features for future baseline updates
            await self._update_user_baseline(features)

            return result

        except (ValueError, ZeroDivisionError, TypeError) as e:
            self.logger.error("Error in behavioral anomaly detection: %s", e)
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                confidence=0.0,
                detected_patterns=[],
                risk_factors=[],
                explanation="Error in anomaly detection",
                threshold_used=0.6,
            )

    async def _detect_temporal_anomalies(self, features: BehaviorFeatures) -> float:
        """Detect temporal anomalies in user behavior."""
        score = 0.0

        # Check unusual hours
        if features.hour_of_day not in self.normal_patterns["typical_hours"]:
            score += 0.3

        # Check very late/early hours for children
        if features.hour_of_day < 6 or features.hour_of_day > 22:
            score += 0.4

        # Check session duration anomalies
        typical_min, typical_max = self.normal_patterns["typical_session_duration"]
        if (
            features.session_duration < typical_min * 0.1
            or features.session_duration > typical_max * 2
        ):
            score += 0.3

        return min(score, 1.0)

    async def _detect_activity_anomalies(self, features: BehaviorFeatures) -> float:
        """Detect activity level anomalies."""
        score = 0.0

        # Check request frequency anomalies
        _, typical_max = self.normal_patterns["typical_requests_per_minute"]
        if features.requests_per_minute > typical_max * 3:
            score += 0.5  # Very high activity
        elif features.requests_per_minute > typical_max * 1.5:
            score += 0.3  # Moderately high activity

        # Check error rate anomalies
        if features.error_rate > 0.3:  # More than 30% errors
            score += 0.4
        elif features.error_rate > 0.1:  # More than 10% errors
            score += 0.2

        return min(score, 1.0)

    async def _detect_content_anomalies(self, features: BehaviorFeatures) -> float:
        """Detect content-related anomalies."""
        score = 0.0

        # Check content length anomalies
        _, typical_max = self.normal_patterns["typical_content_length"]
        if features.content_length_avg > typical_max * 2:
            score += 0.3

        # Check content variation (high std deviation might indicate automated behavior)
        if features.content_length_std > features.content_length_avg * 2:
            score += 0.2

        return min(score, 1.0)

    async def _detect_child_safety_anomalies(self, features: BehaviorFeatures) -> float:
        """Detect child safety-related anomalies."""
        score = 0.0

        # Any safety violations are concerning
        if features.child_safety_violations > 0:
            score += min(features.child_safety_violations * 0.3, 0.8)

        # Age-inappropriate attempts
        if features.age_inappropriate_attempts > 0:
            score += min(features.age_inappropriate_attempts * 0.4, 0.9)

        return min(score, 1.0)

    def _calculate_confidence(self, scores: List[float], patterns: List[str]) -> float:
        """Calculate confidence in anomaly detection."""
        if not scores:
            return 0.0

        # Higher confidence when multiple detection methods agree
        high_scores = sum(1 for score in scores if score > 0.5)
        consistency = high_scores / len(scores)

        # Boost confidence when child safety is involved
        safety_boost = 0.2 if any("safety" in pattern for pattern in patterns) else 0.0

        return min(consistency + safety_boost, 1.0)

    def _generate_explanation(
        self, patterns: List[str], risk_factors: List[str], score: float
    ) -> str:
        """Generate human-readable explanation of anomaly detection."""
        if not patterns:
            return "Normal behavior detected"

        explanation = f"Anomaly detected (score: {score:.2f}). "

        if risk_factors:
            explanation += "Risk factors: " + ", ".join(
                risk_factors[:3]
            )  # Top 3 factors

        if "child_safety_anomaly" in patterns:
            explanation += " ⚠️ Child safety concerns identified."

        return explanation

    async def _get_user_historical_data(
        self, user_id: str, hours: int
    ) -> List[Dict[str, Any]]:
        """Get historical data for user from Redis or memory."""
        try:
            if self.redis:
                key = f"user_history:{user_id}"
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)

                # Get historical sessions
                sessions = await self.redis.lrange(key, 0, -1)
                historical_data = []

                for session_json in sessions:
                    session = json.loads(session_json)
                    session_time = datetime.fromisoformat(session.get("timestamp", ""))
                    if session_time >= cutoff_time:
                        historical_data.append(session)

                return historical_data
            else:
                # Fallback to in-memory storage
                return self.feature_windows.get(user_id, [])

        except (ConnectionError, json.JSONDecodeError, ValueError) as e:
            safe_user_id = str(user_id).replace("\n", "").replace("\r", "")[:50]
            safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
            self.logger.warning(
                "Error getting historical data for user %s: %s",
                safe_user_id,
                safe_error,
            )
            return []

    async def _update_user_baseline(self, features: BehaviorFeatures):
        """Update user behavioral baseline with new features."""
        try:
            user_id = features.user_id

            # Store in Redis if available
            if self.redis:
                key = f"user_history:{user_id}"
                session_data = {
                    "timestamp": features.timestamp.isoformat(),
                    "hour_of_day": features.hour_of_day,
                    "session_duration": features.session_duration,
                    "requests_per_minute": features.requests_per_minute,
                    "content_length_avg": features.content_length_avg,
                    "error_rate": features.error_rate,
                    "safety_violations": features.child_safety_violations,
                }

                await self.redis.lpush(key, json.dumps(session_data))
                await self.redis.ltrim(key, 0, 99)  # Keep last 100 sessions
                await self.redis.expire(key, 604800)  # 7 days

            # Also update in-memory for immediate access
            self.feature_windows[user_id].append(
                {"timestamp": features.timestamp, "features": features}
            )

        except (ConnectionError, TypeError, AttributeError) as e:
            safe_user_id = (
                str(features.user_id).replace("\n", "").replace("\r", "")[:50]
            )
            safe_error = str(e).replace("\n", "").replace("\r", "")[:200]
            self.logger.warning(
                "Error updating user baseline for %s: %s", safe_user_id, safe_error
            )


class ThreatDetector:
    """Detect security threats and suspicious activities."""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None, config=None):
        self.logger = get_logger(__name__, "threat_detection")
        self.redis = redis_client
        self.config = config or get_config()
        self.failed_attempts = {}  # Fallback for when Redis is unavailable
        self.suspicious_patterns = {}  # Pattern tracking
        self.ml_anomaly_detector = MLAnomalyDetector(redis_client, config)

    async def detect_brute_force(
        self, ip_address: str, user_id: str = None
    ) -> Optional[SecurityThreat]:
        """Detect brute force attacks using Redis for persistence."""

        current_time = time.time()
        redis_key = f"brute_force:{ip_address}"

        try:
            if self.redis:
                # Use Redis for persistent tracking
                pipe = self.redis.pipeline()
                pipe.zadd(redis_key, {str(current_time): current_time})
                pipe.zremrangebyscore(
                    redis_key, 0, current_time - self.config.SECURITY_BRUTE_FORCE_WINDOW
                )
                pipe.zcount(
                    redis_key,
                    current_time - self.config.SECURITY_BRUTE_FORCE_WINDOW,
                    current_time,
                )
                pipe.expire(redis_key, self.config.SECURITY_BRUTE_FORCE_WINDOW)
                results = await pipe.execute()
                recent_attempts = results[2]
            else:
                # Fallback to in-memory tracking
                if ip_address not in self.failed_attempts:
                    self.failed_attempts[ip_address] = []

                self.failed_attempts[ip_address].append(current_time)
                self.failed_attempts[ip_address] = [
                    attempt
                    for attempt in self.failed_attempts[ip_address]
                    if current_time - attempt < self.config.SECURITY_BRUTE_FORCE_WINDOW
                ]
                recent_attempts = len(self.failed_attempts[ip_address])

        except (ConnectionError, AttributeError) as e:
            self.logger.warning(
                "Redis error in brute force detection, using fallback: %s", e
            )
            # Fallback to in-memory tracking on Redis error
            if ip_address not in self.failed_attempts:
                self.failed_attempts[ip_address] = []

            self.failed_attempts[ip_address].append(current_time)
            self.failed_attempts[ip_address] = [
                attempt
                for attempt in self.failed_attempts[ip_address]
                if current_time - attempt < self.config.SECURITY_BRUTE_FORCE_WINDOW
            ]
            recent_attempts = len(self.failed_attempts[ip_address])

        if recent_attempts >= self.config.SECURITY_BRUTE_FORCE_ATTEMPTS:
            return SecurityThreat(
                threat_id=f"brute_force_{int(current_time)}",
                threat_type="brute_force_attack",
                severity="high",
                description=f"Brute force attack detected from {ip_address}",
                detected_at=datetime.utcnow(),
                source_ip=ip_address,
                user_id=user_id,
                metadata={
                    "attempt_count": recent_attempts,
                    "time_window": f"{self.config.SECURITY_BRUTE_FORCE_WINDOW}_seconds",
                },
            )

        return None

    def detect_suspicious_child_access(
        self, user_id: str, child_id: str, access_pattern: Dict[str, Any]
    ) -> Optional[SecurityThreat]:
        """Detect suspicious access to child data using configurable thresholds."""

        # Check for unusual access patterns using configurable thresholds
        access_count = access_pattern.get("access_count", 0)
        access_frequency = access_pattern.get("access_frequency", 0)
        unusual_hours = access_pattern.get("unusual_hours", False)

        threat_indicators = []

        if access_count > self.config.SECURITY_CHILD_ACCESS_EXCESSIVE_COUNT:
            threat_indicators.append("excessive_access_count")

        if access_frequency > self.config.SECURITY_CHILD_ACCESS_HIGH_FREQUENCY:
            threat_indicators.append("high_frequency_access")

        if unusual_hours:
            threat_indicators.append("unusual_time_access")

        if threat_indicators:
            severity = "critical" if len(threat_indicators) >= 2 else "medium"

            return SecurityThreat(
                threat_id=f"suspicious_child_access_{int(time.time())}",
                threat_type="suspicious_child_data_access",
                severity=severity,
                description="Suspicious access pattern to child data",
                detected_at=datetime.utcnow(),
                user_id=user_id,
                metadata={
                    "child_id_hash": hashlib.sha256(child_id.encode()).hexdigest()[:16],
                    "threat_indicators": threat_indicators,
                    "access_pattern": access_pattern,
                },
            )

        return None

    def detect_content_injection(
        self, content: str, user_id: str = None
    ) -> Optional[SecurityThreat]:
        """Detect potential content injection attacks."""

        # Patterns that might indicate injection attempts
        injection_patterns = [
            "<script",
            "javascript:",
            "onload=",
            "onerror=",
            "eval(",
            "document.cookie",
            "window.location",
            "alert(",
            "prompt(",
            "confirm(",
            "DROP TABLE",
            "SELECT * FROM",
            "UNION SELECT",
            "INSERT INTO",
            "UPDATE SET",
            "DELETE FROM",
        ]

        detected_patterns = []
        content_lower = content.lower()

        for pattern in injection_patterns:
            if pattern.lower() in content_lower:
                detected_patterns.append(pattern)

        if detected_patterns:
            return SecurityThreat(
                threat_id=f"content_injection_{int(time.time())}",
                threat_type="content_injection_attempt",
                severity="high",
                description="Potential content injection detected",
                detected_at=datetime.utcnow(),
                user_id=user_id,
                metadata={
                    "detected_patterns": detected_patterns,
                    "content_length": len(content),
                    "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
                },
            )

        return None

    async def detect_behavioral_anomalies(
        self,
        user_id: str,
        session_data: Dict[str, Any],
        user_context: Dict[str, Any] = None,
    ) -> Optional[SecurityThreat]:
        """Detect behavioral anomalies using ML-based analysis."""

        try:
            # Extract behavioral features
            features = await self.ml_anomaly_detector.extract_behavior_features(
                user_id, session_data
            )

            # Detect anomalies
            anomaly_result = await self.ml_anomaly_detector.detect_behavioral_anomalies(
                features
            )

            # Create security threat if anomaly detected
            if anomaly_result.is_anomaly:
                severity = "critical" if anomaly_result.anomaly_score > 0.8 else "high"
                if "child_safety_anomaly" in anomaly_result.detected_patterns:
                    severity = "critical"  # Always critical for child safety

                return SecurityThreat(
                    threat_id=f"behavioral_anomaly_{int(time.time())}",
                    threat_type="behavioral_anomaly",
                    severity=severity,
                    description=anomaly_result.explanation,
                    detected_at=datetime.utcnow(),
                    source_ip=user_context.get("ip_address") if user_context else None,
                    user_id=user_id,
                    metadata={
                        "anomaly_score": anomaly_result.anomaly_score,
                        "confidence": anomaly_result.confidence,
                        "detected_patterns": anomaly_result.detected_patterns,
                        "risk_factors": anomaly_result.risk_factors,
                        "features": {
                            "hour_of_day": features.hour_of_day,
                            "requests_per_minute": features.requests_per_minute,
                            "session_duration": features.session_duration,
                            "safety_violations": features.child_safety_violations,
                        },
                    },
                )

            return None

        except (ValueError, AttributeError, KeyError) as e:
            self.logger.error(
                "Error in behavioral anomaly detection for user %s: %s", user_id, e
            )
            return None


class SecurityService:
    """Core security service for the application."""

    def __init__(
        self,
        rate_limiting_service: Optional[RateLimitingService] = None,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self.logger = get_logger(__name__, "security_service")
        self.config = get_config()
        self.redis = redis_client
        self.threat_detector = ThreatDetector(redis_client, self.config)
        self.rate_limiting_service = rate_limiting_service
        self.active_threats = []
        self.blocked_ips = set()  # Fallback for when Redis is unavailable
        self.security_events = []

        # Initialize encryption components
        self._init_encryption_keys()
        self._init_field_encryption_mappings()

        # Audit log configuration
        self.audit_key_prefix = "audit_log"
        self.max_audit_batch_size = 100
        self._audit_buffer: List[AuditLogEntry] = []

    async def verify_parent_child_relationship(
        self, parent_id: str, child_id: str
    ) -> bool:
        """Verify that the given parent_id is the legal guardian of child_id (production, async, ORM)."""
        db_manager = await initialize_database()
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    # Query for child with matching parent
                    ChildModel.__table__.select().where(
                        (ChildModel.id == child_id)
                        & (ChildModel.parent_id == parent_id)
                    )
                )
                child_row = await result.first()
                return child_row is not None
        except SQLAlchemyError as e:
            self.logger.error(
                "Database error during parent-child verification", error=str(e)
            )
            return False

    async def validate_request_security(
        self, request_data: Dict[str, Any], user_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Validate request for security threats."""

        validation_result = {
            "is_safe": True,
            "threats_detected": [],
            "security_score": 1.0,
            "recommendations": [],
        }

        user_id = user_context.get("user_id") if user_context else None
        ip_address = user_context.get("ip_address") if user_context else None

        # Check rate limits first if service is available
        if self.rate_limiting_service and user_id:
            try:
                operation = OperationType.API_CALL  # Default operation type
                if "content" in request_data:
                    operation = OperationType.CONVERSATION_MESSAGE
                elif "ai_request" in request_data:
                    operation = OperationType.AI_REQUEST

                child_age = user_context.get("child_age") if user_context else None
                rate_limit_result = await self.rate_limiting_service.check_rate_limit(
                    child_id=user_id,
                    operation=operation,
                    child_age=child_age,
                    additional_context=user_context,
                )

                if not rate_limit_result.allowed:
                    validation_result["is_safe"] = False
                    validation_result[
                        "security_score"
                    ] *= 0.0  # Zero score for rate limit violations
                    validation_result["recommendations"].append("rate_limit_exceeded")

                    # Log rate limit violation
                    security_logger.warning(
                        "Rate limit exceeded",
                        user_id=user_id,
                        operation=operation.value,
                        remaining=rate_limit_result.remaining,
                        reason=rate_limit_result.reason,
                    )

                    return validation_result

            except (ConnectionError, AttributeError, ValueError) as e:
                self.logger.warning(
                    "Rate limiting check failed, continuing with other checks: %s", e
                )

        # Check for behavioral anomalies if we have user session data
        if user_id and user_context:
            try:
                # Build session data for anomaly detection
                session_data = {
                    "session_duration": user_context.get("session_duration", 0),
                    "requests": [request_data],
                    "safety_violations": user_context.get("safety_violations", 0),
                    "age_inappropriate_attempts": user_context.get(
                        "age_inappropriate_attempts", 0
                    ),
                }

                behavioral_threat = (
                    await self.threat_detector.detect_behavioral_anomalies(
                        user_id, session_data, user_context
                    )
                )

                if behavioral_threat:
                    validation_result["threats_detected"].append(behavioral_threat)
                    validation_result["is_safe"] = False
                    validation_result[
                        "security_score"
                    ] *= 0.3  # Significant penalty for behavioral anomalies

                    # Log behavioral anomaly
                    security_logger.warning(
                        "Behavioral anomaly detected",
                        user_id=user_id,
                        anomaly_score=behavioral_threat.metadata.get("anomaly_score"),
                        detected_patterns=behavioral_threat.metadata.get(
                            "detected_patterns"
                        ),
                        risk_factors=behavioral_threat.metadata.get("risk_factors"),
                    )

            except (ValueError, AttributeError, KeyError) as e:
                self.logger.warning(
                    "Behavioral anomaly detection failed, continuing: %s", e
                )

        # Check for content injection
        if "content" in request_data:
            injection_threat = self.threat_detector.detect_content_injection(
                request_data["content"], user_id
            )
            if injection_threat:
                validation_result["threats_detected"].append(injection_threat)
                validation_result["is_safe"] = False
                validation_result["security_score"] *= 0.1

        # Check for brute force if authentication failed
        if request_data.get("authentication_failed") and ip_address:
            brute_force_threat = await self.threat_detector.detect_brute_force(
                ip_address, user_id
            )
            if brute_force_threat:
                validation_result["threats_detected"].append(brute_force_threat)
                validation_result["is_safe"] = False
                validation_result["security_score"] *= 0.2

                # Block IP if critical threat
                if brute_force_threat.severity == "high":
                    await self.block_ip(ip_address, "brute_force_attack")
                    validation_result["recommendations"].append("ip_blocked")

        # Log security validation
        if not validation_result["is_safe"]:
            security_logger.warning(
                "Security threats detected in request",
                user_id=user_id,
                ip_address=ip_address,
                threat_count=len(validation_result["threats_detected"]),
                security_score=validation_result["security_score"],
            )

            # Audit log for security events
            for threat in validation_result["threats_detected"]:
                coppa_audit.log_event(
                    {
                        "event_type": "security_threat_detected",
                        "severity": threat.severity,
                        "description": threat.description,
                        "user_id": user_id,
                        "metadata": {
                            "threat_id": threat.threat_id,
                            "threat_type": threat.threat_type,
                            "ip_address": ip_address,
                            **(threat.metadata or {}),
                        },
                    }
                )

        return validation_result

    # --- Access Pattern Analysis State ---
    _access_logs: Dict[str, List[Dict[str, Any]]] = {}  # Fallback storage

    def _get_access_thresholds(self) -> Dict[str, Any]:
        """Get access thresholds from configuration."""
        return {
            "max_access_per_hour": self.config.SECURITY_ACCESS_MAX_PER_HOUR,
            "max_access_per_day": self.config.SECURITY_ACCESS_MAX_PER_DAY,
            "max_frequency_per_minute": self.config.SECURITY_ACCESS_MAX_PER_MINUTE,
            "unusual_hours": (
                self.config.SECURITY_UNUSUAL_HOURS_START,
                self.config.SECURITY_UNUSUAL_HOURS_END,
            ),
        }

    async def validate_child_data_access(
        self,
        user_id: str,
        child_id: str,
        access_type: str,
        user_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Validate access to child data for COPPA compliance, with full access pattern analysis."""

        validation_result = {
            "access_allowed": True,
            "requires_parental_consent": False,
            "coppa_compliant": True,
            "audit_required": True,
            "restrictions": [],
        }

        # Check user permissions
        user_role = (
            user_context.get("user_type", "unknown") if user_context else "unknown"
        )

        if user_role == "child":
            # Children can only access their own data
            if user_id != child_id:
                validation_result["access_allowed"] = False
                validation_result["restrictions"].append(
                    "child_can_only_access_own_data"
                )

        elif user_role == "parent":
            # Parents need verified relationship to child
            is_parent = await self.verify_parent_child_relationship(user_id, child_id)
            if not is_parent:
                validation_result["access_allowed"] = False
                validation_result["restrictions"].append(
                    "parent_child_relationship_invalid"
                )

        elif user_role not in ["admin", "system"]:
            # Unknown or unauthorized role
            validation_result["access_allowed"] = False
            validation_result["restrictions"].append("unauthorized_user_role")

        # --- Access Pattern Analysis ---
        now = datetime.utcnow()
        log_key = f"{user_id}:{child_id}:{user_role}"
        log_entry = {
            "timestamp": now,
            "access_type": access_type,
            "ip_address": user_context.get("ip_address") if user_context else None,
        }
        # Store access log in Redis (with fallback to memory)
        try:
            if self.redis:
                redis_key = f"access_log:{log_key}"
                await self.redis.lpush(redis_key, json.dumps(log_entry, default=str))
                # Keep only last 500 entries
                await self.redis.ltrim(redis_key, 0, 499)
                # Set expiration for 7 days
                await self.redis.expire(redis_key, 604800)

                # Get recent logs from Redis for analysis
                redis_logs = await self.redis.lrange(redis_key, 0, -1)
                logs = [json.loads(entry) for entry in redis_logs]
                # Convert string timestamps back to datetime
                for log in logs:
                    log["timestamp"] = datetime.fromisoformat(
                        log["timestamp"].replace("Z", "+00:00")
                    )
            else:
                # Fallback to in-memory storage
                logs = self._access_logs.setdefault(log_key, [])
                logs.append(log_entry)
                if len(logs) > 500:
                    self._access_logs[log_key] = logs[-500:]
        except (ConnectionError, json.JSONDecodeError, ValueError) as e:
            safe_error = re.sub(r"[\r\n\x00-\x1f\x7f-\x9f]", "", str(e))[:200]
            self.logger.warning(
                "Redis error in access logging, using fallback: %s", safe_error
            )
            # Fallback to in-memory storage
            logs = self._access_logs.setdefault(log_key, [])
            logs.append(log_entry)
            if len(logs) > 500:
                self._access_logs[log_key] = logs[-500:]

        # Optimized pattern analysis using Redis sorted sets for better performance
        thresholds = self._get_access_thresholds()

        # Use Redis sorted sets for efficient time-based queries
        if "logs" not in locals():
            try:
                if self.redis:
                    # Use sorted set for time-based efficient queries
                    sorted_set_key = f"access_times:{log_key}"
                    current_timestamp = now.timestamp()

                    # Add current access to sorted set
                    await self.redis.zadd(
                        sorted_set_key, {str(current_timestamp): current_timestamp}
                    )

                    # Remove entries older than 24 hours for efficiency
                    await self.redis.zremrangebyscore(
                        sorted_set_key, 0, current_timestamp - 86400
                    )

                    # Set expiration for the sorted set
                    await self.redis.expire(sorted_set_key, 86400)

                    # Get counts for different time windows efficiently
                    hour_ago = current_timestamp - 3600
                    day_ago = current_timestamp - 86400
                    minute_ago = current_timestamp - 60

                    # Use pipeline for batch operations
                    pipe = self.redis.pipeline()
                    pipe.zcount(sorted_set_key, hour_ago, current_timestamp)
                    pipe.zcount(sorted_set_key, day_ago, current_timestamp)
                    pipe.zcount(sorted_set_key, minute_ago, current_timestamp)

                    counts = await pipe.execute()
                    accesses_last_hour_count = counts[0]
                    accesses_last_day_count = counts[1]
                    accesses_last_minute_count = counts[2]

                    # Create mock log entries for compatibility (only if needed for detailed analysis)
                    logs = []
                else:
                    logs = self._access_logs.get(log_key, [])
                    accesses_last_hour_count = len(
                        [
                            log
                            for log in logs
                            if (now - log["timestamp"]).total_seconds() < 3600
                        ]
                    )
                    accesses_last_day_count = len(
                        [
                            log
                            for log in logs
                            if (now - log["timestamp"]).total_seconds() < 86400
                        ]
                    )
                    accesses_last_minute_count = len(
                        [
                            log
                            for log in logs
                            if (now - log["timestamp"]).total_seconds() < 60
                        ]
                    )
            except (ConnectionError, AttributeError, ValueError) as e:
                self.logger.warning(
                    "Redis error in pattern analysis, using fallback: %s", e
                )
                logs = self._access_logs.get(log_key, [])
                accesses_last_hour_count = len(
                    [
                        log
                        for log in logs
                        if (now - log["timestamp"]).total_seconds() < 3600
                    ]
                )
                accesses_last_day_count = len(
                    [
                        log
                        for log in logs
                        if (now - log["timestamp"]).total_seconds() < 86400
                    ]
                )
                accesses_last_minute_count = len(
                    [
                        log
                        for log in logs
                        if (now - log["timestamp"]).total_seconds() < 60
                    ]
                )

        # Use optimized counts when available, fallback to list analysis
        if "accesses_last_hour_count" in locals():
            # Use pre-calculated counts for better performance
            hour_count = accesses_last_hour_count
            day_count = accesses_last_day_count
            minute_count = accesses_last_minute_count
        else:
            # Fallback to traditional counting
            accesses_last_hour = [
                log_entry
                for log_entry in logs
                if (now - log_entry["timestamp"]).total_seconds() < 3600
            ]
            accesses_last_day = [
                log_entry
                for log_entry in logs
                if (now - log_entry["timestamp"]).total_seconds() < 86400
            ]
            accesses_last_minute = [
                log_entry
                for log_entry in logs
                if (now - log_entry["timestamp"]).total_seconds() < 60
            ]
            hour_count = len(accesses_last_hour)
            day_count = len(accesses_last_day)
            minute_count = len(accesses_last_minute)

        hour = now.hour
        unusual_hours = thresholds["unusual_hours"]
        is_unusual_hour = hour >= unusual_hours[0] and hour < unusual_hours[1]

        suspicious_indicators = []
        if hour_count > thresholds["max_access_per_hour"]:
            suspicious_indicators.append("excessive_access_hour")
        if day_count > thresholds["max_access_per_day"]:
            suspicious_indicators.append("excessive_access_day")
        if minute_count > thresholds["max_frequency_per_minute"]:
            suspicious_indicators.append("high_frequency_minute")
        if is_unusual_hour:
            suspicious_indicators.append("unusual_access_time")

        if suspicious_indicators:
            # سجل الحدث في نظام التدقيق مع التفاصيل
            coppa_audit.log_event(
                {
                    "event_type": "suspicious_activity",
                    "severity": (
                        "warning" if len(suspicious_indicators) == 1 else "critical"
                    ),
                    "description": f"Suspicious access pattern detected: {', '.join(suspicious_indicators)}",
                    "user_id": user_id,
                    "user_type": user_role,
                    "child_id": child_id,
                    "metadata": {
                        "access_type": access_type,
                        "indicators": suspicious_indicators,
                        "access_count_hour": hour_count,
                        "access_count_day": day_count,
                        "access_count_minute": minute_count,
                        "ip_address": (
                            user_context.get("ip_address") if user_context else None
                        ),
                        "timestamp": now.isoformat(),
                    },
                }
            )
            # تقييد الوصول إذا تجاوزت المؤشرات الحرجة
            if len(suspicious_indicators) >= 2:
                validation_result["access_allowed"] = False
                validation_result["restrictions"].append(
                    "suspicious_access_pattern_detected"
                )
                validation_result["coppa_compliant"] = False
                security_logger.warning(
                    "Access denied due to suspicious pattern",
                    user_id=user_id,
                    child_id=child_id,
                    access_type=access_type,
                    indicators=suspicious_indicators,
                )

        # Log child data access
        if validation_result["access_allowed"]:
            coppa_audit.log_event(
                {
                    "event_type": "child_data_access",
                    "severity": "info",
                    "description": f"Child data access: {access_type}",
                    "user_id": user_id,
                    "child_id": child_id,
                    "metadata": {
                        "access_type": access_type,
                        "user_role": user_role,
                        "coppa_compliant": validation_result["coppa_compliant"],
                    },
                }
            )
        else:
            security_logger.warning(
                "Child data access denied",
                user_id=user_id,
                child_id=child_id,
                access_type=access_type,
                restrictions=validation_result["restrictions"],
            )

        return validation_result

    async def check_content_safety(
        self, content: str, child_age: int = None
    ) -> Dict[str, Any]:
        """Check content safety for children."""

        # Input validation
        if not content or not isinstance(content, str):
            return {
                "is_safe": False,
                "safety_score": 0.0,
                "violations": ["invalid_content"],
                "filtered_content": "",
                "age_appropriate": False,
            }

        # Validate child age
        if child_age is not None and (
            not isinstance(child_age, int) or child_age < 0 or child_age > 18
        ):
            child_age = None

        # Limit content length
        if len(content) > 5000:
            content = content[:5000]

        safety_result = {
            "is_safe": True,
            "safety_score": 1.0,
            "violations": [],
            "filtered_content": content,
            "age_appropriate": True,
        }

        # Basic content safety checks
        unsafe_patterns = [
            # Violence
            "kill",
            "murder",
            "blood",
            "weapon",
            "gun",
            "knife",
            # Inappropriate content
            "sex",
            "adult",
            "mature",
            "explicit",
            # Personal information requests
            "address",
            "phone number",
            "email",
            "password",
            # External contact
            "meet me",
            "come to",
            "visit me",
            "secret",
        ]

        content_lower = content.lower()
        detected_violations = []

        for pattern in unsafe_patterns:
            if pattern in content_lower:
                detected_violations.append(pattern)

        if detected_violations:
            safety_result["is_safe"] = False
            safety_result["violations"] = detected_violations
            safety_result["safety_score"] = max(
                0.1, 1.0 - (len(detected_violations) * 0.2)
            )

            # Filter content
            filtered_content = content
            for violation in detected_violations:
                filtered_content = filtered_content.replace(violation, "***")
            safety_result["filtered_content"] = filtered_content

        # Age appropriateness check
        if child_age and child_age < 13:
            # Stricter checks for younger children
            if any(
                word in content_lower for word in ["scary", "frightening", "nightmare"]
            ):
                safety_result["age_appropriate"] = False
                safety_result["safety_score"] *= 0.8

        # Log safety violations
        if not safety_result["is_safe"]:
            security_logger.warning(
                "Content safety violation detected",
                violations=detected_violations,
                safety_score=safety_result["safety_score"],
                child_age=child_age,
            )

            coppa_audit.log_event(
                {
                    "event_type": "content_safety_violation",
                    "severity": "warning",
                    "description": "Unsafe content detected",
                    "metadata": {
                        "violations": detected_violations,
                        "safety_score": safety_result["safety_score"],
                        "child_age": child_age,
                        "content_length": len(content),
                    },
                }
            )

        return safety_result

    async def health_check(self) -> Dict[str, Any]:
        """Security service health check."""

        return {
            "status": "healthy",
            "active_threats": len(self.active_threats),
            "blocked_ips": len(self.blocked_ips),
            "security_events_24h": len(
                [
                    event
                    for event in self.security_events
                    if event.get("timestamp", 0) > time.time() - 86400
                ]
            ),
            "threat_detection": "active",
            "content_filtering": "active",
        }

    async def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if IP address is blocked using Redis with fallback."""
        try:
            if self.redis:
                blocked = await self.redis.get(f"blocked_ip:{ip_address}")
                return blocked is not None
            else:
                return ip_address in self.blocked_ips
        except ConnectionError as e:
            self.logger.warning(
                "Redis error checking blocked IP, using fallback: %s", e
            )
            return ip_address in self.blocked_ips

    async def block_ip(self, ip_address: str, reason: str = "security_violation"):
        """Block an IP address with persistent storage and expiration."""
        try:
            if self.redis:
                # Store in Redis with expiration
                await self.redis.setex(
                    f"blocked_ip:{ip_address}",
                    self.config.SECURITY_IP_BLOCK_DURATION,
                    json.dumps(
                        {
                            "reason": reason,
                            "blocked_at": datetime.utcnow().isoformat(),
                            "expires_at": (
                                datetime.utcnow()
                                + timedelta(
                                    seconds=self.config.SECURITY_IP_BLOCK_DURATION
                                )
                            ).isoformat(),
                        }
                    ),
                )
            else:
                # Fallback to in-memory storage
                self.blocked_ips.add(ip_address)
        except ConnectionError as e:
            self.logger.warning("Redis error blocking IP, using fallback: %s", e)
            self.blocked_ips.add(ip_address)

        security_logger.warning(
            "IP address blocked", ip_address=ip_address, reason=reason
        )

        coppa_audit.log_event(
            {
                "event_type": "ip_blocked",
                "severity": "warning",
                "description": f"IP address blocked: {reason}",
                "metadata": {"ip_address": ip_address, "reason": reason},
            }
        )

    async def get_rate_limit_status(self, child_id: str) -> Dict[str, Any]:
        """Get current rate limiting status for a child."""
        if not self.rate_limiting_service:
            return {"error": "Rate limiting service not available"}

        try:
            return await self.rate_limiting_service.get_usage_stats(child_id)
        except (ConnectionError, AttributeError) as e:
            self.logger.error("Error getting rate limit status: %s", e)
            return {"error": f"Failed to get rate limit status: {e}"}

    async def reset_rate_limits(
        self, child_id: str, operation: Optional[OperationType] = None
    ) -> bool:
        """Reset rate limits for a child (admin function)."""
        if not self.rate_limiting_service:
            return False

        try:
            await self.rate_limiting_service.reset_limits(child_id, operation)
            return True
        except (ConnectionError, AttributeError) as e:
            self.logger.error("Error resetting rate limits: %s", e)
            return False

    async def analyze_user_behavior(
        self,
        user_id: str,
        session_data: Dict[str, Any],
        include_recommendations: bool = True,
    ) -> Dict[str, Any]:
        """Analyze user behavior for anomalies and provide insights."""

        try:
            # Extract behavioral features
            features = await self.threat_detector.ml_anomaly_detector.extract_behavior_features(
                user_id, session_data
            )

            # Detect anomalies
            anomaly_result = await self.threat_detector.ml_anomaly_detector.detect_behavioral_anomalies(
                features
            )

            analysis = {
                "user_id": user_id,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "behavior_summary": {
                    "session_duration": features.session_duration,
                    "requests_per_minute": features.requests_per_minute,
                    "hour_of_day": features.hour_of_day,
                    "day_of_week": features.day_of_week,
                    "error_rate": features.error_rate,
                    "safety_violations": features.child_safety_violations,
                },
                "anomaly_detection": {
                    "is_anomaly": anomaly_result.is_anomaly,
                    "anomaly_score": anomaly_result.anomaly_score,
                    "confidence": anomaly_result.confidence,
                    "detected_patterns": anomaly_result.detected_patterns,
                    "risk_factors": anomaly_result.risk_factors,
                    "explanation": anomaly_result.explanation,
                },
            }

            if include_recommendations and anomaly_result.is_anomaly:
                recommendations = []

                if "temporal_anomaly" in anomaly_result.detected_patterns:
                    recommendations.append("Monitor unusual access times")

                if "activity_anomaly" in anomaly_result.detected_patterns:
                    recommendations.append("Review activity levels and patterns")

                if "child_safety_anomaly" in anomaly_result.detected_patterns:
                    recommendations.append(
                        "⚠️ URGENT: Review child safety violations immediately"
                    )
                    recommendations.append("Consider enhanced parental controls")

                if "content_anomaly" in anomaly_result.detected_patterns:
                    recommendations.append("Analyze content interaction patterns")

                analysis["recommendations"] = recommendations

            return analysis

        except (ValueError, AttributeError, KeyError) as e:
            self.logger.error("Error analyzing user behavior: %s", e)
            return {
                "error": f"Failed to analyze user behavior: {e}",
                "user_id": user_id,
                "analysis_timestamp": datetime.utcnow().isoformat(),
            }

    # ========================================================================
    # FUNCTIONS FROM security_utils.py
    # ========================================================================

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate secure random token."""
        return secrets.token_hex(length)

    def detect_sql_injection(self, input_text: str) -> bool:
        """Detect SQL injection patterns in input text."""
        if not input_text or not isinstance(input_text, str):
            return False

        # Limit input length to prevent DoS
        if len(input_text) > 10000:
            return True  # Suspicious large input

        sql_patterns = [
            r"';.*--",
            r"'\s*OR\s*'.*'='",
            r"'\s*UNION\s*SELECT",
            r"';.*DROP\s*TABLE",
            r"';.*DELETE\s*FROM",
            r"';.*INSERT\s*INTO",
            r"';.*UPDATE\s*.*SET",
            r"'\s*AND\s*'.*'='",
        ]

        # Sanitize input before checking
        input_clean = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", input_text)
        input_upper = input_clean.upper()

        return any(
            re.search(pattern, input_upper, re.IGNORECASE) for pattern in sql_patterns
        )

    def sanitize_html(self, html_input: str) -> str:
        """Sanitize HTML input to prevent XSS attacks."""
        if not html_input or not isinstance(html_input, str):
            return ""

        # Limit input length
        if len(html_input) > 50000:
            html_input = html_input[:50000]

        # Remove null bytes and control characters
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", html_input)

        # Remove script tags and content
        sanitized = re.sub(
            r"<script[^>]*?>.*?</script>",
            "",
            sanitized,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Remove javascript: protocol
        sanitized = re.sub(r"javascript:", "", sanitized, flags=re.IGNORECASE)

        # Remove event handlers
        sanitized = re.sub(
            r"\son\w+\s*=\s*[\"'][^\"']*[\"']", "", sanitized, flags=re.IGNORECASE
        )

        # Remove dangerous tags
        dangerous_tags = ["iframe", "object", "embed", "form", "input", "meta", "link"]
        for tag in dangerous_tags:
            sanitized = re.sub(f"<{tag}[^>]*?>", "", sanitized, flags=re.IGNORECASE)
            sanitized = re.sub(f"</{tag}>", "", sanitized, flags=re.IGNORECASE)

        return sanitized

    def create_jwt_session(
        self, user_data: Dict[str, Any], secret_key: str = None
    ) -> str:
        """Create JWT session token."""
        if not secret_key:
            from src.infrastructure.config.loader import get_config

            config = get_config()
            secret_key = config.JWT_SECRET_KEY
            if not secret_key:
                raise Exception(
                    "JWT_SECRET_KEY missing in config. COPPA compliance violation."
                )
        payload = {
            "user_id": user_data["user_id"],
            "email": user_data.get("email"),
            "role": user_data.get("role"),
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=24),
        }
        return jwt.encode(payload, secret_key, algorithm="HS256")

    def validate_jwt_session(
        self, session_token: str, secret_key: str = None
    ) -> Dict[str, Any]:
        """Validate JWT session token."""
        try:
            if not secret_key:
                from src.infrastructure.config.loader import get_config

                config = get_config()
                secret_key = config.JWT_SECRET_KEY
                if not secret_key:
                    raise Exception(
                        "JWT_SECRET_KEY missing in config. COPPA compliance violation."
                    )
            payload = jwt.decode(session_token, secret_key, algorithms=["HS256"])
            return {
                "valid": True,
                "user_id": payload["user_id"],
                "email": payload.get("email"),
                "role": payload.get("role"),
                "expires_at": datetime.fromtimestamp(payload["exp"]),
            }
        except jwt.ExpiredSignatureError:
            return {"valid": False, "error": "Token expired"}
        except jwt.InvalidTokenError:
            return {"valid": False, "error": "Invalid token"}

    # ========================================================================
    # FUNCTIONS FROM data_encryption_service.py
    # ========================================================================

    def _init_encryption_keys(self, master_key: Optional[bytes] = None):
        """Initialize encryption keys and key management."""
        if master_key:
            self.master_key = master_key
        else:
            # Generate secure master key
            self.master_key = Fernet.generate_key()

        # Create Fernet instance for symmetric encryption
        self.fernet = Fernet(self.master_key)

        # Generate RSA key pair for asymmetric encryption
        self.private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        self.public_key = self.private_key.public_key()

    def _init_field_encryption_mappings(self):
        """Initialize field-level encryption mappings."""
        self.field_encryption_map = {
            # User data
            "email": EncryptionLevel.SENSITIVE,
            "phone_number": EncryptionLevel.SENSITIVE,
            "address": EncryptionLevel.SENSITIVE,
            "date_of_birth": EncryptionLevel.SENSITIVE,
            "ssn": EncryptionLevel.HIGHLY_SENSITIVE,
            "payment_info": EncryptionLevel.HIGHLY_SENSITIVE,
            # Child data (COPPA protected)
            "child_name": EncryptionLevel.SENSITIVE,
            "child_age": EncryptionLevel.SENSITIVE,
            "child_preferences": EncryptionLevel.SENSITIVE,
            "child_location": EncryptionLevel.HIGHLY_SENSITIVE,
            "child_medical_info": EncryptionLevel.HIGHLY_SENSITIVE,
            # Session data
            "device_info": EncryptionLevel.STANDARD,
            "session_metadata": EncryptionLevel.STANDARD,
            # Communication data
            "conversation_content": EncryptionLevel.SENSITIVE,
            "voice_recordings": EncryptionLevel.HIGHLY_SENSITIVE,
        }

    async def encrypt_field(
        self,
        field_name: str,
        value: Any,
        encryption_level: Optional[EncryptionLevel] = None,
    ) -> str:
        """Encrypt a single field based on its sensitivity level."""
        if value is None:
            return None

        # Determine encryption level
        level = encryption_level or self.field_encryption_map.get(
            field_name, EncryptionLevel.STANDARD
        )

        # Convert value to string if needed
        if not isinstance(value, str):
            value = json.dumps(value)

        try:
            if level == EncryptionLevel.NONE:
                return value
            elif level == EncryptionLevel.STANDARD:
                return self._encrypt_standard(value)
            elif level == EncryptionLevel.SENSITIVE:
                return self._encrypt_sensitive(value)
            elif level == EncryptionLevel.HIGHLY_SENSITIVE:
                return self._encrypt_highly_sensitive(value)
            else:
                return self._encrypt_standard(value)

        except Exception as e:
            self.logger.error("Failed to encrypt field %s: %s", field_name, e)
            raise

    async def decrypt_field(
        self,
        field_name: str,
        encrypted_value: str,
        encryption_level: Optional[EncryptionLevel] = None,
    ) -> Any:
        """Decrypt a field value."""
        if encrypted_value is None:
            return None

        # Determine encryption level
        level = encryption_level or self.field_encryption_map.get(
            field_name, EncryptionLevel.STANDARD
        )

        try:
            if level == EncryptionLevel.NONE:
                return encrypted_value
            elif level == EncryptionLevel.STANDARD:
                return self._decrypt_standard(encrypted_value)
            elif level == EncryptionLevel.SENSITIVE:
                return self._decrypt_sensitive(encrypted_value)
            elif level == EncryptionLevel.HIGHLY_SENSITIVE:
                return self._decrypt_highly_sensitive(encrypted_value)
            else:
                return self._decrypt_standard(encrypted_value)

        except Exception as e:
            # Sanitize field_name and error for logging to prevent log injection
            safe_field_name = (
                re.sub(r"[\r\n\x00-\x1f\x7f-\x9f]", "", str(field_name))[:50]
                if field_name
                else "None"
            )
            safe_error = re.sub(r"[\r\n\x00-\x1f\x7f-\x9f]", "", str(e))[:200]
            self.logger.error(
                "Failed to decrypt field %s: %s", safe_field_name, safe_error
            )
            raise

    def _encrypt_standard(self, value: str) -> str:
        """Standard AES-256 encryption."""
        encrypted_bytes = self.fernet.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted_bytes).decode()

    def _decrypt_standard(self, encrypted_value: str) -> str:
        """Standard AES-256 decryption."""
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode())
        decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()

    def _encrypt_sensitive(self, value: str) -> str:
        """Enhanced encryption for sensitive data."""
        # Add additional entropy
        salt = secrets.token_bytes(16)
        salted_value = salt + value.encode()

        encrypted_bytes = self.fernet.encrypt(salted_value)
        return base64.urlsafe_b64encode(encrypted_bytes).decode()

    def _decrypt_sensitive(self, encrypted_value: str) -> str:
        """Decrypt sensitive data."""
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_value.encode())
        decrypted_bytes = self.fernet.decrypt(encrypted_bytes)

        # Remove salt (first 16 bytes)
        return decrypted_bytes[16:].decode()

    def _encrypt_highly_sensitive(self, value: str) -> str:
        """RSA + AES hybrid encryption for highly sensitive data."""
        # Generate symmetric key for this specific data
        aes_key = Fernet.generate_key()
        aes_cipher = Fernet(aes_key)

        # Encrypt data with AES
        encrypted_data = aes_cipher.encrypt(value.encode())

        # Encrypt AES key with RSA public key
        encrypted_key = self.public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        # Combine encrypted key and data
        combined = encrypted_key + b":::" + encrypted_data
        return base64.urlsafe_b64encode(combined).decode()

    def _decrypt_highly_sensitive(self, encrypted_value: str) -> str:
        """Decrypt highly sensitive data."""
        combined = base64.urlsafe_b64decode(encrypted_value.encode())

        # Split encrypted key and data
        parts = combined.split(b":::", 1)
        encrypted_key, encrypted_data = parts[0], parts[1]

        # Decrypt AES key with RSA private key
        aes_key = self.private_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        # Decrypt data with AES key
        aes_cipher = Fernet(aes_key)
        decrypted_data = aes_cipher.decrypt(encrypted_data)
        return decrypted_data.decode()

    async def log_audit_event(
        self,
        event_type: AuditEventType,
        action_performed: str,
        resource_type: str,
        user_id: Optional[str] = None,
        user_type: Optional[str] = None,
        child_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        data_classification: DataClassification = DataClassification.INTERNAL,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        data_before: Optional[Dict[str, Any]] = None,
        data_after: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log a comprehensive audit event."""
        # Create audit log entry
        audit_entry = AuditLogEntry(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_type=user_type,
            child_id=child_id,
            action_performed=action_performed,
            resource_type=resource_type,
            resource_id=resource_id,
            data_classification=data_classification,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
            data_before=data_before,
            data_after=data_after,
            metadata=metadata,
        )

        # Add to buffer for batch processing
        self._audit_buffer.append(audit_entry)

        # If buffer is full, flush to storage
        if len(self._audit_buffer) >= self.max_audit_batch_size:
            await self._flush_audit_buffer()

    async def _flush_audit_buffer(self):
        """Flush audit buffer to Redis storage."""
        if not self._audit_buffer:
            return

        try:
            # Create Redis pipeline for batch processing
            pipe = self.redis.pipeline()

            for entry in self._audit_buffer:
                # Store in multiple formats for different query patterns
                entry_data = entry.to_dict()
                entry_json = json.dumps(entry_data)

                # Main audit log (chronological)
                pipe.zadd(
                    f"{self.audit_key_prefix}:chronological",
                    {entry_json: entry.timestamp.timestamp()},
                )

                # Index by user
                if entry.user_id:
                    pipe.zadd(
                        f"{self.audit_key_prefix}:user:{entry.user_id}",
                        {entry_json: entry.timestamp.timestamp()},
                    )

                # Index by child (COPPA compliance)
                if entry.child_id:
                    pipe.zadd(
                        f"{self.audit_key_prefix}:child:{entry.child_id}",
                        {entry_json: entry.timestamp.timestamp()},
                    )

            # Execute pipeline
            await pipe.execute()

            # Clear buffer
            self._audit_buffer.clear()

        except ConnectionError as e:
            self.logger.error("Failed to flush audit buffer: %s", e)
            # Keep entries in buffer for retry


async def create_security_service(
    rate_limiting_service: Optional[RateLimitingService] = None,
    redis_client: Optional[aioredis.Redis] = None,
) -> SecurityService:
    """Factory function to create security service with Redis and rate limiting support."""
    config = get_config()  # Use already imported get_config
    if redis_client is None:
        try:
            redis_client = aioredis.from_url(config.REDIS_URL)
            # Test connection
            await redis_client.ping()
        except ConnectionError as e:
            logger = get_logger(__name__, "security_service_factory")
            logger.warning(
                "Could not connect to Redis, using in-memory fallback: %s", str(e)
            )
            redis_client = None
    if rate_limiting_service is None:
        try:
            from src.infrastructure.rate_limiting.rate_limiter import (
                create_rate_limiting_service,
            )

            rate_limiting_service = create_rate_limiting_service(
                redis_url=config.REDIS_URL,
                use_redis=redis_client is not None,
                redis_client=redis_client if redis_client else None,
            )
            logger = get_logger(__name__, "security_service_factory")
            logger.info(
                "Rate limiting service created and integrated with security service"
            )
        except (ImportError, AttributeError) as e:
            logger = get_logger(__name__, "security_service_factory")
            logger.warning("Could not create rate limiting service: %s", str(e))
            rate_limiting_service = None
    return SecurityService(
        rate_limiting_service, redis_client
    )  # Fixed: removed extra config parameter


# =============================================================================
# CHILD DATA ENCRYPTION IMPLEMENTATION
# =============================================================================

class ProductionChildDataEncryption:
    """
    Production implementation of IChildDataEncryption.
    
    Provides secure encryption for child data with COPPA compliance.
    """
    
    def __init__(self, encryption_key: str = None):
        """Initialize encryption service."""
        from src.infrastructure.config.production_config import get_config
        
        self.config = get_config() if hasattr(get_config, '__call__') else None
        
        # Use provided key or get from config
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode()[:44] + b'=') 
        elif self.config and hasattr(self.config, 'COPPA_ENCRYPTION_KEY'):
            key = self.config.COPPA_ENCRYPTION_KEY
            if len(key) < 32:
                key = key.ljust(32, '0')[:32]
            key_bytes = base64.urlsafe_b64encode(key.encode()[:32])
            self.fernet = Fernet(key_bytes)
        else:
            # Generate a secure key for production
            key = Fernet.generate_key()
            self.fernet = Fernet(key)
            
        self.logger = get_logger(__name__, "child_data_encryption")
    
    async def encrypt_child_pii(self, data: str, child_id: str, classification: str = "PII") -> Dict[str, Any]:
        """Encrypt child PII data."""
        try:
            encrypted_data = self.fernet.encrypt(data.encode())
            
            result = {
                "encrypted_data": base64.b64encode(encrypted_data).decode(),
                "encryption_method": "Fernet-AES256",
                "key_id": f"child_{child_id}",
                "data_classification": classification,
                "created_at": time.time(),
                "metadata": {
                    "child_id": child_id,
                    "original_length": len(data),
                    "encrypted_length": len(encrypted_data)
                }
            }
            
            # Log encryption for COPPA audit
            self.logger.info(
                f"Encrypted child PII data",
                extra={
                    "child_id": child_id,
                    "classification": classification,
                    "operation": "encrypt_pii"
                }
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to encrypt child PII: {e}")
            raise ValueError(f"Encryption failed: {e}")
    
    async def decrypt_child_data(self, encrypted_result: Dict[str, Any]) -> str:
        """Decrypt child data."""
        try:
            encrypted_data = base64.b64decode(encrypted_result["encrypted_data"])
            decrypted_bytes = self.fernet.decrypt(encrypted_data)
            
            # Log decryption for COPPA audit
            self.logger.info(
                f"Decrypted child data",
                extra={
                    "key_id": encrypted_result.get("key_id"),
                    "classification": encrypted_result.get("data_classification"),
                    "operation": "decrypt_data"
                }
            )
            
            return decrypted_bytes.decode()
            
        except Exception as e:
            self.logger.error(f"Failed to decrypt child data: {e}")
            raise ValueError(f"Decryption failed: {e}")
    
    async def encrypt_conversation_data(self, conversation_text: str, child_id: str) -> Dict[str, Any]:
        """Encrypt conversation data for a child."""
        return await self.encrypt_child_pii(
            conversation_text, 
            child_id, 
            classification="CONFIDENTIAL"
        )
    
    async def anonymize_child_data(self, data: Dict[str, Any], child_id: str) -> Dict[str, Any]:
        """Anonymize child data for analytics."""
        try:
            # Remove direct identifiers
            anonymized = data.copy()
            sensitive_fields = ["name", "email", "phone", "address"]
            
            for field in sensitive_fields:
                if field in anonymized:
                    # Replace with anonymized hash
                    hash_input = f"{child_id}_{field}_{data[field]}".encode()
                    anonymized[field] = hashlib.sha256(hash_input).hexdigest()[:8]
            
            # Log anonymization for COPPA audit
            self.logger.info(
                f"Anonymized child data for analytics",
                extra={
                    "child_id": child_id,
                    "fields_anonymized": len([f for f in sensitive_fields if f in data]),
                    "operation": "anonymize_data"
                }
            )
            
            return anonymized
            
        except Exception as e:
            self.logger.error(f"Failed to anonymize child data: {e}")
            raise ValueError(f"Anonymization failed: {e}")


# Factory function
def create_child_data_encryption() -> ProductionChildDataEncryption:
    """Create child data encryption service."""
    return ProductionChildDataEncryption()
