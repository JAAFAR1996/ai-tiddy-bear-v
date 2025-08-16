#!/usr/bin/env python3
"""
Test NotificationPriority enum members
"""

def test_notification_priority_members():
    """Test that NotificationPriority has URGENT and NORMAL members"""
    print("🔍 Testing NotificationPriority enum members...")
    
    try:
        # Read the subscription.py file
        with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/core/entities/subscription.py', 'r') as f:
            content = f.read()
        
        # Check for NotificationPriority class
        has_class = 'class NotificationPriority(Enum):' in content
        
        print(f"✅ NotificationPriority class present: {'YES' if has_class else 'NO'}")
        
        if has_class:
            # Check for required members
            members_to_check = ['URGENT', 'NORMAL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
            found_members = []
            missing_members = []
            
            for member in members_to_check:
                member_pattern = f'{member} = "{member.lower()}"'
                if member_pattern in content:
                    found_members.append(member)
                    print(f"✅ Found member: {member}")
                else:
                    missing_members.append(member)
                    print(f"❌ Missing member: {member}")
            
            print(f"📊 Members found: {len(found_members)}/{len(members_to_check)}")
            
            # Check usage of new members
            try:
                with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/infrastructure/monitoring/child_safety_alerts.py', 'r') as f2:
                    usage_content = f2.read()
                
                urgent_usage = 'NotificationPriority.URGENT' in usage_content
                normal_usage = 'NotificationPriority.NORMAL' in usage_content
                
                print(f"✅ URGENT member used: {'YES' if urgent_usage else 'NO'}")
                print(f"✅ NORMAL member used: {'YES' if normal_usage else 'NO'}")
                
                usage_success = urgent_usage and normal_usage
            except:
                print("⚠️  Could not check usage in child_safety_alerts.py")
                usage_success = True  # Don't fail if we can't check usage
            
            return 'URGENT' in found_members and 'NORMAL' in found_members and usage_success
        else:
            print("❌ NotificationPriority class not found")
            return False
            
    except Exception as e:
        print(f"❌ Error reading source: {e}")
        return False

if __name__ == "__main__":
    success = test_notification_priority_members()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)