#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات التكامل بين الوحدات
Integration Tests between Units
"""

import requests
import json
import time
from datetime import datetime, date
from typing import Dict, List, Any

class IntegrationTester:
    """فئة اختبار التكامل بين الوحدات"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:5001"):
        self.base_url = base_url
        self.sessions = {}  # جلسات منفصلة لكل وحدة
        self.csrf_tokens = {}
        
    def get_csrf_token(self, unit: str) -> bool:
        """الحصول على CSRF token لوحدة معينة"""
        try:
            if unit not in self.sessions:
                self.sessions[unit] = requests.Session()
            
            response = self.sessions[unit].get(f"{self.base_url}/auth/login")
            if response.status_code == 200:
                import re
                csrf_match = re.search(r'name="csrf_token" value="([^"]*)"', response.text)
                if csrf_match:
                    self.csrf_tokens[unit] = csrf_match.group(1)
                    return True
            return False
        except:
            return False
    
    def login_unit(self, unit: str, username: str, password: str) -> bool:
        """تسجيل دخول وحدة معينة"""
        try:
            if not self.get_csrf_token(unit):
                return False
                
            login_data = {
                'username': username,
                'password': password,
                'csrf_token': self.csrf_tokens[unit]
            }
            
            response = self.sessions[unit].post(
                f"{self.base_url}/auth/login",
                data=login_data,
                allow_redirects=False
            )
            
            return response.status_code == 302
        except:
            return False
    
    def test_patient_flow_integration(self) -> Dict[str, Any]:
        """اختبار تدفق المريض بين الوحدات"""
        print("🔄 Testing Patient Flow Integration...")
        results = {
            'test_name': 'Patient Flow Integration',
            'steps': [],
            'passed': 0,
            'total': 0
        }
        
        # 1. تسجيل دخول الاستقبال
        if self.login_unit('reception', 'reception', '123456'):
            results['steps'].append({'step': 'Reception Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Reception Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 2. تسجيل دخول الطبيب
        if self.login_unit('doctor', 'dr_ahmed', '123456'):
            results['steps'].append({'step': 'Doctor Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Doctor Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 3. اختبار وصول الاستقبال لصفحة إنشاء زيارة
        try:
            response = self.sessions['reception'].get(f"{self.base_url}/reception/create-visit")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Reception Create Visit Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Reception Create Visit Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Reception Create Visit Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # 4. اختبار وصول الطبيب لصفحة المرضى
        try:
            response = self.sessions['doctor'].get(f"{self.base_url}/doctor/patients")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Doctor Patients Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Doctor Patients Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Doctor Patients Access', 'status': 'FAILED'})
        results['total'] += 1
        
        return results
    
    def test_lab_workflow_integration(self) -> Dict[str, Any]:
        """اختبار تدفق عمل المختبر"""
        print("🧪 Testing Lab Workflow Integration...")
        results = {
            'test_name': 'Lab Workflow Integration',
            'steps': [],
            'passed': 0,
            'total': 0
        }
        
        # 1. تسجيل دخول الطبيب
        if self.login_unit('doctor', 'dr_ahmed', '123456'):
            results['steps'].append({'step': 'Doctor Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Doctor Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 2. تسجيل دخول المختبر
        if self.login_unit('lab', 'lab_tech', '123456'):
            results['steps'].append({'step': 'Lab Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Lab Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 3. اختبار وصول الطبيب لطلب فحوصات
        try:
            response = self.sessions['doctor'].get(f"{self.base_url}/doctor/lab-requests")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Doctor Lab Requests Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Doctor Lab Requests Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Doctor Lab Requests Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # 4. اختبار وصول المختبر لطلبات الفحوصات
        try:
            response = self.sessions['lab'].get(f"{self.base_url}/lab/requests")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Lab Requests Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Lab Requests Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Lab Requests Access', 'status': 'FAILED'})
        results['total'] += 1
        
        return results
    
    def test_radiology_workflow_integration(self) -> Dict[str, Any]:
        """اختبار تدفق عمل الأشعة"""
        print("📷 Testing Radiology Workflow Integration...")
        results = {
            'test_name': 'Radiology Workflow Integration',
            'steps': [],
            'passed': 0,
            'total': 0
        }
        
        # 1. تسجيل دخول الطبيب
        if self.login_unit('doctor', 'dr_ahmed', '123456'):
            results['steps'].append({'step': 'Doctor Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Doctor Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 2. تسجيل دخول الأشعة
        if self.login_unit('radiology', 'radiology_tech', '123456'):
            results['steps'].append({'step': 'Radiology Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Radiology Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 3. اختبار وصول الطبيب لطلب أشعة
        try:
            response = self.sessions['doctor'].get(f"{self.base_url}/doctor/radiology-requests")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Doctor Radiology Requests Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Doctor Radiology Requests Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Doctor Radiology Requests Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # 4. اختبار وصول الأشعة لطلبات التصوير
        try:
            response = self.sessions['radiology'].get(f"{self.base_url}/radiology/requests")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Radiology Requests Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Radiology Requests Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Radiology Requests Access', 'status': 'FAILED'})
        results['total'] += 1
        
        return results
    
    def test_emergency_workflow_integration(self) -> Dict[str, Any]:
        """اختبار تدفق عمل الطوارئ"""
        print("🚨 Testing Emergency Workflow Integration...")
        results = {
            'test_name': 'Emergency Workflow Integration',
            'steps': [],
            'passed': 0,
            'total': 0
        }
        
        # 1. تسجيل دخول الطوارئ
        if self.login_unit('emergency', 'emergency_doc', '123456'):
            results['steps'].append({'step': 'Emergency Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Emergency Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 2. تسجيل دخول التمريض
        if self.login_unit('nurse', 'nurse_1', '123456'):
            results['steps'].append({'step': 'Nurse Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Nurse Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 3. اختبار وصول الطوارئ لحالات الطوارئ
        try:
            response = self.sessions['emergency'].get(f"{self.base_url}/emergency/cases")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Emergency Cases Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Emergency Cases Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Emergency Cases Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # 4. اختبار وصول التمريض للمرضى
        try:
            response = self.sessions['nurse'].get(f"{self.base_url}/nurse/patients")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Nurse Patients Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Nurse Patients Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Nurse Patients Access', 'status': 'FAILED'})
        results['total'] += 1
        
        return results
    
    def test_financial_workflow_integration(self) -> Dict[str, Any]:
        """اختبار تدفق العمل المالي"""
        print("💰 Testing Financial Workflow Integration...")
        results = {
            'test_name': 'Financial Workflow Integration',
            'steps': [],
            'passed': 0,
            'total': 0
        }
        
        # 1. تسجيل دخول الاستقبال
        if self.login_unit('reception', 'reception', '123456'):
            results['steps'].append({'step': 'Reception Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Reception Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 2. تسجيل دخول المحاسب
        if self.login_unit('accountant', 'accountant', '123456'):
            results['steps'].append({'step': 'Accountant Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Accountant Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 3. تسجيل دخول المانجر
        if self.login_unit('manager', 'manager', '123456'):
            results['steps'].append({'step': 'Manager Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Manager Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 4. اختبار وصول الاستقبال للمدفوعات
        try:
            response = self.sessions['reception'].get(f"{self.base_url}/reception/payments")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Reception Payments Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Reception Payments Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Reception Payments Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # 5. اختبار وصول المحاسب للمدفوعات
        try:
            response = self.sessions['accountant'].get(f"{self.base_url}/accountant/payments")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Accountant Payments Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Accountant Payments Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Accountant Payments Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # 6. اختبار وصول المانجر للتقارير المالية
        try:
            response = self.sessions['manager'].get(f"{self.base_url}/manager/financial-reports")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Manager Financial Reports Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Manager Financial Reports Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Manager Financial Reports Access', 'status': 'FAILED'})
        results['total'] += 1
        
        return results
    
    def test_management_workflow_integration(self) -> Dict[str, Any]:
        """اختبار تدفق العمل الإداري"""
        print("👔 Testing Management Workflow Integration...")
        results = {
            'test_name': 'Management Workflow Integration',
            'steps': [],
            'passed': 0,
            'total': 0
        }
        
        # 1. تسجيل دخول السوبر أدمن
        if self.login_unit('super_admin', 'super_admin', '123456'):
            results['steps'].append({'step': 'Super Admin Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Super Admin Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 2. تسجيل دخول المانجر
        if self.login_unit('manager', 'manager', '123456'):
            results['steps'].append({'step': 'Manager Login', 'status': 'PASSED'})
            results['passed'] += 1
        else:
            results['steps'].append({'step': 'Manager Login', 'status': 'FAILED'})
        results['total'] += 1
        
        # 3. اختبار وصول السوبر أدمن لإدارة المستخدمين
        try:
            response = self.sessions['super_admin'].get(f"{self.base_url}/super-admin/users")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Super Admin Users Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Super Admin Users Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Super Admin Users Access', 'status': 'FAILED'})
        results['total'] += 1
        
        # 4. اختبار وصول المانجر لإدارة التسعير
        try:
            response = self.sessions['manager'].get(f"{self.base_url}/manager/pricing")
            if response.status_code in [200, 302]:
                results['steps'].append({'step': 'Manager Pricing Access', 'status': 'PASSED'})
                results['passed'] += 1
            else:
                results['steps'].append({'step': 'Manager Pricing Access', 'status': 'FAILED'})
        except:
            results['steps'].append({'step': 'Manager Pricing Access', 'status': 'FAILED'})
        results['total'] += 1
        
        return results
    
    def run_all_integration_tests(self) -> List[Dict[str, Any]]:
        """تشغيل جميع اختبارات التكامل"""
        print("🚀 Starting Integration Tests...")
        print("=" * 60)
        
        integration_tests = [
            self.test_patient_flow_integration,
            self.test_lab_workflow_integration,
            self.test_radiology_workflow_integration,
            self.test_emergency_workflow_integration,
            self.test_financial_workflow_integration,
            self.test_management_workflow_integration
        ]
        
        all_results = []
        for test_func in integration_tests:
            try:
                result = test_func()
                all_results.append(result)
                print(f"📊 {result['test_name']}: {result['passed']}/{result['total']} steps passed")
            except Exception as e:
                print(f"❌ Error in {test_func.__name__}: {e}")
                all_results.append({
                    'test_name': test_func.__name__.replace('test_', '').replace('_integration', ''),
                    'steps': [],
                    'passed': 0,
                    'total': 0,
                    'error': str(e)
                })
        
        return all_results
    
    def generate_integration_report(self, results: List[Dict[str, Any]]):
        """توليد تقرير التكامل"""
        print("\n" + "=" * 60)
        print("📋 INTEGRATION TEST REPORT")
        print("=" * 60)
        
        total_steps = 0
        total_passed = 0
        
        for result in results:
            test_name = result['test_name']
            passed = result['passed']
            total = result['total']
            
            total_steps += total
            total_passed += passed
            
            status = "✅ PASSED" if passed == total else "❌ FAILED"
            print(f"{test_name:30} | {passed:2}/{total:2} | {status}")
            
            # عرض تفاصيل الخطوات الفاشلة
            if passed < total:
                for step in result['steps']:
                    if step['status'] == 'FAILED':
                        print(f"  └─ ❌ {step['step']}")
        
        print("-" * 60)
        print(f"TOTAL: {total_passed}/{total_steps} integration steps passed")
        print(f"Success Rate: {(total_passed/total_steps*100):.1f}%")
        
        overall_success = total_passed == total_steps
        print(f"\n🎯 INTEGRATION RESULT: {'✅ ALL INTEGRATIONS PASSED' if overall_success else '❌ SOME INTEGRATIONS FAILED'}")
        
        return overall_success

def main():
    """الدالة الرئيسية"""
    print("🏥 Medical System Integration Testing")
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
    
    # تشغيل اختبارات التكامل
    tester = IntegrationTester()
    results = tester.run_all_integration_tests()
    success = tester.generate_integration_report(results)
    
    return success

if __name__ == "__main__":
    main()
