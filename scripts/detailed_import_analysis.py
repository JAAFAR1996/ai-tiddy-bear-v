#!/usr/bin/env python3
"""تحليل مفصل للاستيرادات المفقودة مع اقتراحات للحلول"""

import os
import ast
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict

class DetailedImportAnalyzer:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.src_path = self.project_root / "src"
        self.tests_path = self.project_root / "tests"
        self.missing_imports = defaultdict(list)
        self.import_solutions = {}
        self.existing_modules = set()
        
    def scan_existing_modules(self):
        """مسح جميع الوحدات الموجودة في المشروع"""
        for base_path in [self.src_path, self.tests_path]:
            if base_path.exists():
                for py_file in base_path.glob("**/*.py"):
                    # تحويل المسار إلى import path
                    relative_path = py_file.relative_to(self.project_root)
                    parts = list(relative_path.parts)
                    
                    if py_file.name == "__init__.py":
                        module_path = ".".join(parts[:-1])
                    else:
                        parts[-1] = parts[-1].replace(".py", "")
                        module_path = ".".join(parts)
                    
                    self.existing_modules.add(module_path)
                    
                    # مسح محتويات الملف للعثور على الكلاسات والدوال
                    try:
                        with open(py_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        tree = ast.parse(content)
                        
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                self.existing_modules.add(f"{module_path}.{node.name}")
                            elif isinstance(node, ast.FunctionDef):
                                self.existing_modules.add(f"{module_path}.{node.name}")
                    except:
                        pass
    
    def find_similar_modules(self, missing_import: str) -> List[str]:
        """البحث عن وحدات مشابهة للاستيراد المفقود"""
        similar = []
        missing_parts = missing_import.lower().split('.')
        
        for module in self.existing_modules:
            module_parts = module.lower().split('.')
            
            # البحث عن تطابق جزئي
            if any(part in module_parts for part in missing_parts[-2:]):
                similar.append(module)
            
            # البحث عن أسماء مشابهة
            if missing_parts[-1] in module_parts[-1] or module_parts[-1] in missing_parts[-1]:
                similar.append(module)
        
        return list(set(similar))[:5]  # أعلى 5 اقتراحات
    
    def analyze_missing_import(self, import_name: str) -> Dict[str, any]:
        """تحليل استيراد مفقود وإيجاد حلول محتملة"""
        analysis = {
            'import': import_name,
            'type': self.classify_import(import_name),
            'suggestions': [],
            'possible_locations': []
        }
        
        # إيجاد وحدات مشابهة
        similar = self.find_similar_modules(import_name)
        if similar:
            analysis['suggestions'] = similar
        
        # تحديد المواقع المحتملة للملف
        parts = import_name.split('.')
        if parts[0] in ['src', 'tests']:
            base_path = self.project_root / parts[0]
            
            # مسارات محتملة
            possible_paths = [
                base_path / '/'.join(parts[1:]) / '__init__.py',
                base_path / '/'.join(parts[1:-1]) / f"{parts[-1]}.py",
            ]
            
            analysis['possible_locations'] = [str(p.relative_to(self.project_root)) 
                                            for p in possible_paths]
        
        return analysis
    
    def classify_import(self, import_name: str) -> str:
        """تصنيف نوع الاستيراد"""
        if import_name.startswith('src.core'):
            return 'Core Domain'
        elif import_name.startswith('src.application'):
            return 'Application Layer'
        elif import_name.startswith('src.infrastructure'):
            return 'Infrastructure Layer'
        elif import_name.startswith('src.interfaces'):
            return 'Interfaces'
        elif import_name.startswith('src.shared'):
            return 'Shared/DTO'
        elif import_name.startswith('tests'):
            return 'Test Module'
        else:
            return 'External'
    
    def generate_fix_script(self):
        """توليد سكريبت لإصلاح الاستيرادات المفقودة"""
        fixes = []
        
        for file_path, missing_list in self.missing_imports.items():
            for import_name, line_no in missing_list:
                analysis = self.analyze_missing_import(import_name)
                
                if analysis['suggestions']:
                    fixes.append({
                        'file': file_path,
                        'line': line_no,
                        'old_import': import_name,
                        'suggested_import': analysis['suggestions'][0],
                        'type': analysis['type']
                    })
        
        return fixes
    
    def run_detailed_analysis(self):
        """تشغيل التحليل المفصل"""
        print("🔍 مسح الوحدات الموجودة...")
        self.scan_existing_modules()
        print(f"✅ تم العثور على {len(self.existing_modules)} وحدة")
        
        # تحليل الملفات
        python_files = []
        for base_path in [self.src_path, self.tests_path]:
            if base_path.exists():
                python_files.extend(base_path.glob("**/*.py"))
        
        print(f"\n📄 تحليل {len(python_files)} ملف Python...")
        
        for file_path in sorted(python_files):
            self.analyze_file(file_path)
        
        # عرض النتائج المفصلة
        self.display_detailed_results()
    
    def analyze_file(self, file_path: Path):
        """تحليل ملف واحد"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if not self.check_import_exists(alias.name):
                            self.missing_imports[str(file_path)].append((alias.name, node.lineno))
                            
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    full_import = module
                    
                    if not self.check_import_exists(full_import) and (
                        full_import.startswith('src.') or full_import.startswith('tests.')):
                        self.missing_imports[str(file_path)].append((full_import, node.lineno))
        except:
            pass
    
    def check_import_exists(self, import_name: str) -> bool:
        """التحقق من وجود الاستيراد"""
        if import_name.startswith('src.') or import_name.startswith('tests.'):
            # تحقق بسيط من الوجود في قائمة الوحدات
            return any(module.startswith(import_name) for module in self.existing_modules)
        return True
    
    def display_detailed_results(self):
        """عرض النتائج المفصلة"""
        if not self.missing_imports:
            print("\n✅ لا توجد استيرادات مفقودة!")
            return
        
        print("\n" + "="*80)
        print("📊 تحليل مفصل للاستيرادات المفقودة")
        print("="*80)
        
        # تجميع حسب النوع
        by_type = defaultdict(list)
        all_missing = []
        
        for file_path, missing_list in self.missing_imports.items():
            for import_name, line_no in missing_list:
                import_type = self.classify_import(import_name)
                by_type[import_type].append({
                    'file': Path(file_path).relative_to(self.project_root),
                    'import': import_name,
                    'line': line_no
                })
                all_missing.append(import_name)
        
        # عرض حسب النوع
        for import_type, items in sorted(by_type.items()):
            print(f"\n📦 {import_type} ({len(items)} استيراد)")
            print("-" * 60)
            
            # تجميع الاستيرادات المتكررة
            import_count = defaultdict(list)
            for item in items:
                import_count[item['import']].append((item['file'], item['line']))
            
            for import_name, locations in sorted(import_count.items()):
                print(f"\n  ❌ {import_name}")
                analysis = self.analyze_missing_import(import_name)
                
                if analysis['suggestions']:
                    print(f"     💡 اقتراحات:")
                    for sugg in analysis['suggestions'][:3]:
                        print(f"        - {sugg}")
                
                print(f"     📍 مواقع الاستخدام:")
                for file_path, line_no in locations[:3]:
                    print(f"        - {file_path}:{line_no}")
                
                if len(locations) > 3:
                    print(f"        ... و {len(locations) - 3} موقع آخر")
        
        # إحصائيات نهائية
        print("\n" + "="*80)
        print("📈 الإحصائيات النهائية:")
        print(f"   - إجمالي الملفات المتأثرة: {len(self.missing_imports)}")
        print(f"   - إجمالي الاستيرادات المفقودة: {len(all_missing)}")
        print(f"   - الاستيرادات الفريدة المفقودة: {len(set(all_missing))}")
        
        # توليد سكريبت الإصلاح
        fixes = self.generate_fix_script()
        if fixes:
            print(f"\n🔧 يمكن إصلاح {len(fixes)} استيراد تلقائياً")
            print("   قم بتشغيل: python scripts/auto_fix_imports.py")

if __name__ == "__main__":
    project_root = "/mnt/c/Users/jaafa/Desktop/ai teddy bear"
    analyzer = DetailedImportAnalyzer(project_root)
    analyzer.run_detailed_analysis()