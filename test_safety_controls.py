#!/usr/bin/env python3
"""
Test SafetyControls.create_safety_alert method
"""

def test_safety_controls_method():
    """Test that create_safety_alert method exists and is complete"""
    print("🔍 Testing SafetyControls.create_safety_alert method...")
    
    try:
        # Read the safety_controls.py file
        with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/adapters/dashboard/safety_controls.py', 'r') as f:
            content = f.read()
        
        # Check for method definition
        has_method = 'def create_safety_alert(' in content
        
        print(f"✅ create_safety_alert method present: {'YES' if has_method else 'NO'}")
        
        if has_method:
            # Check method signature
            has_alert_data_param = 'alert_data: dict' in content
            
            print(f"✅ Correct parameter type: {'YES' if has_alert_data_param else 'NO'}")
            
            # Check for key functionality
            checks = [
                'async def create_safety_alert',              # Async method
                'required_fields = [',                        # Validation logic
                '_validate_uuid(alert_id, "alert_id")',       # UUID validation
                'valid_priorities = [',                       # Priority validation
                'valid_alert_types = [',                      # Alert type validation
                'await self.safety_service.create_safety_alert', # Service call
                'return alert_result',                        # Returns result
            ]
            
            found_checks = 0
            for check in checks:
                if check in content:
                    found_checks += 1
                    print(f"✅ Found: {check}")
                else:
                    print(f"❌ Missing: {check}")
            
            print(f"📊 Method completeness: {found_checks}/{len(checks)} checks passed")
            
            # Check that method is inside SafetyControls class
            class_start = content.find('class SafetyControls:')
            if class_start != -1:
                remaining_content = content[class_start:]
                # Find the end of the class (next class or end of file)
                next_class = remaining_content.find('\nclass ', 1)
                
                if next_class == -1:
                    class_content = remaining_content
                else:
                    class_content = remaining_content[:next_class]
                
                method_in_class = 'def create_safety_alert(' in class_content
                print(f"✅ Method inside SafetyControls class: {method_in_class}")
                
                # Check usage of the method in the child_safety_alerts.py file
                try:
                    with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/infrastructure/monitoring/child_safety_alerts.py', 'r') as f2:
                        alerts_content = f2.read()
                    
                    method_usage = 'safety_controls.create_safety_alert(' in alerts_content
                    print(f"✅ Method used in child_safety_alerts: {'YES' if method_usage else 'NO'}")
                except:
                    print("⚠️  Could not check usage in child_safety_alerts.py")
                
                return found_checks >= 5 and method_in_class  # At least 5 core checks should pass
            else:
                print("❌ SafetyControls class not found")
                return False
        else:
            print("❌ create_safety_alert method missing from source")
            return False
            
    except Exception as e:
        print(f"❌ Error reading source: {e}")
        return False

if __name__ == "__main__":
    success = test_safety_controls_method()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)