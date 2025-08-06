from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any


@dataclass
class AIResponse:
    """
    Unified AI response DTO for all business, API, and safety logic.
    Includes all fields required for production, safety, and test compatibility.
    """

    # --- Core AI response fields ---
    content: str = field(
        metadata={"description": "AI generated text response (required)"}
    )
    confidence: float = field(
        default=1.0, metadata={"description": "Model confidence score (0-1)"}
    )
    timestamp: datetime = field(
        default_factory=datetime.now,
        metadata={"description": "Response creation timestamp"},
    )
    model_used: str = field(
        default="gpt-4-turbo-preview", metadata={"description": "AI model identifier"}
    )
    metadata: Optional[dict[str, Any]] = field(
        default=None,
        metadata={
            "description": "Additional metadata (processing_time, safety_checked, personalized, etc.)"
        },
    )
    audio_url: Optional[str] = field(
        default=None,
        metadata={"description": "URL to generated audio response (if any)"},
    )

    # --- Safety & compliance fields ---
    safe: bool = field(
        default=True, metadata={"description": "Content safety validation result"}
    )
    safety_score: float = field(
        default=1.0, metadata={"description": "Detailed safety score (0.0-1.0)"}
    )
    moderation_flags: list[str] = field(
        default_factory=list, metadata={"description": "Content moderation warnings"}
    )
    age_appropriate: bool = field(
        default=True, metadata={"description": "COPPA age appropriateness"}
    )
    conversation_id: Optional[str] = field(
        default=None, metadata={"description": "Conversation tracking ID"}
    )

    # --- Optional advanced fields (for future extensibility) ---
    emotion: Optional[str] = field(
        default=None,
        metadata={"description": "Detected emotion (happy, sad, excited, etc.)"},
    )
    sentiment: Optional[float] = field(
        default=None,
        metadata={
            "description": "Sentiment score from -1.0 (negative) to 1.0 (positive)"
        },
    )
    audio_response: Optional[bytes] = field(
        default=None, metadata={"description": "Binary audio data (if needed)"}
    )

    def __post_init__(self) -> None:
        # --- Core validation ---
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("Response content cannot be empty")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        if not (0.0 <= self.safety_score <= 1.0):
            raise ValueError(
                f"Safety score must be between 0.0 and 1.0, got {self.safety_score}"
            )
        if self.sentiment is not None and not (-1.0 <= self.sentiment <= 1.0):
            raise ValueError(
                f"Sentiment must be between -1.0 and 1.0, got {self.sentiment}"
            )

        # --- Safety logic ---
        if self.safety_score < 0.8:
            self.safe = False
            if "low_safety_score" not in self.moderation_flags:
                self.moderation_flags.append("low_safety_score")
        # COPPA: Always enforce age appropriateness
        if self.age_appropriate is False:
            self.safe = False
            if "not_age_appropriate" not in self.moderation_flags:
                self.moderation_flags.append("not_age_appropriate")
