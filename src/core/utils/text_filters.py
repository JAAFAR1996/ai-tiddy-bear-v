"""
Core Text Filtering Utilities - Independent Module
No dependencies on business logic or services.
"""

import re
from typing import Dict, List


class TextFilter:
    """Pure text filtering without external dependencies."""
    
    def __init__(self):
        self.inappropriate_words = [
            "bad", "hate", "stupid", "dumb", "kill", "die", "hurt", "harm"
        ]
        
        self.pii_patterns = [
            r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone numbers
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit cards
        ]
    
    def filter_inappropriate_content(self, text: str) -> Dict[str, any]:
        """Filter inappropriate content using basic filtering."""
        sanitized_text = text
        was_filtered = False
        
        for word in self.inappropriate_words:
            if word.lower() in text.lower():
                sanitized_text = sanitized_text.replace(word, "***")
                was_filtered = True
        
        return {
            "filtered_text": sanitized_text,
            "was_filtered": was_filtered,
            "original_length": len(text),
            "filtered_length": len(sanitized_text),
        }
    
    def detect_pii(self, text: str) -> List[str]:
        """Detect PII patterns in text."""
        detected = []
        for pattern in self.pii_patterns:
            if re.search(pattern, text):
                detected.append(pattern)
        return detected
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.strip())


# Global instance for backward compatibility
_text_filter = TextFilter()


def filter_inappropriate_content(text: str) -> Dict[str, any]:
    """Filter inappropriate content."""
    return _text_filter.filter_inappropriate_content(text)


def detect_pii(text: str) -> List[str]:
    """Detect PII in text."""
    return _text_filter.detect_pii(text)


def clean_text(text: str) -> str:
    """Clean text."""
    return _text_filter.clean_text(text)
