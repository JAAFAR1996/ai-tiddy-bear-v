#!/usr/bin/env python3
"""
Layer Dependency Validator

This script validates that the application follows clean architecture principles:
- Core layer should not import from any other layer
- Application layer can import from Core and Interfaces
- Infrastructure layer can import from Interfaces only
- Adapters can import from Application and Interfaces

Fails with exit code 1 if violations are found.
"""

import os
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict


class ImportAnalyzer(ast.NodeVisitor):
    """AST visitor to extract import statements from Python files."""
    
    def __init__(self):
        self.imports: List[Tuple[str, int]] = []
        self.from_imports: List[Tuple[str, int]] = []
    
    def visit_Import(self, node: ast.Import) -> None:
        """Handle 'import module' statements."""
        for alias in node.names:
            self.imports.append((alias.name, node.lineno))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Handle 'from module import ...' statements."""
        if node.module:
            self.from_imports.append((node.module, node.lineno))
        self.generic_visit(node)


def get_layer_from_path(file_path: str) -> str:
    """Determine which layer a file belongs to based on its path."""
    if 'src/core' in file_path:
        return 'core'
    elif 'src/application' in file_path:
        return 'application'
    elif 'src/infrastructure' in file_path:
        return 'infrastructure'
    elif 'src/adapters' in file_path:
        return 'adapters'
    elif 'src/interfaces' in file_path:
        return 'interfaces'
    elif 'src/api' in file_path or 'src/presentation' in file_path:
        return 'presentation'
    else:
        return 'other'


def analyze_imports(file_path: str) -> List[Tuple[str, int]]:
    """Extract all imports from a Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        analyzer = ImportAnalyzer()
        analyzer.visit(tree)
        
        all_imports = []
        all_imports.extend(analyzer.imports)
        all_imports.extend(analyzer.from_imports)
        
        return all_imports
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return []


def check_import_violation(importing_file: str, imported_module: str, line_no: int) -> Tuple[bool, str]:
    """Check if an import violates layer dependencies."""
    source_layer = get_layer_from_path(importing_file)
    
    # Determine target layer from import
    target_layer = None
    if imported_module.startswith('src.core') or imported_module.startswith('..core'):
        target_layer = 'core'
    elif imported_module.startswith('src.application') or imported_module.startswith('..application'):
        target_layer = 'application'
    elif imported_module.startswith('src.infrastructure') or imported_module.startswith('..infrastructure'):
        target_layer = 'infrastructure'
    elif imported_module.startswith('src.adapters') or imported_module.startswith('..adapters'):
        target_layer = 'adapters'
    elif imported_module.startswith('src.interfaces') or imported_module.startswith('..interfaces'):
        target_layer = 'interfaces'
    elif imported_module.startswith('src.api') or imported_module.startswith('..api'):
        target_layer = 'presentation'
    
    if not target_layer:
        return False, ""
    
    # Define allowed dependencies
    allowed_dependencies = {
        'core': [],  # Core should not depend on any other layer
        'application': ['core', 'interfaces'],
        'infrastructure': ['interfaces'],
        'adapters': ['application', 'interfaces'],
        'presentation': ['application', 'interfaces', 'adapters'],
        'interfaces': [],  # Interfaces should be independent
        'other': ['core', 'application', 'infrastructure', 'adapters', 'interfaces', 'presentation']
    }
    
    # Check if the import is allowed
    if target_layer not in allowed_dependencies.get(source_layer, []):
        return True, f"{source_layer} → {target_layer}"
    
    return False, ""


def find_circular_dependencies(dependencies: Dict[str, Set[str]]) -> List[List[str]]:
    """Find circular dependencies using DFS."""
    def dfs(node: str, visited: Set[str], path: List[str]) -> List[List[str]]:
        cycles = []
        
        if node in path:
            # Found a cycle
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:] + [node])
            return cycles
        
        if node in visited:
            return cycles
        
        visited.add(node)
        path.append(node)
        
        for neighbor in dependencies.get(node, set()):
            cycles.extend(dfs(neighbor, visited.copy(), path.copy()))
        
        return cycles
    
    all_cycles = []
    for node in dependencies:
        cycles = dfs(node, set(), [])
        for cycle in cycles:
            # Normalize cycle to start with the smallest element
            min_idx = cycle.index(min(cycle))
            normalized = cycle[min_idx:] + cycle[:min_idx]
            if normalized not in all_cycles:
                all_cycles.append(normalized)
    
    return all_cycles


def main():
    """Main validation function."""
    print("🔍 Validating Layer Dependencies...")
    print("=" * 80)
    
    violations = []
    layer_dependencies = defaultdict(set)
    file_count = 0
    
    # Find all Python files in src directory
    src_dir = Path(__file__).parent.parent / 'src'
    
    for py_file in src_dir.rglob('*.py'):
        if '__pycache__' in str(py_file):
            continue
        
        file_count += 1
        file_path = str(py_file)
        imports = analyze_imports(file_path)
        
        source_layer = get_layer_from_path(file_path)
        
        for imported_module, line_no in imports:
            is_violation, violation_type = check_import_violation(file_path, imported_module, line_no)
            
            if is_violation:
                relative_path = os.path.relpath(file_path, src_dir.parent)
                violations.append({
                    'file': relative_path,
                    'line': line_no,
                    'import': imported_module,
                    'type': violation_type
                })
            
            # Track dependencies for circular dependency check
            if imported_module.startswith('src.') or imported_module.startswith('..'):
                target_layer = None
                if '.core' in imported_module:
                    target_layer = 'core'
                elif '.application' in imported_module:
                    target_layer = 'application'
                elif '.infrastructure' in imported_module:
                    target_layer = 'infrastructure'
                elif '.adapters' in imported_module:
                    target_layer = 'adapters'
                
                if target_layer and source_layer != target_layer:
                    layer_dependencies[source_layer].add(target_layer)
    
    # Report violations
    if violations:
        print(f"\n❌ Found {len(violations)} layer dependency violations:\n")
        
        # Group violations by type
        violations_by_type = defaultdict(list)
        for v in violations:
            violations_by_type[v['type']].append(v)
        
        for violation_type, items in sorted(violations_by_type.items()):
            print(f"\n🚫 {violation_type} violations ({len(items)}):")
            for item in sorted(items, key=lambda x: x['file']):
                print(f"   {item['file']}:{item['line']} - imports '{item['import']}'")
    
    # Check for circular dependencies
    cycles = find_circular_dependencies(layer_dependencies)
    if cycles:
        print(f"\n🔄 Found {len(cycles)} circular dependencies:")
        for cycle in cycles:
            print(f"   {' → '.join(cycle)}")
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"   Files analyzed: {file_count}")
    print(f"   Violations found: {len(violations)}")
    print(f"   Circular dependencies: {len(cycles)}")
    
    # Layer dependency graph
    print(f"\n📈 Current layer dependencies:")
    for layer, deps in sorted(layer_dependencies.items()):
        if deps:
            print(f"   {layer} → {', '.join(sorted(deps))}")
    
    # Verification commands
    print(f"\n🔧 Quick verification commands:")
    print(f"   Core imports from infrastructure: ", end="")
    os.system('grep -r "from.*infrastructure" src/core/ 2>/dev/null | wc -l')
    
    print(f"   Adapters import from core: ", end="")
    os.system('grep -r "from.*core" src/adapters/ 2>/dev/null | wc -l')
    
    print(f"   Infrastructure imports from application: ", end="")
    os.system('grep -r "from.*application" src/infrastructure/ 2>/dev/null | wc -l')
    
    if violations or cycles:
        print(f"\n❌ Layer dependency validation FAILED!")
        print(f"💡 Fix the violations listed above to ensure clean architecture.")
        sys.exit(1)
    else:
        print(f"\n✅ Layer dependency validation PASSED!")
        print(f"🎉 All layers follow clean architecture principles.")
        sys.exit(0)


if __name__ == "__main__":
    main()