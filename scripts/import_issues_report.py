#!/usr/bin/env python3
"""تقرير شامل عن مشاكل الاستيرادات في المشروع"""

import os
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict
import json

class ImportIssuesReport:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.src_path = self.project_root / "src"
        self.tests_path = self.project_root / "tests"
        self.issues = {
            'missing_imports': defaultdict(list),
            'circular_imports': [],
            'unused_imports': defaultdict(list),
            'import_from_wrong_layer': defaultdict(list)
        }
        self.module_map = {}
        self.layer_map = {
            'core': ['entities', 'value_objects', 'repositories', 'services', 'exceptions', 'models', 'constants'],
            'application': ['use_cases', 'interfaces', 'services', 'event_handlers', 'dependencies'],
            'infrastructure': ['persistence', 'config', 'security', 'monitoring', 'logging', 'factories', 'container'],
            'interfaces': ['services', 'repositories', 'adapters', 'config', 'external', 'exceptions'],
            'adapters': ['api', 'database', 'messaging', 'external_services'],
            'api': ['endpoints', 'middleware', 'docs', 'openapi_config'],
            'shared': ['dto', 'utils', 'constants']
        }
        
    def extract_all_imports(self, file_path: Path) -> List[Dict]:
        """استخراج جميع الاستيرادات من ملف"""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append({
                            'type': 'import',
                            'module': alias.name,
                            'name': alias.asname or alias.name,
                            'line': node.lineno
                        })
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports.append({
                            'type': 'from',
                            'module': module,
                            'name': alias.name,
                            'asname': alias.asname,
                            'line': node.lineno
                        })
        except Exception as e:
            print(f"خطأ في معالجة {file_path}: {e}")
        
        return imports
    
    def check_import_exists(self, module_path: str) -> bool:
        """التحقق من وجود الوحدة"""
        if not (module_path.startswith('src.') or module_path.startswith('tests.')):
            return True  # نفترض أن الوحدات الخارجية موجودة
        
        parts = module_path.split('.')
        
        # مسارات محتملة للملف
        possible_paths = [
            self.project_root / '/'.join(parts) / '__init__.py',
            self.project_root / '/'.join(parts[:-1]) / f"{parts[-1]}.py",
            self.project_root / f"{'/'.join(parts)}.py"
        ]
        
        # التحقق من وجود أي من المسارات
        for path in possible_paths:
            if path.exists():
                return True
                
        # التحقق من الكلاسات والدوال المُصدرة
        parent_module = '.'.join(parts[:-1])
        if parent_module in self.module_map:
            return parts[-1] in self.module_map[parent_module]
            
        return False
    
    def get_layer(self, module_path: str) -> Optional[str]:
        """تحديد الطبقة التي ينتمي إليها الملف"""
        if module_path.startswith('src.'):
            parts = module_path.split('.')
            if len(parts) >= 2:
                return parts[1]
        return None
    
    def check_layer_violation(self, from_module: str, to_module: str) -> bool:
        """التحقق من انتهاك قواعد الطبقات"""
        from_layer = self.get_layer(from_module)
        to_layer = self.get_layer(to_module)
        
        if not from_layer or not to_layer:
            return False
        
        # قواعد الاعتماديات بين الطبقات
        allowed_dependencies = {
            'api': ['application', 'interfaces', 'shared', 'infrastructure'],
            'application': ['core', 'interfaces', 'shared'],
            'infrastructure': ['core', 'interfaces', 'shared', 'application'],
            'adapters': ['core', 'interfaces', 'infrastructure'],
            'core': ['shared'],
            'interfaces': ['shared'],
            'shared': []
        }
        
        if from_layer in allowed_dependencies:
            return to_layer not in allowed_dependencies[from_layer] and to_layer != from_layer
        
        return False
    
    def scan_modules(self):
        """مسح جميع الوحدات وصادراتها"""
        for base_path in [self.src_path, self.tests_path]:
            if not base_path.exists():
                continue
                
            for py_file in base_path.glob("**/*.py"):
                module_path = self.get_module_path(py_file)
                exports = self.get_module_exports(py_file)
                self.module_map[module_path] = exports
    
    def get_module_path(self, file_path: Path) -> str:
        """تحويل مسار الملف إلى مسار الوحدة"""
        relative = file_path.relative_to(self.project_root)
        parts = list(relative.parts)
        
        if file_path.name == '__init__.py':
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1].replace('.py', '')
            
        return '.'.join(parts)
    
    def get_module_exports(self, file_path: Path) -> Set[str]:
        """الحصول على جميع الصادرات من الوحدة"""
        exports = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    exports.add(node.name)
                elif isinstance(node, ast.FunctionDef):
                    exports.add(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            exports.add(target.id)
        except:
            pass
            
        return exports
    
    def analyze_file(self, file_path: Path):
        """تحليل ملف واحد"""
        module_path = self.get_module_path(file_path)
        imports = self.extract_all_imports(file_path)
        
        for imp in imports:
            full_import = imp['module']
            if imp['type'] == 'from' and imp['name'] != '*':
                full_import = f"{imp['module']}.{imp['name']}"
            
            # فحص الاستيرادات المفقودة
            if full_import.startswith(('src.', 'tests.')):
                if not self.check_import_exists(full_import):
                    self.issues['missing_imports'][str(file_path)].append({
                        'import': full_import,
                        'line': imp['line'],
                        'type': imp['type']
                    })
            
            # فحص انتهاكات الطبقات
            if self.check_layer_violation(module_path, full_import):
                self.issues['import_from_wrong_layer'][str(file_path)].append({
                    'import': full_import,
                    'line': imp['line'],
                    'from_layer': self.get_layer(module_path),
                    'to_layer': self.get_layer(full_import)
                })
    
    def generate_report(self):
        """توليد التقرير الشامل"""
        print("🔍 مسح الوحدات...")
        self.scan_modules()
        
        print("📄 تحليل الملفات...")
        python_files = []
        for base_path in [self.src_path, self.tests_path]:
            if base_path.exists():
                python_files.extend(base_path.glob("**/*.py"))
        
        for file_path in sorted(python_files):
            self.analyze_file(file_path)
        
        # عرض التقرير
        self.display_report()
        
        # حفظ التقرير كـ JSON
        self.save_json_report()
    
    def display_report(self):
        """عرض التقرير على الشاشة"""
        print("\n" + "="*80)
        print("📊 تقرير شامل عن مشاكل الاستيرادات")
        print("="*80)
        
        # 1. الاستيرادات المفقودة
        if self.issues['missing_imports']:
            print("\n❌ الاستيرادات المفقودة:")
            print("-" * 60)
            
            total_missing = 0
            unique_missing = set()
            
            for file_path, issues in sorted(self.issues['missing_imports'].items()):
                if issues:
                    rel_path = Path(file_path).relative_to(self.project_root)
                    print(f"\n📄 {rel_path}")
                    
                    for issue in issues:
                        print(f"   ✗ السطر {issue['line']}: {issue['import']}")
                        total_missing += 1
                        unique_missing.add(issue['import'])
            
            print(f"\n📈 الإحصائيات:")
            print(f"   - إجمالي الاستيرادات المفقودة: {total_missing}")
            print(f"   - الاستيرادات الفريدة المفقودة: {len(unique_missing)}")
            print(f"   - الملفات المتأثرة: {len(self.issues['missing_imports'])}")
            
            # أكثر الاستيرادات المفقودة تكراراً
            missing_count = defaultdict(int)
            for issues in self.issues['missing_imports'].values():
                for issue in issues:
                    missing_count[issue['import']] += 1
            
            print(f"\n🔝 أكثر الاستيرادات المفقودة تكراراً:")
            for imp, count in sorted(missing_count.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"   - {imp}: {count} مرة")
        
        # 2. انتهاكات الطبقات
        if self.issues['import_from_wrong_layer']:
            print("\n\n⚠️ انتهاكات قواعد الطبقات:")
            print("-" * 60)
            
            for file_path, violations in sorted(self.issues['import_from_wrong_layer'].items()):
                if violations:
                    rel_path = Path(file_path).relative_to(self.project_root)
                    print(f"\n📄 {rel_path}")
                    
                    for violation in violations:
                        print(f"   ⚠️ السطر {violation['line']}: {violation['from_layer']} ← {violation['to_layer']}")
                        print(f"      الاستيراد: {violation['import']}")
        
        print("\n" + "="*80)
    
    def save_json_report(self):
        """حفظ التقرير كملف JSON"""
        report_path = self.project_root / "import_issues_report.json"
        
        # تحويل البيانات لتكون قابلة للتسلسل
        serializable_issues = {}
        for key, value in self.issues.items():
            if isinstance(value, defaultdict):
                serializable_issues[key] = dict(value)
            else:
                serializable_issues[key] = value
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_issues, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 تم حفظ التقرير في: {report_path}")

if __name__ == "__main__":
    project_root = "/mnt/c/Users/jaafa/Desktop/ai teddy bear"
    reporter = ImportIssuesReport(project_root)
    reporter.generate_report()