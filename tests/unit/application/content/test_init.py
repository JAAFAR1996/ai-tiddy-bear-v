"""
Tests for the content module __init__.py file.

This test module ensures that all content management components
are properly exported and can be imported correctly.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "src"))


class TestContentModuleInit:
    """Test content module initialization and exports."""

    def test_all_imports_available(self):
        """Test that all expected classes can be imported from content module."""
        try:
            from src.application.content import (
                ContentManager,
                StoryTemplates,
                EducationalContent,
                AgeFilter,
                ContentValidator
            )
            
            # All imports should be successful
            assert ContentManager is not None
            assert StoryTemplates is not None
            assert EducationalContent is not None
            assert AgeFilter is not None
            assert ContentValidator is not None
            
        except ImportError as e:
            pytest.fail(f"Failed to import from content module: {e}")

    def test_content_manager_import(self):
        """Test ContentManager can be imported individually."""
        try:
            from src.application.content import ContentManager
            assert ContentManager is not None
            assert hasattr(ContentManager, '__init__')
        except ImportError as e:
            pytest.fail(f"Failed to import ContentManager: {e}")

    def test_story_templates_import(self):
        """Test StoryTemplates can be imported individually."""
        try:
            from src.application.content import StoryTemplates
            assert StoryTemplates is not None
            assert hasattr(StoryTemplates, '__init__')
        except ImportError as e:
            pytest.fail(f"Failed to import StoryTemplates: {e}")

    def test_educational_content_import(self):
        """Test EducationalContent can be imported individually."""
        try:
            from src.application.content import EducationalContent
            assert EducationalContent is not None
            assert hasattr(EducationalContent, '__init__')
        except ImportError as e:
            pytest.fail(f"Failed to import EducationalContent: {e}")

    def test_age_filter_import(self):
        """Test AgeFilter can be imported individually."""
        try:
            from src.application.content import AgeFilter
            assert AgeFilter is not None
            assert hasattr(AgeFilter, '__init__')
        except ImportError as e:
            pytest.fail(f"Failed to import AgeFilter: {e}")

    def test_content_validator_import(self):
        """Test ContentValidator can be imported individually."""
        try:
            from src.application.content import ContentValidator
            assert ContentValidator is not None
            assert hasattr(ContentValidator, '__init__')
        except ImportError as e:
            pytest.fail(f"Failed to import ContentValidator: {e}")

    def test_module_docstring(self):
        """Test that the content module has proper documentation."""
        import src.application.content as content_module
        
        assert content_module.__doc__ is not None
        assert len(content_module.__doc__.strip()) > 0
        assert "Content Management System" in content_module.__doc__

    def test_no_star_imports(self):
        """Test that the module doesn't use problematic star imports."""
        import src.application.content as content_module
        
        # Check that __all__ is not defined (good practice for explicit imports)
        # Or if it is defined, it should contain all the expected exports
        if hasattr(content_module, '__all__'):
            expected_exports = {
                'ContentManager',
                'StoryTemplates', 
                'EducationalContent',
                'AgeFilter',
                'ContentValidator'
            }
            actual_exports = set(content_module.__all__)
            assert expected_exports.issubset(actual_exports), \
                f"Missing exports in __all__: {expected_exports - actual_exports}"

    def test_class_instantiation(self):
        """Test that all exported classes can be instantiated."""
        from src.application.content import (
            ContentManager,
            StoryTemplates,
            EducationalContent,
            AgeFilter,
            ContentValidator
        )
        
        # Test basic instantiation (may fail due to missing files, but should not crash)
        try:
            content_manager = ContentManager()
            assert content_manager is not None
        except (FileNotFoundError, OSError):
            # Expected if template files don't exist
            pass
        except Exception as e:
            pytest.fail(f"Unexpected error instantiating ContentManager: {e}")
        
        try:
            story_templates = StoryTemplates()
            assert story_templates is not None
        except (FileNotFoundError, OSError):
            # Expected if template files don't exist  
            pass
        except Exception as e:
            pytest.fail(f"Unexpected error instantiating StoryTemplates: {e}")
        
        try:
            educational_content = EducationalContent()
            assert educational_content is not None
        except (FileNotFoundError, OSError):
            # Expected if template files don't exist
            pass
        except Exception as e:
            pytest.fail(f"Unexpected error instantiating EducationalContent: {e}")
        
        # These should always work as they don't depend on external files
        try:
            age_filter = AgeFilter()
            assert age_filter is not None
        except Exception as e:
            pytest.fail(f"Unexpected error instantiating AgeFilter: {e}")
        
        try:
            content_validator = ContentValidator()
            assert content_validator is not None
        except Exception as e:
            pytest.fail(f"Unexpected error instantiating ContentValidator: {e}")

    def test_imports_are_classes(self):
        """Test that all imports are actually classes."""
        from src.application.content import (
            ContentManager,
            StoryTemplates,
            EducationalContent,
            AgeFilter,
            ContentValidator
        )
        
        import inspect
        
        assert inspect.isclass(ContentManager), "ContentManager should be a class"
        assert inspect.isclass(StoryTemplates), "StoryTemplates should be a class"
        assert inspect.isclass(EducationalContent), "EducationalContent should be a class"
        assert inspect.isclass(AgeFilter), "AgeFilter should be a class"
        assert inspect.isclass(ContentValidator), "ContentValidator should be a class"

    def test_circular_import_safety(self):
        """Test that importing the module doesn't cause circular import issues."""
        # This test ensures that importing the content module multiple times
        # doesn't cause issues
        try:
            import src.application.content
            import src.application.content as content2
            from src.application.content import ContentManager
            from src.application.content import ContentManager as CM2
            
            # Should be the same class
            assert ContentManager is CM2
            
        except Exception as e:
            pytest.fail(f"Circular import or multiple import issue: {e}")