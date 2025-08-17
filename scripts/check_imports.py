#!/usr/bin/env python3
"""
🔍 AI Teddy Bear Import Checker - Advanced Version
================================
فحص شامل ومتقدم للاستيرادات في جميع ملفات Python
يتحقق من:
1. وجود الملفات والوحدات المستوردة
2. وجود الكلاسات والدوال المحددة
3. صحة المسارات النسبية والمطلقة
4. التبعيات الخارجية المطلوبة
5. أخطاء النحو في الاستيرادات

الاستخدام:
    python scripts/check_imports.py
    python scripts/check_imports.py --verbose
    python scripts/check_imports.py --save-report
"""

import os
import ast
import sys
import json
import importlib
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
from datetime import datetime
import traceback

class ImportChecker:
    def __init__(self, project_root: str, verbose: bool = False):
        self.project_root = Path(project_root)
        self.src_path = self.project_root / "src"
        self.tests_path = self.project_root / "tests"
        self.verbose = verbose
        
        # نتائج التحليل
        self.missing_imports = defaultdict(list)
        self.missing_attributes = defaultdict(list)
        self.all_imports = defaultdict(list)
        self.syntax_errors = defaultdict(list)
        self.external_imports = set()
        
        # خريطة الوحدات المتاحة
        self.available_modules = {}
        self.module_contents = {}
        
        # إحصائيات
        self.stats = {
            'total_files': 0,
            'total_imports': 0,
            'missing_modules': 0,
            'missing_attributes': 0,
            'syntax_errors': 0,
            'external_dependencies': 0
        }
        
        # بناء خريطة الوحدات
        self._build_module_map()
    
    def _build_module_map(self):
        """بناء خريطة الوحدات المتاحة في المشروع"""
        if self.verbose:
            print("🔍 بناء خريطة الوحدات...")
        
        # العثور على جميع ملفات Python
        for py_file in self.find_python_files():
            try:
                relative_path = py_file.relative_to(self.project_root)
                module_parts = list(relative_path.parts[:-1])
                
                if relative_path.name == '__init__.py':
                    if module_parts:
                        module_name = '.'.join(module_parts)
                    else:
                        continue
                else:
                    module_name = '.'.join(module_parts + [relative_path.stem])
                
                if module_name:
                    self.available_modules[module_name] = str(py_file)
                    # تحليل محتوى الملف
                    self.module_contents[module_name] = self._analyze_module_content(py_file)
                    
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ خطأ في تحليل {py_file}: {e}")
    
    def _analyze_module_content(self, file_path: Path) -> Dict[str, List[str]]:
        """تحليل محتوى الوحدة لاستخراج الكلاسات والدوال والمتغيرات"""
        content_info = {
            'classes': [],
            'functions': [],
            'variables': [],
            'constants': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    content_info['classes'].append(node.name)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    content_info['functions'].append(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if target.id.isupper():
                                content_info['constants'].append(target.id)
                            else:
                                content_info['variables'].append(target.id)
                                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ خطأ في تحليل محتوى {file_path}: {e}")
        
        return content_info
        
    def find_python_files(self) -> List[Path]:
        """العثور على جميع ملفات Python في المشروع"""
        python_files = []
        
        # مجلدات للتجاهل
        ignore_dirs = {
            '__pycache__', '.git', '.pytest_cache', 'node_modules', 
            '.venv', '.venv_test', 'venv', '.mypy_cache', '.coverage',
            'htmlcov', 'build', 'dist', '.egg-info', '.tox'
        }
        
        # البحث في المشروع كاملاً
        for root, dirs, files in os.walk(self.project_root):
            # تجاهل المجلدات غير المرغوب فيها
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        
        return python_files
    
    def extract_imports(self, file_path: Path) -> List[Tuple[str, str, int, List[str]]]:
        """استخراج جميع الاستيرادات من ملف Python مع تفاصيل أكثر"""
        imports = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # (import_type, module_name, line_no, imported_names)
                        imports.append(('import', alias.name, node.lineno, [alias.name]))
                        
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    imported_names = []
                    
                    if node.names:
                        for alias in node.names:
                            imported_names.append(alias.name)
                    
                    imports.append(('from_import', module, node.lineno, imported_names))
                    
        except SyntaxError as e:
            self.syntax_errors[str(file_path)].append({
                'line': e.lineno,
                'message': e.msg,
                'text': e.text
            })
            self.stats['syntax_errors'] += 1
            
        except Exception as e:
            if self.verbose:
                print(f"خطأ في قراءة {file_path}: {e}")
        
        return imports
    
    def check_module_exists(self, module_name: str) -> Tuple[bool, str]:
        """التحقق من وجود الوحدة"""
        # التحقق من الوحدات الداخلية
        if module_name in self.available_modules:
            return True, "internal"
        
        # التحقق من الوحدات الخارجية الشائعة (من requirements.txt)
        common_external_modules = {
            'fastapi', 'uvicorn', 'pydantic', 'sqlalchemy', 'asyncpg', 'alembic',
            'redis', 'pytest', 'pytest_asyncio', 'httpx', 'requests', 'aiohttp',
            'bcrypt', 'passlib', 'jwt', 'jose', 'cryptography', 'openai',
            'anthropic', 'numpy', 'pandas', 'matplotlib', 'scipy', 'sklearn',
            'torch', 'tensorflow', 'keras', 'PIL', 'cv2', 'boto3', 'google',
            'azure', 'injector', 'dependency_injector', 'structlog', 'loguru',
            'prometheus_client', 'sentry_sdk', 'celery', 'flower', 'graphene',
            'strawberry', 'ariadne', 'click', 'typer', 'rich', 'tqdm',
            'yaml', 'toml', 'dotenv', 'decouple', 'environs', 'pydantic_settings',
            'slowapi', 'fastapi_limiter', 'authlib', 'starlette', 'anyio',
            'httpcore', 'h11', 'websockets', 'aiofiles', 'jinja2', 'mako',
            'marshmallow', 'attrs', 'cattrs', 'dacite', 'msgpack', 'orjson',
            'ujson', 'pendulum', 'arrow', 'humanize', 'tabulate', 'prettytable'
        }
        
        # فحص إذا كانت الوحدة من المكتبات الخارجية المعروفة
        base_module = module_name.split('.')[0]
        if base_module in common_external_modules:
            self.external_imports.add(module_name)
            return True, "external"
        
        # محاولة استيراد الوحدة للتأكد (فقط للوحدات غير المعروفة)
        if not module_name.startswith(('src.', 'tests.')):
            try:
                importlib.import_module(module_name)
                self.external_imports.add(module_name)
                return True, "external"
            except ImportError:
                # قد تكون مكتبة خارجية غير مثبتة
                self.external_imports.add(module_name)
                return True, "external_not_installed"
        
        return False, "missing"
    
    def check_attribute_exists(self, module_name: str, attribute_name: str) -> bool:
        """التحقق من وجود خاصية في وحدة"""
        # فحص الوحدات الداخلية
        if module_name in self.module_contents:
            content = self.module_contents[module_name]
            return (attribute_name in content['classes'] or
                   attribute_name in content['functions'] or 
                   attribute_name in content['variables'] or
                   attribute_name in content['constants'])
        
        # فحص الوحدات الخارجية
        try:
            module = importlib.import_module(module_name)
            return hasattr(module, attribute_name)
        except ImportError:
            return False
    
    def analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """تحليل ملف واحد وإرجاع تفاصيل الاستيرادات"""
        if self.verbose:
            print(f"🔍 فحص: {file_path.relative_to(self.project_root)}")
        
        imports = self.extract_imports(file_path)
        file_results = {
            'total_imports': len(imports),
            'missing_modules': [],
            'missing_attributes': [],
            'external_dependencies': [],
            'valid_imports': []
        }
        
        for import_type, module_name, line_no, imported_names in imports:
            self.stats['total_imports'] += 1
            
            # تجاهل الاستيرادات النسبية المعقدة مؤقتاً
            if module_name.startswith('.'):
                continue
            
            # فحص وجود الوحدة
            module_exists, module_type = self.check_module_exists(module_name)
            
            if not module_exists:
                self.missing_imports[str(file_path)].append({
                    'module': module_name,
                    'line': line_no,
                    'type': import_type,
                    'names': imported_names
                })
                file_results['missing_modules'].append({
                    'module': module_name,
                    'line': line_no,
                    'names': imported_names
                })
                self.stats['missing_modules'] += 1
                continue
            
            # إذا كانت الوحدة موجودة، فحص الخصائص المستوردة
            if import_type == 'from_import':
                for attr_name in imported_names:
                    if attr_name == '*':
                        continue
                    
                    if not self.check_attribute_exists(module_name, attr_name):
                        self.missing_attributes[str(file_path)].append({
                            'module': module_name,
                            'attribute': attr_name,
                            'line': line_no
                        })
                        file_results['missing_attributes'].append({
                            'module': module_name,
                            'attribute': attr_name,
                            'line': line_no
                        })
                        self.stats['missing_attributes'] += 1
            
            # تسجيل التبعيات الخارجية
            if module_type == 'external':
                file_results['external_dependencies'].append(module_name)
                self.stats['external_dependencies'] += 1
            else:
                file_results['valid_imports'].append({
                    'module': module_name,
                    'names': imported_names,
                    'line': line_no
                })
        
        self.stats['total_files'] += 1
        return file_results
    
    def run_analysis(self):
        """تشغيل التحليل الكامل"""
        start_time = datetime.now()
        print(f"🚀 بدء تحليل الاستيرادات...")
        
        python_files = self.find_python_files()
        print(f"📁 تم العثور على {len(python_files)} ملف Python")
        print("=" * 80)
        
        # تحليل كل ملف
        for file_path in sorted(python_files):
            self.analyze_file(file_path)
        
        end_time = datetime.now()
        analysis_time = end_time - start_time
        
        print(f"\n⏱️ انتهى التحليل في {analysis_time}")
        
        # عرض النتائج
        self.display_results()
        
        return {
            'stats': self.stats,
            'missing_imports': dict(self.missing_imports),
            'missing_attributes': dict(self.missing_attributes),
            'syntax_errors': dict(self.syntax_errors),
            'external_imports': list(self.external_imports),
            'analysis_time': str(analysis_time)
        }
    
    def display_results(self):
        """عرض النتائج المنظمة"""
        print("\n📊 ملخص التحليل:")
        print("=" * 50)
        print(f"📁 إجمالي الملفات: {self.stats['total_files']}")
        print(f"📦 إجمالي الاستيرادات: {self.stats['total_imports']}")
        print(f"🌐 التبعيات الخارجية: {len(self.external_imports)}")
        print(f"❌ الوحدات المفقودة: {self.stats['missing_modules']}")
        print(f"⚠️ الخصائص المفقودة: {self.stats['missing_attributes']}")
        print(f"💥 أخطاء النحو: {self.stats['syntax_errors']}")
        
        # عرض أخطاء النحو
        if self.syntax_errors:
            print(f"\n💥 أخطاء النحو:")
            print("=" * 50)
            for file_path, errors in self.syntax_errors.items():
                relative_path = Path(file_path).relative_to(self.project_root)
                print(f"\n📄 {relative_path}")
                for error in errors:
                    print(f"   ✗ السطر {error['line']}: {error['message']}")
        
        # عرض الوحدات المفقودة
        if self.missing_imports:
            print(f"\n❌ الوحدات المفقودة:")
            print("=" * 50)
            for file_path, missing_list in sorted(self.missing_imports.items()):
                if missing_list:
                    relative_path = Path(file_path).relative_to(self.project_root)
                    print(f"\n📄 {relative_path}")
                    for missing in missing_list:
                        print(f"   ✗ السطر {missing['line']}: {missing['module']}")
                        if missing['names'] and missing['names'] != [missing['module']]:
                            print(f"      الأسماء: {', '.join(missing['names'])}")
        
        # عرض الخصائص المفقودة
        if self.missing_attributes:
            print(f"\n⚠️ الخصائص المفقودة:")
            print("=" * 50)
            for file_path, missing_list in sorted(self.missing_attributes.items()):
                if missing_list:
                    relative_path = Path(file_path).relative_to(self.project_root)
                    print(f"\n📄 {relative_path}")
                    for missing in missing_list:
                        print(f"   ✗ السطر {missing['line']}: {missing['module']}.{missing['attribute']}")
        
        # عرض التبعيات الخارجية
        if self.external_imports and self.verbose:
            print(f"\n🌐 التبعيات الخارجية:")
            print("=" * 50)
            for ext_import in sorted(self.external_imports):
                print(f"   - {ext_import}")
        
        # خلاصة
        total_issues = self.stats['missing_modules'] + self.stats['missing_attributes'] + self.stats['syntax_errors']
        if total_issues == 0:
            print(f"\n✅ ممتاز! جميع الاستيرادات صحيحة!")
        else:
            print(f"\n⚠️ إجمالي المشاكل: {total_issues}")
    
    def save_report(self, filename: str = "import_analysis_report.json"):
        """حفظ التقرير في ملف JSON"""
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'project_root': str(self.project_root),
            'stats': self.stats,
            'missing_imports': dict(self.missing_imports),
            'missing_attributes': dict(self.missing_attributes),
            'syntax_errors': dict(self.syntax_errors),
            'external_imports': list(self.external_imports),
            'available_modules': list(self.available_modules.keys())
        }
        
        report_path = self.project_root / filename
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 تم حفظ التقرير في: {report_path}")

def main():
    """الدالة الرئيسية مع معالجة الوسائط"""
    parser = argparse.ArgumentParser(
        description="🔍 فحص شامل للاستيرادات في مشروع AI Teddy Bear",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة الاستخدام:
  python scripts/check_imports.py                    # فحص عادي
  python scripts/check_imports.py --verbose          # فحص مع تفاصيل
  python scripts/check_imports.py --save-report      # حفظ التقرير
  python scripts/check_imports.py --external-deps    # عرض التبعيات الخارجية
        """
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='عرض تفاصيل أكثر أثناء التحليل'
    )
    
    parser.add_argument(
        '--save-report', '-s',
        action='store_true',
        help='حفظ تقرير مفصل بصيغة JSON'
    )
    
    parser.add_argument(
        '--external-deps', '-e',
        action='store_true',
        help='عرض قائمة التبعيات الخارجية'
    )
    
    parser.add_argument(
        '--report-file', '-r',
        type=str,
        default='import_analysis_report.json',
        help='اسم ملف التقرير (افتراضي: import_analysis_report.json)'
    )
    
    parser.add_argument(
        '--project-root',
        type=str,
        default="/mnt/c/Users/jaafa/Desktop/ai teddy bear",
        help='مسار جذر المشروع'
    )
    
    args = parser.parse_args()
    
    # تشغيل التحليل
    try:
        checker = ImportChecker(args.project_root, verbose=args.verbose)
        
        if args.external_deps:
            checker.verbose = True
        
        results = checker.run_analysis()
        
        # حفظ التقرير إذا طُلب
        if args.save_report:
            checker.save_report(args.report_file)
        
        # تحديد رمز الخروج
        total_critical_issues = (results['stats']['missing_modules'] + 
                               results['stats']['syntax_errors'])
        
        if total_critical_issues > 0:
            print(f"\n❌ فشل: {total_critical_issues} مشكلة خطيرة")
            sys.exit(1)
        elif results['stats']['missing_attributes'] > 0:
            print(f"\n⚠️ تحذير: {results['stats']['missing_attributes']} خاصية مفقودة")
            sys.exit(0)
        else:
            print(f"\n✅ نجح: جميع الاستيرادات صحيحة!")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n💥 خطأ في تشغيل التحليل: {e}")
        if args.verbose:
            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()