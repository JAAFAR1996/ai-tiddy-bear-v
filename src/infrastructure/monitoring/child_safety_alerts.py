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


class SafetyAlertPriority(Enum):
    """Priority levels for safety alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
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
        # TODO: Integrate with session management system
    
    async def _pause_session(self, session_id: str):
        """Pause a user session for human review."""
        self.logger.warning(f"PAUSING SESSION: {session_id}")
        # TODO: Integrate with session management system
    
    async def _enable_enhanced_monitoring(self, session_id: str):
        """Enable enhanced monitoring for a session."""
        self.logger.info(f"ENABLING ENHANCED MONITORING: {session_id}")
        # TODO: Integrate with monitoring system
    
    async def _flag_account_for_review(self, child_id: str, priority: str):
        """Flag an account for human review."""
        self.logger.warning(f"FLAGGING ACCOUNT FOR {priority.upper()} REVIEW: {child_id}")
        # TODO: Integrate with user management system
    
    async def _queue_for_human_review(self, incident: ChildSafetyIncident):
        """Queue incident for human review."""
        self.logger.info(f"QUEUING FOR HUMAN REVIEW: {incident.incident_id}")
        # TODO: Integrate with review queue system
    
    async def _notify_parent(self, incident: ChildSafetyIncident):
        """Notify parent of safety incident."""
        self.logger.info(f"NOTIFYING PARENT: {incident.parent_id}")
        # TODO: Integrate with notification system
    
    async def _notify_emergency_contacts(self, incident: ChildSafetyIncident):
        """Notify emergency contacts."""
        self.logger.critical(f"NOTIFYING EMERGENCY CONTACTS: {incident.incident_id}")
        # TODO: Implement emergency notification system
    
    async def _notify_child_safety_team(self, incident: ChildSafetyIncident):
        """Notify child safety team."""
        self.logger.critical(f"NOTIFYING CHILD SAFETY TEAM: {incident.incident_id}")
        # TODO: Implement child safety team notification
    
    async def _escalate_incident(self, incident: ChildSafetyIncident, reason: str):
        """Escalate an incident."""
        self.logger.critical(f"ESCALATING INCIDENT {incident.incident_id}: {reason}")
        # TODO: Implement incident escalation
    
    async def _send_compliance_email(self, incident: COPPAComplianceIncident, email: str):
        """Send compliance notification email."""
        self.logger.info(f"SENDING COMPLIANCE EMAIL: {incident.incident_id}")
        # TODO: Implement email notification
    
    async def _send_compliance_slack_notification(self, incident: COPPAComplianceIncident, webhook: str):
        """Send compliance Slack notification."""
        self.logger.info(f"SENDING COMPLIANCE SLACK: {incident.incident_id}")
        # TODO: Implement Slack notification
    
    async def _notify_legal_team_deadline(self, incident: COPPAComplianceIncident, time_left: str):
        """Notify legal team of approaching deadline."""
        self.logger.critical(f"LEGAL TEAM DEADLINE ALERT: {incident.incident_id} - {time_left} remaining")
        # TODO: Implement legal team notification
    
    async def _send_deadline_warning(self, incident: COPPAComplianceIncident, time_left: str):
        """Send deadline warning."""
        self.logger.warning(f"DEADLINE WARNING: {incident.incident_id} - {time_left} remaining")
        # TODO: Implement deadline warning system
    
    async def _handle_deadline_breach(self, incident: COPPAComplianceIncident):
        """Handle deadline breach."""
        self.logger.critical(f"DEADLINE BREACHED: {incident.incident_id}")
        # TODO: Implement deadline breach handling
    
    async def _generate_daily_safety_report(self):
        """Generate daily child safety report."""
        self.logger.info("GENERATING DAILY SAFETY REPORT")
        # TODO: Implement daily reporting
    
    async def _generate_weekly_coppa_report(self):
        """Generate weekly COPPA compliance report."""
        self.logger.info("GENERATING WEEKLY COPPA REPORT")
        # TODO: Implement weekly reporting
    
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