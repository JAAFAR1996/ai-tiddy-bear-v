#!/usr/bin/env python3
"""Generate visual dependency graph of the codebase architecture.

This script creates a graphical representation of module dependencies
to visualize the clean architecture and ensure no circular dependencies.
"""

import os
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict
import json

# Try to import graphviz for visualization
try:
    import graphviz
    GRAPHVIZ_AVAILABLE = True
except ImportError:
    GRAPHVIZ_AVAILABLE = False
    print("Warning: graphviz not available. Install with: pip install graphviz")

# Try to import networkx for graph analysis
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    print("Warning: networkx not available. Install with: pip install networkx")


class DependencyAnalyzer:
    """Analyzes Python module dependencies and creates visual graphs."""
    
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)
        self.dependencies = defaultdict(set)
        self.layer_mapping = {}
        self.external_deps = defaultdict(set)
        
    def get_layer(self, file_path: str) -> str:
        """Determine which architectural layer a file belongs to."""
        rel_path = str(Path(file_path).relative_to(self.root_path))
        
        # Normalize path separators
        rel_path = rel_path.replace('\\', '/')
        
        if 'src/core' in rel_path:
            return 'core'
        elif 'src/application' in rel_path:
            return 'application'
        elif 'src/infrastructure' in rel_path:
            return 'infrastructure'
        elif 'src/adapters' in rel_path:
            return 'adapters'
        elif 'src/interfaces' in rel_path:
            return 'interfaces'
        elif 'src/api' in rel_path or 'src/presentation' in rel_path:
            return 'presentation'
        elif 'src/shared' in rel_path:
            return 'shared'
        else:
            return 'other'
    
    def analyze_file(self, file_path: Path) -> None:
        """Analyze imports in a Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            module_name = str(file_path.relative_to(self.root_path)).replace('/', '.').replace('.py', '')
            layer = self.get_layer(str(file_path))
            self.layer_mapping[module_name] = layer
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self._process_import(module_name, alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self._process_import(module_name, node.module, node.level)
                        
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
    
    def _process_import(self, from_module: str, to_module: str, level: int = 0) -> None:
        """Process an import statement."""
        # Handle relative imports
        if level > 0:
            parts = from_module.split('.')
            if level <= len(parts):
                base = '.'.join(parts[:-level])
                to_module = f"{base}.{to_module}" if to_module else base
        
        # Filter internal imports only
        if to_module.startswith('src.'):
            self.dependencies[from_module].add(to_module)
        elif not to_module.startswith('.'):
            # Track external dependencies
            self.external_deps[from_module].add(to_module.split('.')[0])
    
    def analyze_directory(self, directory: Path) -> None:
        """Recursively analyze all Python files in a directory."""
        for py_file in directory.rglob('*.py'):
            if '__pycache__' not in str(py_file):
                self.analyze_file(py_file)
    
    def detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular dependencies using DFS."""
        if not NETWORKX_AVAILABLE:
            return []
        
        # Create directed graph
        G = nx.DiGraph()
        for module, deps in self.dependencies.items():
            for dep in deps:
                G.add_edge(module, dep)
        
        # Find all simple cycles
        try:
            cycles = list(nx.simple_cycles(G))
            return cycles
        except:
            return []
    
    def generate_graphviz(self, output_file: str = 'dependency_graph') -> None:
        """Generate a visual graph using Graphviz."""
        if not GRAPHVIZ_AVAILABLE:
            print("Graphviz not available. Skipping visual generation.")
            return
        
        dot = graphviz.Digraph(comment='Architecture Dependencies')
        dot.attr(rankdir='TB', size='12,10')
        dot.attr('node', shape='box', style='filled')
        
        # Define colors for each layer
        layer_colors = {
            'core': '#FFE6E6',
            'application': '#E6F3FF',
            'infrastructure': '#E6FFE6',
            'adapters': '#FFFFE6',
            'interfaces': '#F0E6FF',
            'presentation': '#FFE6F0',
            'shared': '#E6FFF0',
            'other': '#F0F0F0'
        }
        
        # Create subgraphs for each layer
        layer_nodes = defaultdict(list)
        for module, layer in self.layer_mapping.items():
            layer_nodes[layer].append(module)
        
        for layer, nodes in layer_nodes.items():
            with dot.subgraph(name=f'cluster_{layer}') as sub:
                sub.attr(label=layer.upper(), style='filled', fillcolor=layer_colors.get(layer, '#FFFFFF'))
                for node in nodes:
                    # Simplify module name for display
                    display_name = node.split('.')[-1]
                    sub.node(node, display_name, fillcolor=layer_colors.get(layer, '#FFFFFF'))
        
        # Add edges
        for module, deps in self.dependencies.items():
            for dep in deps:
                # Color violations in red
                from_layer = self.layer_mapping.get(module, 'other')
                to_layer = self.layer_mapping.get(dep, 'other')
                
                edge_color = 'black'
                if self._is_violation(from_layer, to_layer):
                    edge_color = 'red'
                    dot.edge(module, dep, color=edge_color, penwidth='2')
                else:
                    dot.edge(module, dep, color=edge_color)
        
        # Render graph
        dot.render(output_file, format='png', cleanup=True)
        dot.render(output_file, format='svg', cleanup=True)
        print(f"Generated dependency graphs: {output_file}.png and {output_file}.svg")
    
    def _is_violation(self, from_layer: str, to_layer: str) -> bool:
        """Check if a dependency violates clean architecture rules."""
        allowed = {
            'core': [],
            'application': ['core', 'interfaces', 'shared'],
            'infrastructure': ['interfaces', 'shared'],
            'adapters': ['application', 'interfaces', 'shared'],
            'presentation': ['application', 'adapters', 'interfaces', 'shared'],
            'interfaces': ['shared'],
            'shared': [],
            'other': ['core', 'application', 'infrastructure', 'adapters', 'interfaces', 'presentation', 'shared']
        }
        
        return to_layer not in allowed.get(from_layer, []) and to_layer != from_layer
    
    def generate_report(self) -> Dict[str, any]:
        """Generate a detailed dependency report."""
        report = {
            'total_modules': len(self.dependencies),
            'total_dependencies': sum(len(deps) for deps in self.dependencies.values()),
            'layers': {},
            'violations': [],
            'circular_dependencies': self.detect_circular_dependencies(),
            'external_dependencies': {}
        }
        
        # Count modules per layer
        for layer in set(self.layer_mapping.values()):
            report['layers'][layer] = {
                'module_count': sum(1 for l in self.layer_mapping.values() if l == layer),
                'modules': [m for m, l in self.layer_mapping.items() if l == layer]
            }
        
        # Find violations
        for module, deps in self.dependencies.items():
            from_layer = self.layer_mapping.get(module, 'other')
            for dep in deps:
                to_layer = self.layer_mapping.get(dep, 'other')
                if self._is_violation(from_layer, to_layer):
                    report['violations'].append({
                        'from': module,
                        'to': dep,
                        'from_layer': from_layer,
                        'to_layer': to_layer
                    })
        
        # External dependencies summary
        for module, ext_deps in self.external_deps.items():
            layer = self.layer_mapping.get(module, 'other')
            if layer not in report['external_dependencies']:
                report['external_dependencies'][layer] = set()
            report['external_dependencies'][layer].update(ext_deps)
        
        # Convert sets to lists for JSON serialization
        for layer in report['external_dependencies']:
            report['external_dependencies'][layer] = list(report['external_dependencies'][layer])
        
        return report


def main():
    """Main function to analyze and visualize dependencies."""
    # Get project root
    project_root = Path(__file__).parent.parent
    src_dir = project_root / 'src'
    
    if not src_dir.exists():
        print(f"Error: Source directory not found at {src_dir}")
        sys.exit(1)
    
    print("🔍 Analyzing dependencies...")
    analyzer = DependencyAnalyzer(project_root)
    analyzer.analyze_directory(src_dir)
    
    # Generate report
    report = analyzer.generate_report()
    
    print("\n📊 Dependency Analysis Report")
    print("=" * 60)
    print(f"Total modules analyzed: {report['total_modules']}")
    print(f"Total dependencies: {report['total_dependencies']}")
    
    print("\n📁 Modules per layer:")
    for layer, info in report['layers'].items():
        print(f"  {layer}: {info['module_count']} modules")
    
    print(f"\n❌ Architecture violations: {len(report['violations'])}")
    if report['violations']:
        print("\nViolations:")
        for v in report['violations'][:10]:  # Show first 10
            print(f"  {v['from_layer']} → {v['to_layer']}: {v['from']} → {v['to']}")
        if len(report['violations']) > 10:
            print(f"  ... and {len(report['violations']) - 10} more")
    
    print(f"\n🔄 Circular dependencies: {len(report['circular_dependencies'])}")
    if report['circular_dependencies']:
        print("\nCircular dependency chains:")
        for cycle in report['circular_dependencies'][:5]:  # Show first 5
            print(f"  {' → '.join(cycle)}")
    
    # Save report as JSON
    report_file = project_root / 'dependency_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n💾 Detailed report saved to: {report_file}")
    
    # Generate visual graph
    if GRAPHVIZ_AVAILABLE:
        print("\n🎨 Generating visual dependency graph...")
        output_path = project_root / 'dependency_graph'
        analyzer.generate_graphviz(str(output_path))
    
    # Exit with error if violations found
    if report['violations'] or report['circular_dependencies']:
        print("\n❌ Dependency validation FAILED!")
        sys.exit(1)
    else:
        print("\n✅ Dependency validation PASSED!")
        sys.exit(0)


if __name__ == "__main__":
    main()