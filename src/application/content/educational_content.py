"""
EducationalContent: Advanced educational content manager with caching, validation, and efficient search.
- Used by ContentManager and story generation use case
- Supports multiple content types and dynamic file discovery
- Includes comprehensive error handling and data validation
- Implements intelligent caching and indexing for performance
- Provides detailed logging and content analytics
"""

import json
import os
import logging
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from threading import Lock
import glob

logger = logging.getLogger(__name__)


@dataclass
class ContentMetadata:
    """Metadata for educational content files."""
    file_path: str
    last_modified: float
    file_size: int
    content_count: int
    topics: Set[str] = field(default_factory=set)
    subjects: Set[str] = field(default_factory=set)
    age_ranges: List[Tuple[int, int]] = field(default_factory=list)
    checksum: str = ""


@dataclass
class ContentValidationResult:
    """Result of content validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_items: int = 0


class ContentIndex:
    """Efficient index for educational content search."""
    
    def __init__(self):
        self.topic_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.subject_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.age_index: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        self.difficulty_index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.full_text_index: Dict[str, Set[str]] = defaultdict(set)  # word -> content_ids
        self._lock = Lock()
    
    def add_content(self, content: Dict[str, Any], content_id: str):
        """Add content to all relevant indexes."""
        with self._lock:
            # Topic index
            topic = content.get('topic', '').lower()
            if topic:
                self.topic_index[topic].append(content)
            
            # Subject index
            subject = content.get('subject', '').lower()
            if subject:
                self.subject_index[subject].append(content)
            
            # Age index
            min_age = content.get('min_age', 3)
            max_age = content.get('max_age', 13)
            for age in range(min_age, max_age + 1):
                self.age_index[age].append(content)
            
            # Difficulty index
            difficulty = content.get('difficulty', 'easy').lower()
            self.difficulty_index[difficulty].append(content)
            
            # Full-text index for search
            text_content = self._extract_searchable_text(content)
            words = text_content.lower().split()
            for word in words:
                if len(word) > 2:  # Skip very short words
                    self.full_text_index[word].add(content_id)
    
    def _extract_searchable_text(self, content: Dict[str, Any]) -> str:
        """Extract searchable text from content."""
        searchable_fields = ['title', 'description', 'content', 'summary', 'keywords']
        text_parts = []
        
        for field in searchable_fields:
            if field in content:
                value = content[field]
                if isinstance(value, str):
                    text_parts.append(value)
                elif isinstance(value, list):
                    text_parts.extend(str(item) for item in value)
        
        return ' '.join(text_parts)
    
    def clear(self):
        """Clear all indexes."""
        with self._lock:
            self.topic_index.clear()
            self.subject_index.clear()
            self.age_index.clear()
            self.difficulty_index.clear()
            self.full_text_index.clear()


class EducationalContent:
    """Advanced educational content manager with caching, validation, and efficient search."""
    
    # Supported file patterns for dynamic discovery
    SUPPORTED_PATTERNS = [
        "*educational*.json",
        "*learning*.json", 
        "*content*.json",
        "*curriculum*.json",
        "*lessons*.json"
    ]
    
    # Required fields for content validation
    REQUIRED_FIELDS = ['topic', 'content', 'min_age', 'max_age']
    OPTIONAL_FIELDS = ['title', 'description', 'subject', 'difficulty', 'duration', 'keywords', 'objectives']
    
    def __init__(self, templates_dir: Optional[str] = None, cache_enabled: bool = True):
        """
        Initialize EducationalContent with advanced features.
        
        Args:
            templates_dir: Directory containing educational content files
            cache_enabled: Whether to enable content caching
        """
        self.cache_enabled = cache_enabled
        self.templates_dir = self._determine_templates_directory(templates_dir)
        self.contents: Dict[str, Any] = {}
        self.metadata: Dict[str, ContentMetadata] = {}
        self.index = ContentIndex()
        self._cache_lock = Lock()
        self._last_scan_time = 0
        self._scan_interval = 300  # 5 minutes
        
        try:
            logger.info(f"Initializing EducationalContent with directory: {self.templates_dir}")
            self._load_all_contents()
            logger.info(f"EducationalContent initialized successfully with {len(self.contents)} content items")
        except Exception as e:
            logger.error(f"Failed to initialize EducationalContent: {e}")
            # Initialize with empty content to prevent crashes
            self.contents = {}
            self.metadata = {}
    
    def _determine_templates_directory(self, custom_dir: Optional[str]) -> str:
        """Determine the templates directory with fallback options."""
        if custom_dir and os.path.exists(custom_dir):
            return custom_dir
        
        # Default directory relative to this file
        default_dir = os.path.join(os.path.dirname(__file__), "../templates/stories")
        if os.path.exists(default_dir):
            return default_dir
        
        # Alternative directories to try
        alternative_dirs = [
            os.path.join(os.path.dirname(__file__), "../../templates/educational"),
            os.path.join(os.path.dirname(__file__), "../../../templates/content"),
            os.path.join(os.path.dirname(__file__), "../../../content/educational")
        ]
        
        for alt_dir in alternative_dirs:
            if os.path.exists(alt_dir):
                logger.info(f"Using alternative templates directory: {alt_dir}")
                return alt_dir
        
        # Create default directory if none exists
        os.makedirs(default_dir, exist_ok=True)
        logger.warning(f"Created default templates directory: {default_dir}")
        return default_dir
    
    def _discover_content_files(self) -> List[str]:
        """Dynamically discover all educational content files."""
        discovered_files = []
        
        try:
            for pattern in self.SUPPORTED_PATTERNS:
                pattern_path = os.path.join(self.templates_dir, pattern)
                matching_files = glob.glob(pattern_path)
                discovered_files.extend(matching_files)
            
            # Remove duplicates and sort
            discovered_files = sorted(list(set(discovered_files)))
            
            logger.debug(f"Discovered {len(discovered_files)} content files: {[os.path.basename(f) for f in discovered_files]}")
            return discovered_files
            
        except Exception as e:
            logger.error(f"Error discovering content files: {e}")
            return []
    
    def _load_all_contents(self):
        """Load all educational content with comprehensive error handling and caching."""
        start_time = time.time()
        
        # Check if we need to rescan
        if self.cache_enabled and (time.time() - self._last_scan_time) < self._scan_interval:
            if self.contents:
                logger.debug("Using cached content (scan interval not reached)")
                return
        
        content_files = self._discover_content_files()
        
        if not content_files:
            logger.warning("No educational content files found")
            # Create default content file for demonstration
            self._create_default_content()
            return
        
        new_contents = {}
        new_metadata = {}
        successful_loads = 0
        failed_loads = 0
        
        for file_path in content_files:
            try:
                file_metadata = self._get_file_metadata(file_path)
                file_basename = os.path.basename(file_path)
                
                # Check if file has changed (cache validation)
                if (self.cache_enabled and 
                    file_basename in self.metadata and 
                    self.metadata[file_basename].last_modified == file_metadata.last_modified and
                    self.metadata[file_basename].checksum == file_metadata.checksum):
                    
                    # Use cached content
                    new_contents[file_basename] = self.contents.get(file_basename, [])
                    new_metadata[file_basename] = self.metadata[file_basename]
                    logger.debug(f"Using cached content for {file_basename}")
                    successful_loads += 1
                    continue
                
                # Load fresh content
                content_list = self._load_single_file(file_path)
                if content_list is not None:
                    # Validate content
                    validation_result = self._validate_content_list(content_list, file_basename)
                    
                    if validation_result.is_valid:
                        new_contents[file_basename] = content_list
                        
                        # Update metadata
                        file_metadata.content_count = len(content_list)
                        file_metadata.topics = {item.get('topic', '').lower() for item in content_list if item.get('topic')}
                        file_metadata.subjects = {item.get('subject', '').lower() for item in content_list if item.get('subject')}
                        file_metadata.age_ranges = [(item.get('min_age', 3), item.get('max_age', 13)) for item in content_list]
                        
                        new_metadata[file_basename] = file_metadata
                        successful_loads += 1
                        
                        logger.info(f"Loaded {len(content_list)} items from {file_basename}")
                    else:
                        logger.error(f"Content validation failed for {file_basename}: {validation_result.errors}")
                        failed_loads += 1
                else:
                    failed_loads += 1
                    
            except Exception as e:
                logger.error(f"Error loading content from {file_path}: {e}")
                failed_loads += 1
        
        # Update instance variables
        with self._cache_lock:
            self.contents = new_contents
            self.metadata = new_metadata
            self._last_scan_time = time.time()
        
        # Rebuild search index
        self._rebuild_search_index()
        
        load_time = time.time() - start_time
        total_items = sum(len(items) for items in new_contents.values())
        
        logger.info(
            f"Content loading completed: {successful_loads} files succeeded, "
            f"{failed_loads} files failed, {total_items} total items, "
            f"load time: {load_time:.2f}s"
        )
    
    def _get_file_metadata(self, file_path: str) -> ContentMetadata:
        """Get metadata for a content file."""
        stat = os.stat(file_path)
        
        # Calculate file checksum for change detection
        checksum = ""
        try:
            with open(file_path, 'rb') as f:
                checksum = hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Could not calculate checksum for {file_path}: {e}")
        
        return ContentMetadata(
            file_path=file_path,
            last_modified=stat.st_mtime,
            file_size=stat.st_size,
            content_count=0,
            checksum=checksum
        )
    
    def _load_single_file(self, file_path: str) -> Optional[List[Dict[str, Any]]]:
        """Load content from a single file with comprehensive error handling."""
        try:
            logger.debug(f"Loading content from: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON structures
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Look for common content keys
                content_keys = ['content', 'items', 'educational_content', 'lessons', 'stories']
                for key in content_keys:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                
                # If no list found, treat the dict as a single content item
                return [data]
            else:
                logger.error(f"Unexpected JSON structure in {file_path}: {type(data)}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {file_path}: {e}")
            return None
        except FileNotFoundError:
            logger.error(f"Content file not found: {file_path}")
            return None
        except PermissionError:
            logger.error(f"Permission denied reading {file_path}")
            return None
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error in {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading {file_path}: {e}")
            return None
    
    def _validate_content_list(self, content_list: List[Dict[str, Any]], file_name: str) -> ContentValidationResult:
        """Validate a list of content items."""
        result = ContentValidationResult(is_valid=True)
        
        if not isinstance(content_list, list):
            result.is_valid = False
            result.errors.append(f"Content must be a list, got {type(content_list)}")
            return result
        
        for i, item in enumerate(content_list):
            if not isinstance(item, dict):
                result.errors.append(f"Item {i} must be a dictionary, got {type(item)}")
                continue
            
            # Check required fields
            missing_fields = []
            for field in self.REQUIRED_FIELDS:
                if field not in item:
                    missing_fields.append(field)
            
            if missing_fields:
                result.errors.append(f"Item {i} missing required fields: {missing_fields}")
                continue
            
            # Validate field types and values
            validation_errors = self._validate_content_item(item, i)
            result.errors.extend(validation_errors)
            
            if not validation_errors:
                result.validated_items += 1
        
        # Determine overall validity
        if result.errors:
            if result.validated_items == 0:
                result.is_valid = False
            else:
                # Some items are valid, just log warnings for invalid ones
                result.warnings.extend(result.errors)
                result.errors = []
                logger.warning(f"Some content items in {file_name} have validation issues but proceeding with valid items")
        
        return result
    
    def _validate_content_item(self, item: Dict[str, Any], index: int) -> List[str]:
        """Validate a single content item."""
        errors = []
        
        # Validate age range
        min_age = item.get('min_age')
        max_age = item.get('max_age')
        
        if not isinstance(min_age, int) or not isinstance(max_age, int):
            errors.append(f"Item {index}: min_age and max_age must be integers")
        elif min_age < 3 or max_age > 13 or min_age > max_age:
            errors.append(f"Item {index}: invalid age range {min_age}-{max_age} (must be 3-13)")
        
        # Validate topic
        topic = item.get('topic')
        if not isinstance(topic, str) or not topic.strip():
            errors.append(f"Item {index}: topic must be a non-empty string")
        
        # Validate content
        content = item.get('content')
        if not isinstance(content, str) or not content.strip():
            errors.append(f"Item {index}: content must be a non-empty string")
        
        # Validate optional fields
        difficulty = item.get('difficulty')
        if difficulty and difficulty not in ['easy', 'medium', 'hard']:
            errors.append(f"Item {index}: difficulty must be 'easy', 'medium', or 'hard'")
        
        duration = item.get('duration')
        if duration and not isinstance(duration, (int, float)):
            errors.append(f"Item {index}: duration must be a number")
        
        return errors
    
    def _rebuild_search_index(self):
        """Rebuild the search index from current content."""
        logger.debug("Rebuilding search index...")
        start_time = time.time()
        
        self.index.clear()
        indexed_count = 0
        
        for file_name, content_list in self.contents.items():
            for i, item in enumerate(content_list):
                content_id = f"{file_name}:{i}"
                self.index.add_content(item, content_id)
                indexed_count += 1
        
        index_time = time.time() - start_time
        logger.info(f"Search index rebuilt: {indexed_count} items indexed in {index_time:.2f}s")
    
    def _create_default_content(self):
        """Create default educational content for demonstration."""
        default_content = [
            {
                "topic": "colors",
                "title": "Learning Colors",
                "content": "Red is the color of apples and fire trucks. Blue is the color of the sky and ocean.",
                "subject": "art",
                "min_age": 3,
                "max_age": 5,
                "difficulty": "easy",
                "duration": 5,
                "keywords": ["red", "blue", "colors", "learning"]
            },
            {
                "topic": "numbers",
                "title": "Counting to Ten",
                "content": "Let's count together: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10! Great job!",
                "subject": "math",
                "min_age": 4,
                "max_age": 6,
                "difficulty": "easy",
                "duration": 10,
                "keywords": ["counting", "numbers", "math", "one to ten"]
            }
        ]
        
        default_file = os.path.join(self.templates_dir, "default_educational_content.json")
        try:
            with open(default_file, 'w', encoding='utf-8') as f:
                json.dump(default_content, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created default content file: {default_file}")
            
            # Load the default content
            self._load_all_contents()
            
        except Exception as e:
            logger.error(f"Failed to create default content: {e}")
    
    def get_content(self, topic: str) -> Optional[Dict[str, Any]]:
        """
        Get educational content by topic with efficient indexed search.
        
        Args:
            topic: The topic to search for
            
        Returns:
            Content dictionary if found, None otherwise
        """
        try:
            if not topic:
                logger.warning("get_content called with empty topic")
                return None
            
            topic_lower = topic.lower().strip()
            logger.debug(f"Searching for content with topic: '{topic_lower}'")
            
            # Try indexed search first (much faster)
            if topic_lower in self.index.topic_index:
                content_list = self.index.topic_index[topic_lower]
                if content_list:
                    result = content_list[0]  # Return first match
                    logger.debug(f"Found content for topic '{topic_lower}' via index")
                    return result
            
            # Fallback to linear search for partial matches
            for file_name, content_list in self.contents.items():
                for item in content_list:
                    item_topic = item.get('topic', '').lower()
                    if item_topic == topic_lower or topic_lower in item_topic:
                        logger.debug(f"Found content for topic '{topic_lower}' via linear search")
                        return item
            
            logger.info(f"No content found for topic: '{topic}'")
            return None
            
        except Exception as e:
            logger.error(f"Error searching for content with topic '{topic}': {e}")
            return None
    
    def search_content(
        self, 
        query: str = "", 
        subject: str = "", 
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        difficulty: str = "",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Advanced content search with multiple filters.
        
        Args:
            query: Text query to search in content
            subject: Subject filter
            min_age: Minimum age filter
            max_age: Maximum age filter
            difficulty: Difficulty level filter
            limit: Maximum number of results
            
        Returns:
            List of matching content items
        """
        try:
            logger.debug(f"Searching content: query='{query}', subject='{subject}', ages={min_age}-{max_age}")
            
            results = []
            candidates = set()
            
            # Get candidates from relevant indexes
            if subject:
                subject_lower = subject.lower()
                if subject_lower in self.index.subject_index:
                    candidates.update(id(item) for item in self.index.subject_index[subject_lower])
            
            if difficulty:
                difficulty_lower = difficulty.lower()
                if difficulty_lower in self.index.difficulty_index:
                    difficulty_candidates = {id(item) for item in self.index.difficulty_index[difficulty_lower]}
                    if candidates:
                        candidates &= difficulty_candidates
                    else:
                        candidates = difficulty_candidates
            
            # Age filtering
            if min_age is not None:
                age_candidates = set()
                for age in range(min_age, (max_age or 13) + 1):
                    if age in self.index.age_index:
                        age_candidates.update(id(item) for item in self.index.age_index[age])
                
                if candidates:
                    candidates &= age_candidates
                else:
                    candidates = age_candidates
            
            # If no specific filters, search all content
            if not candidates and not any([subject, difficulty, min_age]):
                candidates = {id(item) for content_list in self.contents.values() for item in content_list}
            
            # Text search within candidates
            if query:
                query_words = query.lower().split()
                text_candidates = set()
                
                for word in query_words:
                    if word in self.index.full_text_index:
                        # Convert content_ids back to actual content objects
                        for content_id in self.index.full_text_index[word]:
                            file_name, index_str = content_id.split(':', 1)
                            index = int(index_str)
                            if file_name in self.contents and index < len(self.contents[file_name]):
                                item = self.contents[file_name][index]
                                text_candidates.add(id(item))
                
                if candidates:
                    candidates &= text_candidates
                else:
                    candidates = text_candidates
            
            # Convert candidate IDs back to actual content objects
            for content_list in self.contents.values():
                for item in content_list:
                    if id(item) in candidates:
                        results.append(item)
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break
            
            logger.debug(f"Search completed: {len(results)} results found")
            return results
            
        except Exception as e:
            logger.error(f"Error in content search: {e}")
            return []
    
    def get_content_by_age(self, target_age: int) -> List[Dict[str, Any]]:
        """Get all content appropriate for a specific age."""
        try:
            if target_age not in range(3, 14):
                logger.warning(f"Age {target_age} outside valid range (3-13)")
                return []
            
            if target_age in self.index.age_index:
                return self.index.age_index[target_age].copy()
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting content for age {target_age}: {e}")
            return []
    
    def get_all_topics(self) -> Set[str]:
        """Get all available topics."""
        return set(self.index.topic_index.keys())
    
    def get_all_subjects(self) -> Set[str]:
        """Get all available subjects."""
        return set(self.index.subject_index.keys())
    
    def get_content_stats(self) -> Dict[str, Any]:
        """Get detailed statistics about loaded content."""
        try:
            total_items = sum(len(items) for items in self.contents.values())
            
            stats = {
                'total_files': len(self.contents),
                'total_items': total_items,
                'topics_count': len(self.index.topic_index.keys()),
                'subjects_count': len(self.index.subject_index.keys()),
                'age_ranges': {},
                'difficulty_distribution': {},
                'file_details': {}
            }
            
            # Age range distribution
            for age in range(3, 14):
                if age in self.index.age_index:
                    stats['age_ranges'][age] = len(self.index.age_index[age])
            
            # Difficulty distribution
            for difficulty, items in self.index.difficulty_index.items():
                stats['difficulty_distribution'][difficulty] = len(items)
            
            # File details
            for file_name, metadata in self.metadata.items():
                stats['file_details'][file_name] = {
                    'content_count': metadata.content_count,
                    'topics': list(metadata.topics),
                    'subjects': list(metadata.subjects),
                    'file_size': metadata.file_size,
                    'last_modified': metadata.last_modified
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error generating content stats: {e}")
            return {'error': str(e)}
    
    def reload_content(self, force: bool = False) -> bool:
        """
        Reload content from files.
        
        Args:
            force: Force reload even if cache is valid
            
        Returns:
            True if reload was successful
        """
        try:
            if force:
                self._last_scan_time = 0  # Force rescan
            
            logger.info("Reloading educational content...")
            self._load_all_contents()
            return True
            
        except Exception as e:
            logger.error(f"Error reloading content: {e}")
            return False
    
    def validate_all_content(self) -> Dict[str, ContentValidationResult]:
        """Validate all loaded content and return detailed results."""
        validation_results = {}
        
        for file_name, content_list in self.contents.items():
            result = self._validate_content_list(content_list, file_name)
            validation_results[file_name] = result
        
        return validation_results
