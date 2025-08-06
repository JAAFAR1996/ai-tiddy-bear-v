from dataclasses import dataclass
from uuid import UUID


@dataclass
class ESP32Request:
    """Represents a request from an ESP32 device containing child
    interaction data. Supports multiple input types including audio,
    text, and sensor data while maintaining COPPA compliance and child
    safety requirements.

    Attributes:
        child_id: Unique identifier for the child using the device
        audio_data: Optional audio data from device microphone
        language_code: Optional language preference for response
        text_input: Optional text input for testing/debugging
    """

    child_id: UUID
    audio_data: bytes | None = None
    language_code: str | None = None
    text_input: str | None = None
