"""
ContentManager: Central manager for stories, educational content, and games.
- Loads, filters, and validates content from templates.
- Integrates with story generation use case, AI service, and child safety service.
- Provides async operations with comprehensive error handling and logging.
"""

import logging
from typing import Dict, Any, Optional

from .story_templates import StoryTemplates
from .educational_content import EducationalContent
from .age_filter import AgeFilter
from .content_validator import ContentValidator

logger = logging.getLogger(__name__)


class ContentManager:
    """Central content manager with async operations and comprehensive error handling."""
    
    def __init__(self):
        """Initialize ContentManager with all required components."""
        try:
            self.stories = StoryTemplates()
            self.educational = EducationalContent()
            self.age_filter = AgeFilter()
            self.validator = ContentValidator()
            logger.info("ContentManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ContentManager: {e}")
            raise

    async def get_story(
        self, 
        template_id: str, 
        child_age: int, 
        preferences: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a story template with age filtering and validation.
        
        Args:
            template_id: ID of the story template
            child_age: Child's age for filtering
            preferences: Optional preferences for story selection
            
        Returns:
            Story dictionary if found and valid, None otherwise
        """
        try:
            logger.debug(f"Retrieving story '{template_id}' for age {child_age}")
            
            # Get story template
            story = self.stories.get_template(template_id)
            if story is None:
                logger.warning(f"Story template '{template_id}' not found")
                return None
            
            # Apply preferences if provided
            if preferences:
                story = await self._apply_story_preferences(story, preferences)
                logger.debug(f"Applied preferences to story '{template_id}': {list(preferences.keys())}")
            
            # Age filtering
            if not self.age_filter.is_allowed(story, child_age):
                logger.info(f"Story '{template_id}' blocked by age filter for age {child_age}")
                return None
            
            # Content validation
            if not self.validator.is_valid(story):
                logger.warning(f"Story '{template_id}' failed content validation")
                return None
            
            logger.info(f"Story '{template_id}' approved for age {child_age}")
            return story
            
        except Exception as e:
            logger.error(f"Error retrieving story '{template_id}' for age {child_age}: {e}")
            return None

    async def get_educational_content(
        self, 
        topic: str, 
        child_age: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get educational content with age filtering and validation.
        
        Args:
            topic: Educational topic to retrieve
            child_age: Child's age for filtering
            
        Returns:
            Educational content dictionary if found and valid, None otherwise
        """
        try:
            logger.debug(f"Retrieving educational content '{topic}' for age {child_age}")
            
            # Get educational content
            content = self.educational.get_content(topic)
            if content is None:
                logger.warning(f"Educational content '{topic}' not found")
                return None
            
            # Age filtering
            if not self.age_filter.is_allowed(content, child_age):
                logger.info(f"Educational content '{topic}' blocked by age filter for age {child_age}")
                return None
            
            # Content validation
            if not self.validator.is_valid(content):
                logger.warning(f"Educational content '{topic}' failed content validation")
                return None
            
            logger.info(f"Educational content '{topic}' approved for age {child_age}")
            return content
            
        except Exception as e:
            logger.error(f"Error retrieving educational content '{topic}' for age {child_age}: {e}")
            return None
    
    async def _apply_story_preferences(
        self, 
        story: Dict[str, Any], 
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply user preferences to story content.
        
        Args:
            story: Original story dictionary
            preferences: User preferences to apply
            
        Returns:
            Modified story with preferences applied
        """
        try:
            # Create a copy to avoid modifying original
            modified_story = story.copy()
            
            # Apply theme preferences
            if 'theme' in preferences:
                theme = preferences['theme']
                if 'themes' not in modified_story:
                    modified_story['themes'] = []
                if theme not in modified_story['themes']:
                    modified_story['themes'].append(theme)
                    logger.debug(f"Added theme preference: {theme}")
            
            # Apply length preferences
            if 'length' in preferences:
                length = preferences['length']
                modified_story['preferred_length'] = length
                logger.debug(f"Applied length preference: {length}")
            
            # Apply difficulty preferences
            if 'difficulty' in preferences:
                difficulty = preferences['difficulty']
                modified_story['preferred_difficulty'] = difficulty
                logger.debug(f"Applied difficulty preference: {difficulty}")
            
            # Apply character preferences
            if 'characters' in preferences:
                characters = preferences['characters']
                if isinstance(characters, list):
                    modified_story['preferred_characters'] = characters
                    logger.debug(f"Applied character preferences: {characters}")
            
            return modified_story
            
        except Exception as e:
            logger.error(f"Error applying story preferences: {e}")
            # Return original story if preferences application fails
            return story
    
    async def get_content_recommendations(
        self, 
        child_age: int, 
        content_type: str = 'story'
    ) -> Dict[str, Any]:
        """
        Get content recommendations based on child's age.
        
        Args:
            child_age: Child's age
            content_type: Type of content ('story' or 'educational')
            
        Returns:
            Dictionary with recommendations and filtering results
        """
        try:
            logger.debug(f"Getting {content_type} recommendations for age {child_age}")
            
            # Get age category and complexity recommendations
            age_category = self.age_filter.get_age_category(child_age)
            complexity = self.age_filter.get_recommended_complexity(child_age)
            
            recommendations = {
                'age_category': age_category.value if age_category else None,
                'recommended_complexity': complexity.value if complexity else None,
                'content_type': content_type,
                'child_age': child_age
            }
            
            # Add age-specific recommendations
            if age_category:
                if content_type == 'story':
                    recommendations['story_recommendations'] = self._get_story_recommendations(age_category)
                elif content_type == 'educational':
                    recommendations['educational_recommendations'] = self._get_educational_recommendations(age_category)
            
            logger.info(f"Generated recommendations for age {child_age}, type {content_type}")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting recommendations for age {child_age}: {e}")
            return {
                'error': f'Failed to generate recommendations: {str(e)}',
                'child_age': child_age,
                'content_type': content_type
            }
    
    def _get_story_recommendations(self, age_category) -> Dict[str, Any]:
        """Get story-specific recommendations for age category."""
        recommendations = {
            'toddler': {
                'themes': ['animals', 'colors', 'simple_actions'],
                'length': 'very_short',
                'interaction': 'high',
                'complexity': 'simple'
            },
            'preschool': {
                'themes': ['friendship', 'family', 'counting', 'shapes'],
                'length': 'short',
                'interaction': 'medium',
                'complexity': 'simple'
            },
            'early_elementary': {
                'themes': ['adventure', 'problem_solving', 'school', 'nature'],
                'length': 'medium',
                'interaction': 'medium',
                'complexity': 'moderate'
            },
            'late_elementary': {
                'themes': ['mystery', 'science', 'history', 'friendship_challenges'],
                'length': 'medium_long',
                'interaction': 'low',
                'complexity': 'moderate'
            },
            'preteen': {
                'themes': ['character_growth', 'moral_dilemmas', 'complex_relationships'],
                'length': 'long',
                'interaction': 'low',
                'complexity': 'advanced'
            }
        }
        return recommendations.get(age_category.value, {})
    
    def _get_educational_recommendations(self, age_category) -> Dict[str, Any]:
        """Get educational-specific recommendations for age category."""
        recommendations = {
            'toddler': {
                'subjects': ['colors', 'shapes', 'numbers_1_to_5', 'body_parts'],
                'format': 'interactive_visual',
                'duration': 'very_short',
                'repetition': 'high'
            },
            'preschool': {
                'subjects': ['alphabet', 'numbers_1_to_10', 'animals', 'basic_emotions'],
                'format': 'story_based',
                'duration': 'short',
                'repetition': 'medium'
            },
            'early_elementary': {
                'subjects': ['basic_math', 'reading', 'science_basics', 'geography'],
                'format': 'structured_learning',
                'duration': 'medium',
                'repetition': 'low'
            },
            'late_elementary': {
                'subjects': ['advanced_math', 'science_experiments', 'history', 'critical_thinking'],
                'format': 'project_based',
                'duration': 'long',
                'repetition': 'very_low'
            },
            'preteen': {
                'subjects': ['complex_science', 'literature', 'social_studies', 'research_skills'],
                'format': 'independent_study',
                'duration': 'extended',
                'repetition': 'none'
            }
        }
        return recommendations.get(age_category.value, {})
    
    async def validate_content_request(
        self,
        content_id: str,
        child_age: int,
        content_type: str = 'story'
    ) -> Dict[str, Any]:
        """
        Validate a content request before processing.
        
        Args:
            content_id: ID of the content to validate
            child_age: Child's age
            content_type: Type of content ('story' or 'educational')
            
        Returns:
            Validation result dictionary with detailed information
        """
        try:
            logger.debug(f"Validating {content_type} request: {content_id} for age {child_age}")
            
            # Validate age first
            age_validation = self.age_filter.validate_child_age(child_age)
            if not age_validation['is_valid']:
                logger.warning(f"Invalid age {child_age}: {age_validation['reason']}")
                return {
                    'valid': False,
                    'reason': age_validation['reason'],
                    'error_type': 'invalid_age',
                    'content_id': content_id,
                    'content_type': content_type
                }
            
            # Check if content exists
            if content_type == 'story':
                content = self.stories.get_template(content_id)
            elif content_type == 'educational':
                content = self.educational.get_content(content_id)
            else:
                return {
                    'valid': False,
                    'reason': f"Unknown content type: {content_type}",
                    'error_type': 'invalid_content_type',
                    'content_id': content_id,
                    'content_type': content_type
                }
            
            if content is None:
                logger.warning(f"Content not found: {content_id}")
                return {
                    'valid': False,
                    'reason': f"Content '{content_id}' not found",
                    'error_type': 'content_not_found',
                    'content_id': content_id,
                    'content_type': content_type
                }
            
            # Validate content safety
            if not self.validator.is_valid(content):
                logger.warning(f"Content {content_id} failed safety validation")
                return {
                    'valid': False,
                    'reason': f"Content '{content_id}' failed safety validation",
                    'error_type': 'safety_violation',
                    'content_id': content_id,
                    'content_type': content_type
                }
            
            # Check age appropriateness
            if not self.age_filter.is_allowed(content, child_age):
                logger.info(f"Content {content_id} not age-appropriate for {child_age}")
                return {
                    'valid': False,
                    'reason': f"Content '{content_id}' not appropriate for age {child_age}",
                    'error_type': 'age_inappropriate',
                    'content_id': content_id,
                    'content_type': content_type,
                    'child_age': child_age
                }
            
            # All validations passed
            logger.info(f"Content request validated successfully: {content_id} for age {child_age}")
            return {
                'valid': True,
                'reason': 'Content request is valid and safe',
                'content_id': content_id,
                'content_type': content_type,
                'child_age': child_age,
                'age_category': age_validation.get('age_category')
            }
            
        except Exception as e:
            logger.error(f"Error validating content request {content_id}: {e}")
            return {
                'valid': False,
                'reason': f"Validation error: {str(e)}",
                'error_type': 'validation_error',
                'content_id': content_id,
                'content_type': content_type
            }