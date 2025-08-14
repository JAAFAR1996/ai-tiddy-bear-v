#!/usr/bin/env python3
"""
تشغيل سريع لفحص ESP32 - AI Teddy Bear
====================================
تشغيل فوري لفحص حالة ESP32 مع نتائج مبسطة
"""

import subprocess
import sys
import os

def main():
    """تشغيل الفحص السريع"""
    print("🚀 تشغيل فحص ESP32 السريع...")
    print("="*40)
    
    # تشغيل الفحص السريع
    try:
        result = subprocess.run([
            sys.executable, "quick_esp32_check.py"
        ], capture_output=False, text=True)
        
        return result.returncode
        
    except FileNotFoundError:
        print("❌ ملف quick_esp32_check.py غير موجود")
        return 1
    except Exception as e:
        print(f"❌ خطأ في التشغيل: {e}")
        return 2

if __name__ == "__main__":
    sys.exit(main())