#!/usr/bin/env python3
"""
Simple test for PrometheusMetrics methods - bypass logger issues
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_method_presence():
    """Test methods exist without instantiating (avoid logger issues)"""
    print("🔍 Testing method presence...")
    
    try:
        # Import the class
        from src.infrastructure.monitoring.prometheus_metrics import PrometheusMetrics
        
        # Check methods using class inspection
        methods = dir(PrometheusMetrics)
        
        print(f"📝 Total methods in PrometheusMetrics: {len(methods)}")
        
        # Check for deployment methods
        has_success = 'record_deployment_success' in methods
        has_failure = 'record_deployment_failure' in methods
        
        print(f"✅ record_deployment_success: {'YES' if has_success else 'NO'}")
        print(f"✅ record_deployment_failure: {'YES' if has_failure else 'NO'}")
        
        if has_success and has_failure:
            print("✅ Both deployment methods are present in class")
            return True
        else:
            print("❌ Deployment methods missing from class")
            
            # Show all record_ methods for debugging
            record_methods = [m for m in methods if 'record_' in m]
            print(f"📋 Available record_ methods: {record_methods}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_method_presence()
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'}")
    exit(0 if success else 1)