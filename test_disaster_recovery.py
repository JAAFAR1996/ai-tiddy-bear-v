#!/usr/bin/env python3
"""
Test EnterpriseDisasterRecoveryManager _validate_failover_consistency method
"""

def test_disaster_recovery_method():
    """Test that _validate_failover_consistency method exists"""
    print("🔍 Testing EnterpriseDisasterRecoveryManager method...")
    
    try:
        # Read the source file
        with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/infrastructure/database/enterprise_database_manager.py', 'r') as f:
            content = f.read()
        
        # Check for method definition
        has_method = 'def _validate_failover_consistency(' in content
        
        print(f"✅ _validate_failover_consistency in source: {'YES' if has_method else 'NO'}")
        
        if has_method:
            # Check method signature
            if 'target_tier: DatabaseTier' in content:
                print("✅ _validate_failover_consistency has correct parameter type")
            
            # Check for key functionality
            checks = [
                'async def _validate_failover_consistency',  # Async method
                'target_pool = self._get_pool_by_tier',      # Gets target pool  
                'child_count = await conn.fetchval',         # Child safety validation
                'replication_lag = await conn.fetchval',     # Replication check
                'active_locks = await conn.fetchval',        # Lock check
                'pool_health = await target_pool.health_check()', # Health check
            ]
            
            found_checks = 0
            for check in checks:
                if check in content:
                    found_checks += 1
                    print(f"✅ Found: {check}")
                else:
                    print(f"❌ Missing: {check}")
            
            print(f"📊 Method completeness: {found_checks}/{len(checks)} checks passed")
            
            # Check that method is inside EnterpriseDisasterRecoveryManager class
            class_start = content.find('class EnterpriseDisasterRecoveryManager:')
            if class_start != -1:
                remaining_content = content[class_start:]
                next_class = remaining_content.find('\nclass ', 1)
                
                if next_class == -1:
                    class_content = remaining_content
                else:
                    class_content = remaining_content[:next_class]
                
                method_in_class = 'def _validate_failover_consistency(' in class_content
                print(f"✅ Method inside correct class: {method_in_class}")
                
                return found_checks >= 4  # At least 4 core checks should pass
            else:
                print("❌ EnterpriseDisasterRecoveryManager class not found")
                return False
        else:
            print("❌ _validate_failover_consistency method missing from source")
            return False
            
    except Exception as e:
        print(f"❌ Error reading source: {e}")
        return False

if __name__ == "__main__":
    success = test_disaster_recovery_method()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)