"""Comprehensive unit tests for core value objects - 100% coverage"""

import pytest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from src.core.value_objects.value_objects import (
    SafetyLevel,
    AgeGroup,
    SafetyScore,
    EmotionResult,
    ContentComplexity,
    ChildPreferences,
)


class TestSafetyLevel:
    """Test SafetyLevel enum with all mapping methods."""

    def test_safety_level_enum_values(self):
        """Test all enum values are accessible."""
        assert SafetyLevel.STRICT.value == "strict"
        assert SafetyLevel.MODERATE.value == "moderate"
        assert SafetyLevel.RELAXED.value == "relaxed"
        assert SafetyLevel.CRITICAL.value == "critical"
        assert SafetyLevel.HIGH.value == "high"
        assert SafetyLevel.MEDIUM.value == "medium"
        assert SafetyLevel.LOW.value == "low"
        assert SafetyLevel.SAFE.value == "safe"

    def test_from_score_safe_range(self):
        """Test from_score returns SAFE for high scores."""
        assert SafetyLevel.from_score(0.9) == SafetyLevel.SAFE
        assert SafetyLevel.from_score(0.95) == SafetyLevel.SAFE
        assert SafetyLevel.from_score(1.0) == SafetyLevel.SAFE

    def test_from_score_low_range(self):
        """Test from_score returns LOW for moderate scores."""
        assert SafetyLevel.from_score(0.7) == SafetyLevel.LOW
        assert SafetyLevel.from_score(0.8) == SafetyLevel.LOW
        assert SafetyLevel.from_score(0.89) == SafetyLevel.LOW

    def test_from_score_medium_range(self):
        """Test from_score returns MEDIUM for mid-range scores."""
        assert SafetyLevel.from_score(0.5) == SafetyLevel.MEDIUM
        assert SafetyLevel.from_score(0.6) == SafetyLevel.MEDIUM
        assert SafetyLevel.from_score(0.69) == SafetyLevel.MEDIUM

    def test_from_score_high_range(self):
        """Test from_score returns HIGH for low scores."""
        assert SafetyLevel.from_score(0.0) == SafetyLevel.HIGH
        assert SafetyLevel.from_score(0.3) == SafetyLevel.HIGH
        assert SafetyLevel.from_score(0.49) == SafetyLevel.HIGH

    def test_from_score_boundary_conditions(self):
        """Test boundary conditions for score mapping."""
        assert SafetyLevel.from_score(0.5) == SafetyLevel.MEDIUM
        assert SafetyLevel.from_score(0.7) == SafetyLevel.LOW
        assert SafetyLevel.from_score(0.9) == SafetyLevel.SAFE

    def test_from_score_negative_values(self):
        """Test negative scores return HIGH risk."""
        assert SafetyLevel.from_score(-0.1) == SafetyLevel.HIGH
        assert SafetyLevel.from_score(-1.0) == SafetyLevel.HIGH

    def test_from_score_values_over_one(self):
        """Test scores over 1.0 return SAFE."""
        assert SafetyLevel.from_score(1.1) == SafetyLevel.SAFE
        assert SafetyLevel.from_score(2.0) == SafetyLevel.SAFE


class TestAgeGroup:
    """Test AgeGroup enum with age mapping functionality."""

    def test_age_group_enum_values(self):
        """Test all enum values are accessible."""
        assert AgeGroup.TODDLER.value == "toddler"
        assert AgeGroup.PRESCHOOL.value == "preschool"
        assert AgeGroup.EARLY_SCHOOL.value == "early_school"
        assert AgeGroup.ELEMENTARY.value == "elementary"
        assert AgeGroup.MIDDLE_SCHOOL.value == "middle_school"
        assert AgeGroup.LATE_SCHOOL.value == "late_school"
        assert AgeGroup.PRETEEN.value == "preteen"
        assert AgeGroup.UNDER_5.value == "under_5"
        assert AgeGroup.UNDER_8.value == "under_8"
        assert AgeGroup.UNDER_13.value == "under_13"

    def test_elementary_middle_school_alias(self):
        """Test ELEMENTARY is alias for MIDDLE_SCHOOL."""
        assert AgeGroup.ELEMENTARY.value == "elementary"
        assert AgeGroup.MIDDLE_SCHOOL.value == "middle_school"
        # They have different string values but same age mapping

    def test_from_age_toddler_range(self):
        """Test from_age returns TODDLER for ages 0-2."""
        assert AgeGroup.from_age(0) == AgeGroup.TODDLER
        assert AgeGroup.from_age(1) == AgeGroup.TODDLER
        assert AgeGroup.from_age(2) == AgeGroup.TODDLER

    def test_from_age_preschool_range(self):
        """Test from_age returns PRESCHOOL for ages 3-4."""
        assert AgeGroup.from_age(3) == AgeGroup.PRESCHOOL
        assert AgeGroup.from_age(4) == AgeGroup.PRESCHOOL

    def test_from_age_early_school_range(self):
        """Test from_age returns EARLY_SCHOOL for ages 5-6."""
        assert AgeGroup.from_age(5) == AgeGroup.EARLY_SCHOOL
        assert AgeGroup.from_age(6) == AgeGroup.EARLY_SCHOOL

    def test_from_age_middle_school_range(self):
        """Test from_age returns MIDDLE_SCHOOL for ages 7-8."""
        assert AgeGroup.from_age(7) == AgeGroup.MIDDLE_SCHOOL
        assert AgeGroup.from_age(8) == AgeGroup.MIDDLE_SCHOOL

    def test_from_age_late_school_range(self):
        """Test from_age returns LATE_SCHOOL for ages 9-10."""
        assert AgeGroup.from_age(9) == AgeGroup.LATE_SCHOOL
        assert AgeGroup.from_age(10) == AgeGroup.LATE_SCHOOL

    def test_from_age_preteen_range(self):
        """Test from_age returns PRETEEN for ages 11+."""
        assert AgeGroup.from_age(11) == AgeGroup.PRETEEN
        assert AgeGroup.from_age(12) == AgeGroup.PRETEEN
        assert AgeGroup.from_age(13) == AgeGroup.PRETEEN
        assert AgeGroup.from_age(15) == AgeGroup.PRETEEN
        assert AgeGroup.from_age(100) == AgeGroup.PRETEEN

    def test_from_age_boundary_conditions(self):
        """Test boundary conditions for age mapping."""
        assert AgeGroup.from_age(3) == AgeGroup.PRESCHOOL
        assert AgeGroup.from_age(5) == AgeGroup.EARLY_SCHOOL
        assert AgeGroup.from_age(7) == AgeGroup.MIDDLE_SCHOOL
        assert AgeGroup.from_age(9) == AgeGroup.LATE_SCHOOL
        assert AgeGroup.from_age(11) == AgeGroup.PRETEEN

    def test_from_age_negative_values(self):
        """Test negative ages return TODDLER."""
        assert AgeGroup.from_age(-1) == AgeGroup.TODDLER
        assert AgeGroup.from_age(-10) == AgeGroup.TODDLER


class TestSafetyScore:
    """Test SafetyScore frozen dataclass with properties."""

    def test_safety_score_creation(self):
        """Test basic SafetyScore creation."""
        score = SafetyScore(score=0.9, confidence=0.8, violations=[])
        assert score.score == 0.9
        assert score.confidence == 0.8
        assert score.violations == []

    def test_safety_score_with_violations(self):
        """Test SafetyScore with violations list."""
        violations = ["inappropriate_content", "age_unsuitable"]
        score = SafetyScore(score=0.5, confidence=0.7, violations=violations)
        assert score.score == 0.5
        assert score.confidence == 0.7
        assert score.violations == violations

    def test_is_safe_property_true(self):
        """Test is_safe returns True for safe content."""
        score = SafetyScore(score=0.9, confidence=0.8, violations=[])
        assert score.is_safe is True

    def test_is_safe_property_false_low_score(self):
        """Test is_safe returns False for low score."""
        score = SafetyScore(score=0.7, confidence=0.8, violations=[])
        assert score.is_safe is False

    def test_is_safe_property_false_with_violations(self):
        """Test is_safe returns False when violations exist."""
        score = SafetyScore(score=0.9, confidence=0.8, violations=["test_violation"])
        assert score.is_safe is False

    def test_is_safe_boundary_condition(self):
        """Test is_safe boundary at score 0.8."""
        safe_score = SafetyScore(score=0.8, confidence=0.8, violations=[])
        assert safe_score.is_safe is True
        
        unsafe_score = SafetyScore(score=0.79, confidence=0.8, violations=[])
        assert unsafe_score.is_safe is False

    def test_severity_property_safe(self):
        """Test severity returns 'safe' for high scores."""
        score = SafetyScore(score=0.95, confidence=0.8, violations=[])
        assert score.severity == "safe"
        
        score = SafetyScore(score=0.9, confidence=0.8, violations=[])
        assert score.severity == "safe"

    def test_severity_property_low(self):
        """Test severity returns 'low' for moderate scores."""
        score = SafetyScore(score=0.8, confidence=0.8, violations=[])
        assert score.severity == "low"
        
        score = SafetyScore(score=0.7, confidence=0.8, violations=[])
        assert score.severity == "low"

    def test_severity_property_medium(self):
        """Test severity returns 'medium' for mid-range scores."""
        score = SafetyScore(score=0.6, confidence=0.8, violations=[])
        assert score.severity == "medium"
        
        score = SafetyScore(score=0.5, confidence=0.8, violations=[])
        assert score.severity == "medium"

    def test_severity_property_high(self):
        """Test severity returns 'high' for low scores."""
        score = SafetyScore(score=0.4, confidence=0.8, violations=[])
        assert score.severity == "high"
        
        score = SafetyScore(score=0.0, confidence=0.8, violations=[])
        assert score.severity == "high"

    def test_frozen_dataclass_immutability(self):
        """Test SafetyScore is immutable (frozen)."""
        score = SafetyScore(score=0.9, confidence=0.8, violations=[])
        
        with pytest.raises(FrozenInstanceError):
            score.score = 0.5
            
        with pytest.raises(FrozenInstanceError):
            score.confidence = 0.5
            
        with pytest.raises(FrozenInstanceError):
            score.violations = ["new_violation"]

    def test_safety_score_edge_cases(self):
        """Test edge cases for SafetyScore."""
        # Zero scores
        score = SafetyScore(score=0.0, confidence=0.0, violations=[])
        assert score.severity == "high"
        assert score.is_safe is False
        
        # Maximum scores
        score = SafetyScore(score=1.0, confidence=1.0, violations=[])
        assert score.severity == "safe"
        assert score.is_safe is True


class TestEmotionResult:
    """Test EmotionResult frozen dataclass with post_init."""

    def test_emotion_result_creation(self):
        """Test basic EmotionResult creation."""
        result = EmotionResult(
            primary_emotion="happy",
            confidence=0.9,
            secondary_emotions=["excited", "joyful"]
        )
        assert result.primary_emotion == "happy"
        assert result.confidence == 0.9
        assert result.secondary_emotions == ["excited", "joyful"]

    def test_emotion_result_with_none_secondary(self):
        """Test EmotionResult with None secondary_emotions."""
        result = EmotionResult(primary_emotion="sad", confidence=0.8, secondary_emotions=None)
        assert result.primary_emotion == "sad"
        assert result.confidence == 0.8
        assert result.secondary_emotions == []

    def test_emotion_result_default_secondary(self):
        """Test EmotionResult with default secondary_emotions."""
        result = EmotionResult(primary_emotion="neutral", confidence=0.7)
        assert result.primary_emotion == "neutral"
        assert result.confidence == 0.7
        assert result.secondary_emotions == []

    def test_post_init_conversion(self):
        """Test __post_init__ properly handles None values."""
        # Create with explicit None
        result = EmotionResult(
            primary_emotion="angry",
            confidence=0.6,
            secondary_emotions=None
        )
        assert result.secondary_emotions == []
        
        # Verify it's still a list we can work with
        assert isinstance(result.secondary_emotions, list)
        assert len(result.secondary_emotions) == 0

    def test_emotion_result_frozen_immutability(self):
        """Test EmotionResult is immutable (frozen)."""
        result = EmotionResult(
            primary_emotion="happy",
            confidence=0.9,
            secondary_emotions=["excited"]
        )
        
        with pytest.raises(FrozenInstanceError):
            result.primary_emotion = "sad"
            
        with pytest.raises(FrozenInstanceError):
            result.confidence = 0.5
            
        with pytest.raises(FrozenInstanceError):
            result.secondary_emotions = ["angry"]

    def test_emotion_result_edge_cases(self):
        """Test edge cases for EmotionResult."""
        # Empty string emotion
        result = EmotionResult(primary_emotion="", confidence=0.0)
        assert result.primary_emotion == ""
        assert result.confidence == 0.0
        assert result.secondary_emotions == []
        
        # Maximum confidence
        result = EmotionResult(primary_emotion="confident", confidence=1.0)
        assert result.confidence == 1.0
        
        # Empty secondary emotions list
        result = EmotionResult(
            primary_emotion="calm",
            confidence=0.8,
            secondary_emotions=[]
        )
        assert result.secondary_emotions == []


class TestContentComplexity:
    """Test ContentComplexity frozen dataclass with age appropriateness."""

    def test_content_complexity_creation(self):
        """Test basic ContentComplexity creation."""
        complexity = ContentComplexity(
            level="moderate",
            vocabulary_score=0.7,
            sentence_complexity=0.6,
            concept_difficulty=0.8
        )
        assert complexity.level == "moderate"
        assert complexity.vocabulary_score == 0.7
        assert complexity.sentence_complexity == 0.6
        assert complexity.concept_difficulty == 0.8

    def test_is_age_appropriate_simple_content(self):
        """Test simple content is appropriate for all ages."""
        complexity = ContentComplexity(
            level="simple",
            vocabulary_score=0.3,
            sentence_complexity=0.2,
            concept_difficulty=0.4
        )
        
        assert complexity.is_age_appropriate(3) is True
        assert complexity.is_age_appropriate(5) is True
        assert complexity.is_age_appropriate(8) is True
        assert complexity.is_age_appropriate(12) is True

    def test_is_age_appropriate_moderate_content(self):
        """Test moderate content age restrictions."""
        complexity = ContentComplexity(
            level="moderate",
            vocabulary_score=0.6,
            sentence_complexity=0.7,
            concept_difficulty=0.5
        )
        
        # Not appropriate for under 5
        assert complexity.is_age_appropriate(3) is False
        assert complexity.is_age_appropriate(4) is False
        
        # Appropriate for 5 and above
        assert complexity.is_age_appropriate(5) is True
        assert complexity.is_age_appropriate(8) is True
        assert complexity.is_age_appropriate(12) is True

    def test_is_age_appropriate_complex_content(self):
        """Test complex content age restrictions."""
        complexity = ContentComplexity(
            level="complex",
            vocabulary_score=0.9,
            sentence_complexity=0.8,
            concept_difficulty=0.9
        )
        
        # Not appropriate for under 8
        assert complexity.is_age_appropriate(3) is False
        assert complexity.is_age_appropriate(5) is False
        assert complexity.is_age_appropriate(7) is False
        
        # Appropriate for 8 and above
        assert complexity.is_age_appropriate(8) is True
        assert complexity.is_age_appropriate(10) is True
        assert complexity.is_age_appropriate(12) is True

    def test_is_age_appropriate_boundary_conditions(self):
        """Test boundary conditions for age appropriateness."""
        moderate = ContentComplexity(level="moderate", vocabulary_score=0.5, sentence_complexity=0.5, concept_difficulty=0.5)
        complex_content = ContentComplexity(level="complex", vocabulary_score=0.8, sentence_complexity=0.8, concept_difficulty=0.8)
        
        # Age 5 boundary for moderate
        assert moderate.is_age_appropriate(4) is False
        assert moderate.is_age_appropriate(5) is True
        
        # Age 8 boundary for complex
        assert complex_content.is_age_appropriate(7) is False
        assert complex_content.is_age_appropriate(8) is True

    def test_content_complexity_frozen_immutability(self):
        """Test ContentComplexity is immutable (frozen)."""
        complexity = ContentComplexity(
            level="simple",
            vocabulary_score=0.3,
            sentence_complexity=0.2,
            concept_difficulty=0.4
        )
        
        with pytest.raises(FrozenInstanceError):
            complexity.level = "complex"
            
        with pytest.raises(FrozenInstanceError):
            complexity.vocabulary_score = 0.9
            
        with pytest.raises(FrozenInstanceError):
            complexity.sentence_complexity = 0.8
            
        with pytest.raises(FrozenInstanceError):
            complexity.concept_difficulty = 0.9

    def test_content_complexity_edge_cases(self):
        """Test edge cases for ContentComplexity."""
        # Zero scores
        complexity = ContentComplexity(
            level="simple",
            vocabulary_score=0.0,
            sentence_complexity=0.0,
            concept_difficulty=0.0
        )
        assert complexity.is_age_appropriate(3) is True
        
        # Maximum scores
        complexity = ContentComplexity(
            level="complex",
            vocabulary_score=1.0,
            sentence_complexity=1.0,
            concept_difficulty=1.0
        )
        assert complexity.is_age_appropriate(7) is False
        assert complexity.is_age_appropriate(8) is True

    def test_unknown_complexity_level(self):
        """Test unknown complexity levels don't break age checking."""
        complexity = ContentComplexity(
            level="unknown",
            vocabulary_score=0.5,
            sentence_complexity=0.5,
            concept_difficulty=0.5
        )
        
        # Should pass since it's not "complex"
        assert complexity.is_age_appropriate(7) is True
        assert complexity.is_age_appropriate(3) is False  # Still fails under 5 check


class TestChildPreferences:
    """Test ChildPreferences mutable dataclass with post_init."""

    def test_child_preferences_creation_with_defaults(self):
        """Test ChildPreferences creation with default values."""
        prefs = ChildPreferences()
        
        assert prefs.favorite_topics == []
        assert prefs.favorite_characters == []
        assert prefs.favorite_activities == []
        assert prefs.interests == []
        assert prefs.learning_style == "visual"
        assert prefs.language_preference == "en"
        assert prefs.voice_speed == 1.0
        assert prefs.volume_level == 0.8
        assert prefs.age_range is None
        assert prefs.audio_enabled is False

    def test_child_preferences_creation_with_values(self):
        """Test ChildPreferences creation with explicit values."""
        prefs = ChildPreferences(
            favorite_topics=["animals", "space"],
            favorite_characters=["teddy", "robot"],
            favorite_activities=["reading", "drawing"],
            interests=["science", "art"],
            learning_style="auditory",
            language_preference="es",
            voice_speed=1.2,
            volume_level=0.9,
            age_range="5-7",
            audio_enabled=True
        )
        
        assert prefs.favorite_topics == ["animals", "space"]
        assert prefs.favorite_characters == ["teddy", "robot"]
        assert prefs.favorite_activities == ["reading", "drawing"]
        assert prefs.interests == ["science", "art"]
        assert prefs.learning_style == "auditory"
        assert prefs.language_preference == "es"
        assert prefs.voice_speed == 1.2
        assert prefs.volume_level == 0.9
        assert prefs.age_range == "5-7"
        assert prefs.audio_enabled is True

    def test_post_init_none_list_conversion(self):
        """Test __post_init__ converts None lists to empty lists."""
        prefs = ChildPreferences(
            favorite_topics=None,
            favorite_characters=None,
            favorite_activities=None,
            interests=None
        )
        
        assert prefs.favorite_topics == []
        assert prefs.favorite_characters == []
        assert prefs.favorite_activities == []
        assert prefs.interests == []
        
        # Verify they're actual list objects
        assert isinstance(prefs.favorite_topics, list)
        assert isinstance(prefs.favorite_characters, list)
        assert isinstance(prefs.favorite_activities, list)
        assert isinstance(prefs.interests, list)

    def test_post_init_preserves_existing_lists(self):
        """Test __post_init__ preserves non-None lists."""
        existing_topics = ["math", "reading"]
        existing_characters = ["bear"]
        
        prefs = ChildPreferences(
            favorite_topics=existing_topics,
            favorite_characters=existing_characters,
            favorite_activities=None,  # This should become []
            interests=None  # This should become []
        )
        
        assert prefs.favorite_topics == existing_topics
        assert prefs.favorite_characters == existing_characters
        assert prefs.favorite_activities == []
        assert prefs.interests == []
        
        # Verify we get the same list objects for non-None values
        assert prefs.favorite_topics is existing_topics
        assert prefs.favorite_characters is existing_characters

    def test_child_preferences_mutability(self):
        """Test ChildPreferences is mutable (not frozen)."""
        prefs = ChildPreferences()
        
        # Should be able to modify attributes
        prefs.learning_style = "kinesthetic"
        prefs.language_preference = "fr"
        prefs.voice_speed = 0.8
        prefs.volume_level = 0.6
        prefs.audio_enabled = True
        prefs.age_range = "8-10"
        
        assert prefs.learning_style == "kinesthetic"
        assert prefs.language_preference == "fr"
        assert prefs.voice_speed == 0.8
        assert prefs.volume_level == 0.6
        assert prefs.audio_enabled is True
        assert prefs.age_range == "8-10"

    def test_child_preferences_list_modification(self):
        """Test list attributes can be modified after creation."""
        prefs = ChildPreferences()
        
        # Should be able to modify list contents
        prefs.favorite_topics.append("dinosaurs")
        prefs.favorite_characters.extend(["dragon", "unicorn"])
        prefs.favorite_activities.insert(0, "singing")
        prefs.interests += ["music", "dance"]
        
        assert "dinosaurs" in prefs.favorite_topics
        assert "dragon" in prefs.favorite_characters
        assert "unicorn" in prefs.favorite_characters
        assert prefs.favorite_activities[0] == "singing"
        assert "music" in prefs.interests
        assert "dance" in prefs.interests

    def test_child_preferences_edge_cases(self):
        """Test edge cases for ChildPreferences."""
        # Empty string values
        prefs = ChildPreferences(
            learning_style="",
            language_preference="",
            age_range=""
        )
        assert prefs.learning_style == ""
        assert prefs.language_preference == ""
        assert prefs.age_range == ""
        
        # Extreme numeric values
        prefs = ChildPreferences(
            voice_speed=0.0,
            volume_level=0.0
        )
        assert prefs.voice_speed == 0.0
        assert prefs.volume_level == 0.0
        
        prefs = ChildPreferences(
            voice_speed=10.0,
            volume_level=2.0
        )
        assert prefs.voice_speed == 10.0
        assert prefs.volume_level == 2.0

    def test_child_preferences_learning_styles(self):
        """Test different learning style values."""
        styles = ["visual", "auditory", "kinesthetic", "mixed"]
        
        for style in styles:
            prefs = ChildPreferences(learning_style=style)
            assert prefs.learning_style == style

    def test_child_preferences_language_codes(self):
        """Test different language preference values."""
        languages = ["en", "es", "fr", "de", "zh", "ja"]
        
        for lang in languages:
            prefs = ChildPreferences(language_preference=lang)
            assert prefs.language_preference == lang


class TestValueObjectsIntegration:
    """Integration tests combining multiple value objects."""

    def test_safety_level_and_score_consistency(self):
        """Test SafetyLevel.from_score matches SafetyScore.severity."""
        test_scores = [0.0, 0.3, 0.5, 0.7, 0.9, 1.0]
        
        for score_val in test_scores:
            safety_score = SafetyScore(score=score_val, confidence=0.8, violations=[])
            safety_level = SafetyLevel.from_score(score_val)
            
            # Map SafetyLevel to severity strings for comparison
            level_to_severity = {
                SafetyLevel.SAFE: "safe",
                SafetyLevel.LOW: "low", 
                SafetyLevel.MEDIUM: "medium",
                SafetyLevel.HIGH: "high"
            }
            
            expected_severity = level_to_severity[safety_level]
            assert safety_score.severity == expected_severity

    def test_age_group_and_content_complexity_compatibility(self):
        """Test AgeGroup mapping works with ContentComplexity age checks."""
        ages_and_groups = [
            (3, AgeGroup.PRESCHOOL),
            (5, AgeGroup.EARLY_SCHOOL),
            (8, AgeGroup.MIDDLE_SCHOOL),
            (11, AgeGroup.PRETEEN)
        ]
        
        simple_content = ContentComplexity(
            level="simple", vocabulary_score=0.3, sentence_complexity=0.2, concept_difficulty=0.3
        )
        complex_content = ContentComplexity(
            level="complex", vocabulary_score=0.9, sentence_complexity=0.8, concept_difficulty=0.9
        )
        
        for age, expected_group in ages_and_groups:
            assert AgeGroup.from_age(age) == expected_group
            assert simple_content.is_age_appropriate(age) is True
            
            # Complex content should only be appropriate for age 8+
            if age >= 8:
                assert complex_content.is_age_appropriate(age) is True
            else:
                assert complex_content.is_age_appropriate(age) is False

    def test_child_preferences_with_emotion_and_safety(self):
        """Test ChildPreferences can work with emotion and safety data."""
        prefs = ChildPreferences(
            favorite_topics=["happy stories", "safe adventures"],
            learning_style="visual",
            audio_enabled=True
        )
        
        # Simulate matching preferences with emotion results
        happy_emotion = EmotionResult(
            primary_emotion="happy",
            confidence=0.9,
            secondary_emotions=["excited", "joyful"]
        )
        
        safe_content = SafetyScore(score=0.95, confidence=0.9, violations=[])
        
        # These would be used together in the application
        assert "happy stories" in prefs.favorite_topics
        assert happy_emotion.primary_emotion == "happy"
        assert safe_content.is_safe is True
        assert safe_content.severity == "safe"

    def test_coppa_compliance_age_validation(self):
        """Test age-related value objects support COPPA compliance."""
        coppa_ages = [3, 5, 8, 10, 13]
        
        for age in coppa_ages:
            # All ages should map to valid age groups
            age_group = AgeGroup.from_age(age)
            assert age_group is not None
            
            # Content complexity should have appropriate restrictions
            simple_content = ContentComplexity(
                level="simple", vocabulary_score=0.2, sentence_complexity=0.1, concept_difficulty=0.2
            )
            assert simple_content.is_age_appropriate(age) is True
            
            # Safety scoring should work for all ages
            safety_score = SafetyScore(score=0.9, confidence=0.8, violations=[])
            assert safety_score.is_safe is True

    def test_error_handling_with_invalid_data(self):
        """Test value objects handle edge cases gracefully."""
        # Test with extreme values that might come from corrupted data
        extreme_safety = SafetyScore(score=-1.0, confidence=2.0, violations=["test"])
        assert extreme_safety.is_safe is False
        assert extreme_safety.severity == "high"
        
        # Test with very large age
        very_old = AgeGroup.from_age(999)
        assert very_old == AgeGroup.PRETEEN
        
        # Test with negative age
        negative_age = AgeGroup.from_age(-5)
        assert negative_age == AgeGroup.TODDLER
        
        # Test content complexity with unusual values
        weird_complexity = ContentComplexity(
            level="unknown_level",
            vocabulary_score=-0.5,
            sentence_complexity=10.0,
            concept_difficulty=999.9
        )
        # Should still work for age appropriateness checks
        assert isinstance(weird_complexity.is_age_appropriate(8), bool)
