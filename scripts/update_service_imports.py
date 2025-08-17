#!/usr/bin/env python3
"""
Update Service Imports
Updates all imports to use the new unified service locations.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
import json
import re

class ServiceImportUpdater:
    """Update imports throughout the codebase to use unified services."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.tests_dir = project_root / "tests"
        
        # Load consolidation log if available
        log_path = project_root / "service_consolidation_log.json"
        if log_path.exists():
            with open(log_path, 'r') as f:
                self.consolidation_log = json.load(f)
        else:
            self.consolidation_log = {"import_mappings": {}}
        
        # Define import mappings
        self.import_mappings = {
            # AI Service mappings
            "from src.services.ai_service import": "from src.application.services.ai_service import",
            "from src.application.services.ai.ai_service import": "from src.application.services.ai_service import",
            "from src.core.services import AITeddyBearService": "from src.application.services.ai_service import AIService",
            "from src.services.ai_service import ConsolidatedAIService": "from src.application.services.ai_service import AIService",
            
            # Audio Service mappings
            "from src.services.audio_service import": "from src.application.services.audio_service import",
            "from src.application.services.device.voice_service import": "from src.application.services.audio_service import",
            "from src.services.audio_service import ConsolidatedAudioService": "from src.application.services.audio_service import AudioService",
            
            # Child Safety Service mappings
            "from src.services.child_safety_service import": "from src.application.services.child_safety_service import",
            "from src.application.services.child_safety.child_safety_service import": "from src.application.services.child_safety_service import",
            "from src.services.child_safety_service import ConsolidatedChildSafetyService": "from src.application.services.child_safety_service import ChildSafetyService",
            
            # User Service mappings
            "from src.services.user_service import": "from src.application.services.user_service import",
            "from src.services.user_service import ConsolidatedUserService": "from src.application.services.user_service import UserService",
            
            # Conversation Service mappings
            "from src.services.conversation_service import": "from src.application.services.conversation_service import",
            "from src.services.conversation_service import ConsolidatedConversationService": "from src.application.services.conversation_service import ConversationService",
        }
        
        self.class_mappings = {
            "ConsolidatedAIService": "AIService",
            "ConsolidatedAudioService": "AudioService",
            "ConsolidatedChildSafetyService": "ChildSafetyService",
            "ConsolidatedUserService": "UserService",
            "ConsolidatedConversationService": "ConversationService",
            "AITeddyBearService": "AIService",
        }
        
        self.update_log = {
            "files_updated": [],
            "imports_updated": [],
            "classes_renamed": [],
            "errors": []
        }
    
    def update_all_imports(self):
        """Update all imports in the codebase."""
        print("🔄 Updating Service Imports...")
        print("=" * 60)
        
        # Find all Python files
        python_files = []
        for directory in [self.src_dir, self.tests_dir]:
            if directory.exists():
                python_files.extend(directory.rglob("*.py"))
        
        # Update each file
        for file_path in python_files:
            if "__pycache__" in str(file_path):
                continue
            
            self.update_file_imports(file_path)
        
        # Save update log
        self.save_update_log()
    
    def update_file_imports(self, file_path: Path):
        """Update imports in a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            updated = False
            
            # Update import statements
            for old_import, new_import in self.import_mappings.items():
                if old_import in content:
                    content = content.replace(old_import, new_import)
                    self.update_log["imports_updated"].append({
                        "file": str(file_path.relative_to(self.project_root)),
                        "from": old_import,
                        "to": new_import
                    })
                    updated = True
            
            # Update class names
            for old_class, new_class in self.class_mappings.items():
                # Update class instantiation
                pattern = rf'\b{old_class}\b(?=\s*\()'
                if re.search(pattern, content):
                    content = re.sub(pattern, new_class, content)
                    self.update_log["classes_renamed"].append({
                        "file": str(file_path.relative_to(self.project_root)),
                        "from": old_class,
                        "to": new_class
                    })
                    updated = True
                
                # Update type hints
                pattern = rf':\s*{old_class}\b'
                if re.search(pattern, content):
                    content = re.sub(pattern, f': {new_class}', content)
                    updated = True
            
            # Write back if changed
            if updated and content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.update_log["files_updated"].append(str(file_path.relative_to(self.project_root)))
                print(f"  ✅ Updated: {file_path.relative_to(self.project_root)}")
        
        except Exception as e:
            self.update_log["errors"].append({
                "file": str(file_path.relative_to(self.project_root)),
                "error": str(e)
            })
            print(f"  ❌ Error updating {file_path}: {e}")
    
    def save_update_log(self):
        """Save the update log."""
        log_path = self.project_root / "service_import_update_log.json"
        
        with open(log_path, 'w') as f:
            json.dump(self.update_log, f, indent=2)
        
        # Print summary
        print("\n" + "=" * 60)
        print("IMPORT UPDATE COMPLETE")
        print("=" * 60)
        print(f"Files updated: {len(self.update_log['files_updated'])}")
        print(f"Imports updated: {len(self.update_log['imports_updated'])}")
        print(f"Classes renamed: {len(self.update_log['classes_renamed'])}")
        print(f"Errors: {len(self.update_log['errors'])}")
        
        if self.update_log["errors"]:
            print("\n⚠️  Errors encountered:")
            for error in self.update_log["errors"][:5]:
                print(f"  - {error['file']}: {error['error']}")
        
        print(f"\nDetailed log saved to: {log_path}")


def main():
    """Run import updates."""
    project_root = Path(__file__).parent.parent
    updater = ServiceImportUpdater(project_root)
    updater.update_all_imports()


if __name__ == "__main__":
    main()