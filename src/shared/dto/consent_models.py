from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional
from pydantic import model_validator, field_validator
import uuid


class ConsentType(str, Enum):
    """Enum for different types of consent."""

    DATA_COLLECTION = "data_collection"
    VOICE_RECORDING = "voice_recording"
    MARKETING_EMAILS = "marketing_emails"


class ConsentStatus(str, Enum):
    """Enum for the status of consent."""

    PENDING = "pending"
    GRANTED = "granted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ConsentRecord(BaseModel):
    """Pydantic model for a consent record."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Immutable record ID"
    )
    child_id: str = Field(..., description="Immutable child ID")
    parent_id: str = Field(..., description="Immutable parent ID")
    consent_type: ConsentType
    status: ConsentStatus = ConsentStatus.PENDING
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    version: str = "1.0"
    updated_by: Optional[str] = Field(
        None, description="User/admin who modified the consent record"
    )
    audit_id: Optional[str] = Field(None, description="Audit trail correlation ID")

    @model_validator(mode='before')
    @classmethod
    def validate_timestamps(cls, values):
        status = values.get("status")
        granted_at = values.get("granted_at")
        revoked_at = values.get("revoked_at")
        expires_at = values.get("expires_at")
        from datetime import datetime

        # Auto-set timestamps if not provided (for convenience in testing)
        if status == ConsentStatus.GRANTED and not granted_at:
            values["granted_at"] = datetime.utcnow()
        if status == ConsentStatus.REVOKED and not revoked_at:
            values["revoked_at"] = datetime.utcnow()
        if expires_at and expires_at < datetime.utcnow():
            values["status"] = ConsentStatus.EXPIRED
        return values

    @field_validator("id", "child_id", "parent_id", mode='before')
    @classmethod
    def validate_required_fields(cls, v):
        # Validate that required string fields are not empty
        if isinstance(v, str) and v.strip() == "":
            raise ValueError("Field cannot be empty string")
        return v

    def to_dict_sanitized(self) -> dict:
        """Return a dict with sensitive fields (parent_id, audit_id) removed."""
        data = self.dict()
        data.pop("parent_id", None)
        data.pop("audit_id", None)
        return data

    class Config:
        use_enum_values = True
