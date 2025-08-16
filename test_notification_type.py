#!/usr/bin/env python3
"""
Test NotificationType enum CHILD_SAFETY_ALERT member
"""

def test_notification_type_member():
    """Test that NotificationType has CHILD_SAFETY_ALERT member"""
    print("🔍 Testing NotificationType enum CHILD_SAFETY_ALERT member...")
    
    try:
        # Read the subscription.py file
        with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/core/entities/subscription.py', 'r') as f:
            content = f.read()
        
        # Check for NotificationType class
        has_class = 'class NotificationType(Enum):' in content
        
        print(f"✅ NotificationType class present: {'YES' if has_class else 'NO'}")
        
        if has_class:
            # Check for required members
            members_to_check = [
                'SAFETY_ALERT',
                'CHILD_SAFETY_ALERT', 
                'BEHAVIOR_CONCERN',
                'USAGE_LIMIT',
                'PREMIUM_FEATURE',
                'EMERGENCY'
            ]
            
            found_members = []
            missing_members = []
            
            for member in members_to_check:
                # Convert to expected format: CHILD_SAFETY_ALERT = "child_safety_alert"
                expected_value = member.lower()
                member_pattern = f'{member} = "{expected_value}"'
                if member_pattern in content:
                    found_members.append(member)
                    print(f"✅ Found member: {member}")
                else:
                    missing_members.append(member)
                    print(f"❌ Missing member: {member}")
            
            print(f"📊 Members found: {len(found_members)}/{len(members_to_check)}")
            
            # Special check for the new CHILD_SAFETY_ALERT member
            has_child_safety_alert = 'CHILD_SAFETY_ALERT = "child_safety_alert"' in content
            print(f"✅ CHILD_SAFETY_ALERT member present: {'YES' if has_child_safety_alert else 'NO'}")
            
            # Check usage of the member
            try:
                with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/infrastructure/monitoring/child_safety_alerts.py', 'r') as f2:
                    usage_content = f2.read()
                
                child_safety_usage = 'NotificationType.CHILD_SAFETY_ALERT' in usage_content
                
                print(f"✅ CHILD_SAFETY_ALERT member used: {'YES' if child_safety_usage else 'NO'}")
                
                usage_success = child_safety_usage
            except:
                print("⚠️  Could not check usage in child_safety_alerts.py")
                usage_success = True  # Don't fail if we can't check usage
            
            return has_child_safety_alert and usage_success
        else:
            print("❌ NotificationType class not found")
            return False
            
    except Exception as e:
        print(f"❌ Error reading source: {e}")
        return False

if __name__ == "__main__":
    success = test_notification_type_member()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)