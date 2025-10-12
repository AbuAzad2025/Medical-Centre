#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات التكامل وتدفق العمل
Integration and Workflow Tests
"""

import unittest
import requests
import sys
import os

# إضافة المسار الجذر للمشروع
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestIntegrationWorkflows(unittest.TestCase):
    """اختبارات التكامل وتدفق العمل"""
    
    def setUp(self):
        """إعداد الاختبار"""
        self.base_url = "http://127.0.0.1:5001"
        self.sessions = {}
        self.csrf_tokens = {}
        
    def get_csrf_token(self, unit):
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
    
    def login_unit(self, unit, username, password):
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
    
    def test_patient_flow_integration(self):
        """اختبار تدفق المريض بين الوحدات"""
        # تسجيل دخول الاستقبال
        self.assertTrue(self.login_unit('reception', 'reception', '123456'),
                       "Reception login should succeed")
        
        # تسجيل دخول الطبيب
        self.assertTrue(self.login_unit('doctor', 'dr_ahmed', '123456'),
                       "Doctor login should succeed")
        
        # اختبار وصول الاستقبال لصفحة إنشاء زيارة
        response = self.sessions['reception'].get(f"{self.base_url}/reception/create-visit")
        self.assertIn(response.status_code, [200, 302],
                     "Reception should access create visit page")
        
        # اختبار وصول الطبيب لصفحة المرضى
        response = self.sessions['doctor'].get(f"{self.base_url}/doctor/patients")
        self.assertIn(response.status_code, [200, 302],
                     "Doctor should access patients page")
    
    def test_lab_workflow_integration(self):
        """اختبار تدفق عمل المختبر"""
        # تسجيل دخول الطبيب
        self.assertTrue(self.login_unit('doctor', 'dr_ahmed', '123456'),
                       "Doctor login should succeed")
        
        # تسجيل دخول المختبر
        self.assertTrue(self.login_unit('lab', 'lab_tech', '123456'),
                       "Lab login should succeed")
        
        # اختبار وصول الطبيب لطلب فحوصات
        response = self.sessions['doctor'].get(f"{self.base_url}/doctor/lab-requests")
        self.assertIn(response.status_code, [200, 302],
                     "Doctor should access lab requests page")
        
        # اختبار وصول المختبر لطلبات الفحوصات
        response = self.sessions['lab'].get(f"{self.base_url}/lab/requests")
        self.assertIn(response.status_code, [200, 302],
                     "Lab should access requests page")
    
    def test_radiology_workflow_integration(self):
        """اختبار تدفق عمل الأشعة"""
        # تسجيل دخول الطبيب
        self.assertTrue(self.login_unit('doctor', 'dr_ahmed', '123456'),
                       "Doctor login should succeed")
        
        # تسجيل دخول الأشعة
        self.assertTrue(self.login_unit('radiology', 'radiology_tech', '123456'),
                       "Radiology login should succeed")
        
        # اختبار وصول الطبيب لطلب أشعة
        response = self.sessions['doctor'].get(f"{self.base_url}/doctor/radiology-requests")
        self.assertIn(response.status_code, [200, 302],
                     "Doctor should access radiology requests page")
        
        # اختبار وصول الأشعة لطلبات التصوير
        response = self.sessions['radiology'].get(f"{self.base_url}/radiology/requests")
        self.assertIn(response.status_code, [200, 302],
                     "Radiology should access requests page")
    
    def test_emergency_workflow_integration(self):
        """اختبار تدفق عمل الطوارئ"""
        # تسجيل دخول الطوارئ
        self.assertTrue(self.login_unit('emergency', 'emergency_doc', '123456'),
                       "Emergency login should succeed")
        
        # تسجيل دخول التمريض
        self.assertTrue(self.login_unit('nurse', 'nurse_1', '123456'),
                       "Nurse login should succeed")
        
        # اختبار وصول الطوارئ لحالات الطوارئ
        response = self.sessions['emergency'].get(f"{self.base_url}/emergency/cases")
        self.assertIn(response.status_code, [200, 302],
                     "Emergency should access cases page")
        
        # اختبار وصول التمريض للمرضى
        response = self.sessions['nurse'].get(f"{self.base_url}/nurse/patients")
        self.assertIn(response.status_code, [200, 302],
                     "Nurse should access patients page")
    
    def test_financial_workflow_integration(self):
        """اختبار تدفق العمل المالي"""
        # تسجيل دخول الاستقبال
        self.assertTrue(self.login_unit('reception', 'reception', '123456'),
                       "Reception login should succeed")
        
        # تسجيل دخول المحاسب
        self.assertTrue(self.login_unit('accountant', 'accountant', '123456'),
                       "Accountant login should succeed")
        
        # تسجيل دخول المانجر
        self.assertTrue(self.login_unit('manager', 'manager', '123456'),
                       "Manager login should succeed")
        
        # اختبار وصول الاستقبال للمدفوعات
        response = self.sessions['reception'].get(f"{self.base_url}/reception/payments")
        self.assertIn(response.status_code, [200, 302],
                     "Reception should access payments page")
        
        # اختبار وصول المحاسب للمدفوعات
        response = self.sessions['accountant'].get(f"{self.base_url}/accountant/payments")
        self.assertIn(response.status_code, [200, 302],
                     "Accountant should access payments page")
        
        # اختبار وصول المانجر للتقارير المالية
        response = self.sessions['manager'].get(f"{self.base_url}/manager/financial-reports")
        self.assertIn(response.status_code, [200, 302],
                     "Manager should access financial reports page")
    
    def test_management_workflow_integration(self):
        """اختبار تدفق العمل الإداري"""
        # تسجيل دخول السوبر أدمن
        self.assertTrue(self.login_unit('super_admin', 'super_admin', '123456'),
                       "Super admin login should succeed")
        
        # تسجيل دخول المانجر
        self.assertTrue(self.login_unit('manager', 'manager', '123456'),
                       "Manager login should succeed")
        
        # اختبار وصول السوبر أدمن لإدارة المستخدمين
        response = self.sessions['super_admin'].get(f"{self.base_url}/super-admin/users")
        self.assertIn(response.status_code, [200, 302],
                     "Super admin should access users page")
        
        # اختبار وصول المانجر لإدارة التسعير
        response = self.sessions['manager'].get(f"{self.base_url}/manager/pricing")
        self.assertIn(response.status_code, [200, 302],
                     "Manager should access pricing page")

if __name__ == '__main__':
    unittest.main()
