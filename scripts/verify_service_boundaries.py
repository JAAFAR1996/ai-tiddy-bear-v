#!/usr/bin/env python3
"""
Service Boundary Verifier
Ensures services maintain clear single responsibilities and proper boundaries.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
import json
from datetime import datetime
from collections import defaultdict

class ServiceBoundaryVerifier:
    """Verify that services maintain proper boundaries and single responsibilities."""
    
    # Define expected service responsibilities
    SERVICE_RESPONSIBILITIES = {
        "ai_service": {
            "allowed": [
                "AI model interaction",
                "Prompt management", 
                "Response generation",
                "AI orchestration",
                "Model selection"
            ],
            "forbidden": [
                "Audio processing",
                "WebSocket handling",
                "Database operations",
                "User management",
                "Authentication"
            ],
            "max_lines": 500,
            "max_methods": 15
        },
        "audio_service": {
            "allowed": [
                "Audio capture/playback",
                "Format conversion",
                "Stream management",
                "Voice processing",
                "Audio quality control"
            ],
            "forbidden": [
                "AI processing",
                "Business logic",
                "User management",
                "Database operations"
            ],
            "max_lines": 400,
            "max_methods": 12
        },
        "auth_service": {
            "allowed": [
                "Authentication",
                "Authorization",
                "Token management",
                "Session handling",
                "Permission checking"
            ],
            "forbidden": [
                "User data storage",
                "Business rules",
                "AI processing",
                "Audio handling"
            ],
            "max_lines": 400,
            "max_methods": 10
        },
        "child_safety_service": {
            "allowed": [
                "Content filtering",
                "Age verification",
                "Safety monitoring",
                "COPPA compliance",
                "Parental controls"
            ],
            "forbidden": [
                "AI response generation",
                "Audio processing",
                "Database operations",
                "Authentication"
            ],
            "max_lines": 500,
            "max_methods": 15
        },
        "config_service": {
            "allowed": [
                "Configuration loading",
                "Settings management",
                "Environment handling",
                "Feature flags",
                "Configuration validation"
            ],
            "forbidden": [
                "Business logic",
                "AI processing",
                "Database operations",
                "User management"
            ],
            "max_lines": 300,
            "max_methods": 8
        },
        "websocket_service": {
            "allowed": [
                "WebSocket connections",
                "Real-time messaging",
                "Connection management",
                "Event broadcasting",
                "Protocol handling"
            ],
            "forbidden": [
                "Business logic",
                "AI processing",
                "Database operations",
                "Authentication logic"
            ],
            "max_lines": 400,
            "max_methods": 12
        }
    }
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_dir = project_root / "src"
        self.services_dir = project_root / "src" / "application" / "services"
        self.violations = []
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "services_analyzed": [],
            "violations": [],
            "metrics": {},
            "recommendations": []
        }
    
    def verify_all_services(self):
        """Verify all service boundaries."""
        print("🔍 Verifying Service Boundaries...")
        print("=" * 60)
        
        # Find all service files
        service_files = list(self.services_dir.glob("*_service.py"))
        
        for service_file in service_files:
            self.verify_service(service_file)
        
        # Generate report
        self.generate_report()
    
    def verify_service(self, service_file: Path):
        """Verify a single service maintains proper boundaries."""
        service_name = service_file.stem
        print(f"\n📋 Verifying {service_name}...")
        
        # Get expected boundaries
        boundaries = self.SERVICE_RESPONSIBILITIES.get(service_name, {})
        if not boundaries:
            print(f"  ⚠️  No boundaries defined for {service_name}")
            return
        
        # Analyze service
        analysis = self.analyze_service_file(service_file)
        
        # Check violations
        violations = self.check_boundary_violations(service_name, analysis, boundaries)
        
        # Check metrics
        metric_violations = self.check_metric_violations(service_name, analysis, boundaries)
        
        # Store results
        self.report["services_analyzed"].append({
            "service": service_name,
            "file": str(service_file.relative_to(self.project_root)),
            "analysis": analysis,
            "violations": violations + metric_violations
        })
        
        if violations or metric_violations:
            self.report["violations"].extend(violations + metric_violations)
            print(f"  ❌ Found {len(violations + metric_violations)} violations")
        else:
            print(f"  ✅ No violations found")
    
    def analyze_service_file(self, service_file: Path) -> Dict:
        """Analyze a service file for structure and dependencies."""
        analysis = {
            "lines": 0,
            "classes": [],
            "methods": [],
            "imports": [],
            "dependencies": [],
            "functionality": []
        }
        
        try:
            with open(service_file, 'r', encoding='utf-8') as f:
                content = f.read()
                analysis["lines"] = len(content.splitlines())
                tree = ast.parse(content)
            
            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append(alias.name)
                        self._categorize_import(alias.name, analysis)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analysis["imports"].append(node.module)
                        self._categorize_import(node.module, analysis)
            
            # Extract classes and methods
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "methods": []
                    }
                    
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_info = {
                                "name": item.name,
                                "is_async": isinstance(item, ast.AsyncFunctionDef),
                                "functionality": self._infer_functionality(item)
                            }
                            class_info["methods"].append(method_info)
                            analysis["methods"].append(item.name)
                            analysis["functionality"].extend(method_info["functionality"])
                    
                    analysis["classes"].append(class_info)
            
        except Exception as e:
            print(f"  ⚠️  Error analyzing {service_file}: {e}")
        
        return analysis
    
    def _categorize_import(self, import_name: str, analysis: Dict):
        """Categorize import to determine dependencies."""
        categories = {
            "database": ["sqlalchemy", "asyncpg", "database", "models"],
            "ai": ["openai", "anthropic", "langchain", "transformers"],
            "audio": ["pyaudio", "soundfile", "librosa", "pydub"],
            "auth": ["jwt", "passlib", "bcrypt", "authlib"],
            "websocket": ["websockets", "socketio", "ws"],
            "http": ["httpx", "requests", "aiohttp", "fastapi"]
        }
        
        for category, keywords in categories.items():
            if any(keyword in import_name.lower() for keyword in keywords):
                if category not in analysis["dependencies"]:
                    analysis["dependencies"].append(category)
    
    def _infer_functionality(self, func_node: ast.FunctionDef) -> List[str]:
        """Infer functionality from method name and content."""
        functionality = []
        func_name = func_node.name.lower()
        
        # Check method name patterns
        patterns = {
            "ai": ["generate", "prompt", "model", "gpt", "openai", "llm"],
            "audio": ["audio", "voice", "sound", "stream", "record", "play"],
            "auth": ["auth", "token", "login", "logout", "permission", "authorize"],
            "database": ["save", "load", "query", "create", "update", "delete", "fetch"],
            "websocket": ["socket", "broadcast", "emit", "connect", "disconnect"],
            "safety": ["safe", "filter", "check", "validate", "coppa", "moderate"]
        }
        
        for category, keywords in patterns.items():
            if any(keyword in func_name for keyword in keywords):
                functionality.append(category)
        
        # Check function body for patterns
        for node in ast.walk(func_node):
            if isinstance(node, ast.Name):
                node_id = node.id.lower()
                for category, keywords in patterns.items():
                    if any(keyword in node_id for keyword in keywords):
                        if category not in functionality:
                            functionality.append(category)
        
        return functionality
    
    def check_boundary_violations(self, service_name: str, analysis: Dict, boundaries: Dict) -> List[Dict]:
        """Check for boundary violations in service."""
        violations = []
        
        # Check forbidden dependencies
        forbidden_categories = {
            "ai_service": ["database", "audio", "websocket"],
            "audio_service": ["ai", "database", "auth"],
            "auth_service": ["ai", "audio"],
            "child_safety_service": ["database", "audio"],
            "config_service": ["ai", "audio", "database"],
            "websocket_service": ["ai", "database"]
        }
        
        service_forbidden = forbidden_categories.get(service_name, [])
        for dep in analysis["dependencies"]:
            if dep in service_forbidden:
                violations.append({
                    "type": "forbidden_dependency",
                    "service": service_name,
                    "violation": f"Depends on {dep}",
                    "severity": "high"
                })
        
        # Check for mixed responsibilities
        responsibility_map = {
            "ai": "AI processing",
            "audio": "Audio handling",
            "auth": "Authentication",
            "database": "Database operations",
            "websocket": "WebSocket handling",
            "safety": "Safety filtering"
        }
        
        expected_functionality = service_name.split("_")[0]
        for func in analysis["functionality"]:
            if func != expected_functionality and func in responsibility_map:
                violations.append({
                    "type": "mixed_responsibility",
                    "service": service_name,
                    "violation": f"Contains {responsibility_map[func]} logic",
                    "severity": "medium"
                })
        
        return violations
    
    def check_metric_violations(self, service_name: str, analysis: Dict, boundaries: Dict) -> List[Dict]:
        """Check for metric violations (size, complexity)."""
        violations = []
        
        # Check line count
        max_lines = boundaries.get("max_lines", 500)
        if analysis["lines"] > max_lines:
            violations.append({
                "type": "size_violation",
                "service": service_name,
                "violation": f"Service has {analysis['lines']} lines (max: {max_lines})",
                "severity": "medium"
            })
        
        # Check method count
        max_methods = boundaries.get("max_methods", 15)
        method_count = len(analysis["methods"])
        if method_count > max_methods:
            violations.append({
                "type": "complexity_violation",
                "service": service_name,
                "violation": f"Service has {method_count} methods (max: {max_methods})",
                "severity": "medium"
            })
        
        return violations
    
    def generate_report(self):
        """Generate boundary verification report."""
        # Generate recommendations
        for service_info in self.report["services_analyzed"]:
            if service_info["violations"]:
                service_name = service_info["service"]
                violations = service_info["violations"]
                
                recommendations = []
                
                # Group violations by type
                by_type = defaultdict(list)
                for v in violations:
                    by_type[v["type"]].append(v)
                
                if "forbidden_dependency" in by_type:
                    recommendations.append(f"Remove dependencies on: {', '.join(v['violation'].split()[-1] for v in by_type['forbidden_dependency'])}")
                
                if "mixed_responsibility" in by_type:
                    recommendations.append(f"Extract {', '.join(set(v['violation'] for v in by_type['mixed_responsibility']))} to separate services")
                
                if "size_violation" in by_type:
                    recommendations.append(f"Refactor {service_name} to reduce size below {self.SERVICE_RESPONSIBILITIES[service_name]['max_lines']} lines")
                
                if "complexity_violation" in by_type:
                    recommendations.append(f"Split {service_name} into smaller services with focused responsibilities")
                
                self.report["recommendations"].append({
                    "service": service_name,
                    "actions": recommendations
                })
        
        # Calculate metrics
        self.report["metrics"] = {
            "total_services": len(self.report["services_analyzed"]),
            "services_with_violations": len([s for s in self.report["services_analyzed"] if s["violations"]]),
            "total_violations": len(self.report["violations"]),
            "high_severity_violations": len([v for v in self.report["violations"] if v["severity"] == "high"]),
            "boundary_compliance_rate": (len(self.report["services_analyzed"]) - len([s for s in self.report["services_analyzed"] if s["violations"]])) / max(len(self.report["services_analyzed"]), 1) * 100
        }
        
        # Save report
        report_path = self.project_root / "service_boundary_report.json"
        with open(report_path, 'w') as f:
            json.dump(self.report, f, indent=2)
        
        # Print summary
        print("\n" + "=" * 60)
        print("SERVICE BOUNDARY VERIFICATION COMPLETE")
        print("=" * 60)
        print(f"Services analyzed: {self.report['metrics']['total_services']}")
        print(f"Services with violations: {self.report['metrics']['services_with_violations']}")
        print(f"Total violations: {self.report['metrics']['total_violations']}")
        print(f"High severity violations: {self.report['metrics']['high_severity_violations']}")
        print(f"Boundary compliance: {self.report['metrics']['boundary_compliance_rate']:.1f}%")
        
        if self.report["violations"]:
            print("\n⚠️  Violations found:")
            for v in self.report["violations"][:10]:
                print(f"  - {v['service']}: {v['violation']} ({v['severity']})")
        
        print(f"\nDetailed report saved to: {report_path}")


def main():
    """Run service boundary verification."""
    project_root = Path(__file__).parent.parent
    verifier = ServiceBoundaryVerifier(project_root)
    verifier.verify_all_services()


if __name__ == "__main__":
    main()