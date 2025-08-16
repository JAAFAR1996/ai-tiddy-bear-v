#!/usr/bin/env python3
"""
Test PrometheusMetrics with fallback when prometheus_client not available
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_prometheus_fallback():
    """Test PrometheusMetrics works without prometheus_client"""
    print("🔄 Testing PrometheusMetrics fallback functionality...")
    
    try:
        # First check that prometheus_client is not available
        try:
            import prometheus_client
            print("⚠️  prometheus_client is available - testing normal path")
        except ImportError:
            print("✅ prometheus_client not available - testing fallback path")
        
        from src.infrastructure.monitoring.prometheus_metrics import PrometheusMetrics, PROMETHEUS_AVAILABLE
        
        print(f"📊 PROMETHEUS_AVAILABLE: {PROMETHEUS_AVAILABLE}")
        
        # Create instance (should work regardless of prometheus_client availability)
        metrics = PrometheusMetrics()
        print("✅ PrometheusMetrics instance created successfully")
        
        # Test deployment methods
        assert hasattr(metrics, 'record_deployment_success'), "❌ record_deployment_success method missing"
        assert hasattr(metrics, 'record_deployment_failure'), "❌ record_deployment_failure method missing"
        print("✅ Both deployment methods exist")
        
        # Test method calls
        metrics.record_deployment_success(
            environment="test",
            execution_time=1.5,
            downtime=0.0
        )
        print("✅ record_deployment_success executed without errors")
        
        metrics.record_deployment_failure(
            environment="test",
            error_message="Test deployment error"
        )
        print("✅ record_deployment_failure executed without errors")
        
        # Test get_metrics method
        metrics_output = metrics.get_metrics()
        print(f"📄 Metrics output length: {len(metrics_output)} characters")
        print("✅ get_metrics() works")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_prometheus_fallback()
    exit(0 if success else 1)