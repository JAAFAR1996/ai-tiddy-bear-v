#!/usr/bin/env python3
"""
Direct test of PrometheusMetrics methods by reading source code
"""

def test_source_methods():
    """Test by reading the source file directly"""
    print("🔍 Testing PrometheusMetrics methods by source code analysis...")
    
    try:
        # Read the source file
        with open('/mnt/c/Users/jaafa/Desktop/ai teddy bear/src/infrastructure/monitoring/prometheus_metrics.py', 'r') as f:
            content = f.read()
        
        # Check for method definitions
        has_success = 'def record_deployment_success(' in content
        has_failure = 'def record_deployment_failure(' in content
        
        print(f"✅ record_deployment_success in source: {'YES' if has_success else 'NO'}")
        print(f"✅ record_deployment_failure in source: {'YES' if has_failure else 'NO'}")
        
        if has_success and has_failure:
            print("✅ Both deployment methods are present in source code")
            
            # Check method signatures
            if 'def record_deployment_success(' in content and 'environment: str' in content:
                print("✅ record_deployment_success has correct signature")
            
            if 'def record_deployment_failure(' in content and 'error_message: str' in content:
                print("✅ record_deployment_failure has correct signature")
            
            # Check that methods are inside PrometheusMetrics class
            prometheus_class_start = content.find('class PrometheusMetrics:')
            if prometheus_class_start != -1:
                # Find next class to get the boundary
                remaining_content = content[prometheus_class_start:]
                next_class = remaining_content.find('\nclass ', 1)
                
                if next_class == -1:
                    prometheus_class_content = remaining_content
                else:
                    prometheus_class_content = remaining_content[:next_class]
                
                success_in_class = 'def record_deployment_success(' in prometheus_class_content
                failure_in_class = 'def record_deployment_failure(' in prometheus_class_content
                
                print(f"✅ Methods inside PrometheusMetrics class: {success_in_class and failure_in_class}")
            
            return True
        else:
            print("❌ Deployment methods missing from source")
            return False
            
    except Exception as e:
        print(f"❌ Error reading source: {e}")
        return False

if __name__ == "__main__":
    success = test_source_methods()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)