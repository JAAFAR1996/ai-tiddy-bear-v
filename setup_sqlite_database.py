#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧸 AI TEDDY BEAR - SQLITE DATABASE SETUP
========================================

Simple SQLite database setup for production testing
"""

import sqlite3
import os
import sys
import hashlib
import uuid
from datetime import datetime
from pathlib import Path

def create_database():
    """إنشاء قاعدة البيانات وإعدادها"""
    
    print("🗄️ إعداد قاعدة البيانات SQLite...")
    
    # مسار قاعدة البيانات
    db_path = Path("aiteddy_production.db")
    
    # إنشاء الاتصال
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # إنشاء جدول المستخدمين
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT,
                role TEXT NOT NULL DEFAULT 'child',
                is_active BOOLEAN DEFAULT 1,
                display_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # إنشاء جدول الأطفال
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS children (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                name TEXT NOT NULL,
                age INTEGER,
                parental_consent BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_id) REFERENCES users(id)
            )
        """)
        
        # إنشاء جدول المحادثات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                child_id TEXT,
                status TEXT DEFAULT 'active',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (child_id) REFERENCES children(id)
            )
        """)
        
        # إنشاء جدول التفاعلات
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                safety_score REAL DEFAULT 100.0,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
        
        # إنشاء مستخدم admin
        admin_id = str(uuid.uuid4())
        admin_password = "admin123"  # كلمة مرور بسيطة للاختبار
        password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
        
        cursor.execute("""
            INSERT OR IGNORE INTO users (id, username, email, password_hash, role, display_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (admin_id, "admin", "admin@aiteddybear.com", password_hash, "admin", "System Admin"))
        
        # حفظ التغييرات
        conn.commit()
        
        print("✅ تم إنشاء قاعدة البيانات بنجاح")
        print(f"📁 مسار قاعدة البيانات: {db_path.absolute()}")
        print("👤 تم إنشاء مستخدم admin:")
        print("   Username: admin")
        print("   Password: admin123")
        
        return True
        
    except Exception as e:
        print(f"❌ خطأ في إنشاء قاعدة البيانات: {e}")
        return False
        
    finally:
        conn.close()

def backup_database():
    """إنشاء نسخة احتياطية"""
    
    print("💾 إنشاء نسخة احتياطية...")
    
    db_path = Path("aiteddy_production.db")
    if not db_path.exists():
        print("❌ قاعدة البيانات غير موجودة")
        return False
    
    # إنشاء نسخة احتياطية
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"backup_aiteddy_{timestamp}.db")
    
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ تم إنشاء النسخة الاحتياطية: {backup_path}")
        return True
    except Exception as e:
        print(f"❌ خطأ في النسخ الاحتياطي: {e}")
        return False

def test_database():
    """اختبار قاعدة البيانات"""
    
    print("🧪 اختبار قاعدة البيانات...")
    
    db_path = Path("aiteddy_production.db")
    if not db_path.exists():
        print("❌ قاعدة البيانات غير موجودة")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # اختبار الجداول
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        expected_tables = ['users', 'children', 'conversations', 'interactions']
        found_tables = [table[0] for table in tables]
        
        for table in expected_tables:
            if table in found_tables:
                print(f"✅ جدول {table} موجود")
            else:
                print(f"❌ جدول {table} مفقود")
        
        # اختبار المستخدم admin
        cursor.execute("SELECT username FROM users WHERE role='admin'")
        admin = cursor.fetchone()
        
        if admin:
            print("✅ مستخدم admin موجود")
        else:
            print("❌ مستخدم admin مفقود")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ خطأ في اختبار قاعدة البيانات: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    
    print("🧸 إعداد قاعدة البيانات - AI Teddy Bear")
    print("=" * 40)
    
    # التحقق من المعاملات
    if len(sys.argv) > 1:
        if sys.argv[1] == "--backup":
            return backup_database()
        elif sys.argv[1] == "--test":
            return test_database()
    
    # إعداد قاعدة البيانات
    if create_database():
        if test_database():
            print("\n✅ إعداد قاعدة البيانات مكتمل!")
            return True
    
    print("\n❌ فشل في إعداد قاعدة البيانات")
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)