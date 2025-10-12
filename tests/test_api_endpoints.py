#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات API endpoints
API Endpoints Tests
"""

import unittest
import requests
import sys
import os

# إضافة المسار الجذر للمشروع
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestAPIEndpoints(unittest.TestCase):
    """اختبارات API endpoints"""
    
    def setUp(self):
        """إعداد الاختبار"""
        self.base_url = "http://127.0.0.1:5001"
        self.session = requests.Session()
        self.csrf_token = None
        
    def get_csrf_token(self):
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
    
    def login(self, username, password):
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
    
    def test_reception_endpoints(self):
        """اختبار endpoints الاستقبال"""
        self.login('reception', '123456')
        
        endpoints = [
            '/reception/dashboard',
            '/reception/patients',
            '/reception/visits',
            '/reception/create-visit',
            '/reception/queue'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assertIn(response.status_code, [200, 302], 
                             f"Endpoint {endpoint} should be accessible")
    
    def test_doctor_endpoints(self):
        """اختبار endpoints الطبيب"""
        self.login('dr_ahmed', '123456')
        
        endpoints = [
            '/doctor/dashboard',
            '/doctor/patients',
            '/doctor/visits',
            '/doctor/medical-records',
            '/doctor/prescriptions'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assertIn(response.status_code, [200, 302], 
                             f"Endpoint {endpoint} should be accessible")
    
    def test_emergency_endpoints(self):
        """اختبار endpoints الطوارئ"""
        self.login('emergency_doc', '123456')
        
        endpoints = [
            '/emergency/dashboard',
            '/emergency/cases',
            '/emergency/queue',
            '/emergency/patients',
            '/emergency/reports'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assertIn(response.status_code, [200, 302], 
                             f"Endpoint {endpoint} should be accessible")
    
    def test_lab_endpoints(self):
        """اختبار endpoints المختبر"""
        self.login('lab_tech', '123456')
        
        endpoints = [
            '/lab/dashboard',
            '/lab/requests',
            '/lab/results',
            '/lab/tests',
            '/lab/reports'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assertIn(response.status_code, [200, 302], 
                             f"Endpoint {endpoint} should be accessible")
    
    def test_radiology_endpoints(self):
        """اختبار endpoints الأشعة"""
        self.login('radiology_tech', '123456')
        
        endpoints = [
            '/radiology/dashboard',
            '/radiology/requests',
            '/radiology/reports',
            '/radiology/images',
            '/radiology/tests'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assertIn(response.status_code, [200, 302], 
                             f"Endpoint {endpoint} should be accessible")
    
    def test_nurse_endpoints(self):
        """اختبار endpoints التمريض"""
        self.login('nurse_1', '123456')
        
        endpoints = [
            '/nurse/dashboard',
            '/nurse/patients',
            '/nurse/vitals',
            '/nurse/medications',
            '/nurse/wards'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assertIn(response.status_code, [200, 302], 
                             f"Endpoint {endpoint} should be accessible")
    
    def test_accountant_endpoints(self):
        """اختبار endpoints المحاسب"""
        self.login('accountant', '123456')
        
        endpoints = [
            '/accountant/dashboard',
            '/accountant/payments',
            '/accountant/invoices',
            '/accountant/reports',
            '/accountant/financial'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assertIn(response.status_code, [200, 302], 
                             f"Endpoint {endpoint} should be accessible")
    
    def test_manager_endpoints(self):
        """اختبار endpoints المانجر"""
        self.login('manager', '123456')
        
        endpoints = [
            '/manager/dashboard',
            '/manager/pricing',
            '/manager/reports',
            '/manager/staff',
            '/manager/analytics'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assertIn(response.status_code, [200, 302], 
                             f"Endpoint {endpoint} should be accessible")
    
    def test_super_admin_endpoints(self):
        """اختبار endpoints السوبر أدمن"""
        self.login('super_admin', '123456')
        
        endpoints = [
            '/super-admin/dashboard',
            '/super-admin/users',
            '/super-admin/departments',
            '/super-admin/system',
            '/super-admin/backup'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assertIn(response.status_code, [200, 302], 
                             f"Endpoint {endpoint} should be accessible")

if __name__ == '__main__':
    unittest.main()
