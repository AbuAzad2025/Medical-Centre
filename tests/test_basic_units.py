#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات الوحدات الأساسية
Basic Unit Tests
"""

import unittest
import requests
import sys
import os

# إضافة المسار الجذر للمشروع
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestBasicUnits(unittest.TestCase):
    """اختبارات الوحدات الأساسية"""
    
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
    
    def test_server_connectivity(self):
        """اختبار الاتصال بالخادم"""
        try:
            response = requests.get(f"{self.base_url}/auth/login", timeout=5)
            self.assertEqual(response.status_code, 200, "Server should be accessible")
        except requests.exceptions.RequestException:
            self.fail("Cannot connect to server")
    
    def test_super_admin_login(self):
        """اختبار تسجيل دخول السوبر أدمن"""
        success = self.login('super_admin', '123456')
        self.assertTrue(success, "Super admin login should succeed")
    
    def test_manager_login(self):
        """اختبار تسجيل دخول المانجر"""
        success = self.login('manager', '123456')
        self.assertTrue(success, "Manager login should succeed")
    
    def test_reception_login(self):
        """اختبار تسجيل دخول الاستقبال"""
        success = self.login('reception', '123456')
        self.assertTrue(success, "Reception login should succeed")
    
    def test_doctor_login(self):
        """اختبار تسجيل دخول الطبيب"""
        success = self.login('dr_ahmed', '123456')
        self.assertTrue(success, "Doctor login should succeed")
    
    def test_emergency_login(self):
        """اختبار تسجيل دخول الطوارئ"""
        success = self.login('emergency_doc', '123456')
        self.assertTrue(success, "Emergency login should succeed")
    
    def test_lab_login(self):
        """اختبار تسجيل دخول المختبر"""
        success = self.login('lab_tech', '123456')
        self.assertTrue(success, "Lab login should succeed")
    
    def test_radiology_login(self):
        """اختبار تسجيل دخول الأشعة"""
        success = self.login('radiology_tech', '123456')
        self.assertTrue(success, "Radiology login should succeed")
    
    def test_nurse_login(self):
        """اختبار تسجيل دخول التمريض"""
        success = self.login('nurse_1', '123456')
        self.assertTrue(success, "Nurse login should succeed")
    
    def test_accountant_login(self):
        """اختبار تسجيل دخول المحاسب"""
        success = self.login('accountant', '123456')
        self.assertTrue(success, "Accountant login should succeed")

if __name__ == '__main__':
    unittest.main()
