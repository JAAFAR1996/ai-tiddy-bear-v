"""
Child Data Transfer Objects for AI Teddy Bear

This module defines COPPA-compliant data structures for representing child information throughout the application.
All child data handling follows strict privacy and safety regulations to ensure legal compliance and child protection.

COPPA Compliance Features:
- Age validation (3-13 years only)
- Parental consent tracking
- Data minimization principles
- Secure data handling

Security Features:
- PII encryption at rest
- Access logging and audit trails
- Data retention limits (90 days)
- Automatic data purging

Notes:
- Name field is encrypted using Fernet. Encryption can be triggered via encrypt_name().
- All validation failures are logged for audit trail.
- Use ChildData.demo() for safe test/demo objects.
- The dataclass is immutable (frozen=True) for safety.
- Use to_dict() and to_public_dict() for safe serialization.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4
import logging


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChildData:
    """COPPA-Compliant Child Data Transfer Object.

    Represents child information in compliance with the Children's Online
    Privacy Protection Act (COPPA). This class enforces strict data protection
    standards and privacy requirements for children under 13 years of age.
    """

    id: UUID = field(metadata={"description": "Unique child identifier"})
    name: str = field(metadata={"description": "Child name (will be encrypted)"})
    age: int = field(
        metadata={"description": "Child age (3-13 years, COPPA compliant)"}
    )
    preferences: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "Child preferences and settings"},
    )
    parent_id: UUID | None = field(
        default=None, metadata={"description": "Parent/guardian identifier"}
    )
    consent_granted: bool = field(
        default=False, metadata={"description": "Parental consent status"}
    )
    consent_date: datetime | None = field(
        default=None, metadata={"description": "Consent grant timestamp"}
    )
    data_created: datetime = field(
        default_factory=datetime.utcnow,
        metadata={"description": "Data creation timestamp"},
    )
    last_interaction: datetime | None = field(
        default=None, metadata={"description": "Last interaction timestamp"}
    )
    encrypted_data: bool = field(
        default=False, metadata={"description": "Data encryption status"}
    )

    def __post_init__(self):
        # Age validation for COPPA compliance
        if not isinstance(self.age, int) or not (3 <= self.age <= 13):
            logger.warning(f"COPPA Violation: Invalid child age: {self.age}")
            raise ValueError(
                f"COPPA Violation: Child age must be between 3-13 years. Received age: {self.age}"
            )

        # Name validation
        if not self.name or not self.name.strip():
            logger.warning("Child name cannot be empty")
            raise ValueError("Child name cannot be empty")
        if len(self.name.strip()) > 100:
            logger.warning("Child name too long (max 100 characters)")
            raise ValueError("Child name too long (max 100 characters)")

        # Parental consent validation for children under 13
        if self.age < 13:
            if not self.parent_id:
                logger.warning("Missing parent ID for child under 13")
                raise ValueError(
                    "COPPA Compliance: Parent ID required for children under 13"
                )
            if not self.consent_granted:
                logger.warning("Parental consent not granted for child under 13")
                raise ValueError(
                    "COPPA Compliance: Parental consent required for children under 13"
                )
            if not self.consent_date:
                logger.warning("Consent date missing when consent is granted")
                raise ValueError(
                    "COPPA Compliance: Consent date required when consent is granted"
                )

        # Data retention check (90 days maximum)
        if self.data_created:
            days_since_creation = (datetime.utcnow() - self.data_created).days
            if days_since_creation > 90:
                logger.warning(
                    f"COPPA Compliance: Child data expired after 90 days. Data age: {days_since_creation} days"
                )
                raise ValueError(
                    f"COPPA Compliance: Child data expired after 90 days. Data age: {days_since_creation} days"
                )

    def encrypt_name(self) -> "ChildData":
        """Return a new ChildData instance with the name encrypted using unified encryption service."""
        from src.utils.crypto_utils import EncryptionService
        service = EncryptionService()
        encrypted_name = service.encrypt_message_content(self.name)
        # Return a new instance with encrypted name and encrypted_data=True
        return self.__class__(
            id=self.id,
            name=encrypted_name,
            age=self.age,
            preferences=self.preferences,
            parent_id=self.parent_id,
            consent_granted=self.consent_granted,
            consent_date=self.consent_date,
            data_created=self.data_created,
            last_interaction=self.last_interaction,
            encrypted_data=True,
        )

    def decrypt_name(self) -> str:
        """Decrypt the name field using unified encryption service and return the plaintext name."""
        from src.utils.crypto_utils import EncryptionService
        service = EncryptionService()
        try:
            return service.decrypt_message_content(self.name)
        except Exception:
            logger.error(
                "Failed to decrypt child name: Invalid encryption key or data."
            )
            return ""

    def to_dict(self) -> dict:
        """Return a dict representation of the object (including all fields)."""
        return {
            "id": str(self.id),
            "name": self.name,
            "age": self.age,
            "preferences": self.preferences,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "consent_granted": self.consent_granted,
            "consent_date": (
                self.consent_date.isoformat() if self.consent_date else None
            ),
            "data_created": self.data_created.isoformat(),
            "last_interaction": (
                self.last_interaction.isoformat() if self.last_interaction else None
            ),
            "encrypted_data": self.encrypted_data,
        }

    def to_public_dict(self) -> dict:
        """Return a dict representation with sensitive fields removed or masked."""
        return {
            "id": str(self.id),
            "age": self.age,
            "preferences": self.preferences,
            "consent_granted": self.consent_granted,
            "data_created": self.data_created.isoformat(),
            "last_interaction": (
                self.last_interaction.isoformat() if self.last_interaction else None
            ),
        }

    @classmethod
    def demo(cls) -> "ChildData":
        """Create a demo/test ChildData object (for testing only)."""
        return cls(
            id=uuid4(),
            name="Test Child",
            age=10,
            preferences={},
            parent_id=uuid4(),
            consent_granted=True,
            consent_date=datetime.utcnow(),
            data_created=datetime.utcnow(),
            last_interaction=None,
            encrypted_data=False,
        )

    def should_purge_data(self) -> bool:
        """Determine if child data should be automatically purged."""
        if not self.data_created:
            return False

        days_since_creation = (datetime.utcnow() - self.data_created).days
        return days_since_creation >= 90
