"""
StoryTemplates: Advanced story template manager with validation, versioning, and efficient memory management.
- Used by ContentManager and story generation use case
- Supports template versioning and lazy loading for memory efficiency
- Includes comprehensive error handling and structure validation
- Implements intelligent caching and indexing for high performance
- Provides detailed logging and template analytics
"""

import json
import os
import logging
import time
import hashlib
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from collections import defaultdict
from threading import Lock, RLock
# WeakValueDictionary removed due to dict compatibility issues
import glob
import re

logger = logging.getLogger(__name__)


@dataclass
class TemplateVersion:
    """Template version information."""
    version: str
    created_at: float
    author: str = "unknown"
    description: str = ""
    changelog: List[str] = field(default_factory=list)
    deprecated: bool = False
    min_app_version: str = "1.0.0"
    
    def __post_init__(self):
        """Validate version format."""
        try:
            self._validate_version_format(self.version)
        except Exception:
            raise ValueError(f"Invalid version format: {self.version}")
    
    def _validate_version_format(self, version_str: str):
        """Validate semantic version format (e.g., 1.0.0)."""
        pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)*$'
        if not re.match(pattern, version_str):
            raise ValueError(f"Invalid version format: {version_str}")


@dataclass
class TemplateMetadata:
    """Metadata for story template files."""
    file_path: str
    last_modified: float
    file_size: int
    template_count: int
    versions: Dict[str, TemplateVersion] = field(default_factory=dict)
    categories: Set[str] = field(default_factory=set)
    age_ranges: List[Tuple[int, int]] = field(default_factory=list)
    checksum: str = ""
    schema_version: str = "1.0.0"


@dataclass
class TemplateValidationResult:
    """Result of template validation."""
    is_valid: bool
    template_id: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    version_info: Optional[TemplateVersion] = None


class TemplateIndex:
    """Efficient index for story template search with thread safety."""
    
    def __init__(self):
        self.id_index: Dict[str, Dict[str, Any]] = {}  # template_id -> template
        self.category_index: Dict[str, List[str]] = defaultdict(list)  # category -> template_ids
        self.age_index: Dict[int, List[str]] = defaultdict(list)  # age -> template_ids
        self.tag_index: Dict[str, Set[str]] = defaultdict(set)  # tag -> template_ids
        self.version_index: Dict[str, Dict[str, str]] = defaultdict(dict)  # template_id -> version -> template_id
        self.full_text_index: Dict[str, Set[str]] = defaultdict(set)  # word -> template_ids
        self._lock = RLock()
        self._stats = {
            'total_templates': 0,
            'categories': set(),
            'age_ranges': set(),
            'versions': set()
        }
    
    def add_template(self, template: Dict[str, Any], file_source: str = ""):
        """Add template to all relevant indexes with thread safety."""
        with self._lock:
            template_id = template.get('id')
            if not template_id:
                logger.warning(f"Template without ID found in {file_source}")
                return
            
            # Main ID index
            self.id_index[template_id] = template.copy()
            
            # Category index
            category = template.get('category', 'general').lower()
            if template_id not in self.category_index[category]:
                self.category_index[category].append(template_id)
                self._stats['categories'].add(category)
            
            # Age index
            min_age = template.get('min_age', 3)
            max_age = template.get('max_age', 13)
            for age in range(min_age, max_age + 1):
                if template_id not in self.age_index[age]:
                    self.age_index[age].append(template_id)
                    self._stats['age_ranges'].add((min_age, max_age))
            
            # Tag index
            tags = template.get('tags', [])
            if isinstance(tags, str):
                tags = [tags]
            for tag in tags:
                tag_lower = tag.lower().strip()
                if tag_lower:
                    self.tag_index[tag_lower].add(template_id)
            
            # Version index
            template_version = template.get('version', '1.0.0')
            self.version_index[template_id][template_version] = template_id
            self._stats['versions'].add(template_version)
            
            # Full-text search index
            searchable_text = self._extract_searchable_text(template)
            words = searchable_text.lower().split()
            for word in words:
                if len(word) > 2:  # Skip very short words
                    self.full_text_index[word].add(template_id)
            
            self._stats['total_templates'] = len(self.id_index)
    
    def _extract_searchable_text(self, template: Dict[str, Any]) -> str:
        """Extract searchable text from template."""
        searchable_fields = ['title', 'description', 'content', 'summary', 'dialogue', 'narrative']
        text_parts = []
        
        for field in searchable_fields:
            if field in template:
                value = template[field]
                if isinstance(value, str):
                    text_parts.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            text_parts.append(item)
                        elif isinstance(item, dict) and 'text' in item:
                            text_parts.append(item['text'])
        
        return ' '.join(text_parts)
    
    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get template by ID with thread safety."""
        with self._lock:
            return self.id_index.get(template_id)
    
    def search_by_category(self, category: str) -> List[str]:
        """Get template IDs by category."""
        with self._lock:
            return self.category_index.get(category.lower(), []).copy()
    
    def search_by_age(self, age: int) -> List[str]:
        """Get template IDs suitable for specific age."""
        with self._lock:
            return self.age_index.get(age, []).copy()
    
    def search_by_tags(self, tags: List[str]) -> Set[str]:
        """Get template IDs that match any of the given tags."""
        with self._lock:
            result = set()
            for tag in tags:
                tag_lower = tag.lower().strip()
                if tag_lower in self.tag_index:
                    result.update(self.tag_index[tag_lower])
            return result
    
    def search_text(self, query: str) -> Set[str]:
        """Full-text search in templates."""
        with self._lock:
            query_words = query.lower().split()
            if not query_words:
                return set()
            
            # Start with templates matching the first word
            result = set(self.full_text_index.get(query_words[0], set()))
            
            # Intersect with templates matching other words
            for word in query_words[1:]:
                if word in self.full_text_index:
                    result &= self.full_text_index[word]
                else:
                    return set()  # If any word is not found, no results
            
            return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        with self._lock:
            return {
                'total_templates': self._stats['total_templates'],
                'categories': list(self._stats['categories']),
                'age_ranges': list(self._stats['age_ranges']),
                'versions': list(self._stats['versions'])
            }
    
    def clear(self):
        """Clear all indexes."""
        with self._lock:
            self.id_index.clear()
            self.category_index.clear()
            self.age_index.clear()
            self.tag_index.clear()
            self.version_index.clear()
            self.full_text_index.clear()
            self._stats = {
                'total_templates': 0,
                'categories': set(),
                'age_ranges': set(),
                'versions': set()
            }


class LazyTemplateLoader:
    """Lazy loader for templates to manage memory efficiently."""
    
    def __init__(self, max_cache_size: int = 100):
        self.max_cache_size = max_cache_size
        self.cache: Dict[str, Dict[str, Any]] = {}  # Regular dict instead of WeakValueDictionary
        self.access_times: Dict[str, float] = {}
        self.file_paths: Dict[str, str] = {}  # template_id -> file_path
        self._lock = Lock()
    
    def register_template(self, template_id: str, file_path: str):
        """Register a template for lazy loading."""
        with self._lock:
            self.file_paths[template_id] = file_path
    
    def load_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Load template on-demand."""
        with self._lock:
            # Check cache first
            if template_id in self.cache:
                self.access_times[template_id] = time.time()
                return self.cache[template_id]
            
            # Load from file
            file_path = self.file_paths.get(template_id)
            if not file_path:
                return None
            
            try:
                template = self._load_from_file(file_path, template_id)
                if template:
                    # Manage cache size
                    self._manage_cache_size()
                    
                    # Add to cache
                    self.cache[template_id] = template
                    self.access_times[template_id] = time.time()
                    
                return template
                
            except Exception as e:
                logger.error(f"Error lazy loading template {template_id}: {e}")
                return None
    
    def _load_from_file(self, file_path: str, target_template_id: str) -> Optional[Dict[str, Any]]:
        """Load specific template from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON structures
            templates = data if isinstance(data, list) else data.get('templates', [data])
            
            for template in templates:
                if template.get('id') == target_template_id:
                    return template
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading template from {file_path}: {e}")
            return None
    
    def _manage_cache_size(self):
        """Remove least recently used templates to maintain cache size."""
        if len(self.cache) >= self.max_cache_size:
            # Find least recently used template
            if self.access_times:
                lru_template_id = min(self.access_times.keys(), 
                                    key=lambda k: self.access_times[k])
                
                # Remove from cache
                if lru_template_id in self.cache:
                    del self.cache[lru_template_id]
                if lru_template_id in self.access_times:
                    del self.access_times[lru_template_id]
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'cache_size': len(self.cache),
                'max_cache_size': self.max_cache_size,
                'registered_templates': len(self.file_paths),
                'hit_rate': len(self.cache) / max(len(self.file_paths), 1)
            }


class StoryTemplates:
    """Advanced story template manager with validation, versioning, and efficient memory management."""
    
    # Supported file patterns for dynamic discovery
    SUPPORTED_PATTERNS = [
        "*story*.json",
        "*template*.json",
        "*bedtime*.json",
        "*interactive*.json",
        "*game*.json"
    ]
    
    # Template schema requirements
    REQUIRED_FIELDS = ['id', 'title', 'content']
    OPTIONAL_FIELDS = ['category', 'description', 'min_age', 'max_age', 'tags', 'version', 'author']
    
    # Template schema versions
    SUPPORTED_SCHEMA_VERSIONS = ['1.0.0', '1.1.0', '2.0.0']
    CURRENT_SCHEMA_VERSION = '2.0.0'
    
    def __init__(self, 
                 templates_dir: Optional[str] = None,
                 lazy_loading: bool = True,
                 max_cache_size: int = 100):
        """
        Initialize StoryTemplates with advanced features.
        
        Args:
            templates_dir: Directory containing template files
            lazy_loading: Enable lazy loading for memory efficiency
            max_cache_size: Maximum number of templates to keep in memory
        """
        self.lazy_loading = lazy_loading
        self.templates_dir = self._determine_templates_directory(templates_dir)
        self.index = TemplateIndex()
        self.lazy_loader = LazyTemplateLoader(max_cache_size) if lazy_loading else None
        self.metadata: Dict[str, TemplateMetadata] = {}
        self._cache_lock = RLock()
        self._last_scan_time = 0
        self._scan_interval = 300  # 5 minutes
        
        # Performance metrics
        self._metrics = {
            'load_time': 0,
            'validation_time': 0,
            'indexing_time': 0,
            'templates_loaded': 0,
            'templates_failed': 0
        }
        
        try:
            logger.info(f"Initializing StoryTemplates with directory: {self.templates_dir}")
            self._load_all_templates()
            logger.info(f"StoryTemplates initialized successfully with {self.index._stats['total_templates']} templates")
        except Exception as e:
            logger.error(f"Failed to initialize StoryTemplates: {e}")
            # Initialize empty to prevent crashes
            self.index = TemplateIndex()
    
    def _determine_templates_directory(self, custom_dir: Optional[str]) -> str:
        """Determine templates directory with fallback options."""
        if custom_dir and os.path.exists(custom_dir):
            return custom_dir
        
        # Default directory
        default_dir = os.path.join(os.path.dirname(__file__), "../templates/stories")
        if os.path.exists(default_dir):
            return default_dir
        
        # Alternative directories
        alternative_dirs = [
            os.path.join(os.path.dirname(__file__), "../../templates/stories"),
            os.path.join(os.path.dirname(__file__), "../../../templates/stories"),
            os.path.join(os.path.dirname(__file__), "../../../content/stories")
        ]
        
        for alt_dir in alternative_dirs:
            if os.path.exists(alt_dir):
                logger.info(f"Using alternative templates directory: {alt_dir}")
                return alt_dir
        
        # Create default directory
        os.makedirs(default_dir, exist_ok=True)
        logger.warning(f"Created default templates directory: {default_dir}")
        return default_dir
    
    def _discover_template_files(self) -> List[str]:
        """Dynamically discover all template files."""
        discovered_files = []
        
        try:
            for pattern in self.SUPPORTED_PATTERNS:
                pattern_path = os.path.join(self.templates_dir, pattern)
                matching_files = glob.glob(pattern_path)
                discovered_files.extend(matching_files)
            
            # Remove duplicates and sort
            discovered_files = sorted(list(set(discovered_files)))
            
            logger.debug(f"Discovered {len(discovered_files)} template files: {[os.path.basename(f) for f in discovered_files]}")
            return discovered_files
            
        except Exception as e:
            logger.error(f"Error discovering template files: {e}")
            return []
    
    def _load_all_templates(self):
        """Load all templates with comprehensive error handling."""
        start_time = time.time()
        
        # Check if we need to rescan
        if (time.time() - self._last_scan_time) < self._scan_interval:
            if self.index._stats['total_templates'] > 0:
                logger.debug("Using cached templates (scan interval not reached)")
                return
        
        template_files = self._discover_template_files()
        
        if not template_files:
            logger.warning("No template files found")
            self._create_sample_templates()
            return
        
        # Clear existing data
        self.index.clear()
        if self.lazy_loader:
            self.lazy_loader = LazyTemplateLoader(self.lazy_loader.max_cache_size)
        
        successful_loads = 0
        failed_loads = 0
        
        for file_path in template_files:
            try:
                file_metadata = self._get_file_metadata(file_path)
                file_basename = os.path.basename(file_path)
                
                # Load templates from file
                templates = self._load_templates_from_file(file_path)
                if templates:
                    # Validate templates
                    valid_templates = []
                    for template in templates:
                        validation_result = self._validate_template(template, file_basename)
                        if validation_result.is_valid:
                            valid_templates.append(template)
                        else:
                            logger.warning(f"Template {validation_result.template_id} validation failed: {validation_result.errors}")
                    
                    if valid_templates:
                        # Add to index or lazy loader
                        for template in valid_templates:
                            if self.lazy_loading:
                                self.lazy_loader.register_template(template['id'], file_path)
                                # Add minimal info to index for search
                                template_minimal = {
                                    'id': template['id'],
                                    'title': template.get('title', ''),
                                    'category': template.get('category', 'general'),
                                    'min_age': template.get('min_age', 3),
                                    'max_age': template.get('max_age', 13),
                                    'tags': template.get('tags', []),
                                    'version': template.get('version', '1.0.0')
                                }
                                self.index.add_template(template_minimal, file_basename)
                            else:
                                self.index.add_template(template, file_basename)
                        
                        # Update metadata
                        file_metadata.template_count = len(valid_templates)
                        self.metadata[file_basename] = file_metadata
                        successful_loads += 1
                        
                        logger.info(f"Loaded {len(valid_templates)} templates from {file_basename}")
                    else:
                        logger.error(f"No valid templates found in {file_basename}")
                        failed_loads += 1
                else:
                    failed_loads += 1
                    
            except Exception as e:
                logger.error(f"Error loading templates from {file_path}: {e}")
                failed_loads += 1
        
        self._last_scan_time = time.time()
        load_time = time.time() - start_time
        
        self._metrics.update({
            'load_time': load_time,
            'templates_loaded': successful_loads,
            'templates_failed': failed_loads
        })
        
        logger.info(
            f"Template loading completed: {successful_loads} files succeeded, "
            f"{failed_loads} files failed, load time: {load_time:.2f}s"
        )
    
    def _get_file_metadata(self, file_path: str) -> TemplateMetadata:
        """Get metadata for a template file."""
        stat = os.stat(file_path)
        
        # Calculate checksum
        checksum = ""
        try:
            with open(file_path, 'rb') as f:
                checksum = hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Could not calculate checksum for {file_path}: {e}")
        
        return TemplateMetadata(
            file_path=file_path,
            last_modified=stat.st_mtime,
            file_size=stat.st_size,
            template_count=0,
            checksum=checksum
        )
    
    def _load_templates_from_file(self, file_path: str) -> Optional[List[Dict[str, Any]]]:
        """Load templates from a single file with comprehensive error handling."""
        try:
            logger.debug(f"Loading templates from: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle different JSON structures
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # Look for templates in various keys
                template_keys = ['templates', 'stories', 'content', 'items']
                for key in template_keys:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                
                # If no list found, treat the dict as a single template
                if 'id' in data:
                    return [data]
                
                logger.error(f"No templates found in {file_path}")
                return None
            else:
                logger.error(f"Unexpected JSON structure in {file_path}: {type(data)}")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {file_path}: {e}")
            return None
        except FileNotFoundError:
            logger.error(f"Template file not found: {file_path}")
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
    
    def _validate_template(self, template: Dict[str, Any], file_name: str) -> TemplateValidationResult:
        """Validate a single template with comprehensive checks."""
        template_id = template.get('id', 'unknown')
        result = TemplateValidationResult(is_valid=True, template_id=template_id)
        
        # Check required fields
        missing_fields = []
        for field in self.REQUIRED_FIELDS:
            if field not in template or not template[field]:
                missing_fields.append(field)
        
        if missing_fields:
            result.is_valid = False
            result.errors.append(f"Missing required fields: {missing_fields}")
        
        # Validate template ID format
        if 'id' in template:
            template_id = template['id']
            if not isinstance(template_id, str) or not template_id.strip():
                result.errors.append("Template ID must be a non-empty string")
            elif not template_id.replace('_', '').replace('-', '').isalnum():
                result.warnings.append("Template ID should contain only alphanumeric characters, hyphens, and underscores")
        
        # Validate age range
        min_age = template.get('min_age', 3)
        max_age = template.get('max_age', 13)
        
        if not isinstance(min_age, int) or not isinstance(max_age, int):
            result.errors.append("min_age and max_age must be integers")
        elif min_age < 3 or max_age > 13 or min_age > max_age:
            result.errors.append(f"Invalid age range {min_age}-{max_age} (must be 3-13)")
        
        # Validate version
        template_version = template.get('version', '1.0.0')
        try:
            result.version_info = TemplateVersion(
                version=template_version,
                created_at=time.time(),
                author=template.get('author', 'unknown'),
                description=template.get('description', '')
            )
        except Exception:
            result.warnings.append(f"Invalid version format: {template_version}")
        
        # Validate content structure
        content = template.get('content')
        if content:
            if isinstance(content, str):
                if len(content.strip()) < 10:
                    result.warnings.append("Content seems too short")
            elif isinstance(content, dict):
                # Structured content validation
                if 'text' not in content and 'sections' not in content:
                    result.warnings.append("Structured content should have 'text' or 'sections'")
            elif isinstance(content, list):
                # Multi-part content validation
                for i, part in enumerate(content):
                    if not isinstance(part, dict) or 'text' not in part:
                        result.warnings.append(f"Content part {i} should be a dict with 'text'")
        
        # Validate tags
        tags = template.get('tags', [])
        if tags and not isinstance(tags, list):
            result.warnings.append("Tags should be a list")
        
        return result
    
    def _create_sample_templates(self):
        """Create sample templates for demonstration."""
        sample_templates = [
            {
                "id": "bedtime_001",
                "title": "The Sleepy Little Star",
                "content": "Once upon a time, there was a little star who was very sleepy. The star lived high up in the sky with all the other stars...",
                "category": "bedtime",
                "description": "A gentle bedtime story about a sleepy star",
                "min_age": 3,
                "max_age": 7,
                "tags": ["bedtime", "stars", "gentle", "sleep"],
                "version": "1.0.0",
                "author": "Story Templates System",
                "created_at": time.time()
            },
            {
                "id": "educational_002",
                "title": "Counting with Forest Animals",
                "content": "In the magical forest, there lived many animals who loved to count. Let's count with them! One little rabbit hopping...",
                "category": "educational",
                "description": "Learn counting with friendly forest animals",
                "min_age": 4,
                "max_age": 8,
                "tags": ["counting", "animals", "forest", "educational"],
                "version": "1.0.0",
                "author": "Story Templates System",
                "created_at": time.time()
            }
        ]
        
        sample_file = os.path.join(self.templates_dir, "sample_story_templates.json")
        try:
            with open(sample_file, 'w', encoding='utf-8') as f:
                json.dump(sample_templates, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Created sample template file: {sample_file}")
            
            # Load the sample templates
            self._load_all_templates()
            
        except Exception as e:
            logger.error(f"Failed to create sample templates: {e}")
    
    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Get template by ID with efficient retrieval.
        
        Args:
            template_id: The template ID to retrieve
            
        Returns:
            Template dictionary if found, None otherwise
        """
        try:
            if not template_id:
                logger.warning("get_template called with empty template_id")
                return None
            
            logger.debug(f"Retrieving template: {template_id}")
            
            if self.lazy_loading and self.lazy_loader:
                # Use lazy loader
                template = self.lazy_loader.load_template(template_id)
                if template:
                    logger.debug(f"Template {template_id} loaded via lazy loader")
                return template
            else:
                # Use index
                template = self.index.get_template(template_id)
                if template:
                    logger.debug(f"Template {template_id} found in index")
                return template
            
            logger.info(f"Template not found: {template_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving template {template_id}: {e}")
            return None
    
    def search_templates(self,
                        category: str = "",
                        age: Optional[int] = None,
                        tags: Optional[List[str]] = None,
                        query: str = "",
                        limit: int = 10) -> List[Dict[str, Any]]:
        """
        Advanced template search with multiple filters.
        
        Args:
            category: Category filter
            age: Age filter
            tags: Tags filter
            query: Text search query
            limit: Maximum number of results
            
        Returns:
            List of matching templates
        """
        try:
            logger.debug(f"Searching templates: category='{category}', age={age}, tags={tags}, query='{query}'")
            
            candidate_ids = set()
            
            # Category filtering
            if category:
                category_ids = set(self.index.search_by_category(category))
                candidate_ids = category_ids if not candidate_ids else candidate_ids & category_ids
            
            # Age filtering
            if age is not None:
                age_ids = set(self.index.search_by_age(age))
                candidate_ids = age_ids if not candidate_ids else candidate_ids & age_ids
            
            # Tags filtering
            if tags:
                tag_ids = self.index.search_by_tags(tags)
                candidate_ids = tag_ids if not candidate_ids else candidate_ids & tag_ids
            
            # Text search
            if query:
                text_ids = self.index.search_text(query)
                candidate_ids = text_ids if not candidate_ids else candidate_ids & text_ids
            
            # If no filters specified, get all templates
            if not any([category, age, tags, query]):
                candidate_ids = set(self.index.id_index.keys())
            
            # Retrieve templates
            results = []
            for template_id in list(candidate_ids)[:limit]:
                template = self.get_template(template_id)
                if template:
                    results.append(template)
            
            logger.debug(f"Search completed: {len(results)} results found")
            return results
            
        except Exception as e:
            logger.error(f"Error in template search: {e}")
            return []
    
    def get_templates_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all templates in a specific category."""
        return self.search_templates(category=category, limit=100)
    
    def get_templates_by_age(self, age: int) -> List[Dict[str, Any]]:
        """Get all templates suitable for a specific age."""
        return self.search_templates(age=age, limit=100)
    
    def get_template_versions(self, template_id: str) -> List[str]:
        """Get all available versions of a template."""
        try:
            return list(self.index.version_index.get(template_id, {}).keys())
        except Exception as e:
            logger.error(f"Error getting versions for template {template_id}: {e}")
            return []
    
    def get_all_categories(self) -> Set[str]:
        """Get all available template categories."""
        return set(self.index.category_index.keys())
    
    def get_template_stats(self) -> Dict[str, Any]:
        """Get detailed statistics about loaded templates."""
        try:
            index_stats = self.index.get_stats()
            
            stats = {
                'total_templates': index_stats['total_templates'],
                'categories': index_stats['categories'],
                'age_ranges': index_stats['age_ranges'],
                'versions': index_stats['versions'],
                'file_count': len(self.metadata),
                'lazy_loading_enabled': self.lazy_loading,
                'performance_metrics': self._metrics.copy(),
                'file_details': {}
            }
            
            # Add file details
            for file_name, metadata in self.metadata.items():
                stats['file_details'][file_name] = {
                    'template_count': metadata.template_count,
                    'categories': list(metadata.categories),
                    'age_ranges': metadata.age_ranges,
                    'file_size': metadata.file_size,
                    'last_modified': metadata.last_modified
                }
            
            # Add cache stats if lazy loading is enabled
            if self.lazy_loading and self.lazy_loader:
                stats['cache_stats'] = self.lazy_loader.get_cache_stats()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error generating template stats: {e}")
            return {'error': str(e)}
    
    def reload_templates(self, force: bool = False) -> bool:
        """
        Reload templates from files.
        
        Args:
            force: Force reload even if cache is valid
            
        Returns:
            True if reload was successful
        """
        try:
            if force:
                self._last_scan_time = 0
            
            logger.info("Reloading story templates...")
            self._load_all_templates()
            return True
            
        except Exception as e:
            logger.error(f"Error reloading templates: {e}")
            return False
    
    def validate_all_templates(self) -> Dict[str, List[TemplateValidationResult]]:
        """Validate all loaded templates and return detailed results."""
        validation_results = {}
        
        for file_name, metadata in self.metadata.items():
            file_path = metadata.file_path
            templates = self._load_templates_from_file(file_path)
            
            if templates:
                file_results = []
                for template in templates:
                    result = self._validate_template(template, file_name)
                    file_results.append(result)
                validation_results[file_name] = file_results
        
        return validation_results
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get detailed performance metrics."""
        return {
            'metrics': self._metrics.copy(),
            'index_stats': self.index.get_stats(),
            'cache_stats': self.lazy_loader.get_cache_stats() if self.lazy_loader else None,
            'memory_efficient': self.lazy_loading
        }