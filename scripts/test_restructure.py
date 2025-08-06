#!/usr/bin/env python3
"""
Test Suite Restructuring Script
Enforces proper test directory structure and removes fake/dead tests.
"""

import os
import shutil
import json
from pathlib import Path
from typing import Dict, List, Set
import ast
from datetime import datetime

class TestRestructurer:
    """Restructure test suite according to best practices."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.tests_dir = project_root / "tests"
        self.report_file = project_root / "test_reality_check_report.json"
        self.actions_taken = []
        
        # Load reality check report
        with open(self.report_file, 'r') as f:
            self.reality_report = json.load(f)
    
    def restructure(self):
        """Main restructuring process."""
        print("🔧 Starting Test Suite Restructuring...")
        
        # 1. Clean up dead tests
        self.remove_dead_tests()
        
        # 2. Fix empty assertion tests
        self.fix_empty_assertions()
        
        # 3. Create proper directory structure
        self.create_directory_structure()
        
        # 4. Move tests to proper locations
        self.reorganize_tests()
        
        # 5. Create fixtures directory and base fixtures
        self.setup_fixtures()
        
        # 6. Generate report
        self.generate_report()
    
    def remove_dead_tests(self):
        """Remove tests with no corresponding source files."""
        print("\n📦 Removing dead tests...")
        
        for dead_test in self.reality_report.get("dead_tests", []):
            test_file = self.project_root / dead_test["test_file"]
            if test_file.exists():
                # Archive instead of delete
                archive_dir = self.project_root / "tests_archived"
                archive_dir.mkdir(exist_ok=True)
                
                archive_path = archive_dir / test_file.name
                shutil.move(str(test_file), str(archive_path))
                
                self.actions_taken.append({
                    "action": "archived_dead_test",
                    "file": str(test_file.relative_to(self.project_root)),
                    "reason": dead_test["reason"],
                    "archived_to": str(archive_path.relative_to(self.project_root))
                })
                print(f"  ✓ Archived: {test_file.name}")
    
    def fix_empty_assertions(self):
        """Add TODO comments to tests with empty assertions."""
        print("\n🔍 Fixing empty assertion tests...")
        
        for empty_test in self.reality_report.get("empty_assertions", []):
            test_file = self.project_root / empty_test["file"]
            if test_file.exists():
                # Read file
                with open(test_file, 'r') as f:
                    lines = f.readlines()
                
                # Add TODO comment at the function
                line_num = empty_test["line"] - 1  # 0-indexed
                indent = len(lines[line_num]) - len(lines[line_num].lstrip())
                todo_comment = " " * (indent + 4) + "# TODO: Add proper assertions to this test\n"
                
                # Insert TODO after function definition
                for i in range(line_num, len(lines)):
                    if '"""' in lines[i] or "'''" in lines[i]:
                        # Skip docstring
                        in_docstring = True
                        delimiter = '"""' if '"""' in lines[i] else "'''"
                        i += 1
                        while i < len(lines) and delimiter not in lines[i]:
                            i += 1
                        i += 1
                    if i < len(lines):
                        lines.insert(i + 1, todo_comment)
                        break
                
                # Write back
                with open(test_file, 'w') as f:
                    f.writelines(lines)
                
                self.actions_taken.append({
                    "action": "added_todo",
                    "file": str(test_file.relative_to(self.project_root)),
                    "function": empty_test["function"],
                    "line": empty_test["line"]
                })
                print(f"  ✓ Added TODO to: {test_file.name}::{empty_test['function']}")
    
    def create_directory_structure(self):
        """Create proper test directory structure."""
        print("\n📁 Creating test directory structure...")
        
        directories = [
            "tests/unit",
            "tests/integration", 
            "tests/e2e",
            "tests/performance",
            "tests/security",
            "tests/fixtures",
            "tests/mocks",
            "tests/helpers"
        ]
        
        for dir_path in directories:
            full_path = self.project_root / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            
            # Create __init__.py
            init_file = full_path / "__init__.py"
            if not init_file.exists():
                init_file.write_text('"""Test package."""\n')
                print(f"  ✓ Created: {dir_path}/")
    
    def reorganize_tests(self):
        """Move tests to appropriate directories based on markers and content."""
        print("\n🚚 Reorganizing tests...")
        
        # Map test patterns to directories
        test_patterns = {
            "unit": ["test_entities", "test_value_objects", "test_exceptions", 
                    "test_ai_response", "test_child_safety", "test_coppa_validator"],
            "integration": ["test_api_endpoints", "test_database", "test_auth",
                          "test_child_safety_integration", "test_conversation_service"],
            "e2e": ["test_child_interaction", "test_voice_to_response", "test_e2e"],
            "performance": ["test_response_times", "test_load"],
            "security": ["test_coppa_compliance", "test_security", "test_auth_security"]
        }
        
        # Don't move files that are already in the correct location
        for test_type, patterns in test_patterns.items():
            target_dir = self.tests_dir / test_type
            
            for pattern in patterns:
                # Find matching test files
                matching_files = list(self.tests_dir.glob(f"**/test_*{pattern}*.py"))
                
                for test_file in matching_files:
                    # Skip if already in correct directory
                    if test_file.parent == target_dir:
                        continue
                    
                    # Skip if in archived directory
                    if "archived" in str(test_file):
                        continue
                    
                    # Move to appropriate directory
                    target_path = target_dir / test_file.name
                    if not target_path.exists():
                        shutil.move(str(test_file), str(target_path))
                        self.actions_taken.append({
                            "action": "moved_test",
                            "from": str(test_file.relative_to(self.project_root)),
                            "to": str(target_path.relative_to(self.project_root)),
                            "category": test_type
                        })
                        print(f"  ✓ Moved {test_file.name} to {test_type}/")
    
    def setup_fixtures(self):
        """Create base fixtures and helpers."""
        print("\n🔧 Setting up fixtures...")
        
        # Create base fixtures file
        fixtures_file = self.tests_dir / "fixtures" / "__init__.py"
        fixtures_content = '''"""
Common test fixtures for AI Teddy Bear tests.
"""

import pytest
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any

from src.core.entities import Child, User, Conversation
from src.core.value_objects import AgeGroup


@pytest.fixture
def mock_child() -> Child:
    """Create a mock child entity."""
    return Child(
        id=str(uuid4()),
        name="Test Child",
        age=7,
        parent_id="parent-123",
        created_at=datetime.utcnow(),
        preferences={
            "favorite_color": "blue",
            "interests": ["robots", "space"]
        }
    )


@pytest.fixture
def mock_parent() -> User:
    """Create a mock parent user."""
    return User(
        id="parent-123",
        email="parent@example.com",
        name="Test Parent",
        created_at=datetime.utcnow()
    )


@pytest.fixture
def mock_conversation(mock_child) -> Conversation:
    """Create a mock conversation."""
    return Conversation(
        id=str(uuid4()),
        child_id=mock_child.id,
        started_at=datetime.utcnow(),
        messages=[]
    )


@pytest.fixture
def ai_response_fixture() -> Dict[str, Any]:
    """Standard AI response fixture."""
    return {
        "response": "Hello! How can I help you today?",
        "emotion": "friendly",
        "safety_score": 1.0,
        "age_appropriate": True
    }


@pytest.fixture
def audio_data_fixture() -> bytes:
    """Mock audio data for testing."""
    # Simple WAV header + silent audio
    return b'RIFF' + b'\\x00' * 100


@pytest.fixture
def test_database_url() -> str:
    """Test database URL."""
    return "postgresql://test:test@localhost:5432/teddy_test"
'''
        
        with open(fixtures_file, 'w') as f:
            f.write(fixtures_content)
        
        self.actions_taken.append({
            "action": "created_fixtures",
            "file": str(fixtures_file.relative_to(self.project_root))
        })
        
        # Create test helpers
        helpers_file = self.tests_dir / "helpers" / "__init__.py"
        helpers_content = '''"""
Test helper utilities.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict
import time


class TestTimer:
    """Simple timer for performance tests."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.time()
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


@asynccontextmanager
async def async_test_timeout(seconds: float):
    """Async context manager for test timeouts."""
    async def timeout_handler():
        await asyncio.sleep(seconds)
        raise TimeoutError(f"Test timed out after {seconds} seconds")
    
    task = asyncio.create_task(timeout_handler())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def assert_child_safe_response(response: Dict[str, Any]):
    """Assert that a response is child-safe."""
    assert response.get("safety_score", 0) >= 0.8
    assert response.get("age_appropriate", False) is True
    assert "inappropriate" not in response.get("response", "").lower()


def create_test_audio_data(duration_seconds: float = 1.0) -> bytes:
    """Create test audio data of specified duration."""
    sample_rate = 16000
    num_samples = int(sample_rate * duration_seconds)
    # Create simple sine wave
    import struct
    import math
    
    audio_data = b''
    for i in range(num_samples):
        value = int(32767 * math.sin(2 * math.pi * 440 * i / sample_rate))
        audio_data += struct.pack('<h', value)
    
    return audio_data
'''
        
        with open(helpers_file, 'w') as f:
            f.write(helpers_content)
        
        self.actions_taken.append({
            "action": "created_helpers",
            "file": str(helpers_file.relative_to(self.project_root))
        })
        
        print("  ✓ Created fixtures and helpers")
    
    def generate_report(self):
        """Generate restructuring report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "actions_taken": self.actions_taken,
            "summary": {
                "dead_tests_removed": len([a for a in self.actions_taken if a["action"] == "archived_dead_test"]),
                "empty_assertions_fixed": len([a for a in self.actions_taken if a["action"] == "added_todo"]),
                "tests_moved": len([a for a in self.actions_taken if a["action"] == "moved_test"]),
                "fixtures_created": len([a for a in self.actions_taken if a["action"] in ["created_fixtures", "created_helpers"]])
            }
        }
        
        report_path = self.project_root / "test_restructure_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\n" + "="*50)
        print("TEST RESTRUCTURING COMPLETE")
        print("="*50)
        print(f"Dead tests archived: {report['summary']['dead_tests_removed']}")
        print(f"Empty assertions marked: {report['summary']['empty_assertions_fixed']}")
        print(f"Tests reorganized: {report['summary']['tests_moved']}")
        print(f"Fixtures created: {report['summary']['fixtures_created']}")
        print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    restructurer = TestRestructurer(project_root)
    restructurer.restructure()