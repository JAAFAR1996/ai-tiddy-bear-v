#!/usr/bin/env python3
"""
Service Consolidator
Merges duplicate service implementations into single, unified services.
"""

import ast
import os
import shutil
from pathlib import Path
from typing import Dict, List, Set, Tuple
import json
from datetime import datetime
from collections import defaultdict

class ServiceConsolidator:
    """Consolidate duplicate services into unified implementations."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.consolidation_log = {
            "timestamp": datetime.now().isoformat(),
            "consolidated": [],
            "merged_methods": {},
            "import_mappings": {},
            "backup_locations": {}
        }
    
    def consolidate_services(self):
        """Main consolidation process."""
        print("🔧 Starting Service Consolidation...")
        print("=" * 60)
        
        # Load duplication report
        report_path = self.project_root / "service_duplication_report.json"
        if not report_path.exists():
            print("❌ No duplication report found. Run service_duplicate_analyzer.py first.")
            return
        
        with open(report_path, 'r') as f:
            duplication_report = json.load(f)
        
        # Process each duplicate set
        for recommendation in duplication_report["recommendations"]:
            self.consolidate_service_set(recommendation)
        
        # Save consolidation log
        self.save_consolidation_log()
    
    def consolidate_service_set(self, recommendation: Dict):
        """Consolidate a set of duplicate services."""
        service_type = recommendation["service_type"]
        print(f"\n🔨 Consolidating {service_type} service...")
        
        # 1. Create backup
        self.create_backups(recommendation["current_files"])
        
        # 2. Analyze all implementations
        implementations = self.analyze_implementations(recommendation["current_files"])
        
        # 3. Create unified service
        target_file = self.project_root / recommendation["target_file"]
        base_file = self.project_root / recommendation["base_implementation"]
        
        # 4. Merge implementations
        unified_content = self.merge_implementations(
            service_type,
            base_file,
            implementations,
            recommendation["current_files"]
        )
        
        # 5. Write unified service
        self.write_unified_service(target_file, unified_content)
        
        # 6. Create compatibility layer
        self.create_compatibility_layer(service_type, recommendation["current_files"], target_file)
        
        # 7. Log consolidation
        self.consolidation_log["consolidated"].append({
            "service": service_type,
            "from": recommendation["current_files"],
            "to": str(target_file.relative_to(self.project_root)),
            "timestamp": datetime.now().isoformat()
        })
        
        print(f"✅ {service_type} service consolidated successfully")
    
    def create_backups(self, files: List[str]):
        """Create backups of files to be consolidated."""
        backup_dir = self.project_root / "backups" / f"consolidation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        for file_path in files:
            src = self.project_root / file_path
            if src.exists():
                dst = backup_dir / file_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                self.consolidation_log["backup_locations"][file_path] = str(dst)
                print(f"  📦 Backed up: {file_path}")
    
    def analyze_implementations(self, files: List[str]) -> Dict:
        """Analyze all implementations to extract methods and functionality."""
        implementations = {}
        
        for file_path in files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                
                # Extract classes and methods
                classes = {}
                imports = []
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        methods = []
                        for item in node.body:
                            if isinstance(item, ast.FunctionDef):
                                methods.append({
                                    "name": item.name,
                                    "args": [arg.arg for arg in item.args.args],
                                    "decorators": [ast.unparse(d) for d in item.decorator_list],
                                    "is_async": isinstance(item, ast.AsyncFunctionDef),
                                    "docstring": ast.get_docstring(item),
                                    "body": ast.unparse(item)
                                })
                        classes[node.name] = {
                            "methods": methods,
                            "bases": [ast.unparse(base) for base in node.bases],
                            "decorators": [ast.unparse(d) for d in node.decorator_list]
                        }
                    elif isinstance(node, (ast.Import, ast.ImportFrom)):
                        imports.append(ast.unparse(node))
                
                implementations[file_path] = {
                    "content": content,
                    "classes": classes,
                    "imports": imports
                }
                
            except Exception as e:
                print(f"  ⚠️  Error analyzing {file_path}: {e}")
        
        return implementations
    
    def merge_implementations(self, service_type: str, base_file: Path, implementations: Dict, all_files: List[str]) -> str:
        """Merge all implementations into a unified service."""
        # Start with base implementation
        base_path = str(base_file.relative_to(self.project_root))
        if base_path not in implementations:
            # If base doesn't exist, use the first available
            base_path = next(iter(implementations.keys()))
        
        base_impl = implementations[base_path]
        
        # Collect all unique methods
        all_methods = {}
        all_imports = set()
        
        for file_path, impl in implementations.items():
            all_imports.update(impl["imports"])
            
            for class_name, class_info in impl["classes"].items():
                if class_name not in all_methods:
                    all_methods[class_name] = {}
                
                for method in class_info["methods"]:
                    method_key = method["name"]
                    if method_key not in all_methods[class_name]:
                        all_methods[class_name][method_key] = method
                        self.consolidation_log["merged_methods"].setdefault(service_type, []).append({
                            "method": method_key,
                            "from": file_path,
                            "class": class_name
                        })
        
        # Build unified service content
        unified_content = self._build_unified_service(
            service_type,
            base_impl,
            all_methods,
            all_imports
        )
        
        return unified_content
    
    def _build_unified_service(self, service_type: str, base_impl: Dict, all_methods: Dict, all_imports: Set[str]) -> str:
        """Build the unified service content."""
        # Clean up imports
        cleaned_imports = self._clean_imports(all_imports)
        
        # Generate header
        header = f'''"""Unified {service_type.title()} Service - Single Source of Truth

This unified service consolidates all {service_type} service implementations.
Auto-generated on: {datetime.now().isoformat()}

Merged from multiple implementations to provide a single, comprehensive service.
"""

'''
        
        # Add imports
        imports_section = "\n".join(sorted(cleaned_imports)) + "\n\n"
        
        # Add logging
        logging_section = """import logging

logger = logging.getLogger(__name__)

"""
        
        # Build unified class
        class_content = ""
        
        # Use the main service class from implementations
        main_class_name = None
        for class_name in all_methods.keys():
            if "Service" in class_name and "Consolidated" not in class_name:
                main_class_name = class_name
                break
        
        if not main_class_name and all_methods:
            main_class_name = list(all_methods.keys())[0]
        
        if main_class_name:
            # Generate unified class
            class_content = f"class {main_class_name}:\n"
            class_content += f'    """Unified {service_type} service with all functionality."""\n\n'
            
            # Add all methods
            methods = all_methods.get(main_class_name, {})
            
            # Ensure __init__ comes first
            if "__init__" in methods:
                method = methods["__init__"]
                class_content += self._format_method(method)
                class_content += "\n"
            
            # Add other methods
            for method_name, method in sorted(methods.items()):
                if method_name != "__init__":
                    class_content += self._format_method(method)
                    class_content += "\n"
        
        # Combine all sections
        unified_content = header + imports_section + logging_section + class_content
        
        return unified_content
    
    def _clean_imports(self, imports: Set[str]) -> List[str]:
        """Clean and deduplicate imports."""
        cleaned = set()
        
        for imp in imports:
            # Skip relative imports from old locations
            if "from ." in imp or "from src.services" in imp:
                # Convert to proper imports
                imp = imp.replace("from .", "from src.application.services.")
                imp = imp.replace("from src.services", "from src.application.services")
            
            cleaned.add(imp)
        
        # Remove duplicates and sort
        final_imports = []
        seen = set()
        
        for imp in sorted(cleaned):
            # Extract module name for deduplication
            if "import" in imp:
                parts = imp.split("import")
                if len(parts) > 1:
                    module = parts[0].strip()
                    if module not in seen:
                        seen.add(module)
                        final_imports.append(imp)
                else:
                    final_imports.append(imp)
            else:
                final_imports.append(imp)
        
        return final_imports
    
    def _format_method(self, method: Dict) -> str:
        """Format a method for inclusion in the unified class."""
        # For now, return the original method body
        # In a real implementation, we'd parse and clean this up
        body = method.get("body", "")
        
        # Indent for class
        lines = body.split("\n")
        indented = []
        for line in lines:
            if line.strip():
                indented.append("    " + line)
            else:
                indented.append("")
        
        return "\n".join(indented)
    
    def write_unified_service(self, target_file: Path, content: str):
        """Write the unified service to the target location."""
        # Ensure directory exists
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"  ✅ Written unified service to: {target_file.relative_to(self.project_root)}")
    
    def create_compatibility_layer(self, service_type: str, old_files: List[str], new_file: Path):
        """Create compatibility imports for smooth migration."""
        new_module = str(new_file.relative_to(self.project_root)).replace("/", ".").replace(".py", "")
        
        for old_file in old_files:
            old_path = self.project_root / old_file
            if old_path.exists() and old_path != new_file:
                # Create deprecation wrapper
                compat_content = f'''"""Compatibility layer for {service_type} service migration.

This module provides backward compatibility during the migration to unified services.
It will be removed in a future version.
"""

import warnings
from {new_module} import *

warnings.warn(
    f"Importing from {{__name__}} is deprecated. "
    f"Please import from {new_module} instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything for compatibility
__all__ = [name for name in dir() if not name.startswith("_")]
'''
                
                # Write compatibility file
                with open(old_path, 'w', encoding='utf-8') as f:
                    f.write(compat_content)
                
                self.consolidation_log["import_mappings"][old_file] = new_module
                print(f"  🔄 Created compatibility layer for: {old_file}")
    
    def save_consolidation_log(self):
        """Save consolidation log for reference."""
        log_path = self.project_root / "service_consolidation_log.json"
        
        with open(log_path, 'w') as f:
            json.dump(self.consolidation_log, f, indent=2)
        
        print(f"\n📋 Consolidation log saved to: {log_path}")
        
        # Print summary
        print("\n" + "=" * 60)
        print("SERVICE CONSOLIDATION COMPLETE")
        print("=" * 60)
        print(f"Services consolidated: {len(self.consolidation_log['consolidated'])}")
        print(f"Import mappings created: {len(self.consolidation_log['import_mappings'])}")
        
        # Print migration instructions
        print("\n📝 Next Steps:")
        print("1. Run tests to verify functionality: pytest tests/")
        print("2. Update remaining imports: python scripts/update_service_imports.py")
        print("3. Monitor deprecation warnings in logs")
        print("4. Remove old implementations after verification period")


def main():
    """Run service consolidation."""
    project_root = Path(__file__).parent.parent
    consolidator = ServiceConsolidator(project_root)
    consolidator.consolidate_services()


if __name__ == "__main__":
    main()