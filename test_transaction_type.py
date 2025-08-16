#!/usr/bin/env python3
"""
Test TransactionType member access fixes
"""

def test_transaction_type_access():
    """Test that TransactionType is correctly imported and used"""
    print("🔍 Testing TransactionType member access fixes...")
    
    try:
        # Read the integration.py file
        with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/infrastructure/database/integration.py', 'r') as f:
            content = f.read()
        
        # Check for correct import of TransactionType
        has_transaction_type_import = 'TransactionType,' in content
        
        print(f"✅ TransactionType import present: {'YES' if has_transaction_type_import else 'NO'}")
        
        # Check for correct usage (direct access, not through transaction_manager)
        has_direct_usage = 'TransactionType.CHILD_SAFE' in content and 'TransactionType.SAGA' in content
        has_old_usage = 'transaction_manager.TransactionType' in content
        
        print(f"✅ Direct TransactionType usage: {'YES' if has_direct_usage else 'NO'}")
        print(f"❌ Old transaction_manager.TransactionType usage: {'YES' if has_old_usage else 'NO'}")
        
        if has_transaction_type_import and has_direct_usage and not has_old_usage:
            print("✅ TransactionType access is correctly fixed")
            
            # Check specific usage patterns
            child_safe_usage = 'transaction_type=TransactionType.CHILD_SAFE' in content
            saga_usage = 'transaction_type=TransactionType.SAGA' in content
            
            print(f"✅ CHILD_SAFE usage correct: {'YES' if child_safe_usage else 'NO'}")
            print(f"✅ SAGA usage correct: {'YES' if saga_usage else 'NO'}")
            
            return child_safe_usage and saga_usage
        else:
            if has_old_usage:
                print("❌ Old usage pattern still exists")
            if not has_transaction_type_import:
                print("❌ TransactionType import missing")
            if not has_direct_usage:
                print("❌ Direct usage pattern missing")
            return False
            
    except Exception as e:
        print(f"❌ Error reading source: {e}")
        return False

def test_transaction_manager_class():
    """Test that TransactionManager class has TransactionType attribute"""
    print("🔍 Testing TransactionManager class structure...")
    
    try:
        # Read the transaction_manager.py file
        with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/infrastructure/database/transaction_manager.py', 'r') as f:
            content = f.read()
        
        # Check if TransactionType is made accessible as class attribute
        has_class_attribute = 'TransactionType = TransactionType' in content
        
        print(f"✅ TransactionType as class attribute: {'YES' if has_class_attribute else 'NO'}")
        
        return has_class_attribute
            
    except Exception as e:
        print(f"❌ Error reading transaction_manager source: {e}")
        return False

if __name__ == "__main__":
    success1 = test_transaction_type_access()
    success2 = test_transaction_manager_class()
    
    overall_success = success1 and success2
    print(f"\n{'✅ SUCCESS' if overall_success else '❌ FAILED'}")
    exit(0 if overall_success else 1)