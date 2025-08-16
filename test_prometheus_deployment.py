#!/usr/bin/env python3
"""
Test script for PrometheusMetrics deployment methods
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_prometheus_deployment_methods():
    """Test that PrometheusMetrics has the deployment methods"""
    print("🔄 Testing PrometheusMetrics deployment methods...")
    
    try:
        from src.infrastructure.monitoring.prometheus_metrics import PrometheusMetrics
        
        # Create instance
        metrics = PrometheusMetrics()
        
        # Test that record_deployment_success method exists
        assert hasattr(metrics, 'record_deployment_success'), "❌ record_deployment_success method missing"
        assert callable(getattr(metrics, 'record_deployment_success')), "❌ record_deployment_success not callable"
        
        # Test that record_deployment_failure method exists
        assert hasattr(metrics, 'record_deployment_failure'), "❌ record_deployment_failure method missing"
        assert callable(getattr(metrics, 'record_deployment_failure')), "❌ record_deployment_failure not callable"
        
        print("✅ PrometheusMetrics has both deployment methods")
        
        # Test method signatures by checking parameters
        import inspect
        success_sig = inspect.signature(metrics.record_deployment_success)
        failure_sig = inspect.signature(metrics.record_deployment_failure)
        
        # Check record_deployment_success parameters
        success_params = list(success_sig.parameters.keys())
        expected_success_params = ['environment', 'execution_time', 'downtime', 'version', 'deployment_type']
        
        for param in expected_success_params:
            assert param in success_params, f"❌ record_deployment_success missing parameter: {param}"
        
        print("✅ record_deployment_success has correct parameters")
        
        # Check record_deployment_failure parameters
        failure_params = list(failure_sig.parameters.keys())
        expected_failure_params = ['environment', 'error_message', 'error_type', 'severity']
        
        for param in expected_failure_params:
            assert param in failure_params, f"❌ record_deployment_failure missing parameter: {param}"
        
        print("✅ record_deployment_failure has correct parameters")
        
        # Test method calls (should not raise exceptions)
        try:
            metrics.record_deployment_success(
                environment="test",
                execution_time=1.5,
                downtime=0.1,
                version="1.0.0",
                deployment_type="blue_green"
            )
            print("✅ record_deployment_success call successful")
        except Exception as e:
            print(f"❌ record_deployment_success call failed: {e}")
            return False
        
        try:
            metrics.record_deployment_failure(
                environment="test",
                error_message="Test error",
                error_type="connection_error",
                severity="high"
            )
            print("✅ record_deployment_failure call successful")
        except Exception as e:
            print(f"❌ record_deployment_failure call failed: {e}")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_prometheus_deployment_methods()
    exit(0 if success else 1)