"""Unified Child Safety Service - Single Source of Truth

This unified service consolidates all child safety service implementations.
Provides comprehensive child safety monitoring and content filtering.
"""

import re
import logging
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from sqlalchemy.orm import selectinload

# Import required models for compatibility
from src.core.models import RiskLevel, SafetyAnalysisResult
from src.core.entities import SafetyResult

# Dynamic import to avoid circular dependency
# from src.application.interfaces.safety_monitor import SafetyMonitor
from src.interfaces.services import IChildSafetyService

# Lazy import to avoid circular dependency
# from src.infrastructure.database.database_manager import database_manager
from src.infrastructure.database.models import (
    SafetyReport,
    Child,
    Conversation,
    Interaction,
    AuditLog,
    SafetyLevel,
)
from src.infrastructure.logging import get_logger, security_logger

logger = logging.getLogger(__name__)


def get_database_manager():
    """Get database manager with lazy import to avoid circular dependency."""
    from src.infrastructure.database.database_manager import database_manager

    return database_manager


class ChildSafetyService(IChildSafetyService):
    """Unified child safety service implementation.

    Note: This class also implements SafetyMonitor interface through duck typing
    to avoid circular import issues.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize child safety service.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.safety_events = []  # Keep for backward compatibility

        # Enhanced safety configuration
        self.enable_real_time_monitoring = getattr(
            config, "enable_real_time_monitoring", True
        )
        self.auto_report_threshold = getattr(config, "auto_report_threshold", 0.7)
        self.parent_notification_threshold = getattr(
            config, "parent_notification_threshold", 0.8
        )
        self.emergency_alert_threshold = getattr(
            config, "emergency_alert_threshold", 0.9
        )

        # Cache for recent safety checks (performance optimization)
        self._safety_cache = {}
        self._cache_ttl = timedelta(minutes=5)

        # Enhanced inappropriate content patterns with severity levels
        self.safety_patterns = {
            "critical": [
                r"\b(kill|murder|suicide|death|die|dead|hurt|harm|violence|violent)\b",
                r"\b(drug|drugs|alcohol|smoking|cigarette|cocaine|marijuana)\b",
                r"\b(weapon|gun|knife|bomb|explosive|attack)\b",
                r"\b(sexual|sex|porn|inappropriate|abuse|molest)\b",
                r"\b(address|phone|email|password|credit card|social security)\b",
            ],
            "high": [
                r"\b(hate|racism|discrimination|bully|bullying|stupid|idiot)\b",
                r"\b(scary|monster|nightmare|ghost|demon|devil)\b",
                r"\b(secret|don't tell|our secret|between us)\b",
                r"\b(meet me|come over|visit me|alone)\b",
            ],
            "medium": [
                r"\b(sad|angry|mad|upset|crying|scared)\b",
                r"\b(fight|argue|yell|shout|scream)\b",
                r"\b(sick|pain|hurt|ache|medicine)\b",
            ],
            "low": [
                r"\b(weird|strange|funny|silly|crazy)\b",
                r"\b(tired|sleepy|hungry|thirsty)\b",
            ],
        }

        # PII detection patterns
        self.pii_patterns = [
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone numbers
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
            r"\b\d{1,5}\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b",  # Addresses
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit cards
            r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",  # SSN
        ]

        # Age-appropriate content levels
        self.age_levels = {
            "toddler": (0, 3),
            "preschool": (4, 5),
            "early_elementary": (6, 8),
            "late_elementary": (9, 11),
            "preteen": (12, 13),
        }

        # Real-time safety rule engine (initialize after patterns are defined)
        self.active_safety_rules = self._initialize_safety_rules()

        logger.info(
            f"Enhanced Child Safety Service initialized with {len(self.active_safety_rules)} active rules"
        )

    def _initialize_safety_rules(self) -> List[Dict[str, Any]]:
        """Initialize comprehensive safety rules engine."""
        rules = [
            {
                "id": "pii_detection",
                "name": "Personal Information Detection",
                "type": "pii",
                "severity": "critical",
                "patterns": self.pii_patterns,
                "action": "block_and_alert",
                "enabled": True,
            },
            {
                "id": "violence_content",
                "name": "Violence Content Filter",
                "type": "content",
                "severity": "critical",
                "patterns": self.safety_patterns["critical"][:1],
                "action": "block_and_alert",
                "enabled": True,
            },
            {
                "id": "inappropriate_language",
                "name": "Inappropriate Language Filter",
                "type": "language",
                "severity": "high",
                "patterns": self.safety_patterns["high"],
                "action": "filter_and_log",
                "enabled": True,
            },
            {
                "id": "emotional_distress",
                "name": "Emotional Distress Detection",
                "type": "emotional",
                "severity": "medium",
                "patterns": self.safety_patterns["medium"],
                "action": "log_and_monitor",
                "enabled": True,
            },
        ]
        return rules

    async def validate_content(self, content: str, child_age: int) -> Dict[str, Any]:
        """Validate content appropriateness for child.

        Args:
            content: Content to validate
            child_age: Age of the child

        Returns:
            Dictionary with validation results
        """
        # Check cache first for performance
        content_hash = hashlib.md5(f"{content}_{child_age}".encode()).hexdigest()
        if content_hash in self._safety_cache:
            cached_result, cached_time = self._safety_cache[content_hash]
            if datetime.now() - cached_time < self._cache_ttl:
                return cached_result

        result = {
            "is_safe": True,
            "confidence": 1.0,
            "issues": [],
            "age_appropriate": True,
            "timestamp": datetime.now().isoformat(),
            "risk_score": 0.0,
            "triggered_rules": [],
            "pii_detected": False,
            "requires_human_review": False,
        }

        content_lower = content.lower()

        # Enhanced safety rule processing
        for rule in self.active_safety_rules:
            if not rule["enabled"]:
                continue

            rule_triggered = False
            for pattern in rule["patterns"]:
                if re.search(pattern, content_lower):
                    rule_triggered = True

                    # Calculate risk score based on severity
                    severity_scores = {
                        "low": 0.2,
                        "medium": 0.4,
                        "high": 0.7,
                        "critical": 1.0,
                    }
                    risk_increase = severity_scores.get(rule["severity"], 0.5)
                    result["risk_score"] += risk_increase

                    issue = {
                        "rule_id": rule["id"],
                        "rule_name": rule["name"],
                        "type": rule["type"],
                        "pattern": pattern,
                        "severity": rule["severity"],
                        "action": rule["action"],
                        "match_text": self._extract_match_context(content, pattern),
                    }
                    result["issues"].append(issue)
                    result["triggered_rules"].append(rule["id"])

                    # Special handling for PII
                    if rule["type"] == "pii":
                        result["pii_detected"] = True
                        result["requires_human_review"] = True

                    # Mark as unsafe if critical or high severity
                    if rule["severity"] in ["critical", "high"]:
                        result["is_safe"] = False

                    break

        # Normalize risk score
        result["risk_score"] = min(1.0, result["risk_score"])
        result["confidence"] = max(0.1, 1.0 - result["risk_score"])

        # Enhanced age appropriateness check
        age_inappropriate_content = self._check_age_appropriateness(
            content_lower, child_age
        )
        if age_inappropriate_content:
            result["age_appropriate"] = False
            result["issues"].extend(age_inappropriate_content)
            if any(
                issue["severity"] in ["high", "critical"]
                for issue in age_inappropriate_content
            ):
                result["is_safe"] = False
                result["risk_score"] += 0.3

        # Cache result for performance
        self._safety_cache[content_hash] = (result, datetime.now())

        # Enhanced logging with security implications
        await self.log_safety_event(
            {
                "type": "content_validation",
                "content_length": len(content),
                "child_age": child_age,
                "result": result["is_safe"],
                "risk_score": result["risk_score"],
                "issues_count": len(result["issues"]),
                "pii_detected": result["pii_detected"],
                "requires_review": result["requires_human_review"],
                "timestamp": result["timestamp"],
                "triggered_rules": result["triggered_rules"],
            }
        )

        # Auto-trigger alerts for high-risk content
        if result["risk_score"] >= self.emergency_alert_threshold:
            await self._trigger_emergency_alert(content, child_age, result)
        elif result["risk_score"] >= self.parent_notification_threshold:
            await self._schedule_parent_notification(content, child_age, result)

        return result

    async def filter_content(self, content: str) -> str:
        """Filter inappropriate content.

        Args:
            content: Content to filter

        Returns:
            Filtered content
        """
        filtered = content

        # Replace inappropriate words using new pattern structure
        for severity, patterns in self.safety_patterns.items():
            for pattern in patterns:
                filtered = re.sub(pattern, "[filtered]", filtered, flags=re.IGNORECASE)

        # Remove URLs and email addresses
        filtered = re.sub(r"https?://\S+", "[link removed]", filtered)
        filtered = re.sub(r"\S+@\S+\.\S+", "[email removed]", filtered)

        # Remove phone numbers
        filtered = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[phone removed]", filtered)

        return filtered

    def _extract_match_context(
        self, content: str, pattern: str, context_chars: int = 20
    ) -> str:
        """Extract context around pattern match for logging."""
        try:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                start = max(0, match.start() - context_chars)
                end = min(len(content), match.end() + context_chars)
                context = content[start:end]
                return (
                    f"...{context}..." if start > 0 or end < len(content) else context
                )
        except Exception:
            pass
        return "match_context_unavailable"

    def _check_age_appropriateness(
        self, content_lower: str, child_age: int
    ) -> List[Dict[str, Any]]:
        """Enhanced age appropriateness checking with detailed rules."""
        issues = []

        age_rules = {
            (0, 5): {  # Toddlers/Preschool
                "forbidden": [
                    "scary",
                    "monster",
                    "nightmare",
                    "ghost",
                    "demon",
                    "blood",
                    "fight",
                ],
                "severity": "high",
                "reason": "Content may be too frightening for very young children",
            },
            (6, 8): {  # Early Elementary
                "forbidden": [
                    "violence",
                    "weapon",
                    "kill",
                    "death",
                    "drugs",
                    "alcohol",
                ],
                "severity": "high",
                "reason": "Content contains mature themes inappropriate for elementary age",
            },
            (9, 12): {  # Late Elementary
                "forbidden": ["sexual", "drug", "suicide", "self-harm"],
                "severity": "critical",
                "reason": "Content contains adult themes inappropriate for children",
            },
        }

        for age_range, rules in age_rules.items():
            if age_range[0] <= child_age <= age_range[1]:
                for forbidden_word in rules["forbidden"]:
                    if forbidden_word in content_lower:
                        issues.append(
                            {
                                "type": "age_inappropriate",
                                "severity": rules["severity"],
                                "reason": rules["reason"],
                                "age_range": f"{age_range[0]}-{age_range[1]}",
                                "forbidden_content": forbidden_word,
                                "child_age": child_age,
                            }
                        )

        return issues

    async def _trigger_emergency_alert(
        self, content: str, child_age: int, safety_result: Dict[str, Any]
    ) -> None:
        """Trigger emergency alert for critical safety violations."""
        try:
            async with database_manager.get_session() as db_session:
                # Create critical safety report
                report = SafetyReport(
                    report_type="emergency_alert",
                    severity="critical",
                    description=f"Emergency safety alert triggered: Risk score {safety_result['risk_score']:.2f}",
                    detected_by_ai=True,
                    ai_confidence=safety_result["confidence"],
                    detection_rules=safety_result["triggered_rules"],
                    content_blocked=True,
                    parent_notified=True,
                    notification_sent_at=datetime.utcnow(),
                )

                db_session.add(report)
                await db_session.commit()

                # Log security event
                security_logger.critical(
                    "Emergency safety alert triggered",
                    extra={
                        "child_age": child_age,
                        "risk_score": safety_result["risk_score"],
                        "triggered_rules": safety_result["triggered_rules"],
                        "pii_detected": safety_result["pii_detected"],
                        "content_hash": hashlib.sha256(content.encode()).hexdigest(),
                    },
                )

        except Exception as e:
            logger.error(f"Failed to trigger emergency alert: {e}")

    async def _schedule_parent_notification(
        self, content: str, child_age: int, safety_result: Dict[str, Any]
    ) -> None:
        """Schedule parent notification for concerning content."""
        try:
            async with database_manager.get_session() as db_session:
                # Create safety report for parent review
                report = SafetyReport(
                    report_type="parent_notification",
                    severity="high",
                    description=f"Content flagged for parent review: Risk score {safety_result['risk_score']:.2f}",
                    detected_by_ai=True,
                    ai_confidence=safety_result["confidence"],
                    detection_rules=safety_result["triggered_rules"],
                    parent_notified=False,  # Will be updated when notification sent
                )

                db_session.add(report)
                await db_session.commit()

                logger.warning(
                    f"Parent notification scheduled for safety concern: {safety_result['risk_score']:.2f}"
                )

        except Exception as e:
            logger.error(f"Failed to schedule parent notification: {e}")

    def sanitize_content(self, content: str) -> str:
        """Sanitize content by replacing inappropriate words with safe alternatives.

        Args:
            content: Content to sanitize

        Returns:
            Sanitized content with safe word replacements
        """
        replacements = {
            "stupid": "silly",
            "dumb": "funny",
            "hate": "don't like",
            "kill": "stop",
            "die": "sleep",
            "fight": "play",
            "scary": "interesting",
            "monster": "funny creature",
        }

        sanitized = content
        for bad_word, replacement in replacements.items():
            sanitized = re.sub(
                r"\b" + re.escape(bad_word) + r"\b",
                replacement,
                sanitized,
                flags=re.IGNORECASE,
            )

        return sanitized

    async def check_content_safety(
        self,
        content: str,
        child_age: int = 0,
        conversation_history: Optional[List[str]] = None,
    ) -> SafetyAnalysisResult:
        """Check content safety and return SafetyAnalysisResult for compatibility.

        Args:
            content: Content to analyze
            child_age: Age of the child
            conversation_history: Optional conversation history

        Returns:
            SafetyAnalysisResult for backward compatibility
        """
        validation_result = await self.validate_content(content, child_age)

        # Convert to SafetyAnalysisResult format
        risk_level = RiskLevel.SAFE
        if not validation_result["is_safe"]:
            # Determine risk level based on issues
            high_severity_issues = [
                i for i in validation_result["issues"] if i.get("severity") == "high"
            ]
            if high_severity_issues:
                risk_level = RiskLevel.HIGH
            else:
                risk_level = RiskLevel.MEDIUM

        return SafetyAnalysisResult(
            is_safe=validation_result["is_safe"],
            risk_level=risk_level,
            issues=[i.get("type", "unknown") for i in validation_result["issues"]],
            reason="; ".join(
                [
                    i.get("reason", i.get("type", "unknown"))
                    for i in validation_result["issues"]
                ]
            )
            or "Content is safe",
        )

    def analyze_content(self, content: str, child_age: int) -> SafetyResult:
        """Analyze content safety and return SafetyResult for compatibility.

        Args:
            content: Content to analyze
            child_age: Age of the child

        Returns:
            SafetyResult for backward compatibility
        """
        content_lower = content.lower()
        violations = []
        is_safe = True
        safety_score = 1.0

        # Check inappropriate patterns using new structure
        for severity, patterns in self.safety_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    violations.append(f"{severity}_pattern: {pattern}")
                    is_safe = False
                    # More severe penalties for higher risk content
                    penalty = {
                        "critical": 0.8,
                        "high": 0.6,
                        "medium": 0.4,
                        "low": 0.2,
                    }.get(severity, 0.5)
                    safety_score -= penalty

        # Check age appropriateness
        age_appropriate = True
        if child_age < 6 and any(
            word in content_lower for word in ["scary", "monster", "nightmare"]
        ):
            violations.append("age_inappropriate")
            age_appropriate = False
            safety_score -= 0.2

        return SafetyResult(
            is_safe=is_safe,
            safety_score=max(0.0, safety_score),
            violations=violations,
            age_appropriate=age_appropriate,
        )

    async def create_safety_report(
        self,
        child_id: Optional[UUID] = None,
        conversation_id: Optional[UUID] = None,
        message_id: Optional[UUID] = None,
        report_type: str = "content_violation",
        severity: str = "medium",
        description: str = "",
        ai_confidence: float = 0.8,
        detection_rules: List[str] = None,
        content_blocked: bool = False,
        **kwargs,
    ) -> Optional[UUID]:
        """Create comprehensive safety report in database."""
        try:
            async with database_manager.get_session() as db_session:
                report = SafetyReport(
                    child_id=child_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    report_type=report_type,
                    severity=severity,
                    description=description,
                    detected_by_ai=True,
                    ai_confidence=ai_confidence,
                    detection_rules=detection_rules or [],
                    content_blocked=content_blocked,
                    reviewed=False,
                    resolved=False,
                    **kwargs,
                )

                db_session.add(report)
                await db_session.commit()
                await db_session.refresh(report)

                # Create audit log entry
                audit_log = AuditLog(
                    action="safety_report_created",
                    resource_type="safety_report",
                    resource_id=report.id,
                    description=f"Safety report created: {report_type} ({severity})",
                    involves_child_data=child_id is not None,
                    child_id_hash=(
                        hashlib.sha256(str(child_id).encode()).hexdigest()
                        if child_id
                        else None
                    ),
                    severity="warning" if severity in ["high", "critical"] else "info",
                )

                db_session.add(audit_log)
                await db_session.commit()

                logger.info(f"Safety report created: {report.id}")
                return report.id

        except Exception as e:
            logger.error(f"Failed to create safety report: {e}")
            return None

    async def get_safety_reports_for_child(
        self,
        child_id: UUID,
        limit: int = 50,
        resolved_only: bool = False,
        severity_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get safety reports for specific child."""
        try:
            async with database_manager.get_session() as db_session:
                query = select(SafetyReport).where(
                    and_(
                        SafetyReport.child_id == child_id,
                        SafetyReport.is_deleted == False,
                    )
                )

                if resolved_only:
                    query = query.where(SafetyReport.resolved == True)

                if severity_filter:
                    query = query.where(SafetyReport.severity == severity_filter)

                query = query.order_by(desc(SafetyReport.created_at)).limit(limit)

                result = await db_session.execute(query)
                reports = result.scalars().all()

                return [report.to_dict() for report in reports]

        except Exception as e:
            logger.error(f"Failed to get safety reports for child {child_id}: {e}")
            return []

    async def resolve_safety_report(
        self, report_id: UUID, resolved_by: UUID, resolution_notes: str = ""
    ) -> bool:
        """Mark safety report as resolved."""
        try:
            async with database_manager.get_session() as db_session:
                report = await db_session.get(SafetyReport, report_id)
                if not report:
                    return False

                report.resolved = True
                report.resolved_at = datetime.utcnow()
                report.resolution_notes = resolution_notes
                report.reviewed = True
                report.reviewed_by = resolved_by
                report.reviewed_at = datetime.utcnow()

                await db_session.commit()

                # Log resolution
                logger.info(f"Safety report {report_id} resolved by {resolved_by}")
                return True

        except Exception as e:
            logger.error(f"Failed to resolve safety report {report_id}: {e}")
            return False

    async def get_child_safety_metrics(self, child_id: UUID) -> Dict[str, Any]:
        """Get comprehensive safety metrics for child."""
        try:
            async with database_manager.get_session() as db_session:
                # Count reports by severity
                severity_counts = await db_session.execute(
                    select(
                        SafetyReport.severity,
                        func.count(SafetyReport.id).label("count"),
                    )
                    .where(
                        and_(
                            SafetyReport.child_id == child_id,
                            SafetyReport.is_deleted == False,
                        )
                    )
                    .group_by(SafetyReport.severity)
                )

                severity_data = {row.severity: row.count for row in severity_counts}

                # Count recent reports (last 30 days)
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                recent_reports = await db_session.execute(
                    select(func.count(SafetyReport.id)).where(
                        and_(
                            SafetyReport.child_id == child_id,
                            SafetyReport.created_at >= thirty_days_ago,
                            SafetyReport.is_deleted == False,
                        )
                    )
                )

                # Calculate safety score
                total_reports = sum(severity_data.values())
                critical_reports = severity_data.get("critical", 0)
                high_reports = severity_data.get("high", 0)

                # Safety score: 100 - penalties
                safety_score = 100.0
                safety_score -= critical_reports * 25  # 25 points per critical
                safety_score -= high_reports * 10  # 10 points per high
                safety_score -= (
                    severity_data.get("medium", 0) * 5
                )  # 5 points per medium
                safety_score = max(0.0, safety_score)

                return {
                    "child_id": str(child_id),
                    "safety_score": safety_score,
                    "total_reports": total_reports,
                    "recent_reports_30d": recent_reports.scalar(),
                    "severity_breakdown": severity_data,
                    "risk_level": (
                        "critical"
                        if safety_score < 50
                        else (
                            "high"
                            if safety_score < 70
                            else "medium" if safety_score < 85 else "low"
                        )
                    ),
                    "last_updated": datetime.utcnow().isoformat(),
                }

        except Exception as e:
            logger.error(f"Failed to get safety metrics for child {child_id}: {e}")
            return {"child_id": str(child_id), "safety_score": 0.0, "error": str(e)}

    async def log_safety_event(self, event: Dict[str, Any]) -> bool:
        """Log safety-related event.

        Args:
            event: Event dictionary to log

        Returns:
            True if logged successfully
        """
        try:
            event["logged_at"] = datetime.now().isoformat()
            self.safety_events.append(event)

            # Log to logger as well
            logger.info(f"Safety event: {event.get('type', 'unknown')}", extra=event)

            # Trim events list if too large
            if len(self.safety_events) > 1000:
                self.safety_events = self.safety_events[-500:]

            return True
        except Exception as e:
            logger.error(f"Failed to log safety event: {e}")
            return False

    async def get_safety_recommendations(self, child_id: str) -> List[Dict[str, Any]]:
        """Get safety recommendations for child.

        Args:
            child_id: ID of the child

        Returns:
            List of safety recommendations
        """
        recommendations = [
            {
                "id": "rec_001",
                "type": "general",
                "title": "Monitor Screen Time",
                "description": "Ensure balanced screen time with physical activities",
                "priority": "medium",
            },
            {
                "id": "rec_002",
                "type": "content",
                "title": "Age-Appropriate Content",
                "description": "Verify all content is suitable for child's age group",
                "priority": "high",
            },
            {
                "id": "rec_003",
                "type": "privacy",
                "title": "Personal Information",
                "description": "Teach child not to share personal information",
                "priority": "high",
            },
        ]

        # Add specific recommendations based on recent events
        recent_events = [e for e in self.safety_events if e.get("child_id") == child_id]
        if any(e.get("type") == "inappropriate_content" for e in recent_events):
            recommendations.append(
                {
                    "id": "rec_004",
                    "type": "alert",
                    "title": "Content Concerns",
                    "description": "Recent inappropriate content detected - review settings",
                    "priority": "critical",
                }
            )

        return recommendations

    async def verify_parental_consent(self, child_id: str) -> bool:
        """Verify parental consent status.

        Args:
            child_id: ID of the child

        Returns:
            True if parental consent is verified, False otherwise
        """
        # For now, return True as default implementation
        # In production, this should check against a consent database
        logger.info(f"Verifying parental consent for child {child_id}")

        # Basic implementation - should be enhanced with actual consent verification
        return True

    async def check_message_safety(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Check if a message is safe for children.

        Args:
            message: Message to check
            context: Optional context information

        Returns:
            Safety check results
        """
        child_age = context.get("child_age", 8) if context else 8
        return await self.validate_content(message, child_age)

    async def get_filtered_response(self, response: str, child_id: str) -> str:
        """Get filtered version of AI response.

        Args:
            response: Original response
            child_id: ID of the child

        Returns:
            Filtered response safe for children
        """
        filtered = await self.filter_content(response)

        # Log filtering event
        if filtered != response:
            await self.log_safety_event(
                {
                    "type": "content_filtered",
                    "child_id": child_id,
                    "original_length": len(response),
                    "filtered_length": len(filtered),
                }
            )

        return filtered

    # SafetyMonitor interface implementation
    async def analyze_content_safety(
        self,
        content: str,
        child_id: str,
        context: Optional[Dict[str, Any]] = None,
        monitoring_scope=None,
    ):
        """Implementation of ISafetyMonitor interface."""
        child_age = context.get("child_age", 8) if context else 8
        return await self.validate_content(content, child_age)

    async def detect_threats(
        self,
        content: str,
        child_age: int,
        conversation_history: Optional[List[str]] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ):
        """Implementation of ISafetyMonitor interface."""
        validation_result = await self.validate_content(content, child_age)
        threats = []
        for issue in validation_result["issues"]:
            threats.append(
                {
                    "type": issue.get("type", "unknown"),
                    "severity": issue.get("severity", "medium"),
                    "description": issue.get("reason", "Safety concern detected"),
                }
            )
        return threats

    async def assess_risk_level(
        self,
        threats,
        child_profile: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        """Implementation of ISafetyMonitor interface."""
        if not threats:
            return {
                "overall_risk": "SAFE",
                "risk_score": 0.0,
                "contributing_factors": [],
                "mitigation_suggestions": [],
                "confidence": 1.0,
            }

        high_severity = sum(1 for t in threats if t.get("severity") == "high")
        risk_score = min(1.0, len(threats) * 0.3 + high_severity * 0.4)

        return {
            "overall_risk": (
                "HIGH" if risk_score > 0.7 else "MEDIUM" if risk_score > 0.3 else "LOW"
            ),
            "risk_score": risk_score,
            "contributing_factors": [t.get("type", "unknown") for t in threats],
            "mitigation_suggestions": ["Review content", "Apply filters"],
            "confidence": 0.8,
        }

    async def recommend_safety_actions(
        self,
        analysis_report,
        child_settings: Dict[str, Any],
        parent_preferences: Optional[Dict[str, Any]] = None,
    ):
        """Implementation of ISafetyMonitor interface."""
        actions = []
        if not analysis_report.get("is_safe", True):
            actions.append(
                {
                    "action": "FILTER",
                    "priority": 1,
                    "reason": "Content contains inappropriate material",
                    "impact": "Content will be filtered or blocked",
                    "parameters": {"filter_level": "strict"},
                }
            )
        return actions

    async def monitor_conversation_real_time(
        self,
        conversation_id: UUID,
        child_id: UUID,
        message_content: str,
        child_age: int = 8,
    ) -> Dict[str, Any]:
        """Real-time safety monitoring for conversations with immediate response."""
        try:
            # Validate content
            safety_result = await self.validate_content(message_content, child_age)

            # Create interaction record for tracking
            if not safety_result["is_safe"] or safety_result["risk_score"] > 0.3:
                report_id = await self.create_safety_report(
                    child_id=child_id,
                    conversation_id=conversation_id,
                    report_type="real_time_monitoring",
                    severity="high" if safety_result["risk_score"] > 0.7 else "medium",
                    description=f"Real-time content flagged: {', '.join([issue['type'] for issue in safety_result['issues']])}",
                    ai_confidence=safety_result["confidence"],
                    detection_rules=safety_result["triggered_rules"],
                    content_blocked=not safety_result["is_safe"],
                )

                safety_result["report_id"] = str(report_id) if report_id else None

            # Add monitoring recommendations
            safety_result["monitoring_actions"] = []

            if safety_result["pii_detected"]:
                safety_result["monitoring_actions"].append(
                    {
                        "action": "BLOCK_CONVERSATION",
                        "reason": "Personal information detected",
                        "priority": "critical",
                    }
                )
            elif safety_result["risk_score"] >= self.emergency_alert_threshold:
                safety_result["monitoring_actions"].append(
                    {
                        "action": "EMERGENCY_ALERT",
                        "reason": "Critical safety violation",
                        "priority": "critical",
                    }
                )
            elif safety_result["risk_score"] >= self.parent_notification_threshold:
                safety_result["monitoring_actions"].append(
                    {
                        "action": "NOTIFY_PARENT",
                        "reason": "Safety concern detected",
                        "priority": "high",
                    }
                )

            # Send real-time notifications for concerning content
            await self._send_real_time_safety_notifications(
                child_id=child_id,
                conversation_id=conversation_id,
                safety_result=safety_result,
            )

            return safety_result

        except Exception as e:
            logger.error(
                f"Real-time monitoring failed for conversation {conversation_id}: {e}"
            )
            return {
                "is_safe": False,
                "error": str(e),
                "monitoring_actions": [
                    {
                        "action": "SYSTEM_ERROR",
                        "reason": "Safety monitoring system error",
                        "priority": "high",
                    }
                ],
            }

    async def get_safety_dashboard_data(self, parent_id: UUID) -> Dict[str, Any]:
        """Get comprehensive safety dashboard data for parent."""
        try:
            async with database_manager.get_session() as db_session:
                # Get all children for this parent
                children_query = (
                    select(Child)
                    .where(
                        and_(
                            Child.parent_id == parent_id,
                            Child.is_deleted == False,
                            Child.parental_consent == True,
                        )
                    )
                    .options(selectinload(Child.safety_reports))
                )

                result = await db_session.execute(children_query)
                children = result.scalars().all()

                dashboard_data = {
                    "parent_id": str(parent_id),
                    "children_count": len(children),
                    "overall_safety_score": 100.0,
                    "total_alerts": 0,
                    "unresolved_alerts": 0,
                    "children_safety": [],
                    "recent_alerts": [],
                    "generated_at": datetime.utcnow().isoformat(),
                }

                total_safety_score = 0
                total_alerts = 0
                unresolved_alerts = 0

                for child in children:
                    child_metrics = await self.get_child_safety_metrics(child.id)
                    child_safety = {
                        "child_id": str(child.id),
                        "child_name": child.name,
                        "safety_score": child_metrics["safety_score"],
                        "risk_level": child_metrics["risk_level"],
                        "total_reports": child_metrics["total_reports"],
                        "recent_reports": child_metrics["recent_reports_30d"],
                        "last_interaction": None,  # Would get from conversations
                    }

                    dashboard_data["children_safety"].append(child_safety)
                    total_safety_score += child_metrics["safety_score"]
                    total_alerts += child_metrics["total_reports"]

                    # Count unresolved alerts
                    unresolved_count = sum(
                        1
                        for report in child.safety_reports
                        if not report.resolved
                        and report.severity in ["high", "critical"]
                    )
                    unresolved_alerts += unresolved_count

                # Calculate overall metrics
                if children:
                    dashboard_data["overall_safety_score"] = total_safety_score / len(
                        children
                    )

                dashboard_data["total_alerts"] = total_alerts
                dashboard_data["unresolved_alerts"] = unresolved_alerts

                # Get recent alerts across all children
                recent_alerts_query = (
                    select(SafetyReport)
                    .join(Child)
                    .where(
                        and_(
                            Child.parent_id == parent_id,
                            SafetyReport.created_at
                            >= datetime.utcnow() - timedelta(days=7),
                            SafetyReport.is_deleted == False,
                        )
                    )
                    .order_by(desc(SafetyReport.created_at))
                    .limit(10)
                )

                alerts_result = await db_session.execute(recent_alerts_query)
                recent_alerts = alerts_result.scalars().all()

                dashboard_data["recent_alerts"] = [
                    {
                        "id": str(alert.id),
                        "child_id": str(alert.child_id),
                        "type": alert.report_type,
                        "severity": alert.severity,
                        "description": alert.description,
                        "created_at": alert.created_at.isoformat(),
                        "resolved": alert.resolved,
                    }
                    for alert in recent_alerts
                ]

                return dashboard_data

        except Exception as e:
            logger.error(
                f"Failed to get safety dashboard data for parent {parent_id}: {e}"
            )
            return {
                "parent_id": str(parent_id),
                "error": str(e),
                "generated_at": datetime.utcnow().isoformat(),
            }

    async def _send_real_time_safety_notifications(
        self, child_id: UUID, conversation_id: UUID, safety_result: Dict[str, Any]
    ) -> None:
        """Send real-time safety notifications based on monitoring results."""
        try:
            # Only send notifications for concerning content
            if (
                safety_result.get("is_safe", True)
                and safety_result.get("risk_score", 0) < 0.3
            ):
                return

            # Get parent ID from database
            async with database_manager.get_session() as db_session:
                child_query = (
                    select(Child)
                    .where(Child.id == child_id)
                    .options(selectinload(Child.parent))
                )
                result = await db_session.execute(child_query)
                child = result.scalar_one_or_none()

                if not child or not child.parent:
                    logger.warning(
                        f"No parent found for child {child_id} - skipping notification"
                    )
                    return

                parent_id = str(child.parent_id)
                child_id_str = str(child_id)

                # Import notification orchestrator
                from src.application.services.realtime.unified_notification_orchestrator import (
                    get_notification_orchestrator,
                )

                orchestrator = get_notification_orchestrator()

                # Determine notification type based on safety result
                if safety_result.get("pii_detected", False):
                    # Emergency alert for PII detection
                    emergency_data = {
                        "conversation_id": str(conversation_id),
                        "message": "Personal information detected in conversation - immediate action required",
                        "emergency_type": "pii_exposure",
                        "detected_issues": safety_result.get("detected_issues", []),
                        "immediate_actions": [
                            "Conversation blocked automatically",
                            "Review blocked content immediately",
                            "Discuss online privacy with your child",
                        ],
                        "alert_id": f"pii_{int(datetime.utcnow().timestamp())}",
                    }

                    await orchestrator.send_emergency_alert(
                        child_id=child_id_str,
                        parent_id=parent_id,
                        emergency_data=emergency_data,
                    )

                elif (
                    safety_result.get("risk_score", 0) >= self.emergency_alert_threshold
                ):
                    # Emergency alert for high-risk content
                    emergency_data = {
                        "conversation_id": str(conversation_id),
                        "message": f"Critical safety violation detected (Risk Score: {safety_result.get('risk_score', 0):.1%})",
                        "emergency_type": "safety_violation",
                        "detected_issues": safety_result.get("detected_issues", []),
                        "triggered_rules": safety_result.get("triggered_rules", []),
                        "immediate_actions": [
                            "Review conversation immediately",
                            "Check in with your child",
                            "Consider additional safety measures",
                        ],
                        "alert_id": f"emergency_{int(datetime.utcnow().timestamp())}",
                    }

                    await orchestrator.send_emergency_alert(
                        child_id=child_id_str,
                        parent_id=parent_id,
                        emergency_data=emergency_data,
                    )

                elif (
                    safety_result.get("risk_score", 0)
                    >= self.parent_notification_threshold
                ):
                    # Regular safety alert
                    await orchestrator.send_safety_alert(
                        child_id=child_id_str,
                        parent_id=parent_id,
                        safety_result={
                            "conversation_id": str(conversation_id),
                            "safety_score": (1 - safety_result.get("risk_score", 0))
                            * 100,
                            "event_type": "safety_concern",
                            "detected_issues": safety_result.get("detected_issues", []),
                            "triggered_rules": safety_result.get("triggered_rules", []),
                            "child_age": safety_result.get("child_age", 8),
                            "recommendations": [
                                "Review the conversation content",
                                "Discuss appropriate online behavior",
                                "Monitor future interactions closely",
                            ],
                        },
                    )

                # Log notification attempt
                logger.info(
                    f"Real-time safety notification sent for child {child_id}",
                    extra={
                        "child_id": child_id_str,
                        "parent_id": parent_id,
                        "conversation_id": str(conversation_id),
                        "risk_score": safety_result.get("risk_score", 0),
                        "pii_detected": safety_result.get("pii_detected", False),
                        "notification_type": (
                            "emergency"
                            if safety_result.get("risk_score", 0)
                            >= self.emergency_alert_threshold
                            else "safety_alert"
                        ),
                    },
                )

        except Exception as e:
            logger.error(
                f"Failed to send real-time safety notification: {e}", exc_info=True
            )


# Maintain backward compatibility
ConsolidatedChildSafetyService = ChildSafetyService
