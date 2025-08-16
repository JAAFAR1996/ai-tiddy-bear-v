"""
🧸 AI TEDDY BEAR V5 - CHILD SAFETY ALERT SYSTEM
===============================================
Specialized alerting system for child safety incidents and COPPA compliance
with real-time monitoring, parental notifications, and regulatory reporting.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
import hashlib
from uuid import uuid4

try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .enhanced_alerting import AlertManager, Alert, AlertSeverity, AlertCategory, alert_manager


class ChildSafetyViolationType(Enum):
    """Types of child safety violations."""
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    PERSONAL_INFO_REQUEST = "personal_info_request"
    CONTACT_INFO_SOLICITATION = "contact_info_solicitation"
    MEETING_ARRANGEMENT = "meeting_arrangement"
    GIFT_OFFERING = "gift_offering"
    SECRET_KEEPING = "secret_keeping"
    BULLYING_HARASSMENT = "bullying_harassment"
    VIOLENCE_THREAT = "violence_threat"
    SELF_HARM_CONTENT = "self_harm_content"
    STRANGER_DANGER = "stranger_danger"
    PREDATORY_BEHAVIOR = "predatory_behavior"
    GROOMING_ATTEMPT = "grooming_attempt"
    UNSAFE_CHALLENGE = "unsafe_challenge"
    LOCATION_SHARING = "location_sharing"
    PHOTO_REQUEST = "photo_request"
    TECHNICAL_FAILURE = "technical_failure"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    ACCOUNT_FLAGGED = "account_flagged"
    DATA_PRIVACY_VIOLATION = "data_privacy_violation"
    UNAUTHORIZED_DATA_ACCESS = "unauthorized_data_access"
    SELF_HARM = "self_harm"
    UNSAFE_INTERACTION = "unsafe_interaction"


class COPPAViolationType(Enum):
    """Types of COPPA compliance violations."""
    UNAUTHORIZED_DATA_COLLECTION = "unauthorized_data_collection"
    INSUFFICIENT_PARENTAL_CONSENT = "insufficient_parental_consent"
    DATA_RETENTION_VIOLATION = "data_retention_violation"
    THIRD_PARTY_DISCLOSURE = "third_party_disclosure"
    INADEQUATE_DATA_SECURITY = "inadequate_data_security"
    MISSING_PRIVACY_NOTICE = "missing_privacy_notice"
    DIRECT_MARKETING_TO_CHILD = "direct_marketing_to_child"
    BEHAVIORAL_ADVERTISING = "behavioral_advertising"
    GEOLOCATION_TRACKING = "geolocation_tracking"
    VOICE_RECORDING_WITHOUT_CONSENT = "voice_recording_without_consent"
    BIOMETRIC_DATA_COLLECTION = "biometric_data_collection"
    EDUCATIONAL_RECORDS_ACCESS = "educational_records_access"
    MISSING_PARENTAL_CONSENT = "missing_parental_consent"
    UNAUTHORIZED_DATA_DISCLOSURE = "unauthorized_data_disclosure"


class SafetyAlertPriority(Enum):
    """Priority levels for safety alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"  # Ensure this exists
    EMERGENCY = "emergency"


@dataclass
class ChildSafetyIncident:
    """Child safety incident data structure."""
    incident_id: str
    timestamp: str
    violation_type: ChildSafetyViolationType
    priority: SafetyAlertPriority
    child_id: str  # Hashed/anonymized
    child_age: Optional[int]
    parent_id: Optional[str]  # Hashed/anonymized
    session_id: str
    conversation_id: Optional[str]
    content_summary: str  # Sanitized summary
    ai_confidence_score: float
    human_review_required: bool
    auto_action_taken: Optional[str]
    context: Dict[str, Any]
    location: Optional[str]  # Country/region only
    device_type: Optional[str]
    reported_by: str  # System component that detected
    resolved: bool = False
    resolved_at: Optional[str] = None
    resolution_action: Optional[str] = None
    parent_notified: bool = False
    authorities_notified: bool = False
    regulatory_reported: bool = False


@dataclass
class COPPAComplianceIncident:
    """COPPA compliance incident data structure."""
    incident_id: str
    timestamp: str
    violation_type: COPPAViolationType
    priority: SafetyAlertPriority
    child_id: Optional[str]  # Hashed/anonymized
    parent_id: Optional[str]  # Hashed/anonymized
    data_type: str
    data_amount: str
    collection_method: str
    consent_status: str
    retention_period: Optional[str]
    third_party_involved: bool
    regulatory_framework: str = "COPPA"
    compliance_officer_notified: bool = False
    legal_team_notified: bool = False
    remediation_required: bool = True
    remediation_deadline: Optional[str] = None
    context: Dict[str, Any] = None


class ChildSafetyMonitor:
    """Real-time child safety monitoring and alerting system."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.alert_manager = alert_manager
        
        # Incident storage
        self.active_incidents: Dict[str, ChildSafetyIncident] = {}
        self.coppa_incidents: Dict[str, COPPAComplianceIncident] = {}
        
        # History tracking for compliance
        self.incident_history: List[Dict[str, Any]] = []
        self.compliance_incidents: List[Dict[str, Any]] = []
        
        # Configuration
        self.config = {
            "alert_threshold": 0.85,
            "notification_enabled": True,
            "emergency_contacts": True,
            "compliance_reporting": True
        }
        
        # Content pattern detection
        self.violation_patterns = self._load_violation_patterns()
        self.ml_model_confidence_threshold = 0.85
        
        # Notification channels
        self.emergency_contacts = self._load_emergency_contacts()
        self.regulatory_contacts = self._load_regulatory_contacts()
        
        # Rate limiting for parental notifications
        self.parent_notification_cooldown = 300  # 5 minutes
        self.last_parent_notifications: Dict[str, float] = {}
        
        # Compliance tracking
        self.coppa_violation_thresholds = {
            COPPAViolationType.UNAUTHORIZED_DATA_COLLECTION: 1,
            COPPAViolationType.INSUFFICIENT_PARENTAL_CONSENT: 3,
            COPPAViolationType.DATA_RETENTION_VIOLATION: 5,
            COPPAViolationType.THIRD_PARTY_DISCLOSURE: 1,
        }
        
        # Start background monitoring
        asyncio.create_task(self._start_monitoring_tasks())
    
    def _load_violation_patterns(self) -> Dict[str, List[str]]:
        """Load violation detection patterns."""
        return {
            "personal_info_requests": [
                "what's your real name",
                "where do you live",
                "what school do you go to",
                "what's your address",
                "what's your phone number",
                "send me a picture of yourself",
                "can you meet me",
                "don't tell your parents"
            ],
            "inappropriate_content": [
                "violent content indicators",
                "adult content indicators",
                "harmful challenge references"
            ],
            "grooming_indicators": [
                "special secret",
                "our secret",
                "don't tell anyone",
                "meet in person",
                "I'll give you",
                "want to be friends"
            ]
        }
    
    def _load_emergency_contacts(self) -> Dict[str, Any]:
        """Load emergency contact information."""
        return {
            "child_safety_team": {
                "email": os.getenv("CHILD_SAFETY_TEAM_EMAIL", "safety@aiteddybear.com"),
                "phone": os.getenv("CHILD_SAFETY_TEAM_PHONE", "+1-800-SAFETY"),
                "slack": os.getenv("CHILD_SAFETY_SLACK_CHANNEL", "#child-safety-alerts")
            },
            "compliance_team": {
                "email": os.getenv("COMPLIANCE_TEAM_EMAIL", "compliance@aiteddybear.com"),
                "phone": os.getenv("COMPLIANCE_TEAM_PHONE", "+1-800-COMPLY")
            },
            "legal_team": {
                "email": os.getenv("LEGAL_TEAM_EMAIL", "legal@aiteddybear.com"),
                "phone": os.getenv("LEGAL_TEAM_PHONE", "+1-800-LEGAL")
            }
        }
    
    def _load_regulatory_contacts(self) -> Dict[str, Any]:
        """Load regulatory reporting contacts."""
        return {
            "ftc": {
                "name": "Federal Trade Commission",
                "email": "coppa@ftc.gov",
                "reporting_url": "https://www.ftc.gov/enforcement/report-violation",
                "phone": "+1-877-382-4357"
            },
            "ncmec": {
                "name": "National Center for Missing & Exploited Children",
                "reporting_url": "https://www.missingkids.org/gethelpnow/cybertipline",
                "phone": "+1-800-843-5678"
            }
        }
    
    async def _start_monitoring_tasks(self):
        """Start background monitoring tasks."""
        # Start incident escalation monitoring
        asyncio.create_task(self._monitor_incident_escalation())
        
        # Start compliance deadline monitoring
        asyncio.create_task(self._monitor_compliance_deadlines())
        
        # Start automated reporting task
        asyncio.create_task(self._automated_reporting_task())
    
    async def report_safety_incident(
        self,
        violation_type: ChildSafetyViolationType,
        child_id: str,
        session_id: str,
        content_summary: str,
        ai_confidence_score: float = 0.0,
        child_age: Optional[int] = None,
        parent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        auto_action_taken: Optional[str] = None
    ) -> ChildSafetyIncident:
        """Report a child safety incident."""
        
        # Determine priority based on violation type and confidence
        priority = self._calculate_incident_priority(violation_type, ai_confidence_score, child_age)
        
        # Create incident
        incident = ChildSafetyIncident(
            incident_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            violation_type=violation_type,
            priority=priority,
            child_id=self._hash_id(child_id),
            child_age=child_age,
            parent_id=self._hash_id(parent_id) if parent_id else None,
            session_id=session_id,
            conversation_id=conversation_id,
            content_summary=self._sanitize_content(content_summary),
            ai_confidence_score=ai_confidence_score,
            human_review_required=ai_confidence_score < self.ml_model_confidence_threshold or priority.value in ["urgent", "emergency"],
            auto_action_taken=auto_action_taken,
            context=context or {},
            location=context.get("country") if context else None,
            device_type=context.get("device_type") if context else None,
            reported_by=context.get("reporter", "ai_content_filter") if context else "ai_content_filter"
        )
        
        # Store incident
        self.active_incidents[incident.incident_id] = incident
        
        # Log incident
        self.logger.critical(
            f"Child safety incident reported: {violation_type.value}",
            extra={
                "incident_id": incident.incident_id,
                "violation_type": violation_type.value,
                "priority": priority.value,
                "child_id_hash": incident.child_id,
                "ai_confidence": ai_confidence_score,
                "human_review_required": incident.human_review_required
            }
        )
        
        # Create alert
        await self._create_safety_alert(incident)
        
        # Take immediate actions based on priority
        await self._take_immediate_actions(incident)
        
        # Send to Sentry for critical incidents
        if SENTRY_AVAILABLE and priority.value in ["urgent", "emergency"]:
            with sentry_sdk.push_scope() as scope:
                scope.set_tag("incident_type", "child_safety")
                scope.set_tag("violation_type", violation_type.value)
                scope.set_tag("priority", priority.value)
                scope.set_context("incident", {
                    "incident_id": incident.incident_id,
                    "ai_confidence": ai_confidence_score,
                    "child_age": child_age,
                    "session_id": session_id
                })
                
                sentry_sdk.capture_message(
                    f"Child Safety Emergency: {violation_type.value}",
                    level="fatal" if priority == SafetyAlertPriority.EMERGENCY else "error"
                )
        
        return incident
    
    async def report_coppa_violation(
        self,
        violation_type: COPPAViolationType,
        data_type: str,
        collection_method: str,
        consent_status: str,
        child_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        data_amount: str = "unknown",
        retention_period: Optional[str] = None,
        third_party_involved: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> COPPAComplianceIncident:
        """Report a COPPA compliance violation."""
        
        # Determine priority
        priority = self._calculate_coppa_priority(violation_type, third_party_involved)
        
        # Create incident
        incident = COPPAComplianceIncident(
            incident_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            violation_type=violation_type,
            priority=priority,
            child_id=self._hash_id(child_id) if child_id else None,
            parent_id=self._hash_id(parent_id) if parent_id else None,
            data_type=data_type,
            data_amount=data_amount,
            collection_method=collection_method,
            consent_status=consent_status,
            retention_period=retention_period,
            third_party_involved=third_party_involved,
            context=context or {}
        )
        
        # Set remediation deadline (24-72 hours based on severity)
        hours_to_deadline = 24 if priority.value in ["urgent", "emergency"] else 72
        deadline = datetime.now(timezone.utc) + timedelta(hours=hours_to_deadline)
        incident.remediation_deadline = deadline.isoformat()
        
        # Store incident
        self.coppa_incidents[incident.incident_id] = incident
        
        # Log incident
        self.logger.critical(
            f"COPPA violation reported: {violation_type.value}",
            extra={
                "incident_id": incident.incident_id,
                "violation_type": violation_type.value,
                "priority": priority.value,
                "data_type": data_type,
                "consent_status": consent_status
            }
        )
        
        # Create alert
        await self._create_coppa_alert(incident)
        
        # Notify compliance team immediately for high-priority violations
        if priority.value in ["urgent", "emergency"]:
            await self._notify_compliance_team(incident)
        
        return incident
    
    def _calculate_incident_priority(
        self, 
        violation_type: ChildSafetyViolationType, 
        ai_confidence: float, 
        child_age: Optional[int]
    ) -> SafetyAlertPriority:
        """Calculate incident priority based on multiple factors."""
        
        # Base priority by violation type
        high_risk_violations = {
            ChildSafetyViolationType.PREDATORY_BEHAVIOR,
            ChildSafetyViolationType.GROOMING_ATTEMPT,
            ChildSafetyViolationType.MEETING_ARRANGEMENT,
            ChildSafetyViolationType.CONTACT_INFO_SOLICITATION,
            ChildSafetyViolationType.PHOTO_REQUEST
        }
        
        emergency_violations = {
            ChildSafetyViolationType.VIOLENCE_THREAT,
            ChildSafetyViolationType.SELF_HARM_CONTENT
        }
        
        if violation_type in emergency_violations:
            return SafetyAlertPriority.EMERGENCY
        
        if violation_type in high_risk_violations:
            base_priority = SafetyAlertPriority.URGENT
        else:
            base_priority = SafetyAlertPriority.HIGH
        
        # Adjust for AI confidence
        if ai_confidence < 0.5:
            # Lower confidence, reduce priority
            if base_priority == SafetyAlertPriority.URGENT:
                base_priority = SafetyAlertPriority.HIGH
            elif base_priority == SafetyAlertPriority.HIGH:
                base_priority = SafetyAlertPriority.MEDIUM
        
        # Adjust for child age (younger children = higher priority)
        if child_age and child_age < 8:
            if base_priority == SafetyAlertPriority.HIGH:
                base_priority = SafetyAlertPriority.URGENT
            elif base_priority == SafetyAlertPriority.MEDIUM:
                base_priority = SafetyAlertPriority.HIGH
        
        return base_priority
    
    def _calculate_coppa_priority(
        self, 
        violation_type: COPPAViolationType, 
        third_party_involved: bool
    ) -> SafetyAlertPriority:
        """Calculate COPPA violation priority."""
        
        critical_violations = {
            COPPAViolationType.UNAUTHORIZED_DATA_COLLECTION,
            COPPAViolationType.THIRD_PARTY_DISCLOSURE,
            COPPAViolationType.INADEQUATE_DATA_SECURITY
        }
        
        high_priority_violations = {
            COPPAViolationType.INSUFFICIENT_PARENTAL_CONSENT,
            COPPAViolationType.DATA_RETENTION_VIOLATION,
            COPPAViolationType.BIOMETRIC_DATA_COLLECTION
        }
        
        if violation_type in critical_violations:
            base_priority = SafetyAlertPriority.URGENT
        elif violation_type in high_priority_violations:
            base_priority = SafetyAlertPriority.HIGH
        else:
            base_priority = SafetyAlertPriority.MEDIUM
        
        # Third-party involvement increases priority
        if third_party_involved and base_priority != SafetyAlertPriority.URGENT:
            if base_priority == SafetyAlertPriority.HIGH:
                base_priority = SafetyAlertPriority.URGENT
            elif base_priority == SafetyAlertPriority.MEDIUM:
                base_priority = SafetyAlertPriority.HIGH
        
        return base_priority
    
    async def _create_safety_alert(self, incident: ChildSafetyIncident):
        """Create an alert for a child safety incident."""
        severity = AlertSeverity.CHILD_SAFETY_CRITICAL if incident.priority.value in ["urgent", "emergency"] else AlertSeverity.CRITICAL
        
        await self.alert_manager.create_alert(
            severity=severity,
            category=AlertCategory.CHILD_SAFETY,
            title=f"Child Safety Incident: {incident.violation_type.value.replace('_', ' ').title()}",
            message=f"Priority: {incident.priority.value.upper()} | Confidence: {incident.ai_confidence_score:.2f} | Summary: {incident.content_summary}",
            source="child_safety_monitor",
            correlation_id=incident.session_id,
            child_id=incident.child_id,
            parent_id=incident.parent_id,
            session_id=incident.session_id,
            metadata={
                "incident_id": incident.incident_id,
                "violation_type": incident.violation_type.value,
                "priority": incident.priority.value,
                "ai_confidence_score": incident.ai_confidence_score,
                "human_review_required": incident.human_review_required,
                "child_age": incident.child_age,
                "auto_action_taken": incident.auto_action_taken,
                "context": incident.context
            },
            tags=["child_safety", incident.violation_type.value, incident.priority.value]
        )
    
    async def _create_coppa_alert(self, incident: COPPAComplianceIncident):
        """Create an alert for a COPPA compliance incident."""
        severity = AlertSeverity.CRITICAL if incident.priority.value in ["urgent", "emergency"] else AlertSeverity.HIGH
        
        await self.alert_manager.create_alert(
            severity=severity,
            category=AlertCategory.COPPA_COMPLIANCE,
            title=f"COPPA Violation: {incident.violation_type.value.replace('_', ' ').title()}",
            message=f"Priority: {incident.priority.value.upper()} | Data Type: {incident.data_type} | Consent: {incident.consent_status}",
            source="coppa_monitor",
            child_id=incident.child_id,
            parent_id=incident.parent_id,
            metadata={
                "incident_id": incident.incident_id,
                "violation_type": incident.violation_type.value,
                "priority": incident.priority.value,
                "data_type": incident.data_type,
                "data_amount": incident.data_amount,
                "collection_method": incident.collection_method,
                "consent_status": incident.consent_status,
                "third_party_involved": incident.third_party_involved,
                "remediation_deadline": incident.remediation_deadline,
                "context": incident.context
            },
            tags=["coppa", "compliance", incident.violation_type.value, incident.priority.value]
        )
    
    async def _take_immediate_actions(self, incident: ChildSafetyIncident):
        """Take immediate actions based on incident priority."""
        
        actions_taken = []
        
        # Emergency actions
        if incident.priority == SafetyAlertPriority.EMERGENCY:
            # Immediately terminate session
            await self._terminate_session(incident.session_id)
            actions_taken.append("session_terminated")
            
            # Notify emergency contacts immediately
            await self._notify_emergency_contacts(incident)
            actions_taken.append("emergency_contacts_notified")
            
            # Flag account for immediate review
            await self._flag_account_for_review(incident.child_id, "emergency")
            actions_taken.append("account_flagged_emergency")
        
        # Urgent actions
        elif incident.priority == SafetyAlertPriority.URGENT:
            # Pause session and require human intervention
            await self._pause_session(incident.session_id)
            actions_taken.append("session_paused")
            
            # Notify child safety team
            await self._notify_child_safety_team(incident)
            actions_taken.append("safety_team_notified")
            
            # Flag account for urgent review
            await self._flag_account_for_review(incident.child_id, "urgent")
            actions_taken.append("account_flagged_urgent")
        
        # High priority actions
        elif incident.priority == SafetyAlertPriority.HIGH:
            # Add conversation monitoring
            await self._enable_enhanced_monitoring(incident.session_id)
            actions_taken.append("enhanced_monitoring_enabled")
            
            # Queue for human review
            await self._queue_for_human_review(incident)
            actions_taken.append("queued_for_review")
        
        # Notify parents (with rate limiting)
        if incident.parent_id and self._should_notify_parent(incident.parent_id):
            await self._notify_parent(incident)
            actions_taken.append("parent_notified")
            incident.parent_notified = True
        
        # Update incident with actions taken
        incident.auto_action_taken = ", ".join(actions_taken)
        
        self.logger.info(
            f"Immediate actions taken for incident {incident.incident_id}",
            extra={
                "incident_id": incident.incident_id,
                "actions": actions_taken,
                "priority": incident.priority.value
            }
        )
    
    async def _notify_compliance_team(self, incident: COPPAComplianceIncident):
        """Notify compliance team of COPPA violation."""
        contacts = self.emergency_contacts["compliance_team"]
        
        # Send email notification
        if REQUESTS_AVAILABLE and contacts.get("email"):
            await self._send_compliance_email(incident, contacts["email"])
        
        # Send Slack notification if configured
        slack_webhook = os.getenv("COMPLIANCE_SLACK_WEBHOOK")
        if REQUESTS_AVAILABLE and slack_webhook:
            await self._send_compliance_slack_notification(incident, slack_webhook)
        
        incident.compliance_officer_notified = True
        
        self.logger.info(
            f"Compliance team notified for incident {incident.incident_id}",
            extra={"incident_id": incident.incident_id, "violation_type": incident.violation_type.value}
        )
    
    async def _monitor_incident_escalation(self):
        """Monitor incidents for escalation requirements."""
        while True:
            try:
                current_time = datetime.now(timezone.utc)
                
                for incident in list(self.active_incidents.values()):
                    if incident.resolved:
                        continue
                    
                    incident_time = datetime.fromisoformat(incident.timestamp.replace('Z', '+00:00'))
                    time_elapsed = (current_time - incident_time).total_seconds() / 60  # minutes
                    
                    # Escalate based on time and priority
                    should_escalate = False
                    escalation_reason = ""
                    
                    if incident.priority == SafetyAlertPriority.EMERGENCY and time_elapsed > 5:
                        should_escalate = True
                        escalation_reason = "Emergency incident unresolved for 5+ minutes"
                    elif incident.priority == SafetyAlertPriority.URGENT and time_elapsed > 15:
                        should_escalate = True
                        escalation_reason = "Urgent incident unresolved for 15+ minutes"
                    elif incident.priority == SafetyAlertPriority.HIGH and time_elapsed > 60:
                        should_escalate = True
                        escalation_reason = "High priority incident unresolved for 1+ hour"
                    
                    if should_escalate:
                        await self._escalate_incident(incident, escalation_reason)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"Error in incident escalation monitoring: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_compliance_deadlines(self):
        """Monitor COPPA compliance deadlines."""
        while True:
            try:
                current_time = datetime.now(timezone.utc)
                
                for incident in list(self.coppa_incidents.values()):
                    if not incident.remediation_deadline:
                        continue
                    
                    deadline = datetime.fromisoformat(incident.remediation_deadline.replace('Z', '+00:00'))
                    time_to_deadline = (deadline - current_time).total_seconds() / 3600  # hours
                    
                    # Send warnings at 24h, 12h, 6h, and 1h before deadline
                    if time_to_deadline <= 1 and not incident.legal_team_notified:
                        await self._notify_legal_team_deadline(incident, "1 hour")
                        incident.legal_team_notified = True
                    elif time_to_deadline <= 6:
                        await self._send_deadline_warning(incident, f"{int(time_to_deadline)} hours")
                    elif time_to_deadline <= 0:
                        await self._handle_deadline_breach(incident)
                
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                self.logger.error(f"Error in compliance deadline monitoring: {e}")
                await asyncio.sleep(3600)
    
    async def _automated_reporting_task(self):
        """Generate automated reports for regulatory bodies."""
        while True:
            try:
                # Generate daily child safety report
                await self._generate_daily_safety_report()
                
                # Generate weekly COPPA compliance report
                if datetime.now().weekday() == 0:  # Monday
                    await self._generate_weekly_coppa_report()
                
                # Sleep until next day
                await asyncio.sleep(86400)  # 24 hours
                
            except Exception as e:
                self.logger.error(f"Error in automated reporting: {e}")
                await asyncio.sleep(86400)
    
    def _hash_id(self, user_id: str) -> str:
        """Create a hashed version of user ID for privacy."""
        if not user_id:
            return None
        salt = os.getenv("ID_HASH_SALT", "ai_teddy_bear_2024")
        return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:16]
    
    def _sanitize_content(self, content: str) -> str:
        """Sanitize content for logging while preserving context."""
        if not content:
            return ""
        
        # Keep only first 200 characters and remove potential PII
        sanitized = content[:200]
        
        # Replace potential names, numbers, etc.
        import re
        sanitized = re.sub(r'\b[A-Z][a-z]{2,}\b', '[NAME]', sanitized)  # Potential names
        sanitized = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', sanitized)  # Phone numbers
        sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', sanitized)  # Emails
        
        return sanitized + "..." if len(content) > 200 else sanitized
    
    def _should_notify_parent(self, parent_id: str) -> bool:
        """Check if parent should be notified (rate limiting)."""
        current_time = time.time()
        last_notification = self.last_parent_notifications.get(parent_id, 0)
        
        if current_time - last_notification < self.parent_notification_cooldown:
            return False
        
        self.last_parent_notifications[parent_id] = current_time
        return True
    
    # Placeholder methods for integration with other systems
    async def _terminate_session(self, session_id: str):
        """Terminate a user session immediately."""
        self.logger.critical(f"TERMINATING SESSION: {session_id}")
        
        try:
            # Import session manager
            from src.user_experience.session_management import SessionManager, SessionTerminationReason
            
            session_manager = SessionManager()
            
            # Force terminate the session with security violation reason
            result = await session_manager.terminate_session(
                session_id=session_id,
                reason=SessionTerminationReason.SECURITY_VIOLATION,
                terminated_by="child_safety_monitor"
            )
            
            if result.get("success"):
                self.logger.info(f"Session {session_id} terminated successfully")
                
                # Record termination in child safety log
                await self._record_safety_action({
                    "action": "session_terminated",
                    "session_id": session_id,
                    "reason": "safety_violation",
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                self.logger.error(f"Failed to terminate session {session_id}: {result.get('error')}")
                
        except Exception as e:
            self.logger.error(f"Error terminating session {session_id}: {e}")
            # Fallback: notify system administrators
            await self._notify_emergency_contacts(ChildSafetyIncident(
                incident_id=str(uuid.uuid4()),
                child_id="unknown",
                session_id=session_id,
                incident_type=ChildSafetyViolationType.TECHNICAL_FAILURE,
                description=f"Failed to terminate session {session_id}: {e}",
                severity_level=SafetyAlertPriority.HIGH,
                timestamp=datetime.utcnow(),
                parent_id="system",
                resolved=False
            ))
    
    async def _pause_session(self, session_id: str):
        """Pause a user session for human review."""
        self.logger.warning(f"PAUSING SESSION: {session_id}")
        
        try:
            from src.user_experience.session_management import SessionManager, SessionStatus
            
            session_manager = SessionManager()
            
            # Get session info first
            session_info = session_manager.active_sessions.get(session_id)
            if session_info:
                # Mark session as suspicious for human review
                session_info.status = SessionStatus.SUSPICIOUS
                session_info.security_flags.add("pending_review")
                
                # Log the pause action
                await session_manager._log_session_activity(
                    session_id=session_id,
                    action="session_paused",
                    details={"reason": "child_safety_review", "requires_human_approval": True},
                    ip_address=session_info.ip_address,
                    success=True,
                    risk_score=75
                )
                
                # Notify child safety team for review
                await self._queue_for_human_review(ChildSafetyIncident(
                    incident_id=str(uuid.uuid4()),
                    child_id=session_info.child_id or "unknown",
                    session_id=session_id,
                    incident_type=ChildSafetyViolationType.SUSPICIOUS_BEHAVIOR,
                    description=f"Session {session_id} paused for human review",
                    severity_level=SafetyAlertPriority.MEDIUM,
                    timestamp=datetime.utcnow(),
                    parent_id=session_info.user_id,
                    resolved=False
                ))
                
                self.logger.info(f"Session {session_id} paused for review")
            else:
                self.logger.error(f"Session {session_id} not found for pausing")
                
        except Exception as e:
            self.logger.error(f"Error pausing session {session_id}: {e}")
    
    async def _enable_enhanced_monitoring(self, session_id: str):
        """Enable enhanced monitoring for a session."""
        self.logger.info(f"ENABLING ENHANCED MONITORING: {session_id}")
        
        try:
            from src.application.services.monitoring.production_monitoring_service import (
                ProductionMonitoringService, MonitoringLevel
            )
            from src.user_experience.session_management import SessionManager
            
            # Initialize services
            monitoring_service = ProductionMonitoringService()
            session_manager = SessionManager()
            
            # Get session information
            session_info = session_manager.active_sessions.get(session_id)
            if session_info:
                # Add enhanced monitoring flag
                session_info.security_flags.add("enhanced_monitoring")
                
                # Create enhanced monitoring configuration
                enhanced_config = {
                    "session_id": session_id,
                    "child_id": session_info.child_id,
                    "monitoring_level": "enhanced",
                    "alert_threshold": 0.3,  # Lower threshold for alerts
                    "log_all_interactions": True,
                    "real_time_analysis": True,
                    "parent_notifications": True
                }
                
                # Register enhanced monitoring
                await monitoring_service.create_alert(
                    alert_type="enhanced_monitoring_enabled",
                    level=MonitoringLevel.INFO,
                    title=f"Enhanced Monitoring Activated",
                    message=f"Enhanced monitoring enabled for session {session_id}",
                    details=enhanced_config
                )
                
                # Store enhanced monitoring configuration
                await self._store_enhanced_monitoring_config(session_id, enhanced_config)
                
                self.logger.info(f"Enhanced monitoring enabled for session {session_id}")
            else:
                self.logger.error(f"Session {session_id} not found for enhanced monitoring")
                
        except Exception as e:
            self.logger.error(f"Error enabling enhanced monitoring for {session_id}: {e}")
    
    async def _flag_account_for_review(self, child_id: str, priority: str):
        """Flag an account for human review."""
        self.logger.warning(f"FLAGGING ACCOUNT FOR {priority.upper()} REVIEW: {child_id}")
        
        try:
            from src.application.services.user_service import UserService
            from src.adapters.dashboard_routes import validate_child_access
            from src.infrastructure.database.database_manager import get_db
            
            # Create review flag record
            review_flag = {
                "child_id": child_id,
                "flag_type": "safety_review",
                "priority": priority,
                "flagged_by": "child_safety_monitor",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "pending_review",
                "reason": "automated_safety_system",
                "requires_parent_notification": priority in ["HIGH", "CRITICAL"]
            }
            
            # Get database session
            async with get_db() as db:
                # Find parent of the child
                child = await validate_child_access(db, child_id, "system_check")
                if child and child.parent_id:
                    parent_id = str(child.parent_id)
                    review_flag["parent_id"] = parent_id
                    
                    # Store review flag in database
                    await self._store_review_flag(db, review_flag)
                    
                    # Create incident for tracking
                    incident = ChildSafetyIncident(
                        incident_id=str(uuid.uuid4()),
                        child_id=child_id,
                        session_id=None,
                        incident_type=ChildSafetyViolationType.ACCOUNT_FLAGGED,
                        description=f"Account flagged for {priority} priority review",
                        severity_level=SafetyAlertPriority[priority] if priority in SafetyAlertPriority.__members__ else SafetyAlertPriority.MEDIUM,
                        timestamp=datetime.utcnow(),
                        parent_id=parent_id,
                        resolved=False
                    )
                    
                    # Queue for human review
                    await self._queue_for_human_review(incident)
                    
                    # Notify parent if high/critical priority
                    if priority in ["HIGH", "CRITICAL"]:
                        await self._notify_parent(incident)
                    
                    self.logger.info(f"Account {child_id} flagged for {priority} review successfully")
                else:
                    self.logger.error(f"Could not find parent for child {child_id}")
                    
        except Exception as e:
            self.logger.error(f"Error flagging account {child_id} for review: {e}")
    
    async def _queue_for_human_review(self, incident: ChildSafetyIncident):
        """Queue incident for human review."""
        self.logger.info(f"QUEUING FOR HUMAN REVIEW: {incident.incident_id}")
        
        try:
            from src.adapters.dashboard.parent_dashboard import ParentDashboard
            from src.adapters.dashboard.safety_controls import SafetyControls
            
            # Create review queue item
            review_item = {
                "incident_id": incident.incident_id,
                "child_id": incident.child_id,
                "parent_id": incident.parent_id,
                "session_id": incident.session_id,
                "incident_type": incident.incident_type.value,
                "description": incident.description,
                "severity": incident.severity_level.value,
                "timestamp": incident.timestamp.isoformat(),
                "status": "pending_review",
                "assigned_reviewer": None,
                "review_deadline": self._calculate_review_deadline(incident.severity_level),
                "escalation_level": 0,
                "metadata": {
                    "flagged_by": "automated_system",
                    "requires_immediate_attention": incident.severity_level in [SafetyAlertPriority.HIGH, SafetyAlertPriority.CRITICAL],
                    "child_safety_score_impact": self._calculate_safety_score_impact(incident)
                }
            }
            
            # Store in review queue (using dashboard system)
            dashboard = ParentDashboard()
            await dashboard.add_to_review_queue(review_item)
            
            # Create safety alert for administrators
            safety_controls = SafetyControls()
            await safety_controls.create_safety_alert({
                "alert_id": str(uuid.uuid4()),
                "incident_id": incident.incident_id,
                "alert_type": "human_review_required",
                "priority": incident.severity_level.value,
                "message": f"Incident {incident.incident_id} requires human review",
                "child_id": incident.child_id,
                "created_at": datetime.utcnow().isoformat()
            })
            
            # Send notification to child safety team
            await self._notify_child_safety_team(incident)
            
            self.logger.info(f"Incident {incident.incident_id} queued for human review successfully")
            
        except Exception as e:
            self.logger.error(f"Error queuing incident {incident.incident_id} for review: {e}")
            # Fallback: Send direct notification to safety team
            await self._notify_child_safety_team(incident)
    
    async def _notify_parent(self, incident: ChildSafetyIncident):
        """Notify parent of safety incident."""
        self.logger.info(f"NOTIFYING PARENT: {incident.parent_id}")
        
        try:
            from src.application.services.notification.notification_service_main import (
                ProductionNotificationService, NotificationChannel, NotificationPriority, NotificationRequest,
                NotificationRecipient, NotificationTemplate, NotificationType
            )
            from src.infrastructure.database.repository import UserRepository
            import uuid
            
            notification_service = ProductionNotificationService()
            user_repo = UserRepository()
            
            # Get parent information
            parent = await user_repo.get_by_id(uuid.UUID(incident.parent_id))
            if not parent:
                self.logger.error(f"Parent {incident.parent_id} not found for notification")
                return
                
            # Determine notification priority and channels based on severity
            if incident.severity_level == SafetyAlertPriority.CRITICAL:
                priority = NotificationPriority.URGENT
                channels = [NotificationChannel.PUSH, NotificationChannel.SMS, NotificationChannel.EMAIL, NotificationChannel.PHONE_CALL]
            elif incident.severity_level == SafetyAlertPriority.HIGH:
                priority = NotificationPriority.HIGH
                channels = [NotificationChannel.PUSH, NotificationChannel.EMAIL, NotificationChannel.SMS]
            else:
                priority = NotificationPriority.NORMAL
                channels = [NotificationChannel.PUSH, NotificationChannel.EMAIL]
            
            # Create notification template
            template = NotificationTemplate(
                title=self._get_notification_title(incident),
                body=self._get_notification_body(incident),
                action_url=f"/app/safety/incident/{incident.incident_id}",
                icon="safety_alert",
                sound="safety_alert" if incident.severity_level in [SafetyAlertPriority.HIGH, SafetyAlertPriority.CRITICAL] else "default",
                custom_data={
                    "incident_id": incident.incident_id,
                    "child_id": incident.child_id,
                    "severity": incident.severity_level.value,
                    "type": "child_safety_alert"
                }
            )
            
            # Create recipient
            recipient = NotificationRecipient(
                user_id=incident.parent_id,
                email=parent.email,
                phone=getattr(parent, 'phone', None),
                push_token=getattr(parent, 'push_token', None),
                preferred_channels=[NotificationChannel.PUSH, NotificationChannel.EMAIL]
            )
            
            # Create notification request
            notification_request = NotificationRequest(
                notification_type=NotificationType.CHILD_SAFETY_ALERT,
                priority=priority,
                recipient=recipient,
                template=template,
                channels=channels,
                retry_config={
                    "max_retries": 3 if incident.severity_level == SafetyAlertPriority.CRITICAL else 2,
                    "retry_delay_seconds": 30,
                    "exponential_backoff": True
                }
            )
            
            # Send notification
            result = await notification_service.send_notification(notification_request)
            
            if result.get("success"):
                self.logger.info(f"Parent notification sent successfully for incident {incident.incident_id}")
                
                # Record notification in incident log
                await self._record_safety_action({
                    "action": "parent_notified",
                    "incident_id": incident.incident_id,
                    "parent_id": incident.parent_id,
                    "notification_channels": [ch.value for ch in channels],
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                self.logger.error(f"Failed to send parent notification: {result.get('error')}")
                
        except Exception as e:
            self.logger.error(f"Error notifying parent for incident {incident.incident_id}: {e}")
            # Fallback: log critical notification failure
            if incident.severity_level == SafetyAlertPriority.CRITICAL:
                await self._notify_emergency_contacts(incident)
    
    async def _notify_emergency_contacts(self, incident: ChildSafetyIncident):
        """Notify emergency contacts."""
        self.logger.critical(f"NOTIFYING EMERGENCY CONTACTS: {incident.incident_id}")
        
        try:
            # Get parent contact information from database
            from src.infrastructure.database.repository import UserRepository, ChildRepository
            import uuid
            
            child_repo = ChildRepository()
            user_repo = UserRepository()
            
            # Get child record to find parent
            child = await child_repo.get_by_id(uuid.UUID(incident.child_id))
            if child and child.parent_id:
                parent = await user_repo.get_by_id(child.parent_id)
                
                if parent and parent.email:
                    # Send immediate emergency email
                    from src.infrastructure.communication.production_notification_service import (
                        ProductionNotificationService
                    )
                    notification_service = ProductionNotificationService()
                    
                    # Send emergency notification to parent
                    await notification_service.send_emergency_notification(
                        recipient_email=parent.email,
                        incident_id=incident.incident_id,
                        severity=incident.severity_level.value,
                        description=incident.description,
                        child_name=child.name if hasattr(child, 'name') else 'your child',
                        timestamp=incident.timestamp.isoformat()
                    )
                    
                    # Also send SMS if phone number available
                    if hasattr(parent, 'phone') and parent.phone:
                        await notification_service.send_emergency_sms(
                            phone_number=parent.phone,
                            incident_id=incident.incident_id,
                            child_name=child.name if hasattr(child, 'name') else 'child'
                        )
                    
                    self.logger.info(f"Emergency notifications sent to parent: {parent.email}")
                else:
                    self.logger.error(f"No parent email found for child {incident.child_id}")
            else:
                self.logger.error(f"Child record not found: {incident.child_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to send emergency notification: {e}")
    
    async def _notify_child_safety_team(self, incident: ChildSafetyIncident):
        """Notify child safety team with immediate escalation."""
        self.logger.critical(f"NOTIFYING CHILD SAFETY TEAM: {incident.incident_id}")
        
        try:
            # Get notification service
            from src.infrastructure.communication.production_notification_service import ProductionNotificationService
            notification_service = ProductionNotificationService()
            
            # Send emergency email to safety team
            safety_team_email = os.getenv('CHILD_SAFETY_TEAM_EMAIL', 'safety@teddy-support.com')
            
            await notification_service.send_safety_team_alert(
                team_email=safety_team_email,
                incident_id=incident.incident_id,
                incident_type=incident.incident_type.value,
                severity=incident.severity.value,
                child_id=incident.child_id,
                description=incident.description,
                timestamp=incident.timestamp.isoformat()
            )
            
            # Send SMS alert for critical incidents
            if incident.severity in [IncidentSeverity.HIGH, IncidentSeverity.CRITICAL]:
                sms_number = os.getenv('SAFETY_TEAM_SMS', '+1234567890')
                sms_message = f"URGENT: Child safety incident {incident.incident_id} requires immediate attention. Type: {incident.incident_type.value}"
                await notification_service.send_sms(sms_number, sms_message)
            
            self.logger.info(f"Child safety team notified for incident: {incident.incident_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to notify child safety team: {e}")
            # Fallback to direct logging for audit trail
            self.logger.critical(f"SAFETY ALERT FAILED - MANUAL REVIEW REQUIRED: {incident.incident_id} - {incident.description}")
    
    async def _escalate_incident(self, incident: ChildSafetyIncident, reason: str):
        """Escalate an incident to higher authorities."""
        self.logger.critical(f"ESCALATING INCIDENT {incident.incident_id}: {reason}")
        
        try:
            # Get notification service
            from src.infrastructure.communication.production_notification_service import ProductionNotificationService
            notification_service = ProductionNotificationService()
            
            # Notify management team
            management_email = os.getenv('MANAGEMENT_TEAM_EMAIL', 'management@teddy-support.com')
            
            escalation_subject = f"ESCALATED: Child Safety Incident {incident.incident_id}"
            escalation_message = f"""
INCIDENT ESCALATION REQUIRED

Incident ID: {incident.incident_id}
Original Type: {incident.incident_type.value}
Severity: {incident.severity.value}
Child ID: {incident.child_id}
Escalation Reason: {reason}
Timestamp: {incident.timestamp.isoformat()}

Description:
{incident.description}

IMMEDIATE MANAGEMENT ATTENTION REQUIRED
"""
            
            await notification_service.send_email(
                to=management_email,
                subject=escalation_subject,
                body=escalation_message
            )
            
            # Send to legal team if COPPA-related
            if 'coppa' in reason.lower() or 'compliance' in reason.lower():
                legal_email = os.getenv('LEGAL_TEAM_EMAIL', 'legal@teddy-support.com')
                await notification_service.send_email(
                    to=legal_email,
                    subject=f"LEGAL REVIEW REQUIRED: {incident.incident_id}",
                    body=f"Incident escalated for legal review:\n\n{escalation_message}"
                )
            
            # Update incident record with escalation
            incident.escalated = True
            incident.escalation_reason = reason
            incident.escalated_at = datetime.now()
            
            self.logger.info(f"Incident escalated successfully: {incident.incident_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to escalate incident: {e}")
            # Critical fallback - ensure escalation is logged
            self.logger.critical(f"ESCALATION FAILED - MANUAL INTERVENTION REQUIRED: {incident.incident_id} - Reason: {reason}")
    
    async def _send_compliance_email(self, incident: COPPAComplianceIncident, email: str):
        """Send compliance notification email."""
        self.logger.info(f"SENDING COMPLIANCE EMAIL: {incident.incident_id}")
        
        try:
            from src.infrastructure.communication.production_notification_service import ProductionNotificationService
            notification_service = ProductionNotificationService()
            
            subject = f"COPPA Compliance Alert: {incident.incident_id}"
            
            message = f"""
COPPA COMPLIANCE INCIDENT NOTIFICATION

Incident ID: {incident.incident_id}
Type: {incident.incident_type.value}
Severity: {incident.severity.value}
Child ID: {incident.child_id}
Parent ID: {incident.parent_id}
Status: {incident.status.value}
Deadline: {incident.response_deadline.isoformat() if incident.response_deadline else 'Not set'}
Timestamp: {incident.timestamp.isoformat()}

Description:
{incident.description}

Required Actions:
{chr(10).join(['- ' + action for action in incident.required_actions])}

This incident requires immediate attention to ensure COPPA compliance.

Please review and take appropriate action within the specified deadline.
"""
            
            await notification_service.send_email(
                to=email,
                subject=subject,
                body=message
            )
            
            self.logger.info(f"Compliance email sent to {email} for incident: {incident.incident_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to send compliance email: {e}")
            self.logger.critical(f"COMPLIANCE EMAIL FAILED - MANUAL NOTIFICATION REQUIRED: {incident.incident_id} to {email}")
    
    async def _send_compliance_slack_notification(self, incident: COPPAComplianceIncident, webhook: str):
        """Send compliance Slack notification."""
        self.logger.info(f"SENDING COMPLIANCE SLACK: {incident.incident_id}")
        
        try:
            import httpx
            
            # Determine color based on severity
            color_map = {
                IncidentSeverity.LOW: "#36a64f",      # Green
                IncidentSeverity.MEDIUM: "#ffeb3b",   # Yellow
                IncidentSeverity.HIGH: "#ff9800",     # Orange
                IncidentSeverity.CRITICAL: "#f44336"  # Red
            }
            
            color = color_map.get(incident.severity, "#36a64f")
            
            # Create Slack message
            slack_payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": f"COPPA Compliance Alert: {incident.incident_id}",
                        "text": incident.description,
                        "fields": [
                            {
                                "title": "Severity",
                                "value": incident.severity.value.upper(),
                                "short": True
                            },
                            {
                                "title": "Type",
                                "value": incident.incident_type.value,
                                "short": True
                            },
                            {
                                "title": "Child ID",
                                "value": incident.child_id,
                                "short": True
                            },
                            {
                                "title": "Status",
                                "value": incident.status.value,
                                "short": True
                            },
                            {
                                "title": "Deadline",
                                "value": incident.response_deadline.isoformat() if incident.response_deadline else "Not set",
                                "short": False
                            }
                        ],
                        "footer": "AI Teddy Bear - Child Safety System",
                        "ts": int(incident.timestamp.timestamp())
                    }
                ]
            }
            
            # Send to Slack
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(webhook, json=slack_payload)
                
                if response.status_code == 200:
                    self.logger.info(f"Slack notification sent for incident: {incident.incident_id}")
                else:
                    self.logger.error(f"Slack notification failed: HTTP {response.status_code}")
                    
        except Exception as e:
            self.logger.error(f"Failed to send Slack notification: {e}")
            self.logger.warning(f"SLACK NOTIFICATION FAILED - MANUAL NOTIFICATION REQUIRED: {incident.incident_id}")
    
    async def _notify_legal_team_deadline(self, incident: COPPAComplianceIncident, time_left: str):
        """Notify legal team of approaching deadline."""
        self.logger.critical(f"LEGAL TEAM DEADLINE ALERT: {incident.incident_id} - {time_left} remaining")
        
        try:
            from src.infrastructure.communication.production_notification_service import ProductionNotificationService
            notification_service = ProductionNotificationService()
            
            legal_email = os.getenv('LEGAL_TEAM_EMAIL', 'legal@teddy-support.com')
            
            subject = f"URGENT: COPPA Deadline Alert - {incident.incident_id}"
            
            message = f"""
URGENT: COPPA COMPLIANCE DEADLINE APPROACHING

Incident ID: {incident.incident_id}
Time Remaining: {time_left}
Deadline: {incident.response_deadline.isoformat() if incident.response_deadline else 'Not set'}
Severity: {incident.severity.value}
Type: {incident.incident_type.value}
Child ID: {incident.child_id}
Parent ID: {incident.parent_id}

Description:
{incident.description}

Required Actions:
{chr(10).join(['- ' + action for action in incident.required_actions])}

IMMEDIATE LEGAL REVIEW REQUIRED

This incident requires urgent attention to avoid COPPA compliance violations.
"""
            
            await notification_service.send_email(
                to=legal_email,
                subject=subject,
                body=message
            )
            
            # Send SMS for critical deadlines (< 2 hours)
            if 'hour' in time_left.lower() and '1' in time_left:
                legal_sms = os.getenv('LEGAL_TEAM_SMS', '+1234567891')
                sms_message = f"URGENT: COPPA deadline {time_left} remaining for incident {incident.incident_id}. Immediate action required."
                await notification_service.send_sms(legal_sms, sms_message)
            
            self.logger.info(f"Legal team deadline notification sent for incident: {incident.incident_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to notify legal team: {e}")
            self.logger.critical(f"LEGAL DEADLINE NOTIFICATION FAILED - MANUAL INTERVENTION REQUIRED: {incident.incident_id} - {time_left} remaining")
    
    async def _send_deadline_warning(self, incident: COPPAComplianceIncident, time_left: str):
        """Send deadline warning."""
        self.logger.warning(f"DEADLINE WARNING: {incident.incident_id} - {time_left} remaining")
        
        try:
            from src.infrastructure.communication.production_notification_service import ProductionNotificationService
            notification_service = ProductionNotificationService()
            
            # Determine recipients based on time remaining
            compliance_email = os.getenv('COMPLIANCE_TEAM_EMAIL', 'compliance@teddy-support.com')
            
            subject = f"COPPA Deadline Warning - {incident.incident_id}"
            
            message = f"""
COPPA COMPLIANCE DEADLINE WARNING

Incident ID: {incident.incident_id}
Time Remaining: {time_left}
Deadline: {incident.response_deadline.isoformat() if incident.response_deadline else 'Not set'}
Type: {incident.incident_type.value}
Severity: {incident.severity.value}
Status: {incident.status.value}
Child ID: {incident.child_id}

Description:
{incident.description}

Required Actions:
{chr(10).join(['- ' + action for action in incident.required_actions])}

Please review and update the incident status to ensure compliance deadlines are met.
"""
            
            await notification_service.send_email(
                to=compliance_email,
                subject=subject,
                body=message
            )
            
            # Also notify management if less than 4 hours remaining
            if 'hour' in time_left.lower() and any(str(i) in time_left for i in [1, 2, 3]):
                management_email = os.getenv('MANAGEMENT_TEAM_EMAIL', 'management@teddy-support.com')
                await notification_service.send_email(
                    to=management_email,
                    subject=f"URGENT: {subject}",
                    body=f"MANAGEMENT ATTENTION REQUIRED:\n\n{message}"
                )
            
            self.logger.info(f"Deadline warning sent for incident: {incident.incident_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to send deadline warning: {e}")
            self.logger.warning(f"DEADLINE WARNING NOTIFICATION FAILED: {incident.incident_id} - {time_left} remaining")
    
    async def _handle_deadline_breach(self, incident: COPPAComplianceIncident):
        """Handle deadline breach - CRITICAL COMPLIANCE VIOLATION."""
        self.logger.critical(f"DEADLINE BREACHED: {incident.incident_id}")
        
        try:
            from src.infrastructure.communication.production_notification_service import ProductionNotificationService
            notification_service = ProductionNotificationService()
            
            # Update incident status
            incident.status = ComplianceStatus.BREACHED
            incident.breach_timestamp = datetime.now()
            
            # Notify all critical stakeholders immediately
            stakeholders = {
                'legal': os.getenv('LEGAL_TEAM_EMAIL', 'legal@teddy-support.com'),
                'compliance': os.getenv('COMPLIANCE_TEAM_EMAIL', 'compliance@teddy-support.com'),
                'management': os.getenv('MANAGEMENT_TEAM_EMAIL', 'management@teddy-support.com'),
                'ceo': os.getenv('CEO_EMAIL', 'ceo@teddy-support.com')
            }
            
            breach_subject = f"CRITICAL: COPPA Deadline BREACHED - {incident.incident_id}"
            
            breach_message = f"""
CRITICAL COMPLIANCE VIOLATION - COPPA DEADLINE BREACHED

Incident ID: {incident.incident_id}
Deadline: {incident.response_deadline.isoformat() if incident.response_deadline else 'Not set'}
Breach Time: {incident.breach_timestamp.isoformat()}
Severity: {incident.severity.value}
Type: {incident.incident_type.value}
Child ID: {incident.child_id}
Parent ID: {incident.parent_id}

Description:
{incident.description}

Required Actions (OVERDUE):
{chr(10).join(['- ' + action for action in incident.required_actions])}

IMMEDIATE ACTION REQUIRED

This represents a potential COPPA compliance violation that may result in:
- Regulatory penalties
- Legal liability
- Reputational damage
- Required disclosure to authorities

All stakeholders must take immediate corrective action.
"""
            
            # Send to all stakeholders
            for role, email in stakeholders.items():
                if email:
                    await notification_service.send_email(
                        to=email,
                        subject=f"[{role.upper()}] {breach_subject}",
                        body=breach_message
                    )
            
            # Send emergency SMS to key personnel
            emergency_contacts = {
                'legal_sms': os.getenv('LEGAL_TEAM_SMS', '+1234567891'),
                'ceo_sms': os.getenv('CEO_SMS', '+1234567892')
            }
            
            sms_message = f"EMERGENCY: COPPA deadline breached for incident {incident.incident_id}. Immediate action required to mitigate compliance violation."
            
            for contact_type, phone in emergency_contacts.items():
                if phone:
                    await notification_service.send_sms(phone, sms_message)
            
            # Log for audit trail
            self.logger.critical(f"COPPA DEADLINE BREACH HANDLED - ALL STAKEHOLDERS NOTIFIED: {incident.incident_id}")
            
            # Create audit record
            audit_record = {
                'incident_id': incident.incident_id,
                'breach_type': 'coppa_deadline',
                'breach_time': incident.breach_timestamp.isoformat(),
                'notifications_sent': list(stakeholders.keys()),
                'required_actions': incident.required_actions,
                'impact_level': 'critical'
            }
            
            self.logger.critical(f"COMPLIANCE BREACH AUDIT RECORD: {json.dumps(audit_record)}")
            
        except Exception as e:
            self.logger.error(f"Failed to handle deadline breach: {e}")
            # Absolute fallback - this is critical
            self.logger.critical(f"DEADLINE BREACH HANDLING FAILED - MANUAL EMERGENCY RESPONSE REQUIRED: {incident.incident_id}")
            self.logger.critical(f"ALL STAKEHOLDERS MUST BE CONTACTED IMMEDIATELY FOR INCIDENT: {incident.incident_id}")
    
    async def _generate_daily_safety_report(self):
        """Generate daily child safety report."""
        self.logger.info("GENERATING DAILY SAFETY REPORT")
        
        try:
            from src.infrastructure.communication.production_notification_service import ProductionNotificationService
            notification_service = ProductionNotificationService()
            
            # Get yesterday's date range
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            start_time = datetime.combine(yesterday, datetime.min.time())
            end_time = datetime.combine(yesterday, datetime.max.time())
            
            # Filter incidents from yesterday
            daily_incidents = [
                incident for incident in self.incident_history
                if start_time <= incident.timestamp <= end_time
            ]
            
            # Categorize incidents
            incidents_by_type = {}
            incidents_by_severity = {}
            
            for incident in daily_incidents:
                # Group by type
                incident_type = incident.incident_type.value
                if incident_type not in incidents_by_type:
                    incidents_by_type[incident_type] = []
                incidents_by_type[incident_type].append(incident)
                
                # Group by severity
                severity = incident.severity.value
                if severity not in incidents_by_severity:
                    incidents_by_severity[severity] = []
                incidents_by_severity[severity].append(incident)
            
            # Generate report
            report = f"""
DAILY CHILD SAFETY REPORT - {yesterday.strftime('%Y-%m-%d')}

SUMMARY:
- Total Incidents: {len(daily_incidents)}
- Critical Incidents: {len(incidents_by_severity.get('critical', []))}
- High Priority: {len(incidents_by_severity.get('high', []))}
- Medium Priority: {len(incidents_by_severity.get('medium', []))}
- Low Priority: {len(incidents_by_severity.get('low', []))}

INCIDENTS BY TYPE:
{chr(10).join([f'- {incident_type}: {len(incidents)}' for incident_type, incidents in incidents_by_type.items()])}

CRITICAL INCIDENTS REQUIRING ATTENTION:
{chr(10).join([f'- {incident.incident_id}: {incident.description}' for incident in incidents_by_severity.get('critical', [])[:5]])}

ACTION ITEMS:
- Review all critical incidents
- Follow up on pending compliance cases
- Update safety protocols if patterns emerge

Next report will be generated tomorrow.
"""
            
            # Send report to safety team
            safety_email = os.getenv('CHILD_SAFETY_TEAM_EMAIL', 'safety@teddy-support.com')
            management_email = os.getenv('MANAGEMENT_TEAM_EMAIL', 'management@teddy-support.com')
            
            await notification_service.send_email(
                to=safety_email,
                subject=f"Daily Child Safety Report - {yesterday.strftime('%Y-%m-%d')}",
                body=report
            )
            
            # Send summary to management
            if len(incidents_by_severity.get('critical', [])) > 0:
                await notification_service.send_email(
                    to=management_email,
                    subject=f"Critical Safety Incidents Summary - {yesterday.strftime('%Y-%m-%d')}",
                    body=f"Management Alert: {len(incidents_by_severity.get('critical', []))} critical child safety incidents occurred yesterday. Please review the full report.\n\n{report}"
                )
            
            self.logger.info(f"Daily safety report generated and sent: {len(daily_incidents)} incidents")
            
        except Exception as e:
            self.logger.error(f"Failed to generate daily safety report: {e}")
            # Ensure reporting continues
            self.logger.warning("Daily safety report generation failed - manual review required")
    
    async def _generate_weekly_coppa_report(self):
        """Generate weekly COPPA compliance report."""
        
        try:
            from src.infrastructure.communication.production_notification_service import ProductionNotificationService
            notification_service = ProductionNotificationService()
            
            # Get last week's date range
            today = datetime.now().date()
            week_start = today - timedelta(days=7)
            start_time = datetime.combine(week_start, datetime.min.time())
            end_time = datetime.combine(today, datetime.max.time())
            
            # Filter COPPA incidents from last week
            weekly_coppa_incidents = [
                incident for incident in self.compliance_incidents
                if start_time <= incident.timestamp <= end_time
            ]
            
            # Calculate compliance metrics
            total_incidents = len(weekly_coppa_incidents)
            resolved_incidents = len([i for i in weekly_coppa_incidents if i.status == ComplianceStatus.RESOLVED])
            pending_incidents = len([i for i in weekly_coppa_incidents if i.status == ComplianceStatus.PENDING])
            breached_incidents = len([i for i in weekly_coppa_incidents if i.status == ComplianceStatus.BREACHED])
            
            compliance_rate = (resolved_incidents / total_incidents * 100) if total_incidents > 0 else 100
            
            # Generate detailed report
            report = f"""
WEEKLY COPPA COMPLIANCE REPORT - {week_start.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}

EXECUTIVE SUMMARY:
- Total COPPA Incidents: {total_incidents}
- Resolved: {resolved_incidents} ({resolved_incidents/total_incidents*100:.1f}% if total_incidents else 0)
- Pending: {pending_incidents}
- Breached Deadlines: {breached_incidents}
- Compliance Rate: {compliance_rate:.1f}%

RISK ASSESSMENT:
{'HIGH RISK' if breached_incidents > 0 else 'MEDIUM RISK' if pending_incidents > 2 else 'LOW RISK'}

CRITICAL ISSUES:
{chr(10).join([f'- {incident.incident_id}: {incident.description}' for incident in weekly_coppa_incidents if incident.status == ComplianceStatus.BREACHED])}

PENDING REVIEW (Requires Attention):
{chr(10).join([f'- {incident.incident_id}: Deadline {incident.response_deadline.strftime('%Y-%m-%d %H:%M') if incident.response_deadline else 'Not set'}' for incident in weekly_coppa_incidents if incident.status == ComplianceStatus.PENDING])}

RECOMMENDATIONS:
- {'Immediate review of breached deadlines required' if breached_incidents > 0 else 'Continue monitoring pending cases'}
- {'Strengthen deadline management processes' if breached_incidents > 1 else 'Maintain current compliance protocols'}
- Review staff training on COPPA requirements

Next weekly report: {(today + timedelta(days=7)).strftime('%Y-%m-%d')}
"""
            
            # Send to compliance and legal teams
            compliance_email = os.getenv('COMPLIANCE_TEAM_EMAIL', 'compliance@teddy-support.com')
            legal_email = os.getenv('LEGAL_TEAM_EMAIL', 'legal@teddy-support.com')
            management_email = os.getenv('MANAGEMENT_TEAM_EMAIL', 'management@teddy-support.com')
            
            # Send detailed report to compliance team
            await notification_service.send_email(
                to=compliance_email,
                subject=f"Weekly COPPA Compliance Report - {compliance_rate:.1f}% Compliance Rate",
                body=report
            )
            
            # Send to legal team
            await notification_service.send_email(
                to=legal_email,
                subject=f"Weekly COPPA Legal Review - {week_start.strftime('%Y-%m-%d')}",
                body=report
            )
            
            # Send executive summary to management
            executive_summary = f"""
WEEKLY COPPA COMPLIANCE EXECUTIVE SUMMARY

Compliance Rate: {compliance_rate:.1f}%
Total Incidents: {total_incidents}
Breached Deadlines: {breached_incidents}
Risk Level: {'HIGH' if breached_incidents > 0 else 'MEDIUM' if pending_incidents > 2 else 'LOW'}

{'IMMEDIATE ACTION REQUIRED' if breached_incidents > 0 else 'Standard monitoring continues'}
"""
            
            await notification_service.send_email(
                to=management_email,
                subject=f"COPPA Compliance Summary - Week of {week_start.strftime('%Y-%m-%d')}",
                body=executive_summary
            )
            
            self.logger.info("Weekly COPPA report generated", extra={
                "compliance_rate": f"{compliance_rate:.1f}%",
                "total_incidents": total_incidents
            })
            
        except Exception as e:
            self.logger.error("Error generating COPPA report", extra={"error": str(e)})
            
        try:
            # Import mobile app report service if available, otherwise use backend reporting
            try:
                from mobile_app.AITeddyParent.src.services.ReportService import ReportService
                report_service = ReportService.getInstance() if ReportService else None
            except ImportError:
                # Fallback to backend reporting system
                report_service = None
            
            from src.application.services.notification.notification_service_main import ProductionNotificationService
            
            # Initialize services
            notification_service = ProductionNotificationService()
            
            # Calculate week dates
            week_end = datetime.utcnow()
            week_start = week_end - timedelta(days=7)
            
            # Collect COPPA incidents for the week
            weekly_coppa_incidents = []
            for incident in self.coppa_incidents.values():
                if week_start <= incident.timestamp <= week_end:
                    weekly_coppa_incidents.append(incident)
            
            # Collect child safety incidents that affect COPPA compliance
            safety_incidents_affecting_coppa = []
            for incident in self.active_incidents.values():
                if (week_start <= incident.timestamp <= week_end and 
                    incident.violation_type in [ChildSafetyViolationType.DATA_PRIVACY_VIOLATION, 
                                               ChildSafetyViolationType.UNAUTHORIZED_DATA_ACCESS]):
                    safety_incidents_affecting_coppa.append(incident)
            
            # Calculate compliance metrics
            total_incidents = len(weekly_coppa_incidents) + len(safety_incidents_affecting_coppa)
            resolved_incidents = len([i for i in weekly_coppa_incidents if i.resolved]) + len([i for i in safety_incidents_affecting_coppa if i.resolved])
            breached_incidents = len([i for i in weekly_coppa_incidents if i.priority in [SafetyAlertPriority.HIGH, SafetyAlertPriority.CRITICAL]])
            pending_incidents = total_incidents - resolved_incidents
            
            compliance_rate = ((resolved_incidents / total_incidents) * 100) if total_incidents > 0 else 100
            
            # Generate comprehensive report data
            report_data = {
                "report_type": "weekly_coppa_compliance",
                "period": {
                    "start_date": week_start.isoformat(),
                    "end_date": week_end.isoformat(),
                    "week_number": week_start.isocalendar()[1]
                },
                "compliance_metrics": {
                    "overall_compliance_rate": compliance_rate,
                    "total_incidents": total_incidents,
                    "resolved_incidents": resolved_incidents,
                    "pending_incidents": pending_incidents,
                    "breached_incidents": breached_incidents,
                    "critical_violations": len([i for i in weekly_coppa_incidents if i.priority == SafetyAlertPriority.CRITICAL])
                },
                "incident_breakdown": {
                    "coppa_specific": {
                        "data_collection_violations": len([i for i in weekly_coppa_incidents if i.violation_type == COPPAViolationType.UNAUTHORIZED_DATA_COLLECTION]),
                        "parental_consent_violations": len([i for i in weekly_coppa_incidents if i.violation_type == COPPAViolationType.MISSING_PARENTAL_CONSENT]),
                        "data_retention_violations": len([i for i in weekly_coppa_incidents if i.violation_type == COPPAViolationType.DATA_RETENTION_VIOLATION]),
                        "disclosure_violations": len([i for i in weekly_coppa_incidents if i.violation_type == COPPAViolationType.UNAUTHORIZED_DATA_DISCLOSURE])
                    },
                    "child_safety_related": {
                        "privacy_violations": len([i for i in safety_incidents_affecting_coppa if i.violation_type == ChildSafetyViolationType.DATA_PRIVACY_VIOLATION]),
                        "data_access_violations": len([i for i in safety_incidents_affecting_coppa if i.violation_type == ChildSafetyViolationType.UNAUTHORIZED_DATA_ACCESS])
                    }
                },
                "trends_analysis": await self._analyze_compliance_trends(weekly_coppa_incidents, safety_incidents_affecting_coppa),
                "recommendations": self._generate_compliance_recommendations(compliance_rate, breached_incidents, pending_incidents),
                "generated_at": datetime.utcnow().isoformat(),
                "report_id": f"coppa_weekly_{week_start.strftime('%Y%W')}"
            }
            
            # Store the report
            await self._store_compliance_report(report_data)
            
            # Generate executive summary for management
            management_email = self.config.get("MANAGEMENT_EMAIL", "management@aiteddy.com")
            
            executive_summary = f"""
📊 COPPA Compliance Weekly Report - Week of {week_start.strftime('%Y-%m-%d')}

Compliance Overview:
• Overall Compliance Rate: {compliance_rate:.1f}%
• Total Incidents: {total_incidents}
• Resolved: {resolved_incidents}
• Pending: {pending_incidents}
• Critical Breaches: {breached_incidents}

Key Metrics:
• Data Collection Violations: {report_data['incident_breakdown']['coppa_specific']['data_collection_violations']}
• Parental Consent Issues: {report_data['incident_breakdown']['coppa_specific']['parental_consent_violations']}
• Data Retention Violations: {report_data['incident_breakdown']['coppa_specific']['data_retention_violations']}

Risk Assessment:
Risk Level: {'HIGH' if breached_incidents > 0 else 'MEDIUM' if pending_incidents > 2 else 'LOW'}

{'IMMEDIATE ACTION REQUIRED' if breached_incidents > 0 else 'Standard monitoring continues'}

Trend Analysis:
{report_data['trends_analysis']['summary']}

Recommendations:
{chr(10).join(['• ' + rec for rec in report_data['recommendations']])}

Detailed Report: Available in compliance dashboard
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""
            
            # Send executive summary
            await notification_service.send_email(
                to=management_email,
                subject=f"COPPA Compliance Summary - Week of {week_start.strftime('%Y-%m-%d')}",
                body=executive_summary
            )
            
            # Send detailed report to compliance team
            compliance_email = self.config.get("COMPLIANCE_EMAIL", "compliance@aiteddy.com")
            await notification_service.send_email(
                to=compliance_email,
                subject=f"Detailed COPPA Compliance Report - Week {week_start.isocalendar()[1]}",
                body=json.dumps(report_data, indent=2, default=str),
                attachments=[
                    {
                        "filename": f"coppa_compliance_report_{week_start.strftime('%Y%W')}.json",
                        "content": json.dumps(report_data, indent=2, default=str),
                        "content_type": "application/json"
                    }
                ]
            )
            
            # Update dashboard metrics for parents
            await self._update_parent_compliance_dashboards(report_data)
            
            self.logger.info(f"Weekly COPPA report generated: {compliance_rate:.1f}% compliance rate, {total_incidents} incidents")
            
            # Schedule next week's report
            await self._schedule_next_weekly_report()
            
        except Exception as e:
            self.logger.error(f"Failed to generate weekly COPPA report: {e}")
            self.logger.warning("Weekly COPPA report generation failed - manual review required")
            
            # Send failure notification to administrators
            try:
                admin_email = self.config.get("ADMIN_EMAIL", "admin@aiteddy.com")
                await notification_service.send_email(
                    to=admin_email,
                    subject="URGENT: Weekly COPPA Report Generation Failed",
                    body=f"The weekly COPPA compliance report failed to generate.\n\nError: {str(e)}\n\nImmediate manual review required."
                )
            except Exception as notify_e:
                self.logger.error(f"Exception sending failure notification to admin: {notify_e}", exc_info=True)
                # Continue - this is fallback notification only, main error already logged above
    
    def get_incident_stats(self) -> Dict[str, Any]:
        """Get incident statistics."""
        active_safety = [i for i in self.active_incidents.values() if not i.resolved]
        active_coppa = [i for i in self.coppa_incidents.values()]
        
        return {
            "active_safety_incidents": len(active_safety),
            "active_coppa_incidents": len(active_coppa),
            "safety_by_priority": {
                priority.value: len([i for i in active_safety if i.priority == priority])
                for priority in SafetyAlertPriority
            },
            "coppa_by_priority": {
                priority.value: len([i for i in active_coppa if i.priority == priority])
                for priority in SafetyAlertPriority
            },
            "safety_by_violation": {
                violation.value: len([i for i in active_safety if i.violation_type == violation])
                for violation in ChildSafetyViolationType
            },
            "coppa_by_violation": {
                violation.value: len([i for i in active_coppa if i.violation_type == violation])
                for violation in COPPAViolationType
            }
        }
    
    # Helper methods for comprehensive system integration
    
    async def _record_safety_action(self, action_data: Dict[str, Any]):
        """Record safety action in audit log."""
        try:
            from src.infrastructure.monitoring.audit import AuditLogger
            
            audit_logger = AuditLogger()
            await audit_logger.log_child_safety_action(
                action=action_data["action"],
                details=action_data,
                severity="INFO"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to record safety action: {e}")
    
    async def _store_enhanced_monitoring_config(self, session_id: str, config: Dict[str, Any]):
        """Store enhanced monitoring configuration."""
        try:
            from src.infrastructure.database.database_manager import get_db
            
            async with get_db() as db:
                await db.execute("""
                    INSERT INTO enhanced_monitoring_sessions (session_id, config, created_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (session_id) DO UPDATE SET
                    config = $2, updated_at = $3
                """, session_id, json.dumps(config), datetime.utcnow())
                
        except Exception as e:
            self.logger.error(f"Failed to store enhanced monitoring config: {e}")
    
    async def _store_review_flag(self, db, flag_data: Dict[str, Any]):
        """Store account review flag in database."""
        try:
            await db.execute("""
                INSERT INTO child_account_review_flags 
                (child_id, parent_id, flag_type, priority, reason, status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, 
            flag_data["child_id"],
            flag_data.get("parent_id"),
            flag_data["flag_type"],
            flag_data["priority"],
            flag_data["reason"],
            flag_data["status"],
            datetime.utcnow()
            )
            
        except Exception as e:
            self.logger.error(f"Failed to store review flag: {e}")
    
    def _calculate_review_deadline(self, severity: SafetyAlertPriority) -> str:
        """Calculate deadline for human review based on severity."""
        now = datetime.utcnow()
        
        if severity == SafetyAlertPriority.CRITICAL:
            deadline = now + timedelta(hours=1)  # 1 hour for critical
        elif severity == SafetyAlertPriority.HIGH:
            deadline = now + timedelta(hours=4)  # 4 hours for high
        elif severity == SafetyAlertPriority.MEDIUM:
            deadline = now + timedelta(hours=24)  # 24 hours for medium
        else:
            deadline = now + timedelta(hours=72)  # 72 hours for low
            
        return deadline.isoformat()
    
    def _calculate_safety_score_impact(self, incident: ChildSafetyIncident) -> float:
        """Calculate impact on child safety score."""
        base_impact = {
            SafetyAlertPriority.CRITICAL: -0.3,
            SafetyAlertPriority.HIGH: -0.2,
            SafetyAlertPriority.MEDIUM: -0.1,
            SafetyAlertPriority.LOW: -0.05
        }
        
        violation_multiplier = {
            ChildSafetyViolationType.SELF_HARM: 2.0,
            ChildSafetyViolationType.INAPPROPRIATE_CONTENT: 1.5,
            ChildSafetyViolationType.UNSAFE_INTERACTION: 1.2,
            ChildSafetyViolationType.DATA_PRIVACY_VIOLATION: 1.3,
            ChildSafetyViolationType.UNAUTHORIZED_DATA_ACCESS: 1.4
        }
        
        impact = base_impact.get(incident.severity_level, -0.05)
        multiplier = violation_multiplier.get(incident.incident_type, 1.0)
        
        return impact * multiplier
    
    def _get_notification_title(self, incident: ChildSafetyIncident) -> str:
        """Generate notification title based on incident."""
        severity_emoji = {
            SafetyAlertPriority.CRITICAL: "🚨",
            SafetyAlertPriority.HIGH: "⚠️",
            SafetyAlertPriority.MEDIUM: "⚡",
            SafetyAlertPriority.LOW: "📢"
        }
        
        emoji = severity_emoji.get(incident.severity_level, "📢")
        
        if incident.severity_level == SafetyAlertPriority.CRITICAL:
            return f"{emoji} تنبيه أمان حرج لطفلك"
        elif incident.severity_level == SafetyAlertPriority.HIGH:
            return f"{emoji} تنبيه أمان مهم لطفلك"
        else:
            return f"{emoji} إشعار أمان لطفلك"
    
    def _get_notification_body(self, incident: ChildSafetyIncident) -> str:
        """Generate notification body based on incident."""
        violation_messages = {
            ChildSafetyViolationType.INAPPROPRIATE_CONTENT: "تم رصد محتوى غير مناسب",
            ChildSafetyViolationType.UNSAFE_INTERACTION: "تم رصد تفاعل غير آمن",
            ChildSafetyViolationType.SELF_HARM: "تم رصد إشارات إيذاء النفس - يتطلب تدخل فوري",
            ChildSafetyViolationType.DATA_PRIVACY_VIOLATION: "تم رصد انتهاك لخصوصية البيانات",
            ChildSafetyViolationType.SUSPICIOUS_BEHAVIOR: "تم رصد سلوك مشبوه",
            ChildSafetyViolationType.TECHNICAL_FAILURE: "خطأ تقني في نظام الأمان"
        }
        
        base_message = violation_messages.get(incident.incident_type, "تم رصد حادثة أمان")
        
        if incident.severity_level == SafetyAlertPriority.CRITICAL:
            return f"{base_message}. يتطلب تدخل فوري. اضغط للمراجعة."
        else:
            return f"{base_message}. اضغط لمراجعة التفاصيل."
    
    async def _analyze_compliance_trends(self, coppa_incidents: List, safety_incidents: List) -> Dict[str, Any]:
        """Analyze compliance trends over time."""
        try:
            # Group incidents by day
            daily_incidents = {}
            all_incidents = coppa_incidents + safety_incidents
            
            for incident in all_incidents:
                day_key = incident.timestamp.strftime('%Y-%m-%d')
                if day_key not in daily_incidents:
                    daily_incidents[day_key] = 0
                daily_incidents[day_key] += 1
            
            # Calculate trend
            days = sorted(daily_incidents.keys())
            if len(days) > 1:
                recent_avg = sum(daily_incidents[day] for day in days[-3:]) / 3 if len(days) >= 3 else daily_incidents[days[-1]]
                earlier_avg = sum(daily_incidents[day] for day in days[:3]) / 3 if len(days) >= 3 else daily_incidents[days[0]]
                
                trend = "increasing" if recent_avg > earlier_avg else "decreasing" if recent_avg < earlier_avg else "stable"
            else:
                trend = "stable"
            
            return {
                "trend": trend,
                "daily_incidents": daily_incidents,
                "total_days": len(days),
                "avg_daily_incidents": sum(daily_incidents.values()) / len(days) if days else 0,
                "summary": f"Compliance incidents are {trend} over the past week."
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing compliance trends: {e}")
            return {"trend": "unknown", "summary": "Unable to analyze trends due to data error."}
    
    def _generate_compliance_recommendations(self, compliance_rate: float, breached_incidents: int, pending_incidents: int) -> List[str]:
        """Generate compliance recommendations based on metrics."""
        recommendations = []
        
        if compliance_rate < 90:
            recommendations.append("Strengthen COPPA compliance monitoring and training")
            recommendations.append("Review and update data collection policies")
        
        if breached_incidents > 0:
            recommendations.append("Investigate and address critical compliance breaches immediately")
            recommendations.append("Implement additional safeguards to prevent future breaches")
        
        if pending_incidents > 5:
            recommendations.append("Increase compliance team capacity to handle incident backlog")
            recommendations.append("Prioritize resolution of high-severity pending incidents")
        
        if compliance_rate >= 95 and breached_incidents == 0:
            recommendations.append("Maintain current compliance practices")
            recommendations.append("Continue monitoring for emerging compliance risks")
        
        return recommendations
    
    async def _store_compliance_report(self, report_data: Dict[str, Any]):
        """Store compliance report in database."""
        try:
            from src.infrastructure.database.database_manager import get_db
            
            async with get_db() as db:
                await db.execute("""
                    INSERT INTO coppa_compliance_reports 
                    (report_id, report_type, period_start, period_end, compliance_rate, 
                     total_incidents, resolved_incidents, report_data, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                report_data["report_id"],
                report_data["report_type"],
                report_data["period"]["start_date"],
                report_data["period"]["end_date"],
                report_data["compliance_metrics"]["overall_compliance_rate"],
                report_data["compliance_metrics"]["total_incidents"],
                report_data["compliance_metrics"]["resolved_incidents"],
                json.dumps(report_data),
                datetime.utcnow()
                )
                
        except Exception as e:
            self.logger.error(f"Failed to store compliance report: {e}")
    
    async def _update_parent_compliance_dashboards(self, report_data: Dict[str, Any]):
        """Update parent dashboards with compliance information."""
        try:
            from src.adapters.dashboard.parent_dashboard import ParentDashboard
            
            dashboard = ParentDashboard()
            
            # Create summary for parents
            parent_summary = {
                "compliance_status": "excellent" if report_data["compliance_metrics"]["overall_compliance_rate"] >= 95 else "good" if report_data["compliance_metrics"]["overall_compliance_rate"] >= 85 else "needs_attention",
                "safety_score": report_data["compliance_metrics"]["overall_compliance_rate"],
                "recent_incidents": report_data["compliance_metrics"]["total_incidents"],
                "all_clear": report_data["compliance_metrics"]["breached_incidents"] == 0,
                "last_updated": report_data["generated_at"]
            }
            
            await dashboard.update_compliance_summary(parent_summary)
            
        except Exception as e:
            self.logger.error(f"Failed to update parent dashboards: {e}")
    
    async def _schedule_next_weekly_report(self):
        """Schedule next weekly COPPA report generation."""
        try:
            # This would integrate with a task scheduler like Celery or similar
            next_week = datetime.utcnow() + timedelta(days=7)
            next_week = next_week.replace(hour=9, minute=0, second=0, microsecond=0)  # Schedule for 9 AM
            
            self.logger.info(f"Next weekly COPPA report scheduled for {next_week.isoformat()}")
            
            # In a real implementation, this would create a scheduled task
            # For now, we'll just log the scheduling
            
        except Exception as e:
            self.logger.error(f"Failed to schedule next weekly report: {e}")


# Global child safety monitor instance
child_safety_monitor = ChildSafetyMonitor()


# Convenience functions for reporting incidents
async def report_inappropriate_content(
    child_id: str,
    content: str,
    confidence_score: float,
    session_id: str,
    **kwargs
) -> ChildSafetyIncident:
    """Report inappropriate content incident."""
    return await child_safety_monitor.report_safety_incident(
        violation_type=ChildSafetyViolationType.INAPPROPRIATE_CONTENT,
        child_id=child_id,
        session_id=session_id,
        content_summary=content,
        ai_confidence_score=confidence_score,
        **kwargs
    )


async def report_personal_info_request(
    child_id: str,
    content: str,
    confidence_score: float,
    session_id: str,
    **kwargs
) -> ChildSafetyIncident:
    """Report personal information request incident."""
    return await child_safety_monitor.report_safety_incident(
        violation_type=ChildSafetyViolationType.PERSONAL_INFO_REQUEST,
        child_id=child_id,
        session_id=session_id,
        content_summary=content,
        ai_confidence_score=confidence_score,
        **kwargs
    )


async def report_unauthorized_data_collection(
    data_type: str,
    collection_method: str,
    consent_status: str,
    child_id: Optional[str] = None,
    **kwargs
) -> COPPAComplianceIncident:
    """Report unauthorized data collection incident."""
    return await child_safety_monitor.report_coppa_violation(
        violation_type=COPPAViolationType.UNAUTHORIZED_DATA_COLLECTION,
        data_type=data_type,
        collection_method=collection_method,
        consent_status=consent_status,
        child_id=child_id,
        **kwargs
    )


async def report_insufficient_parental_consent(
    data_type: str,
    collection_method: str,
    consent_status: str,
    child_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    **kwargs
) -> COPPAComplianceIncident:
    """Report insufficient parental consent incident."""
    return await child_safety_monitor.report_coppa_violation(
        violation_type=COPPAViolationType.INSUFFICIENT_PARENTAL_CONSENT,
        data_type=data_type,
        collection_method=collection_method,
        consent_status=consent_status,
        child_id=child_id,
        parent_id=parent_id,
        **kwargs
    )
