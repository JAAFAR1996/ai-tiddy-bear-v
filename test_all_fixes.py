#!/usr/bin/env python3
"""
Comprehensive test suite for all pylint fixes
اختبار شامل لجميع إصلاحات pylint
"""

import subprocess
import sys
import os

def run_test(test_file, test_name):
    """Run a test file and return success status"""
    print(f"\n{'='*60}")
    print(f"🧪 Running: {test_name}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([sys.executable, test_file], 
                              cwd=os.path.dirname(os.path.abspath(__file__)),
                              capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        success = result.returncode == 0
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"\nResult: {status}")
        return success
        
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Running comprehensive test suite for all pylint fixes")
    print("🔧 Testing all 8 major fixes implemented")
    
    tests = [
        ("test_direct_class.py", "1. PrometheusMetrics deployment methods"),
        ("test_disaster_recovery.py", "2. EnterpriseDisasterRecoveryManager method"),
        ("test_transaction_imports.py", "3. Transaction manager imports"),
        ("test_transaction_type.py", "4. TransactionType member access"),
        ("test_safety_controls.py", "5. SafetyControls.create_safety_alert"),
        ("test_notification_priority.py", "6. NotificationPriority members"),
        ("test_notification_type.py", "7. NotificationType member"),
        ("test_prometheus_simple.py", "8. Prometheus client import handling"),
    ]
    
    results = []
    passed = 0
    total = len(tests)
    
    for test_file, test_name in tests:
        success = run_test(test_file, test_name)
        results.append((test_name, success))
        if success:
            passed += 1
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 FINAL TEST RESULTS SUMMARY")
    print(f"{'='*80}")
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status} {test_name}")
    
    print(f"\n📈 Overall Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! All pylint fixes are working correctly.")
        print("🏆 جميع الإصلاحات تعمل بنسبة 100%")
    else:
        print(f"⚠️  {total-passed} tests failed. Review the output above.")
        print(f"⚠️  {total-passed} اختبارات فشلت. راجع النتائج أعلاه.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)