"""
AgeFilter: Enhanced content filter based on child age with COPPA compliance.
- Used by ContentManager, story generation, and child safety service.
- Enforces COPPA age requirements (3-13 years)
- Provides detailed content categorization by age groups
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class AgeCategory(Enum):
    """Age categories for content filtering."""
    TODDLER = "toddler"  # 3-4 years
    PRESCHOOL = "preschool"  # 4-5 years
    EARLY_ELEMENTARY = "early_elementary"  # 6-8 years
    LATE_ELEMENTARY = "late_elementary"  # 9-11 years
    PRETEEN = "preteen"  # 12-13 years


class ContentComplexity(Enum):
    """Content complexity levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    ADVANCED = "advanced"


class AgeFilterResult:
    """Result of age filtering with detailed information."""
    
    def __init__(
        self,
        is_allowed: bool,
        reason: Optional[str] = None,
        age_category: Optional[AgeCategory] = None,
        complexity_level: Optional[ContentComplexity] = None,
        recommendations: Optional[List[str]] = None
    ):
        self.is_allowed = is_allowed
        self.reason = reason
        self.age_category = age_category
        self.complexity_level = complexity_level
        self.recommendations = recommendations or []


class AgeFilter:
    """Enhanced age-based content filter with COPPA compliance."""
    
    # COPPA compliance age limits
    MIN_AGE = 3
    MAX_AGE = 13
    
    # Age category mappings
    AGE_CATEGORIES = {
        (3, 4): AgeCategory.TODDLER,
        (4, 5): AgeCategory.PRESCHOOL,
        (6, 8): AgeCategory.EARLY_ELEMENTARY,
        (9, 11): AgeCategory.LATE_ELEMENTARY,
        (12, 13): AgeCategory.PRETEEN,
    }
    
    # Content complexity by age
    COMPLEXITY_MAPPING = {
        AgeCategory.TODDLER: ContentComplexity.SIMPLE,
        AgeCategory.PRESCHOOL: ContentComplexity.SIMPLE,
        AgeCategory.EARLY_ELEMENTARY: ContentComplexity.MODERATE,
        AgeCategory.LATE_ELEMENTARY: ContentComplexity.MODERATE,
        AgeCategory.PRETEEN: ContentComplexity.ADVANCED,
    }
    
    def __init__(self):
        """Initialize the age filter."""
        logger.info("AgeFilter initialized with COPPA compliance (ages 3-13)")
    
    def is_allowed(self, content: Optional[Dict[str, Any]], child_age: Any) -> bool:
        """
        Legacy method for backward compatibility with enhanced input validation.
        
        Args:
            content: Content dictionary with age restrictions (can be None)
            child_age: Child's age in years (any type, will be validated)
            
        Returns:
            True if content is allowed for the child's age, False otherwise
            
        Note:
            This method provides backward compatibility. Use filter_content() 
            for detailed filtering results. Never raises exceptions.
        """
        try:
            # Handle None content
            if content is None:
                logger.warning("is_allowed called with None content")
                return False
                
            result = self.filter_content(content, child_age)
            return result.is_allowed
        except Exception as e:
            logger.error(f"Error in is_allowed: {e}")
            return False
    
    def filter_content(
        self, 
        content: Dict[str, Any], 
        child_age: int
    ) -> AgeFilterResult:
        """
        Enhanced content filtering with detailed analysis.
        
        Args:
            content: Content dictionary with metadata
            child_age: Child's age in years
            
        Returns:
            AgeFilterResult with detailed filtering information
            
        Raises:
            ValueError: If inputs are invalid
        """
        # Validate inputs
        if not isinstance(content, dict):
            raise ValueError("Content must be a dictionary")
        
        if not self._is_valid_age(child_age):
            return AgeFilterResult(
                is_allowed=False,
                reason=f"Age {child_age} is outside COPPA compliance range ({self.MIN_AGE}-{self.MAX_AGE})"
            )
        
        # Get age category
        age_category = self._get_age_category(child_age)
        complexity_level = self.COMPLEXITY_MAPPING[age_category]
        
        # Check content age restrictions
        content_min_age = content.get("min_age", self.MIN_AGE)
        content_max_age = content.get("max_age", self.MAX_AGE)
        
        # Validate content age bounds
        if not isinstance(content_min_age, int) or not isinstance(content_max_age, int):
            logger.warning("Content has invalid age bounds, using defaults")
            content_min_age = self.MIN_AGE
            content_max_age = self.MAX_AGE
        
        # Check if child's age falls within content's age range
        age_allowed = content_min_age <= child_age <= content_max_age
        
        if not age_allowed:
            return AgeFilterResult(
                is_allowed=False,
                reason=f"Content age range ({content_min_age}-{content_max_age}) doesn't match child age {child_age}",
                age_category=age_category,
                complexity_level=complexity_level
            )
        
        # Check content complexity
        content_complexity = content.get("complexity", "simple")
        complexity_allowed = self._check_complexity_match(content_complexity, complexity_level)
        
        if not complexity_allowed:
            return AgeFilterResult(
                is_allowed=False,
                reason=f"Content complexity '{content_complexity}' not suitable for {age_category.value}",
                age_category=age_category,
                complexity_level=complexity_level,
                recommendations=self._get_complexity_recommendations(age_category)
            )
        
        # Check for age-specific restrictions
        restrictions = self._check_age_specific_restrictions(content, age_category)
        if restrictions:
            return AgeFilterResult(
                is_allowed=False,
                reason=f"Content contains age-inappropriate elements: {', '.join(restrictions)}",
                age_category=age_category,
                complexity_level=complexity_level,
                recommendations=self._get_age_recommendations(age_category)
            )
        
        # Content is allowed
        logger.debug(f"Content approved for {age_category.value} child (age {child_age})")
        return AgeFilterResult(
            is_allowed=True,
            age_category=age_category,
            complexity_level=complexity_level
        )
    
    def get_age_category(self, child_age: int) -> Optional[AgeCategory]:
        """
        Get the age category for a child's age.
        
        Args:
            child_age: Child's age in years
            
        Returns:
            AgeCategory if age is valid, None otherwise
        """
        if not self._is_valid_age(child_age):
            return None
        return self._get_age_category(child_age)
    
    def get_recommended_complexity(self, child_age: int) -> Optional[ContentComplexity]:
        """
        Get recommended content complexity for a child's age.
        
        Args:
            child_age: Child's age in years
            
        Returns:
            ContentComplexity if age is valid, None otherwise
        """
        age_category = self.get_age_category(child_age)
        if age_category:
            return self.COMPLEXITY_MAPPING[age_category]
        return None
    
    def _is_valid_age(self, age: Any) -> bool:
        """
        Check if age is within COPPA compliance range with comprehensive validation.
        
        Args:
            age: Age value to validate (any type)
            
        Returns:
            True if age is a valid integer within COPPA range (3-13), False otherwise
        """
        try:
            # Must be an integer (or convertible to integer)
            if not isinstance(age, int):
                if isinstance(age, float) and age.is_integer():
                    age = int(age)
                else:
                    return False
            
            # Must be within COPPA compliance range
            return self.MIN_AGE <= age <= self.MAX_AGE
            
        except (TypeError, ValueError, AttributeError):
            return False
    
    def _get_age_category(self, child_age: int) -> AgeCategory:
        """Get age category for a valid child age."""
        for (min_age, max_age), category in self.AGE_CATEGORIES.items():
            if min_age <= child_age <= max_age:
                return category
        # Fallback for edge cases
        return AgeCategory.PRETEEN
    
    def _check_complexity_match(
        self, 
        content_complexity: str, 
        required_complexity: ContentComplexity
    ) -> bool:
        """Check if content complexity matches child's level."""
        try:
            content_level = ContentComplexity(content_complexity.lower())
        except ValueError:
            # Default to simple if complexity not recognized
            content_level = ContentComplexity.SIMPLE
        
        # Simple content is always allowed
        if content_level == ContentComplexity.SIMPLE:
            return True
        
        # Check if content complexity matches required level
        complexity_order = [
            ContentComplexity.SIMPLE,
            ContentComplexity.MODERATE,
            ContentComplexity.ADVANCED
        ]
        
        content_index = complexity_order.index(content_level)
        required_index = complexity_order.index(required_complexity)
        
        return content_index <= required_index
    
    def _check_age_specific_restrictions(
        self, 
        content: Dict[str, Any], 
        age_category: AgeCategory
    ) -> List[str]:
        """Check for age-specific content restrictions."""
        restrictions = []
        
        # Get content tags/themes
        themes = content.get("themes", [])
        if isinstance(themes, str):
            themes = [themes]
        
        # Age-specific restriction rules
        if age_category in [AgeCategory.TODDLER, AgeCategory.PRESCHOOL]:
            restricted_themes = [
                "competition", "conflict", "separation", "loss", 
                "complex emotions", "abstract concepts"
            ]
            for theme in themes:
                if theme.lower() in restricted_themes:
                    restrictions.append(f"theme '{theme}' too advanced")
        
        # Check reading level
        reading_level = content.get("reading_level", "beginner")
        if age_category == AgeCategory.TODDLER and reading_level not in ["beginner", "picture"]:
            restrictions.append("reading level too advanced")
        
        # Check content length
        content_length = content.get("length", "short")
        if age_category in [AgeCategory.TODDLER, AgeCategory.PRESCHOOL]:
            if content_length in ["long", "extended"]:
                restrictions.append("content too long for attention span")
        
        return restrictions
    
    def _get_complexity_recommendations(self, age_category: AgeCategory) -> List[str]:
        """Get content complexity recommendations for age category."""
        recommendations = {
            AgeCategory.TODDLER: [
                "Use simple words and concepts",
                "Include colorful pictures",
                "Keep content very short",
                "Focus on basic emotions and actions"
            ],
            AgeCategory.PRESCHOOL: [
                "Use simple sentences",
                "Include interactive elements",
                "Focus on familiar situations",
                "Add counting or color recognition"
            ],
            AgeCategory.EARLY_ELEMENTARY: [
                "Introduce basic problem-solving",
                "Include educational elements",
                "Use slightly longer narratives",
                "Add simple moral lessons"
            ],
            AgeCategory.LATE_ELEMENTARY: [
                "Include more complex stories",
                "Add adventure and discovery themes",
                "Introduce friendship dynamics",
                "Include educational challenges"
            ],
            AgeCategory.PRETEEN: [
                "Allow for more sophisticated themes",
                "Include character development",
                "Add mild challenges and conflicts",
                "Encourage critical thinking"
            ]
        }
        return recommendations.get(age_category, [])
    
    def _get_age_recommendations(self, age_category: AgeCategory) -> List[str]:
        """Get general content recommendations for age category."""
        return [
            f"Content should be appropriate for {age_category.value} children",
            "Ensure positive messaging and outcomes",
            "Avoid scary or concerning themes", 
            "Include age-appropriate vocabulary",
            "Consider attention span limitations",
            "Use appropriate complexity level",
            "Include educational value when possible"
        ]
