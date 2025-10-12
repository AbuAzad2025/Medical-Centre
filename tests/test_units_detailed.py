#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات مفصلة لكل وحدة في النظام الصحي
Detailed Unit Tests for Medical System
"""

import requests
import json
import time
from datetime import datetime, date
from typing import Dict, List, Any

class UnitTester:
    """فئة اختبار الوحدات المفصلة"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:5001"):
        self.base_url = base_url
        self.session = requests.Session()
        self.csrf_token = None
        
    def get_csrf_token(self) -> bool:
        """الحصول على CSRF token"""
        try:
            response = self.session.get(f"{self.base_url}/auth/login")
            if response.status_code == 200:
                import re
                csrf_match = re.search(r'name="csrf_token" value="([^"]*)"', response.text)
                if csrf_match:
                    self.csrf_token = csrf_match.group(1)
                    return True
            return False
        except:
            return False
    
    def login(self, username: str, password: str) -> bool:
        """تسجيل الدخول"""
        try:
            if not self.get_csrf_token():
                return False
                
            login_data = {
                'username': username,
                'password': password,
                'csrf_token': self.csrf_token
            }
            
            response = self.session.post(
                f"{self.base_url}/auth/login",
                data=login_data,
                allow_redirects=False
            )
            
            return response.status_code == 302
        except:
            return False
    
    def test_reception_unit(self) -> Dict[str, Any]:
        """اختبار وحدة الاستقبال"""
        print("🏥 Testing Reception Unit...")
        results = {'unit': 'Reception', 'tests': [], 'passed': 0, 'total': 0}
        
        # تسجيل الدخول
        if self.login('reception', '123456'):
            results['tests'].append({'test': 'Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['tests'].append({'test': 'Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار الداشبورد
        try:
            response = self.session.get(f"{self.base_url}/reception/dashboard")
            if response.status_code == 200:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        except:
            results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار API endpoints
        api_tests = [
            '/reception/patients',
            '/reception/visits',
            '/reception/create-visit',
            '/reception/queue'
        ]
        
        for endpoint in api_tests:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                if response.status_code in [200, 302]:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'PASSED'})
                    results['passed'] += 1
                else:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            except:
                results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            results['total'] += 1
        
        return results
    
    def test_doctor_unit(self) -> Dict[str, Any]:
        """اختبار وحدة الطبيب"""
        print("👨‍⚕️ Testing Doctor Unit...")
        results = {'unit': 'Doctor', 'tests': [], 'passed': 0, 'total': 0}
        
        # تسجيل الدخول
        if self.login('dr_ahmed', '123456'):
            results['tests'].append({'test': 'Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['tests'].append({'test': 'Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار الداشبورد
        try:
            response = self.session.get(f"{self.base_url}/doctor/dashboard")
            if response.status_code == 200:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        except:
            results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار API endpoints
        api_tests = [
            '/doctor/patients',
            '/doctor/visits',
            '/doctor/medical-records',
            '/doctor/prescriptions'
        ]
        
        for endpoint in api_tests:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                if response.status_code in [200, 302]:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'PASSED'})
                    results['passed'] += 1
                else:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            except:
                results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            results['total'] += 1
        
        return results
    
    def test_emergency_unit(self) -> Dict[str, Any]:
        """اختبار وحدة الطوارئ"""
        print("🚨 Testing Emergency Unit...")
        results = {'unit': 'Emergency', 'tests': [], 'passed': 0, 'total': 0}
        
        # تسجيل الدخول
        if self.login('emergency_doc', '123456'):
            results['tests'].append({'test': 'Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['tests'].append({'test': 'Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار الداشبورد
        try:
            response = self.session.get(f"{self.base_url}/emergency/dashboard")
            if response.status_code == 200:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        except:
            results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار API endpoints
        api_tests = [
            '/emergency/cases',
            '/emergency/queue',
            '/emergency/patients',
            '/emergency/reports'
        ]
        
        for endpoint in api_tests:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                if response.status_code in [200, 302]:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'PASSED'})
                    results['passed'] += 1
                else:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            except:
                results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            results['total'] += 1
        
        return results
    
    def test_lab_unit(self) -> Dict[str, Any]:
        """اختبار وحدة المختبر"""
        print("🧪 Testing Lab Unit...")
        results = {'unit': 'Lab', 'tests': [], 'passed': 0, 'total': 0}
        
        # تسجيل الدخول
        if self.login('lab_tech', '123456'):
            results['tests'].append({'test': 'Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['tests'].append({'test': 'Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار الداشبورد
        try:
            response = self.session.get(f"{self.base_url}/lab/dashboard")
            if response.status_code == 200:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        except:
            results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار API endpoints
        api_tests = [
            '/lab/requests',
            '/lab/results',
            '/lab/tests',
            '/lab/reports'
        ]
        
        for endpoint in api_tests:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                if response.status_code in [200, 302]:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'PASSED'})
                    results['passed'] += 1
                else:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            except:
                results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            results['total'] += 1
        
        return results
    
    def test_radiology_unit(self) -> Dict[str, Any]:
        """اختبار وحدة الأشعة"""
        print("📷 Testing Radiology Unit...")
        results = {'unit': 'Radiology', 'tests': [], 'passed': 0, 'total': 0}
        
        # تسجيل الدخول
        if self.login('radiology_tech', '123456'):
            results['tests'].append({'test': 'Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['tests'].append({'test': 'Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار الداشبورد
        try:
            response = self.session.get(f"{self.base_url}/radiology/dashboard")
            if response.status_code == 200:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        except:
            results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار API endpoints
        api_tests = [
            '/radiology/requests',
            '/radiology/reports',
            '/radiology/images',
            '/radiology/tests'
        ]
        
        for endpoint in api_tests:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                if response.status_code in [200, 302]:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'PASSED'})
                    results['passed'] += 1
                else:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            except:
                results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            results['total'] += 1
        
        return results
    
    def test_nurse_unit(self) -> Dict[str, Any]:
        """اختبار وحدة التمريض"""
        print("👩‍⚕️ Testing Nurse Unit...")
        results = {'unit': 'Nurse', 'tests': [], 'passed': 0, 'total': 0}
        
        # تسجيل الدخول
        if self.login('nurse_1', '123456'):
            results['tests'].append({'test': 'Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['tests'].append({'test': 'Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار الداشبورد
        try:
            response = self.session.get(f"{self.base_url}/nurse/dashboard")
            if response.status_code == 200:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        except:
            results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار API endpoints
        api_tests = [
            '/nurse/patients',
            '/nurse/vitals',
            '/nurse/medications',
            '/nurse/wards'
        ]
        
        for endpoint in api_tests:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                if response.status_code in [200, 302]:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'PASSED'})
                    results['passed'] += 1
                else:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            except:
                results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            results['total'] += 1
        
        return results
    
    def test_accountant_unit(self) -> Dict[str, Any]:
        """اختبار وحدة المحاسب"""
        print("💰 Testing Accountant Unit...")
        results = {'unit': 'Accountant', 'tests': [], 'passed': 0, 'total': 0}
        
        # تسجيل الدخول
        if self.login('accountant', '123456'):
            results['tests'].append({'test': 'Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['tests'].append({'test': 'Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار الداشبورد
        try:
            response = self.session.get(f"{self.base_url}/accountant/dashboard")
            if response.status_code == 200:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        except:
            results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار API endpoints
        api_tests = [
            '/accountant/payments',
            '/accountant/invoices',
            '/accountant/reports',
            '/accountant/financial'
        ]
        
        for endpoint in api_tests:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                if response.status_code in [200, 302]:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'PASSED'})
                    results['passed'] += 1
                else:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            except:
                results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            results['total'] += 1
        
        return results
    
    def test_manager_unit(self) -> Dict[str, Any]:
        """اختبار وحدة المانجر"""
        print("👔 Testing Manager Unit...")
        results = {'unit': 'Manager', 'tests': [], 'passed': 0, 'total': 0}
        
        # تسجيل الدخول
        if self.login('manager', '123456'):
            results['tests'].append({'test': 'Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['tests'].append({'test': 'Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار الداشبورد
        try:
            response = self.session.get(f"{self.base_url}/manager/dashboard")
            if response.status_code == 200:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        except:
            results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار API endpoints
        api_tests = [
            '/manager/pricing',
            '/manager/reports',
            '/manager/staff',
            '/manager/analytics'
        ]
        
        for endpoint in api_tests:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                if response.status_code in [200, 302]:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'PASSED'})
                    results['passed'] += 1
                else:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            except:
                results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            results['total'] += 1
        
        return results
    
    def test_super_admin_unit(self) -> Dict[str, Any]:
        """اختبار وحدة السوبر أدمن"""
        print("👑 Testing Super Admin Unit...")
        results = {'unit': 'Super Admin', 'tests': [], 'passed': 0, 'total': 0}
        
        # تسجيل الدخول
        if self.login('super_admin', '123456'):
            results['tests'].append({'test': 'Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['tests'].append({'test': 'Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار الداشبورد
        try:
            response = self.session.get(f"{self.base_url}/super-admin/dashboard")
            if response.status_code == 200:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        except:
            results['tests'].append({'test': 'Dashboard Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # اختبار API endpoints
        api_tests = [
            '/super-admin/users',
            '/super-admin/departments',
            '/super-admin/system',
            '/super-admin/backup'
        ]
        
        for endpoint in api_tests:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                if response.status_code in [200, 302]:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'PASSED'})
                    results['passed'] += 1
                else:
                    results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            except:
                results['tests'].append({'test': f'API {endpoint}', 'status': 'FAILED'})
            results['total'] += 1
        
        return results
    
    def run_all_unit_tests(self) -> List[Dict[str, Any]]:
        """تشغيل جميع اختبارات الوحدات"""
        print("🚀 Starting Detailed Unit Tests...")
        print("=" * 60)
        
        all_results = []
        
        # اختبار جميع الوحدات
        unit_tests = [
            self.test_super_admin_unit,
            self.test_manager_unit,
            self.test_reception_unit,
            self.test_doctor_unit,
            self.test_emergency_unit,
            self.test_lab_unit,
            self.test_radiology_unit,
            self.test_nurse_unit,
            self.test_accountant_unit
        ]
        
        for test_func in unit_tests:
            try:
                result = test_func()
                all_results.append(result)
                print(f"📊 {result['unit']}: {result['passed']}/{result['total']} tests passed")
            except Exception as e:
                print(f"❌ Error testing unit: {e}")
                all_results.append({
                    'unit': test_func.__name__.replace('test_', '').replace('_unit', ''),
                    'tests': [],
                    'passed': 0,
                    'total': 0,
                    'error': str(e)
                })
        
        return all_results
    
    def generate_report(self, results: List[Dict[str, Any]]):
        """توليد تقرير النتائج"""
        print("\n" + "=" * 60)
        print("📋 DETAILED UNIT TEST REPORT")
        print("=" * 60)
        
        total_tests = 0
        total_passed = 0
        
        for result in results:
            unit = result['unit']
            passed = result['passed']
            total = result['total']
            
            total_tests += total
            total_passed += passed
            
            status = "✅ PASSED" if passed == total else "❌ FAILED"
            print(f"{unit:15} | {passed:2}/{total:2} | {status}")
            
            # عرض تفاصيل الاختبارات الفاشلة
            if passed < total:
                for test in result['tests']:
                    if test['status'] == 'FAILED':
                        print(f"  └─ ❌ {test['test']}")
        
        print("-" * 60)
        print(f"TOTAL: {total_passed}/{total_tests} tests passed")
        print(f"Success Rate: {(total_passed/total_tests*100):.1f}%")
        
        overall_success = total_passed == total_tests
        print(f"\n🎯 OVERALL RESULT: {'✅ ALL UNITS PASSED' if overall_success else '❌ SOME UNITS FAILED'}")
        
        return overall_success

def main():
    """الدالة الرئيسية"""
    print("🏥 Medical System Detailed Unit Testing")
    print("=" * 60)
    
    # التحقق من أن الخادم يعمل
    try:
        response = requests.get("http://127.0.0.1:5001/auth/login", timeout=5)
        if response.status_code != 200:
            print("❌ Server is not running or not accessible")
            return False
    except requests.exceptions.RequestException:
        print("❌ Cannot connect to server. Please start the Flask application first.")
        return False
    
    # تشغيل الاختبارات
    tester = UnitTester()
    results = tester.run_all_unit_tests()
    success = tester.generate_report(results)
    
    return success

if __name__ == "__main__":
    main()
