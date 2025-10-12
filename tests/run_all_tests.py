#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تشغيل جميع اختبارات النظام الصحي
Run All Medical System Tests
"""

import sys
import time
import subprocess
import unittest
from datetime import datetime
import os

def print_header(title: str):
    """طباعة عنوان الاختبار"""
    print("\n" + "=" * 80)
    print(f"🏥 {title}")
    print("=" * 80)

def print_footer():
    """طباعة نهاية الاختبار"""
    print("=" * 80)

def run_unittest_script(script_name: str, description: str) -> bool:
    """تشغيل سكريبت unittest"""
    print_header(f"Running {description}")
    
    try:
        start_time = time.time()
        
        # تشغيل unittest
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(script_name.replace('.py', ''))
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"📊 Tests Run: {result.testsRun}")
        print(f"✅ Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
        print(f"❌ Failed: {len(result.failures)}")
        print(f"💥 Errors: {len(result.errors)}")
        
        if result.failures:
            print("\n❌ FAILURES:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback}")
        
        if result.errors:
            print("\n💥 ERRORS:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback}")
        
        success = len(result.failures) == 0 and len(result.errors) == 0
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"\n🎯 RESULT: {status}")
        
        return success
        
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False
    finally:
        print_footer()

def run_custom_test_script(script_name: str, description: str) -> bool:
    """تشغيل سكريبت اختبار مخصص"""
    print_header(f"Running {description}")
    
    try:
        start_time = time.time()
        
        # إضافة المسار الحالي للـ sys.path
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        # تشغيل السكريبت
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=True, text=True, timeout=300,
                              cwd=current_dir)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"📊 Exit Code: {result.returncode}")
        
        if result.stdout:
            print("\n📋 OUTPUT:")
            print(result.stdout)
        
        if result.stderr:
            print("\n❌ ERRORS:")
            print(result.stderr)
        
        success = result.returncode == 0
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"\n🎯 RESULT: {status}")
        
        return success
        
    except subprocess.TimeoutExpired:
        print("⏰ Test timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False
    finally:
        print_footer()

def main():
    """الدالة الرئيسية"""
    print("🚀 Medical System Comprehensive Testing Suite")
    print("=" * 80)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # قائمة الاختبارات
    tests = [
        {
            'script': 'test_basic_units.py',
            'description': 'Basic Unit Tests - اختبارات الوحدات الأساسية',
            'type': 'unittest'
        },
        {
            'script': 'test_api_endpoints.py', 
            'description': 'API Endpoints Tests - اختبارات API endpoints',
            'type': 'unittest'
        },
        {
            'script': 'test_integration_workflows.py',
            'description': 'Integration Workflow Tests - اختبارات التكامل وتدفق العمل',
            'type': 'unittest'
        },
        {
            'script': 'test_system_comprehensive.py',
            'description': 'Comprehensive System Tests - اختبارات النظام الشاملة',
            'type': 'custom'
        },
        {
            'script': 'test_units_detailed.py',
            'description': 'Detailed Unit Tests - اختبارات الوحدات المفصلة',
            'type': 'custom'
        },
        {
            'script': 'test_integration.py',
            'description': 'Integration Tests - اختبارات التكامل',
            'type': 'custom'
        }
    ]
    
    # تشغيل جميع الاختبارات
    results = []
    total_start_time = time.time()
    
    for test in tests:
        if test['type'] == 'unittest':
            success = run_unittest_script(test['script'], test['description'])
        else:
            success = run_custom_test_script(test['script'], test['description'])
            
        results.append({
            'name': test['description'],
            'success': success
        })
        
        # انتظار قصير بين الاختبارات
        time.sleep(2)
    
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    
    # تقرير النتائج النهائية
    print_header("FINAL TEST RESULTS - النتائج النهائية للاختبارات")
    
    passed_tests = sum(1 for r in results if r['success'])
    total_tests = len(results)
    
    print(f"📊 Total Test Suites: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {total_tests - passed_tests}")
    print(f"📈 Success Rate: {(passed_tests/total_tests*100):.1f}%")
    print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
    
    print("\n📋 DETAILED RESULTS:")
    for result in results:
        status = "✅ PASSED" if result['success'] else "❌ FAILED"
        print(f"  {status} - {result['name']}")
    
    overall_success = passed_tests == total_tests
    final_status = "🎉 ALL TESTS PASSED - جميع الاختبارات نجحت" if overall_success else "⚠️  SOME TESTS FAILED - بعض الاختبارات فشلت"
    
    print(f"\n🎯 OVERALL RESULT: {final_status}")
    print_footer()
    
    # إنهاء البرنامج
    sys.exit(0 if overall_success else 1)

if __name__ == "__main__":
    main()