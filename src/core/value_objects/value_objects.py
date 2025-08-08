"""Core value objects for AI Teddy Bear application"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


def _get_config_value(attr_name: str, default_value):
    """Get configuration value with fallback to default."""
    try:
        from src.infrastructure.config.config_provider import get_config

        def get_config_value(attr_name, default_value=None, config=None):
            config = config or get_config()
            return getattr(config, attr_name, default_value)

        return get_config_value(attr_name, default_value)
    except (ImportError, Exception):
        return default_value


class ContentFilterLevel(Enum):
    """Content filtering strictness levels."""

    STRICT = "strict"
    MODERATE = "moderate"
    RELAXED = "relaxed"


class SafetyLevel(Enum):
    """Safety threat severity levels (numeric scale)."""

    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @classmethod
    def from_score(cls, score: float) -> "SafetyLevel":
        """Map a numeric score to a safety severity level."""
        if score >= 0.9:
            return cls.SAFE
        elif score >= 0.7:
            return cls.LOW
        elif score >= 0.5:
            return cls.MEDIUM
        elif score >= 0.3:
            return cls.HIGH
        else:
            return cls.CRITICAL


class AgeGroup(Enum):
    """Age group classifications for content filtering with non-overlapping ranges."""

    # Specific age groups (non-overlapping)
    TODDLER = "toddler"  # 3-4 years (COPPA minimum)
    PRESCHOOL = "preschool"  # 5-6 years
    EARLY_ELEMENTARY = "early_elementary"  # 7-8 years
    LATE_ELEMENTARY = "late_elementary"  # 9-10 years
    MIDDLE_SCHOOL = "middle_school"  # 11-12 years
    PRETEEN = "preteen"  # 13 years

    # Broader categories for convenience
    UNDER_6 = "under_6"  # 3-5 years
    UNDER_9 = "under_9"  # 3-8 years
    UNDER_13 = "under_13"  # 3-12 years

    @classmethod
    def from_age(cls, age: int) -> "AgeGroup":
        """Get age group from numeric age (COPPA compliant: 3-13 years only)."""
        if age < 3 or age > 13:
            raise ValueError(f"Age {age} is outside COPPA-compliant range (3-13 years)")

        if age <= 4:
            return cls.TODDLER
        elif age <= 6:
            return cls.PRESCHOOL
        elif age <= 8:
            return cls.EARLY_ELEMENTARY
        elif age <= 10:
            return cls.LATE_ELEMENTARY
        elif age <= 12:
            return cls.MIDDLE_SCHOOL
        else:  # age == 13
            return cls.PRETEEN

    @classmethod
    def get_age_range(cls, age_group: "AgeGroup") -> tuple[int, int]:
        """Get the age range (min, max) for an age group."""
        age_ranges = {
            cls.TODDLER: (3, 4),
            cls.PRESCHOOL: (5, 6),
            cls.EARLY_ELEMENTARY: (7, 8),
            cls.LATE_ELEMENTARY: (9, 10),
            cls.MIDDLE_SCHOOL: (11, 12),
            cls.PRETEEN: (13, 13),
            cls.UNDER_6: (3, 5),
            cls.UNDER_9: (3, 8),
            cls.UNDER_13: (3, 12),
        }
        return age_ranges[age_group]

    @classmethod
    def validate_coppa_compliance(cls, age: int) -> bool:
        """Validate age is COPPA compliant (3-13 years)."""
        return 3 <= age <= 13

    @classmethod
    def get_content_restriction_level(cls, age_group: "AgeGroup") -> ContentFilterLevel:
        """Get appropriate content filter level for age group."""
        if age_group in (cls.TODDLER, cls.PRESCHOOL, cls.UNDER_6):
            return ContentFilterLevel.STRICT
        elif age_group in (cls.EARLY_ELEMENTARY, cls.LATE_ELEMENTARY, cls.UNDER_9):
            return ContentFilterLevel.MODERATE
        else:  # Middle school and preteen
            return ContentFilterLevel.RELAXED


@dataclass(frozen=True)
class SafetyScore:
    """Safety score for content validation with immutable violations."""

    score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    violations: tuple[str, ...]

    def __post_init__(self):
        # Validate score
        if not (0.0 <= self.score <= 1.0):
            raise ValueError("score must be between 0.0 and 1.0")

        # Validate confidence
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")

        # Ensure violations is immutable and validated
        if isinstance(self.violations, (list, tuple)):
            for violation in self.violations:
                if not isinstance(violation, str) or not violation.strip():
                    raise ValueError("violations must contain non-empty strings")
            if not isinstance(self.violations, tuple):
                object.__setattr__(self, "violations", tuple(self.violations))
        else:
            raise ValueError("violations must be a list or tuple of strings")

    @property
    def is_safe(self) -> bool:
        """Check if content is safe based on configurable threshold."""
        threshold = _get_config_value("SAFETY_SCORE_THRESHOLD", 0.8)
        return self.score >= threshold and len(self.violations) == 0

    @property
    def severity(self) -> SafetyLevel:
        """Get severity level."""
        return SafetyLevel.from_score(self.score)

    def requires_human_review(self) -> bool:
        """Check if content requires human review based on business rules."""
        # High-risk content always requires review
        if self.severity in (SafetyLevel.HIGH, SafetyLevel.CRITICAL):
            return True

        # Medium severity with violations requires review
        if self.severity == SafetyLevel.MEDIUM and len(self.violations) > 0:
            return True

        # Low confidence scores require review
        if self.confidence < 0.7:
            return True

        return False

    def is_suitable_for_age_group(self, age_group: AgeGroup) -> bool:
        """Check if content is suitable for specific age group."""
        required_filter_level = AgeGroup.get_content_restriction_level(age_group)

        # Strict filtering for younger children
        if required_filter_level == ContentFilterLevel.STRICT:
            return self.severity == SafetyLevel.SAFE and len(self.violations) == 0

        # Moderate filtering for middle children
        elif required_filter_level == ContentFilterLevel.MODERATE:
            return (
                self.severity in (SafetyLevel.SAFE, SafetyLevel.LOW)
                and len(self.violations) <= 1
            )

        # Relaxed filtering for older children
        else:  # RELAXED
            return self.severity != SafetyLevel.CRITICAL


@dataclass(frozen=True)
class EmotionResult:
    """
    Result of emotion analysis for a message or utterance.
    Attributes:
        primary_emotion: The main detected emotion (e.g., 'happy', 'sad').
        confidence: Confidence score for the primary emotion (0.0 - 1.0).
        secondary_emotions: Tuple of other detected emotions (immutable).
    """

    primary_emotion: str
    confidence: float
    secondary_emotions: tuple[str, ...] = None

    def __post_init__(self):
        # Validate primary emotion
        if (
            not isinstance(self.primary_emotion, str)
            or not self.primary_emotion.strip()
        ):
            raise ValueError("primary_emotion must be a non-empty string")

        # Validate confidence
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")

        # Make secondary emotions immutable
        if self.secondary_emotions is None:
            object.__setattr__(self, "secondary_emotions", ())
        else:
            # Validate secondary emotions
            for emotion in self.secondary_emotions:
                if not isinstance(emotion, str) or not emotion.strip():
                    raise ValueError(
                        "secondary_emotions must contain non-empty strings"
                    )
            object.__setattr__(
                self, "secondary_emotions", tuple(self.secondary_emotions)
            )


@dataclass(frozen=True)
class ContentComplexity:
    """Content complexity rating with validation."""

    level: str  # "simple", "moderate", "complex"
    vocabulary_score: float
    sentence_complexity: float
    concept_difficulty: float

    def __post_init__(self):
        # Validate complexity level
        valid_levels = {"simple", "moderate", "complex"}
        if self.level not in valid_levels:
            raise ValueError(f"level must be one of {valid_levels}")

        # Validate all scores are between 0.0 and 1.0
        for field_name, field_value in [
            ("vocabulary_score", self.vocabulary_score),
            ("sentence_complexity", self.sentence_complexity),
            ("concept_difficulty", self.concept_difficulty),
        ]:
            if not (0.0 <= field_value <= 1.0):
                raise ValueError(f"{field_name} must be between 0.0 and 1.0")

    @property
    def is_age_appropriate(self, age: int) -> bool:
        """Check if complexity is appropriate for age using configurable thresholds."""
        simple_threshold = _get_config_value(
            "CONTENT_COMPLEXITY_AGE_THRESHOLD_SIMPLE", 5
        )
        complex_threshold = _get_config_value(
            "CONTENT_COMPLEXITY_AGE_THRESHOLD_COMPLEX", 8
        )

        if age < simple_threshold and self.level != "simple":
            return False
        elif age < complex_threshold and self.level == "complex":
            return False
        return True


@dataclass(frozen=True)
class ChildPreferences:
    """Child preferences for personalized experience with strict validation."""

    favorite_topics: list[str] = None
    favorite_characters: list[str] = None
    favorite_activities: list[str] = None
    interests: list[str] = None
    learning_style: str = "visual"  # visual, auditory, kinesthetic
    language_preference: str = "en"
    voice_speed: float = 1.0
    volume_level: float = 0.8
    age_range: Optional[str] = None  # e.g., "5-7", "8-10"
    audio_enabled: bool = False

    def __post_init__(self):
        # Initialize None lists as empty immutable tuples
        if self.favorite_topics is None:
            object.__setattr__(self, "favorite_topics", ())
        else:
            object.__setattr__(self, "favorite_topics", tuple(self.favorite_topics))

        if self.favorite_characters is None:
            object.__setattr__(self, "favorite_characters", ())
        else:
            object.__setattr__(
                self, "favorite_characters", tuple(self.favorite_characters)
            )

        if self.favorite_activities is None:
            object.__setattr__(self, "favorite_activities", ())
        else:
            object.__setattr__(
                self, "favorite_activities", tuple(self.favorite_activities)
            )

        if self.interests is None:
            object.__setattr__(self, "interests", ())
        else:
            object.__setattr__(self, "interests", tuple(self.interests))

        # Validate all fields
        self._validate()

    def _validate(self):
        """Validate all preference values."""
        # Validate learning style
        valid_learning_styles = {"visual", "auditory", "kinesthetic"}
        if self.learning_style not in valid_learning_styles:
            raise ValueError(f"learning_style must be one of {valid_learning_styles}")

        # Validate language preference (basic ISO 639-1 check)
        if (
            not isinstance(self.language_preference, str)
            or len(self.language_preference) != 2
        ):
            raise ValueError(
                "language_preference must be a 2-character language code (e.g., 'en', 'es')"
            )

        # Validate voice speed using configurable limits
        min_speed = _get_config_value("VOICE_SPEED_MIN", 0.5)
        max_speed = _get_config_value("VOICE_SPEED_MAX", 2.0)
        if not (min_speed <= self.voice_speed <= max_speed):
            raise ValueError(f"voice_speed must be between {min_speed} and {max_speed}")

        # Validate volume level using configurable limits
        min_volume = _get_config_value("VOLUME_LEVEL_MIN", 0.1)
        max_volume = _get_config_value("VOLUME_LEVEL_MAX", 1.0)
        if not (min_volume <= self.volume_level <= max_volume):
            raise ValueError(
                f"volume_level must be between {min_volume} and {max_volume}"
            )

        # Validate age range format if provided
        if self.age_range is not None:
            self._validate_age_range(self.age_range)

        # Validate list contents
        for field_name, field_value in [
            ("favorite_topics", self.favorite_topics),
            ("favorite_characters", self.favorite_characters),
            ("favorite_activities", self.favorite_activities),
            ("interests", self.interests),
        ]:
            if field_value:
                for item in field_value:
                    if not isinstance(item, str) or not item.strip():
                        raise ValueError(f"{field_name} must contain non-empty strings")
                    if len(item) > 50:  # Reasonable limit
                        raise ValueError(
                            f"{field_name} items must be 50 characters or less"
                        )

    @staticmethod
    def _validate_age_range(age_range: str):
        """Validate age range format (e.g., '5-7', '8-10')."""
        import re

        pattern = r"^(\d{1,2})-(\d{1,2})$"
        match = re.match(pattern, age_range)
        if not match:
            raise ValueError("age_range must be in format 'min-max' (e.g., '5-7')")

        min_age, max_age = int(match.group(1)), int(match.group(2))
        if min_age >= max_age:
            raise ValueError("age_range minimum must be less than maximum")
        if not (3 <= min_age <= 13) or not (3 <= max_age <= 13):
            raise ValueError(
                "age_range must be within COPPA-compliant range (3-13 years)"
            )

    @classmethod
    def create_safe_defaults(cls, age: Optional[int] = None) -> "ChildPreferences":
        """Create ChildPreferences with safe default values."""
        age_range = None
        if age is not None:
            if not (3 <= age <= 13):
                raise ValueError(
                    "Age must be within COPPA-compliant range (3-13 years)"
                )
            # Create appropriate age range
            if age <= 6:
                age_range = "3-6"
            elif age <= 10:
                age_range = "7-10"
            else:
                age_range = "11-13"

        return cls(
            favorite_topics=(),
            favorite_characters=(),
            favorite_activities=(),
            interests=(),
            learning_style="visual",
            language_preference="en",
            voice_speed=1.0,
            volume_level=0.8,
            age_range=age_range,
            audio_enabled=False,
        )

    def get_age_appropriate_content_filter(self) -> ContentFilterLevel:
        """Get appropriate content filter level based on age range."""
        if self.age_range is None:
            return ContentFilterLevel.STRICT  # Default to strictest for safety

        # Parse age range to get minimum age
        import re

        match = re.match(r"^(\d{1,2})-(\d{1,2})$", self.age_range)
        if not match:
            return ContentFilterLevel.STRICT

        min_age = int(match.group(1))
        try:
            age_group = AgeGroup.from_age(min_age)
            return AgeGroup.get_content_restriction_level(age_group)
        except ValueError:
            return ContentFilterLevel.STRICT

    def is_session_duration_appropriate(self, session_minutes: int) -> bool:
        """Check if session duration is appropriate for child's age."""
        if self.age_range is None:
            return session_minutes <= 10  # Conservative default

        # Parse age range
        import re

        match = re.match(r"^(\d{1,2})-(\d{1,2})$", self.age_range)
        if not match:
            return session_minutes <= 10

        min_age = int(match.group(1))

        # Age-appropriate session limits (in minutes)
        if min_age <= 4:  # Toddler
            return session_minutes <= 15
        elif min_age <= 6:  # Preschool
            return session_minutes <= 20
        elif min_age <= 8:  # Early elementary
            return session_minutes <= 30
        elif min_age <= 10:  # Late elementary
            return session_minutes <= 45
        else:  # Middle school and preteen
            return session_minutes <= 60

    def requires_parental_supervision(self) -> bool:
        """Check if child requires parental supervision based on preferences."""
        if self.age_range is None:
            return True  # Default to requiring supervision

        # Parse age range
        import re

        match = re.match(r"^(\d{1,2})-(\d{1,2})$", self.age_range)
        if not match:
            return True

        min_age = int(match.group(1))

        # Children under 8 always require supervision
        if min_age < 8:
            return True

        # Audio-enabled sessions require supervision for younger children
        if self.audio_enabled and min_age < 10:
            return True

        return False
