#!/usr/bin/env python3
"""
Service Duplication Analyzer
Performs deep analysis to identify all duplicate service implementations.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
import json
from datetime import datetime
from collections import defaultdict

class ServiceDuplicateAnalyzer:
    """Analyze and identify duplicate service implementations."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.services = defaultdict(list)  # service_name -> [file_paths]
        self.service_methods = {}  # file_path -> {class_name: [methods]}
        self.consolidated_services = []
        self.duplicate_report = {
            "timestamp": datetime.now().isoformat(),
            "duplicate_sets": [],
            "consolidated_found": [],
            "method_comparison": {},
            "recommendations": []
        }
    
    def analyze(self, deep_scan: bool = False):
        """Run comprehensive service duplication analysis."""
        print("🔍 Starting Service Duplication Analysis...")
        print("=" * 60)
        
        # 1. Find all service files
        self.find_all_services()
        
        # 2. Analyze service methods
        self.analyze_service_methods()
        
        # 3. Identify duplicates
        self.identify_duplicates()
        
        # 4. Compare duplicate implementations
        if deep_scan:
            self.deep_compare_duplicates()
        
        # 5. Generate recommendations
        self.generate_recommendations()
        
        # 6. Save report
        self.save_report()
    
    def find_all_services(self):
        """Find all service files in the project."""
        print("\n📁 Scanning for service files...")
        
        # Patterns to identify service files
        service_patterns = [
            "*service*.py",
            "*handler*.py",
            "*manager*.py",
            "*processor*.py"
        ]
        
        for pattern in service_patterns:
            for file_path in self.src_dir.rglob(pattern):
                if "__pycache__" in str(file_path) or file_path.name == "__init__.py":
                    continue
                
                # Extract service type from filename
                filename = file_path.stem.lower()
                
                # Check for consolidated versions
                if "consolidated" in filename:
                    self.consolidated_services.append(file_path)
                
                # Group by service type
                service_type = self._extract_service_type(filename)
                if service_type:
                    self.services[service_type].append(file_path)
        
        # Report findings
        print(f"Found {sum(len(files) for files in self.services.values())} service files")
        print(f"Found {len(self.consolidated_services)} consolidated services")
        
        for service_type, files in sorted(self.services.items()):
            if len(files) > 1:
                print(f"  ⚠️  {service_type}: {len(files)} implementations")
    
    def _extract_service_type(self, filename: str) -> str:
        """Extract service type from filename."""
        # Remove common suffixes
        name = filename.replace("_service", "").replace("service", "")
        name = name.replace("_handler", "").replace("handler", "")
        name = name.replace("_manager", "").replace("manager", "")
        name = name.replace("_consolidated", "").replace("consolidated", "")
        
        # Map variations to canonical names
        mappings = {
            "ai": "ai",
            "ai_response": "ai",
            "ai_teddy": "ai",
            "ai_orchestration": "ai",
            "audio": "audio",
            "audio_processing": "audio",
            "voice": "audio",
            "auth": "auth",
            "authentication": "auth",
            "authorization": "auth",
            "config": "config",
            "configuration": "config",
            "websocket": "websocket",
            "ws": "websocket",
            "socket": "websocket",
            "child_safety": "child_safety",
            "safety": "child_safety",
            "conversation": "conversation",
            "user": "user"
        }
        
        for key, canonical in mappings.items():
            if key in name:
                return canonical
        
        return name if name else None
    
    def analyze_service_methods(self):
        """Analyze methods in each service file."""
        print("\n🔬 Analyzing service methods...")
        
        for service_type, files in self.services.items():
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        tree = ast.parse(f.read())
                    
                    classes = self._extract_classes_and_methods(tree)
                    if classes:
                        self.service_methods[str(file_path)] = classes
                        
                        # Print summary
                        for class_name, methods in classes.items():
                            print(f"  {file_path.name}/{class_name}: {len(methods)} methods")
                
                except Exception as e:
                    print(f"  ❌ Error analyzing {file_path}: {e}")
    
    def _extract_classes_and_methods(self, tree: ast.AST) -> Dict[str, List[Dict]]:
        """Extract classes and their methods from AST."""
        classes = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = []
                
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        method_info = {
                            "name": item.name,
                            "args": [arg.arg for arg in item.args.args],
                            "decorators": [self._get_decorator_name(d) for d in item.decorator_list],
                            "is_async": isinstance(item, ast.AsyncFunctionDef),
                            "docstring": ast.get_docstring(item)
                        }
                        methods.append(method_info)
                
                classes[node.name] = methods
        
        return classes
    
    def _get_decorator_name(self, decorator):
        """Extract decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return f"{decorator.attr}"
        return str(decorator)
    
    def identify_duplicates(self):
        """Identify duplicate service implementations."""
        print("\n🔍 Identifying duplicates...")
        
        for service_type, files in self.services.items():
            if len(files) > 1:
                duplicate_set = {
                    "service_type": service_type,
                    "files": [str(f.relative_to(self.project_root)) for f in files],
                    "count": len(files),
                    "has_consolidated": any("consolidated" in str(f) for f in files)
                }
                
                self.duplicate_report["duplicate_sets"].append(duplicate_set)
                
                print(f"\n⚠️  Duplicate: {service_type}")
                for f in files:
                    print(f"    - {f.relative_to(self.project_root)}")
    
    def deep_compare_duplicates(self):
        """Perform deep comparison of duplicate implementations."""
        print("\n🔬 Deep comparison of duplicates...")
        
        for dup_set in self.duplicate_report["duplicate_sets"]:
            service_type = dup_set["service_type"]
            files = [self.project_root / f for f in dup_set["files"]]
            
            comparison = {
                "service_type": service_type,
                "implementations": {}
            }
            
            # Analyze each implementation
            for file_path in files:
                file_key = str(file_path)
                if file_key in self.service_methods:
                    impl_info = {
                        "classes": {},
                        "total_methods": 0,
                        "unique_methods": []
                    }
                    
                    for class_name, methods in self.service_methods[file_key].items():
                        impl_info["classes"][class_name] = {
                            "method_count": len(methods),
                            "method_names": [m["name"] for m in methods if not m["name"].startswith("_")],
                            "async_methods": [m["name"] for m in methods if m["is_async"]]
                        }
                        impl_info["total_methods"] += len(methods)
                    
                    comparison["implementations"][str(file_path.relative_to(self.project_root))] = impl_info
            
            # Find unique methods across implementations
            all_methods = set()
            method_to_files = defaultdict(list)
            
            for file_path, impl_info in comparison["implementations"].items():
                for class_info in impl_info["classes"].values():
                    for method in class_info["method_names"]:
                        all_methods.add(method)
                        method_to_files[method].append(file_path)
            
            # Identify unique methods per file
            for file_path, impl_info in comparison["implementations"].items():
                file_methods = set()
                for class_info in impl_info["classes"].values():
                    file_methods.update(class_info["method_names"])
                
                unique = [m for m in file_methods if len(method_to_files[m]) == 1]
                impl_info["unique_methods"] = unique
            
            comparison["all_methods"] = list(all_methods)
            comparison["method_coverage"] = {
                method: len(files) for method, files in method_to_files.items()
            }
            
            self.duplicate_report["method_comparison"][service_type] = comparison
            
            # Print comparison summary
            print(f"\n📊 {service_type} comparison:")
            for file_path, impl_info in comparison["implementations"].items():
                print(f"  {Path(file_path).name}:")
                print(f"    - Total methods: {impl_info['total_methods']}")
                print(f"    - Unique methods: {len(impl_info['unique_methods'])}")
                if impl_info["unique_methods"]:
                    print(f"      {', '.join(impl_info['unique_methods'][:5])}")
    
    def generate_recommendations(self):
        """Generate consolidation recommendations."""
        print("\n💡 Generating recommendations...")
        
        for dup_set in self.duplicate_report["duplicate_sets"]:
            service_type = dup_set["service_type"]
            
            recommendation = {
                "service_type": service_type,
                "current_files": dup_set["files"],
                "target_file": f"src/application/services/{service_type}_service.py",
                "actions": []
            }
            
            # Determine base implementation
            if dup_set["has_consolidated"]:
                # Use consolidated version as base
                consolidated = [f for f in dup_set["files"] if "consolidated" in f][0]
                recommendation["base_implementation"] = consolidated
                recommendation["actions"].append(f"Use {consolidated} as base implementation")
            else:
                # Use the one with most methods
                if service_type in self.duplicate_report["method_comparison"]:
                    comparison = self.duplicate_report["method_comparison"][service_type]
                    max_methods = 0
                    base_file = None
                    
                    for file_path, impl_info in comparison["implementations"].items():
                        if impl_info["total_methods"] > max_methods:
                            max_methods = impl_info["total_methods"]
                            base_file = file_path
                    
                    recommendation["base_implementation"] = base_file
                    recommendation["actions"].append(f"Use {Path(base_file).name} as base (most complete)")
            
            # Add merge actions
            recommendation["actions"].extend([
                "Merge all unique methods from other implementations",
                "Add compatibility layer for existing imports",
                "Update all references to use new unified service",
                "Add deprecation warnings to old implementations",
                "Delete old implementations after migration"
            ])
            
            self.duplicate_report["recommendations"].append(recommendation)
    
    def save_report(self):
        """Save duplication analysis report."""
        report_path = self.project_root / "service_duplication_report.json"
        
        with open(report_path, 'w') as f:
            json.dump(self.duplicate_report, f, indent=2)
        
        # Print summary
        print("\n" + "=" * 60)
        print("SERVICE DUPLICATION ANALYSIS COMPLETE")
        print("=" * 60)
        
        total_duplicates = sum(d["count"] for d in self.duplicate_report["duplicate_sets"])
        print(f"Total duplicate implementations: {total_duplicates}")
        print(f"Services with duplicates: {len(self.duplicate_report['duplicate_sets'])}")
        print(f"Consolidated services found: {len(self.consolidated_services)}")
        
        # Estimate code reduction
        estimated_reduction = (total_duplicates - len(self.duplicate_report["duplicate_sets"])) * 100 / total_duplicates if total_duplicates > 0 else 0
        print(f"\nEstimated code reduction: {estimated_reduction:.1f}%")
        
        print(f"\nDetailed report saved to: {report_path}")
        
        # Print critical duplicates
        print("\n🚨 Critical duplicates to resolve:")
        for rec in self.duplicate_report["recommendations"][:5]:
            print(f"\n{rec['service_type']}:")
            print(f"  Current: {len(rec['current_files'])} files")
            print(f"  Target: {rec['target_file']}")
            print(f"  Base: {Path(rec.get('base_implementation', 'TBD')).name}")


def main():
    """Run service duplication analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze service duplications")
    parser.add_argument("--deep-scan", action="store_true", help="Perform deep method comparison")
    parser.add_argument("--report", action="store_true", help="Generate detailed report")
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent
    analyzer = ServiceDuplicateAnalyzer(project_root)
    
    analyzer.analyze(deep_scan=args.deep_scan or args.report)
    
    if args.report:
        # Additional reporting
        print("\n📋 Detailed findings:")
        with open(project_root / "service_duplication_report.json", 'r') as f:
            report = json.load(f)
        
        for dup in report["duplicate_sets"]:
            print(f"\n{dup['service_type']}: {dup['count']} implementations")
            for f in dup["files"]:
                print(f"  - {f}")


if __name__ == "__main__":
    main()