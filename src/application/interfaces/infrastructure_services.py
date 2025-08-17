"""
Infrastructure Services Interfaces
==================================

This module defines comprehensive interfaces for infrastructure services used
by the AI Teddy Bear application. All interfaces are designed with COPPA compliance
and child safety as primary concerns.

Architecture:
    - Single Responsibility Principle: Each interface has a focused purpose
    - Dependency Inversion: Application layer depends on these abstractions
    - COPPA Compliance: Built-in age validation and parental consent requirements
    - Comprehensive Error Handling: Detailed exception specifications
    - Audit Trail: All child-related operations are logged
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum


# Enums for better type safety and clarity
class DataRetentionStatus(Enum):
    """Status of data retention operations."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VerificationMethod(Enum):
    """Available parent verification methods."""
    EMAIL_VERIFICATION = "email_verification"
    SMS_VERIFICATION = "sms_verification"
    IDENTITY_DOCUMENT = "identity_document"
    CREDIT_CARD = "credit_card"
    PHONE_CALL = "phone_call"


class ConsentType(Enum):
    """Types of COPPA consent required."""
    DATA_COLLECTION = "data_collection"
    DATA_SHARING = "data_sharing"
    MARKETING = "marketing"
    LOCATION_TRACKING = "location_tracking"
    PHOTO_CAPTURE = "photo_capture"
    VOICE_RECORDING = "voice_recording"


class AccessOperation(Enum):
    """Types of access operations requiring verification."""
    READ_PROFILE = "read_profile"
    UPDATE_PROFILE = "update_profile"
    DELETE_PROFILE = "delete_profile"
    EXPORT_DATA = "export_data"
    VIEW_CONVERSATIONS = "view_conversations"
    MODIFY_SETTINGS = "modify_settings"


class ContentSafetyLevel(Enum):
    """Content safety validation levels."""
    STRICT = "strict"      # Ages 3-5
    MODERATE = "moderate"  # Ages 6-9
    STANDARD = "standard"  # Ages 10-13


class AuditEventType(Enum):
    """Types of audit events to log."""
    CHILD_ACCESS = "child_access"
    CONSENT_CHANGE = "consent_change"
    DATA_EXPORT = "data_export"
    DATA_DELETION = "data_deletion"
    SAFETY_VIOLATION = "safety_violation"
    AUTHENTICATION = "authentication"


# Data classes for structured return types
class DataRetentionInfo:
    """Information about data retention scheduling."""
    def __init__(
        self,
        child_id: str,
        scheduled_date: datetime,
        retention_days: int,
        status: DataRetentionStatus,
        export_url: Optional[str] = None
    ):
        self.child_id = child_id
        self.scheduled_date = scheduled_date
        self.retention_days = retention_days
        self.status = status
        self.export_url = export_url


class ContentFilterResult:
    """Result of content filtering operation."""
    def __init__(
        self,
        is_safe: bool,
        safety_score: float,
        filtered_content: str,
        violations: List[str],
        safety_level: ContentSafetyLevel,
        metadata: Dict[str, Any]
    ):
        self.is_safe = is_safe
        self.safety_score = safety_score  # 0.0 to 1.0
        self.filtered_content = filtered_content
        self.violations = violations
        self.safety_level = safety_level
        self.metadata = metadata


class VerificationResult:
    """Result of parent identity verification."""
    def __init__(
        self,
        is_verified: bool,
        confidence_score: float,
        method_used: VerificationMethod,
        verification_id: str,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.is_verified = is_verified
        self.confidence_score = confidence_score
        self.method_used = method_used
        self.verification_id = verification_id
        self.expires_at = expires_at
        self.metadata = metadata or {}


# ============================================================================
# DATA RETENTION SERVICE
# ============================================================================

class IDataRetentionService(ABC):
    """
    Service for managing COPPA-compliant data retention and deletion.
    
    Responsibilities:
    - Schedule automatic data deletion according to COPPA requirements
    - Export child data for parental access
    - Clean up expired data with audit trails
    - Notify parents before data deletion
    
    COPPA Requirements:
    - Parents must be notified before data deletion
    - Data export must be available before deletion
    - Audit logs must be maintained for all operations
    """
    
    @abstractmethod
    async def schedule_deletion(
        self,
        child_id: str,
        retention_days: int = 365,
        parent_email: Optional[str] = None,
        notify_before_days: int = 30
    ) -> DataRetentionInfo:
        """
        Schedule child data for deletion after retention period.
        
        Args:
            child_id: Unique identifier for the child (must be valid COPPA age 3-13)
            retention_days: Number of days to retain data (default: 365, max: 1095)
            parent_email: Parent email for notifications (required for COPPA)
            notify_before_days: Days before deletion to notify parent (default: 30)
            
        Returns:
            DataRetentionInfo: Scheduling information and export URL
            
        Raises:
            ValueError: If child_id is invalid or retention_days exceeds limits
            COPPAComplianceError: If parental consent is not verified
            ServiceUnavailableError: If scheduling service is unavailable
            
        COPPA Compliance:
            - Verifies child age is 3-13 years
            - Requires valid parental consent
            - Creates audit log entry
        """
        pass
    
    @abstractmethod 
    async def export_child_data(
        self,
        child_id: str,
        parent_id: str,
        export_format: str = "json",
        include_conversations: bool = True,
        include_preferences: bool = True,
        include_usage_stats: bool = False
    ) -> str:
        """
        Export all child data for parental access.
        
        Args:
            child_id: Child identifier
            parent_id: Parent identifier (must have verified access)
            export_format: Data format ("json", "csv", "pdf")
            include_conversations: Include conversation history
            include_preferences: Include child preferences
            include_usage_stats: Include usage statistics
            
        Returns:
            str: Secure download URL (expires in 24 hours)
            
        Raises:
            PermissionError: If parent doesn't have access to child
            ValueError: If export_format is unsupported
            DataNotFoundError: If child data doesn't exist
            ExportError: If export generation fails
            
        Security:
            - URL is signed and expires in 24 hours
            - All data is encrypted during export
            - Access is logged for audit purposes
        """
        pass
    
    @abstractmethod
    async def delete_expired_data(
        self, 
        batch_size: int = 100,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Delete data that has exceeded retention period.
        
        Args:
            batch_size: Number of records to process per batch
            dry_run: If True, only simulate deletion without actual removal
            
        Returns:
            Dict containing:
                - deleted_child_ids: List[str] - Successfully deleted child IDs
                - failed_deletions: List[Dict] - Failed deletions with errors
                - total_processed: int - Total records processed
                - execution_time: float - Time taken in seconds
                
        Raises:
            DatabaseError: If database operations fail
            
        Audit:
            - Logs all deletion operations
            - Creates backup before deletion (if configured)
            - Notifies monitoring systems
        """
        pass
    
    @abstractmethod
    async def get_retention_status(self, child_id: str) -> Optional[DataRetentionInfo]:
        """
        Get current retention status for a child.
        
        Args:
            child_id: Child identifier
            
        Returns:
            DataRetentionInfo if scheduled, None if not scheduled
            
        Raises:
            ValueError: If child_id is invalid
        """
        pass


# ============================================================================
# PARENT VERIFICATION SERVICE  
# ============================================================================

class IParentVerificationService(ABC):
    """
    Service for verifying parent identity for COPPA compliance.
    
    Responsibilities:
    - Verify parent identity using multiple methods
    - Manage verification status and expiration
    - Provide fraud detection and prevention
    - Maintain verification audit trails
    
    COPPA Requirements:
    - Must use verifiable parental consent methods
    - Identity verification must be logged
    - Support multiple verification methods
    """
    
    @abstractmethod
    async def verify_parent_identity(
        self,
        parent_id: str,
        verification_method: VerificationMethod,
        verification_data: Dict[str, Any],
        child_id: Optional[str] = None
    ) -> VerificationResult:
        """
        Verify parent identity using specified method.
        
        Args:
            parent_id: Parent identifier
            verification_method: Method to use for verification
            verification_data: Data required for verification (method-specific)
            child_id: Optional child ID for context
            
        Verification Data by Method:
            EMAIL_VERIFICATION: {"email": str, "verification_code": str}
            SMS_VERIFICATION: {"phone": str, "verification_code": str}
            IDENTITY_DOCUMENT: {"document_type": str, "document_data": bytes}
            CREDIT_CARD: {"card_number": str, "exp_date": str, "cvv": str}
            PHONE_CALL: {"phone": str, "verification_code": str}
            
        Returns:
            VerificationResult: Detailed verification result
            
        Raises:
            ValueError: If verification_data is invalid for method
            VerificationError: If verification fails
            RateLimitError: If too many attempts made
            ServiceUnavailableError: If verification service is down
            
        Security:
            - All verification attempts are logged
            - Rate limiting prevents abuse
            - Sensitive data is encrypted
        """
        pass
    
    @abstractmethod
    async def get_verification_methods(
        self,
        parent_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available verification methods for parent.
        
        Args:
            parent_id: Optional parent ID for personalized methods
            
        Returns:
            List of available methods with details:
            [
                {
                    "method": VerificationMethod,
                    "name": str,
                    "description": str,
                    "requirements": List[str],
                    "estimated_time": str,
                    "is_available": bool
                }
            ]
        """
        pass
    
    @abstractmethod
    async def get_verification_status(self, parent_id: str) -> Dict[str, Any]:
        """
        Get current verification status for parent.
        
        Args:
            parent_id: Parent identifier
            
        Returns:
            Dict containing:
                - is_verified: bool
                - verification_level: str
                - verified_methods: List[VerificationMethod]
                - expires_at: Optional[datetime]
                - last_verified: Optional[datetime]
        """
        pass
    
    @abstractmethod
    async def revoke_verification(
        self,
        parent_id: str,
        reason: str,
        revoked_by: str
    ) -> bool:
        """
        Revoke parent verification status.
        
        Args:
            parent_id: Parent identifier
            reason: Reason for revocation
            revoked_by: Who initiated the revocation
            
        Returns:
            True if successfully revoked
            
        Raises:
            ValueError: If parent_id is invalid
            PermissionError: If revoked_by lacks permission
        """
        pass


# ============================================================================
# AUDIT LOGGING SERVICE
# ============================================================================

class IAuditLogger(ABC):
    """
    Service for comprehensive audit logging of child-related operations.
    
    Responsibilities:
    - Log all child data access
    - Track consent changes
    - Record safety violations
    - Provide audit trail queries
    
    COPPA Requirements:
    - All child data access must be logged
    - Logs must be tamper-proof
    - Retention period must comply with regulations
    """
    
    @abstractmethod
    async def log_child_access(
        self,
        parent_id: str,
        child_id: str,
        action: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Log child data access attempt.
        
        Args:
            parent_id: Parent identifier
            child_id: Child identifier
            action: Action attempted (AccessOperation enum)
            ip_address: Client IP address
            user_agent: Client user agent
            success: Whether action succeeded
            details: Additional details about the action
            session_id: Optional session identifier
            
        Returns:
            str: Audit log entry ID
            
        Raises:
            ValueError: If required parameters are invalid
            AuditError: If logging fails
            
        Security:
            - All entries are immutable
            - Includes cryptographic integrity checks
            - PII is encrypted in logs
        """
        pass
    
    @abstractmethod
    async def log_consent_change(
        self,
        parent_id: str,
        child_id: str,
        consent_type: ConsentType,
        action: str,
        old_value: Optional[bool],
        new_value: bool,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> str:
        """
        Log parental consent changes.
        
        Args:
            parent_id: Parent identifier
            child_id: Child identifier
            consent_type: Type of consent changed
            action: Action taken ("granted", "revoked", "modified")
            old_value: Previous consent value
            new_value: New consent value
            metadata: Additional context about the change
            ip_address: Client IP address
            
        Returns:
            str: Audit log entry ID
            
        COPPA Compliance:
            - All consent changes must be traceable
            - Includes legal basis for processing
            - Maintains complete audit trail
        """
        pass
    
    @abstractmethod
    async def log_safety_violation(
        self,
        child_id: str,
        violation_type: str,
        content: str,
        severity: str,
        action_taken: str,
        detected_by: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log content safety violations.
        
        Args:
            child_id: Child identifier
            violation_type: Type of violation detected
            content: Violating content (may be redacted)
            severity: Severity level ("low", "medium", "high", "critical")
            action_taken: Action taken in response
            detected_by: System/service that detected violation
            metadata: Additional violation details
            
        Returns:
            str: Audit log entry ID
            
        Child Safety:
            - Enables pattern analysis
            - Supports system improvements
            - Required for compliance reporting
        """
        pass
    
    @abstractmethod
    async def query_audit_logs(
        self,
        child_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Query audit logs with filtering.
        
        Args:
            child_id: Filter by child ID
            parent_id: Filter by parent ID
            event_type: Filter by event type
            start_date: Filter from this date
            end_date: Filter to this date
            limit: Maximum results to return
            offset: Results offset for pagination
            
        Returns:
            Dict containing:
                - entries: List[Dict] - Audit log entries
                - total_count: int - Total matching entries
                - has_more: bool - More results available
                
        Raises:
            PermissionError: If caller lacks audit access
            ValueError: If query parameters are invalid
        """
        pass


# ============================================================================
# ACCESS CONTROL SERVICE
# ============================================================================

class IAccessControlService(ABC):
    """
    Service for managing parent-child access relationships.
    
    Responsibilities:
    - Verify parent access to child data
    - Manage access permissions
    - Handle access delegation
    - Audit access attempts
    
    Security:
    - Principle of least privilege
    - Time-limited access tokens
    - Multi-factor authentication support
    """
    
    @abstractmethod
    async def verify_parent_child_access(
        self,
        parent_id: str,
        child_id: str,
        operation: AccessOperation,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Verify parent has access to perform operation on child data.
        
        Args:
            parent_id: Parent identifier
            child_id: Child identifier  
            operation: Operation to verify access for
            context: Additional context (IP, session, etc.)
            
        Returns:
            Dict containing:
                - has_access: bool - Whether access is granted
                - access_level: str - Level of access ("read", "write", "admin")
                - expires_at: Optional[datetime] - When access expires
                - restrictions: List[str] - Any access restrictions
                - reason: str - Reason for access decision
                
        Raises:
            ValueError: If parameters are invalid
            AuthenticationError: If parent is not authenticated
            
        Security:
            - All access attempts are logged
            - Context-aware access decisions
            - Time and location restrictions
        """
        pass
    
    @abstractmethod
    async def get_parent_children(
        self,
        parent_id: str,
        include_inactive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all children accessible by parent.
        
        Args:
            parent_id: Parent identifier
            include_inactive: Include deactivated children
            
        Returns:
            List of child information:
            [
                {
                    "child_id": str,
                    "name": str,  # May be redacted
                    "age": int,
                    "access_level": str,
                    "is_active": bool,
                    "created_at": datetime,
                    "last_accessed": Optional[datetime]
                }
            ]
            
        Raises:
            AuthenticationError: If parent is not authenticated
            PermissionError: If parent lacks list permission
        """
        pass
    
    @abstractmethod
    async def grant_access(
        self,
        parent_id: str,
        child_id: str,
        access_level: str,
        granted_by: str,
        expires_at: Optional[datetime] = None,
        restrictions: Optional[List[str]] = None
    ) -> bool:
        """
        Grant parent access to child data.
        
        Args:
            parent_id: Parent identifier
            child_id: Child identifier
            access_level: Level of access to grant
            granted_by: Who is granting access
            expires_at: When access expires
            restrictions: List of access restrictions
            
        Returns:
            True if access granted successfully
            
        Raises:
            PermissionError: If granted_by lacks permission
            ValueError: If parameters are invalid
            
        Audit:
            - Logs access grant with full details
            - Notifies relevant parties
        """
        pass
    
    @abstractmethod
    async def revoke_access(
        self,
        parent_id: str,
        child_id: str,
        revoked_by: str,
        reason: str
    ) -> bool:
        """
        Revoke parent access to child data.
        
        Args:
            parent_id: Parent identifier
            child_id: Child identifier
            revoked_by: Who is revoking access
            reason: Reason for revocation
            
        Returns:
            True if access revoked successfully
            
        Raises:
            PermissionError: If revoked_by lacks permission
            ValueError: If parameters are invalid
        """
        pass


# ============================================================================
# CONTENT FILTER SERVICE
# ============================================================================

class IContentFilterService(ABC):
    """
    Service for filtering content to ensure child safety.
    
    Responsibilities:
    - Filter inappropriate content for children
    - Validate topics and conversations
    - Provide age-appropriate content recommendations
    - Monitor content safety trends
    
    Child Safety:
    - Multi-layered filtering approach
    - Context-aware content analysis
    - Real-time safety monitoring
    - Continuous learning from incidents
    """
    
    @abstractmethod
    async def filter_content(
        self,
        content: str,
        child_age: int,
        context: str = "general",
        additional_filters: Optional[List[str]] = None,
        parent_settings: Optional[Dict[str, Any]] = None
    ) -> ContentFilterResult:
        """
        Filter content for child safety.
        
        Args:
            content: Content to filter
            child_age: Child's age (must be 3-13 for COPPA compliance)
            context: Content context ("conversation", "story", "educational")
            additional_filters: Custom filters to apply
            parent_settings: Parent-configured safety settings
            
        Returns:
            ContentFilterResult: Comprehensive filtering result
            
        Raises:
            ValueError: If child_age is invalid (not 3-13)
            ContentFilterError: If filtering fails
            
        Filtering Process:
            1. Age-appropriate vocabulary check
            2. Inappropriate topic detection
            3. Context analysis
            4. Sentiment analysis
            5. Parent settings application
            6. Final safety score calculation
        """
        pass
    
    @abstractmethod
    async def validate_topic(
        self,
        topic: str,
        child_id: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate if topic is appropriate for child.
        
        Args:
            topic: Topic to validate
            child_id: Child identifier (for age and settings)
            context: Optional context for validation
            
        Returns:
            Dict containing:
                - is_appropriate: bool
                - safety_score: float (0.0 to 1.0)
                - age_appropriate: bool
                - reasons: List[str] - Reasons for decision
                - alternatives: List[str] - Alternative topics if inappropriate
                
        Raises:
            ValueError: If topic or child_id is invalid
            
        COPPA Compliance:
            - Validates child age is 3-13
            - Applies parental settings
            - Logs validation attempts
        """
        pass
    
    @abstractmethod
    async def get_content_recommendations(
        self,
        child_age: int,
        interests: List[str],
        context: str = "general",
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get age-appropriate content recommendations.
        
        Args:
            child_age: Child's age
            interests: Child's interests/preferences
            context: Content context
            count: Number of recommendations
            
        Returns:
            List of content recommendations:
            [
                {
                    "content_id": str,
                    "title": str,
                    "description": str,
                    "age_range": str,
                    "safety_score": float,
                    "category": str
                }
            ]
        """
        pass
    
    @abstractmethod
    async def report_safety_incident(
        self,
        child_id: str,
        content: str,
        incident_type: str,
        severity: str,
        reporter: str,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Report a content safety incident.
        
        Args:
            child_id: Child identifier
            content: Problematic content
            incident_type: Type of incident
            severity: Incident severity
            reporter: Who reported the incident
            details: Additional incident details
            
        Returns:
            str: Incident report ID
            
        Process:
            - Creates incident report
            - Triggers safety team notification
            - Updates content filters if needed
            - Logs for compliance reporting
        """
        pass


# ============================================================================
# NOTIFICATION SERVICE
# ============================================================================

class INotificationService(ABC):
    """
    Service for sending notifications to parents and system administrators.
    
    Responsibilities:
    - Send COPPA-required notifications
    - Deliver safety alerts
    - Handle notification preferences
    - Manage delivery tracking
    
    COPPA Requirements:
    - Data deletion warnings
    - Consent change notifications
    - Safety incident alerts
    - Privacy policy updates
    """
    
    @abstractmethod
    async def send_coppa_notification(
        self,
        parent_email: str,
        notification_type: str,
        child_name: str,
        data: Dict[str, Any],
        template: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send COPPA-required notification to parent.
        
        Args:
            parent_email: Parent's email address
            notification_type: Type of notification
            child_name: Child's name (may be redacted)
            data: Notification-specific data
            template: Optional custom template
            
        Returns:
            Dict containing:
                - message_id: str
                - delivery_status: str
                - sent_at: datetime
                - expires_at: Optional[datetime]
                
        Notification Types:
            - "data_deletion_warning"
            - "consent_change"
            - "safety_incident"
            - "privacy_policy_update"
            - "account_activity"
        """
        pass
    
    @abstractmethod
    async def send_safety_alert(
        self,
        recipients: List[str],
        alert_type: str,
        child_id: str,
        severity: str,
        details: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Send safety alert to multiple recipients.
        
        Args:
            recipients: List of recipient emails/IDs
            alert_type: Type of safety alert
            child_id: Child identifier
            severity: Alert severity
            details: Alert details
            
        Returns:
            List of delivery results for each recipient
        """
        pass
    
    @abstractmethod
    async def get_notification_preferences(
        self,
        parent_id: str
    ) -> Dict[str, Any]:
        """
        Get parent's notification preferences.
        
        Args:
            parent_id: Parent identifier
            
        Returns:
            Dict of notification preferences
        """
        pass
    
    @abstractmethod
    async def update_notification_preferences(
        self,
        parent_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Update parent's notification preferences.
        
        Args:
            parent_id: Parent identifier
            preferences: New preferences
            
        Returns:
            True if updated successfully
        """
        pass


# Export all interfaces
__all__ = [
    # Enums
    "DataRetentionStatus",
    "VerificationMethod", 
    "ConsentType",
    "AccessOperation",
    "ContentSafetyLevel",
    "AuditEventType",
    
    # Data Classes
    "DataRetentionInfo",
    "ContentFilterResult",
    "VerificationResult",
    
    # Service Interfaces
    "IDataRetentionService",
    "IParentVerificationService",
    "IAuditLogger",
    "IAccessControlService", 
    "IContentFilterService",
    "INotificationService",
]
