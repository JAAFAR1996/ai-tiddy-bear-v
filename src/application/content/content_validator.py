"""
ContentValidator: Advanced content validator with context-aware filtering and comprehensive safety checks.
- Used by ContentManager and child safety service for COPPA-compliant content validation
- Provides context-aware word filtering to avoid false positives
- Includes comprehensive forbidden word lists organized by categories
- Detailed logging and tracking of blocked content for audit purposes
"""

import logging
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Import shared types to avoid duplication
from src.application.services.child_safety_service import ViolationType, ValidationResult

logger = logging.getLogger(__name__)


class ContentValidator:
    """Advanced content validator with context-aware filtering and comprehensive safety checks."""
    
    def __init__(self):
        """Initialize ContentValidator with comprehensive word lists and context patterns."""
        try:
            self._load_forbidden_words()
            self._compile_context_patterns()
            logger.info("ContentValidator initialized with context-aware filtering")
        except Exception as e:
            logger.error(f"Failed to initialize ContentValidator: {e}")
            # Fallback to basic word lists if loading fails
            self._create_fallback_word_lists()
            self._compile_context_patterns()
    
    def _load_forbidden_words(self):
        """Load forbidden words from external files or create comprehensive lists."""
        # Try to load from external configuration file first
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "content_filters.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.forbidden_words = config.get('forbidden_words', {})
                    logger.info(f"Loaded forbidden words from {config_path}")
                    return
            except Exception as e:
                logger.warning(f"Failed to load forbidden words from config: {e}")
        
        # Create comprehensive forbidden word lists organized by categories
        self._create_comprehensive_word_lists()
    
    def _create_comprehensive_word_lists(self):
        """Load forbidden word lists from shared source to avoid duplication."""
        # Use shared word lists from child safety service
        from src.application.services.child_safety_service import ChildSafetyService
        temp_service = ChildSafetyService()
        self.forbidden_words = temp_service.forbidden_words
        logger.info("Loaded forbidden word lists from shared ChildSafetyService")
    
    def _create_fallback_word_lists(self):
        """Create basic fallback word lists if comprehensive loading fails."""
        # Minimal fallback - main lists are in ChildSafetyService
        self.forbidden_words = {
            ViolationType.VIOLENCE: {
                "explicit": ["violence", "kill", "death", "blood", "weapon"],
                "contextual": ["cut", "shot", "fire"]
            },
            ViolationType.SCARY_CONTENT: {
                "explicit": ["scary", "frightening", "monster", "ghost"],
                "contextual": ["dark", "alone"]
            },
            ViolationType.INAPPROPRIATE_LANGUAGE: {
                "explicit": ["stupid", "idiot", "hate"],
                "contextual": ["bad", "wrong"]
            }
        }
        logger.warning("Using minimal fallback word lists - main lists failed to load")
    
    def _compile_context_patterns(self):
        """Compile regex patterns for context-aware checking."""
        # Patterns for safe contexts where potentially problematic words are acceptable
        self.safe_context_patterns = {
            "educational": re.compile(r'\b(learn|study|school|education|teach|lesson|class|book)\b', re.IGNORECASE),
            "food": re.compile(r'\b(eat|food|cook|recipe|kitchen|meal|dinner|lunch|breakfast|diet)\b', re.IGNORECASE),
            "medical": re.compile(r'\b(doctor|medicine|health|hospital|treatment|care|help|heal)\b', re.IGNORECASE),
            "sports": re.compile(r'\b(game|sport|play|team|score|win|competition|exercise)\b', re.IGNORECASE),
            "nature": re.compile(r'\b(animal|plant|nature|garden|forest|tree|flower|bird|fish)\b', re.IGNORECASE),
            "family": re.compile(r'\b(family|parent|mother|father|brother|sister|grandma|grandpa|home)\b', re.IGNORECASE)
        }
        
        # Patterns for problematic contexts that amplify concerns
        self.problematic_context_patterns = {
            "violence": re.compile(r'\b(attack|fight|battle|war|enemy|weapon|danger|threat)\b', re.IGNORECASE),
            "fear": re.compile(r'\b(afraid|scared|terrified|panic|worry|anxiety|nightmare|horror)\b', re.IGNORECASE),
            "negative": re.compile(r'\b(hate|angry|mad|furious|disgusted|terrible|awful|horrible)\b', re.IGNORECASE)
        }
        
        logger.debug("Compiled context patterns for advanced content filtering")
    
    def is_valid(self, content: Optional[Dict[str, Any]]) -> bool:
        """
        Validate content for safety and child-appropriateness.
        
        Args:
            content: Content dictionary to validate
            
        Returns:
            True if content is safe and appropriate, False otherwise
            
        Note:
            This method provides backward compatibility. Use validate_content()
            for detailed validation results.
        """
        try:
            if content is None:
                logger.warning("is_valid called with None content")
                return False
            
            result = self.validate_content(content)
            return result.is_valid
            
        except Exception as e:
            logger.error(f"Error in is_valid: {e}")
            return False
    
    def validate_content(self, content: Dict[str, Any]) -> ValidationResult:
        """
        Comprehensive content validation with detailed results.
        
        Args:
            content: Content dictionary to validate
            
        Returns:
            ValidationResult with detailed validation information
            
        Raises:
            ValueError: If content format is invalid
        """
        try:
            # Input validation
            if not isinstance(content, dict):
                raise ValueError("Content must be a dictionary")
            
            # Extract text content from various possible fields
            text_content = self._extract_text_content(content)
            
            if not text_content:
                logger.debug("No text content found to validate")
                return ValidationResult(
                    is_valid=True,
                    reason="No text content to validate"
                )
            
            logger.debug(f"Validating content: {text_content[:100]}...")
            
            # Perform comprehensive validation
            return self._perform_comprehensive_validation(text_content, content)
            
        except Exception as e:
            logger.error(f"Error validating content: {e}")
            return ValidationResult(
                is_valid=False,
                reason=f"Validation error: {str(e)}",
                violation_type="validation_error"
            )
    
    def _extract_text_content(self, content: Dict[str, Any]) -> str:
        """Extract all text content from various fields in the content dictionary."""
        text_parts = []
        
        # Common text fields to check
        text_fields = ['text', 'content', 'description', 'story', 'dialogue', 'narrative', 'title', 'summary']
        
        for field in text_fields:
            if field in content and isinstance(content[field], str):
                text_parts.append(content[field])
        
        # Check for nested content
        if 'sections' in content and isinstance(content['sections'], list):
            for section in content['sections']:
                if isinstance(section, dict):
                    text_parts.append(self._extract_text_content(section))
        
        return ' '.join(text_parts)
    
    def _perform_comprehensive_validation(self, text: str, original_content: Dict[str, Any]) -> ValidationResult:
        """Perform comprehensive validation with context awareness."""
        text_lower = text.lower()
        all_blocked_words = []
        violations = []
        max_confidence = 0.0
        
        # Check each violation type
        for violation_type, word_categories in self.forbidden_words.items():
            blocked_words, confidence = self._check_violation_type(
                text, text_lower, violation_type, word_categories
            )
            
            if blocked_words:
                all_blocked_words.extend(blocked_words)
                violations.append(violation_type)
                max_confidence = max(max_confidence, confidence)
                
                logger.warning(
                    f"Content validation failed - {violation_type}: "
                    f"blocked words: {blocked_words}, confidence: {confidence:.2f}"
                )
        
        # Determine overall result
        if all_blocked_words:
            violation_summary = f"Content contains {len(all_blocked_words)} prohibited elements"
            if len(violations) == 1:
                primary_violation = violations[0]
            else:
                primary_violation = "multiple_violations"
            
            logger.info(f"Content blocked: {violation_summary}")
            
            return ValidationResult(
                is_valid=False,
                reason=violation_summary,
                blocked_words=list(set(all_blocked_words)),  # Remove duplicates
                violation_type=primary_violation,
                confidence_score=max_confidence
            )
        
        # Content is valid
        logger.debug("Content validation passed - no violations found")
        return ValidationResult(
            is_valid=True,
            reason="Content passed all safety checks",
            confidence_score=1.0
        )
    
    def _check_violation_type(
        self, 
        original_text: str, 
        text_lower: str, 
        violation_type: str, 
        word_categories: Dict[str, List[str]]
    ) -> Tuple[List[str], float]:
        """Check for a specific violation type with context awareness."""
        blocked_words = []
        max_confidence = 0.0
        
        # Check explicit words (always blocked)
        explicit_words = word_categories.get('explicit', [])
        for word in explicit_words:
            if self._contains_word(text_lower, word):
                blocked_words.append(word)
                max_confidence = max(max_confidence, 0.9)
                logger.debug(f"Found explicit forbidden word: '{word}'")
        
        # Check contextual words (context-dependent)
        contextual_words = word_categories.get('contextual', [])
        for word in contextual_words:
            if self._contains_word(text_lower, word):
                confidence = self._check_context_safety(original_text, word, violation_type)
                if confidence > 0.5:  # Block if confidence > 50%
                    blocked_words.append(f"{word} (context)")
                    max_confidence = max(max_confidence, confidence)
                    logger.debug(f"Found contextual forbidden word: '{word}' with confidence {confidence:.2f}")
        
        return blocked_words, max_confidence
    
    def _contains_word(self, text: str, word: str) -> bool:
        """Check if text contains word as a complete word (not as part of another word)."""
        # Use word boundaries to avoid false positives like "die" in "diet"
        pattern = rf'\b{re.escape(word)}\b'
        return bool(re.search(pattern, text, re.IGNORECASE))
    
    def _check_context_safety(self, text: str, word: str, violation_type: str) -> float:
        """Check the context around a word to determine if it's safe or problematic."""
        # Get context around the word (50 characters before and after)
        word_matches = list(re.finditer(rf'\b{re.escape(word)}\b', text, re.IGNORECASE))
        
        total_confidence = 0.0
        context_count = 0
        
        for match in word_matches:
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].lower()
            
            # Check for safe contexts
            safe_score = 0.0
            for context_type, pattern in self.safe_context_patterns.items():
                if pattern.search(context):
                    safe_score += 0.3  # Each safe context reduces problematic score
                    logger.debug(f"Found safe context '{context_type}' for word '{word}'")
            
            # Check for problematic contexts
            problem_score = 0.0
            for context_type, pattern in self.problematic_context_patterns.items():
                if pattern.search(context):
                    problem_score += 0.4  # Each problematic context increases score
                    logger.debug(f"Found problematic context '{context_type}' for word '{word}'")
            
            # Calculate confidence for this occurrence
            # Base confidence is 0.6 for contextual words
            occurrence_confidence = 0.6 + problem_score - safe_score
            occurrence_confidence = max(0.0, min(1.0, occurrence_confidence))  # Clamp to [0,1]
            
            total_confidence += occurrence_confidence
            context_count += 1
        
        # Return average confidence across all occurrences
        return total_confidence / context_count if context_count > 0 else 0.0
    
    def get_content_safety_score(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed safety score and analysis for content.
        
        Args:
            content: Content dictionary to analyze
            
        Returns:
            Dictionary with detailed safety analysis
        """
        try:
            logger.debug("Generating detailed safety score for content")
            
            validation_result = self.validate_content(content)
            text_content = self._extract_text_content(content)
            
            analysis = {
                'overall_safe': validation_result.is_valid,
                'safety_score': 1.0 - validation_result.confidence_score if not validation_result.is_valid else 1.0,
                'content_length': len(text_content),
                'word_count': len(text_content.split()) if text_content else 0,
                'violations': {
                    'found': not validation_result.is_valid,
                    'type': validation_result.violation_type,
                    'blocked_words': validation_result.blocked_words,
                    'reason': validation_result.reason
                },
                'recommendations': self._generate_safety_recommendations(validation_result)
            }
            
            # Add detailed analysis by violation type
            analysis['detailed_analysis'] = self._analyze_by_violation_types(text_content)
            
            logger.info(f"Generated safety analysis: score={analysis['safety_score']:.2f}, violations={len(validation_result.blocked_words)}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error generating safety score: {e}")
            return {
                'overall_safe': False,
                'safety_score': 0.0,
                'error': f'Analysis failed: {str(e)}'
            }
    
    def _analyze_by_violation_types(self, text: str) -> Dict[str, Any]:
        """Analyze content for each violation type separately."""
        analysis = {}
        
        for violation_type in ViolationType:
            word_categories = self.forbidden_words.get(violation_type.value, {})
            if word_categories:
                blocked_words, confidence = self._check_violation_type(
                    text, text.lower(), violation_type.value, word_categories
                )
                
                analysis[violation_type.value] = {
                    'violations_found': len(blocked_words) > 0,
                    'blocked_words': blocked_words,
                    'confidence': confidence,
                    'risk_level': self._categorize_risk_level(confidence)
                }
        
        return analysis
    
    def _categorize_risk_level(self, confidence: float) -> str:
        """Categorize risk level based on confidence score."""
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.6:
            return "medium"
        elif confidence >= 0.3:
            return "low"
        else:
            return "minimal"
    
    def _generate_safety_recommendations(self, validation_result: ValidationResult) -> List[str]:
        """Generate recommendations for improving content safety."""
        recommendations = []
        
        if not validation_result.is_valid:
            recommendations.append("Review and remove problematic words or phrases")
            
            if validation_result.violation_type:
                violation_type = validation_result.violation_type
                
                if violation_type == ViolationType.VIOLENCE.value:
                    recommendations.extend([
                        "Replace violent language with peaceful alternatives",
                        "Focus on positive conflict resolution",
                        "Use gentle, non-threatening vocabulary"
                    ])
                elif violation_type == ViolationType.SCARY_CONTENT.value:
                    recommendations.extend([
                        "Replace scary elements with friendly alternatives",
                        "Ensure content promotes comfort and safety",
                        "Use positive, reassuring language"
                    ])
                elif violation_type == ViolationType.INAPPROPRIATE_LANGUAGE.value:
                    recommendations.extend([
                        "Use kind and respectful language",
                        "Replace negative words with positive alternatives",
                        "Focus on constructive communication"
                    ])
                else:
                    recommendations.extend([
                        "Ensure content is age-appropriate",
                        "Focus on positive themes and messages",
                        "Use simple, child-friendly language"
                    ])
        else:
            recommendations.extend([
                "Content meets safety standards",
                "Continue using positive, child-friendly language",
                "Maintain focus on educational and entertaining themes"
            ])
        
        return recommendations
    
    def validate_batch_content(self, content_list: List[Dict[str, Any]]) -> List[ValidationResult]:
        """
        Validate multiple content items in batch.
        
        Args:
            content_list: List of content dictionaries to validate
            
        Returns:
            List of ValidationResult objects
        """
        try:
            logger.info(f"Starting batch validation of {len(content_list)} content items")
            
            results = []
            for i, content in enumerate(content_list):
                try:
                    result = self.validate_content(content)
                    results.append(result)
                    
                    if not result.is_valid:
                        logger.warning(f"Batch item {i+1} failed validation: {result.reason}")
                        
                except Exception as e:
                    logger.error(f"Error validating batch item {i+1}: {e}")
                    results.append(ValidationResult(
                        is_valid=False,
                        reason=f"Validation error: {str(e)}",
                        violation_type="validation_error"
                    ))
            
            valid_count = sum(1 for r in results if r.is_valid)
            logger.info(f"Batch validation completed: {valid_count}/{len(content_list)} items passed")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch validation: {e}")
            return [ValidationResult(
                is_valid=False,
                reason=f"Batch validation error: {str(e)}",
                violation_type="batch_error"
            ) for _ in content_list]