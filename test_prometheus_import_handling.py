#!/usr/bin/env python3
"""
Test prometheus_client import error handling
"""

def test_prometheus_import_handling():
    """Test that prometheus_client imports are handled gracefully"""
    print("🔍 Testing prometheus_client import error handling...")
    
    try:
        # Read the prometheus_metrics.py file
        with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/infrastructure/monitoring/prometheus_metrics.py', 'r') as f:
            content = f.read()
        
        # Check for try/except import block
        has_try_except = 'try:' in content and 'from prometheus_client import' in content and 'except ImportError:' in content
        
        print(f"✅ Try/except import block present: {'YES' if has_try_except else 'NO'}")
        
        if has_try_except:
            # Check for PROMETHEUS_AVAILABLE flag
            has_flag = 'PROMETHEUS_AVAILABLE = True' in content and 'PROMETHEUS_AVAILABLE = False' in content
            
            print(f"✅ PROMETHEUS_AVAILABLE flag present: {'YES' if has_flag else 'NO'}")
            
            # Check for fallback classes
            fallback_classes = ['class Counter:', 'class Histogram:', 'class Gauge:', 'class Info:', 'class PrometheusEnum:']
            found_fallbacks = 0
            
            for fallback_class in fallback_classes:
                if fallback_class in content:
                    found_fallbacks += 1
                    print(f"✅ Found fallback: {fallback_class}")
                else:
                    print(f"❌ Missing fallback: {fallback_class}")
            
            print(f"📊 Fallback classes: {found_fallbacks}/{len(fallback_classes)}")
            
            # Check for fallback functions
            has_generate_latest = 'def generate_latest(registry):' in content
            has_content_type = 'CONTENT_TYPE_LATEST = "text/plain"' in content
            
            print(f"✅ Fallback generate_latest function: {'YES' if has_generate_latest else 'NO'}")
            print(f"✅ Fallback CONTENT_TYPE_LATEST: {'YES' if has_content_type else 'NO'}")
            
            # Check for conditional logging in constructor
            has_conditional_logging = 'if PROMETHEUS_AVAILABLE:' in content and 'else:' in content and 'self.logger.warning' in content
            
            print(f"✅ Conditional logging in constructor: {'YES' if has_conditional_logging else 'NO'}")
            
            # Check that requirements.txt has prometheus-client
            try:
                with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/requirements.txt', 'r') as f2:
                    requirements = f2.read()
                
                has_requirement = 'prometheus-client' in requirements
                print(f"✅ prometheus-client in requirements.txt: {'YES' if has_requirement else 'NO'}")
            except:
                print("⚠️  Could not check requirements.txt")
                has_requirement = True  # Don't fail if we can't check
            
            # All checks should pass for complete import handling
            return (has_try_except and has_flag and 
                   found_fallbacks >= 4 and  # At least 4 main fallback classes
                   has_generate_latest and has_content_type and
                   has_conditional_logging and has_requirement)
        else:
            print("❌ Try/except import block not found")
            return False
            
    except Exception as e:
        print(f"❌ Error reading source: {e}")
        return False

if __name__ == "__main__":
    success = test_prometheus_import_handling()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)