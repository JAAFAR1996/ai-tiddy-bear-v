#!/usr/bin/env python3
"""
Test transaction_manager import fixes in health_checks
"""

def test_transaction_imports():
    """Test that imports are correctly fixed in health_checks.py"""
    print("🔍 Testing transaction_manager and migration_manager imports...")
    
    try:
        # Read the health_checks file
        with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/infrastructure/database/health_checks.py', 'r') as f:
            content = f.read()
        
        # Check for correct import statements
        has_correct_import = 'from . import transaction_manager, migration_manager' in content
        has_old_imports = 'from .transaction_manager import transaction_manager' in content or 'from .migrations import migration_manager' in content
        
        print(f"✅ Correct module-level import: {'YES' if has_correct_import else 'NO'}")
        print(f"❌ Old direct imports still present: {'YES' if has_old_imports else 'NO'}")
        
        if has_correct_import and not has_old_imports:
            print("✅ Import statements are correctly fixed")
            
            # Check that the imports are used correctly in the code
            uses_transaction_manager = 'transaction_manager.' in content
            uses_migration_manager = 'migration_manager.' in content
            
            print(f"✅ transaction_manager is used: {'YES' if uses_transaction_manager else 'NO'}")
            print(f"✅ migration_manager is used: {'YES' if uses_migration_manager else 'NO'}")
            
            # Check for database_manager import (should still be direct)
            has_db_manager = 'from .database_manager import database_manager' in content
            print(f"✅ database_manager import preserved: {'YES' if has_db_manager else 'NO'}")
            
            return has_correct_import and not has_old_imports
        else:
            if has_old_imports:
                print("❌ Old import pattern still exists")
            if not has_correct_import:
                print("❌ New import pattern missing")
            return False
            
    except Exception as e:
        print(f"❌ Error reading source: {e}")
        return False

if __name__ == "__main__":
    success = test_transaction_imports()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)