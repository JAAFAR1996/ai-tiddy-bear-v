#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
💾 نسخ احتياطي بسيط لقاعدة البيانات
Simple Database Backup
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

def create_backup():
    """إنشاء نسخة احتياطية"""
    
    print("💾 إنشاء نسخة احتياطية...")
    
    # مسار قاعدة البيانات
    db_path = Path("aiteddy_production.db")
    
    if not db_path.exists():
        print("❌ قاعدة البيانات غير موجودة")
        return False
    
    # إنشاء اسم النسخة الاحتياطية
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_aiteddy_{timestamp}.db"
    backup_path = Path(backup_name)
    
    try:
        # نسخ قاعدة البيانات
        shutil.copy2(db_path, backup_path)
        print(f"✅ تم إنشاء النسخة الاحتياطية: {backup_path}")
        
        # إنشاء ملف معلومات النسخة الاحتياطية
        info_file = Path(f"backup_info_{timestamp}.txt")
        with open(info_file, 'w', encoding='utf-8') as f:
            f.write(f"نسخة احتياطية لقاعدة البيانات\n")
            f.write(f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"الملف الأصلي: {db_path}\n")
            f.write(f"النسخة الاحتياطية: {backup_path}\n")
            f.write(f"الحجم: {backup_path.stat().st_size} بايت\n")
        
        print(f"📄 ملف المعلومات: {info_file}")
        return True
        
    except Exception as e:
        print(f"❌ خطأ في النسخ الاحتياطي: {e}")
        return False

def test_restore():
    """اختبار الاستعادة"""
    
    print("🧪 اختبار الاستعادة...")
    
    # البحث عن أحدث نسخة احتياطية
    backup_files = list(Path('.').glob('backup_aiteddy_*.db'))
    
    if not backup_files:
        print("❌ لا توجد نسخ احتياطية")
        return False
    
    # أحدث نسخة احتياطية
    latest_backup = max(backup_files, key=lambda f: f.stat().st_mtime)
    
    try:
        # إنشاء نسخة تجريبية للاختبار
        test_restore_path = Path("test_restore.db")
        shutil.copy2(latest_backup, test_restore_path)
        
        # اختبار فتح قاعدة البيانات
        import sqlite3
        conn = sqlite3.connect(str(test_restore_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        conn.close()
        
        # حذف الملف التجريبي
        test_restore_path.unlink()
        
        print(f"✅ اختبار الاستعادة نجح - {user_count} مستخدم")
        return True
        
    except Exception as e:
        print(f"❌ خطأ في اختبار الاستعادة: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    
    print("💾 نظام النسخ الاحتياطي البسيط")
    print("=" * 40)
    
    # التحقق من المعاملات
    if len(sys.argv) > 1:
        if sys.argv[1] == "--backup":
            return create_backup()
        elif sys.argv[1] == "--test":
            return test_restore()
        elif sys.argv[1] == "--restore":
            return test_restore()  # نفس الاختبار
    
    # تشغيل النسخ الاحتياطي والاختبار
    backup_success = create_backup()
    if backup_success:
        test_success = test_restore()
        if test_success:
            print("\n✅ نظام النسخ الاحتياطي يعمل بشكل مثالي!")
            return True
    
    print("\n❌ مشكلة في نظام النسخ الاحتياطي")
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)