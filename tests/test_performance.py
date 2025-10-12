#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبارات الأداء
Performance Tests
"""

import unittest
import requests
import time
import sys
import os

# إضافة المسار الجذر للمشروع
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestPerformance(unittest.TestCase):
    """اختبارات الأداء"""
    
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
    
    def test_login_performance(self):
        """اختبار أداء تسجيل الدخول"""
        start_time = time.time()
        
        success = self.login('reception', '123456')
        
        end_time = time.time()
        duration = end_time - start_time
        
        self.assertTrue(success, "Login should succeed")
        self.assertLess(duration, 2.0, f"Login should complete within 2 seconds, took {duration:.2f}s")
    
    def test_dashboard_load_performance(self):
        """اختبار أداء تحميل الداشبورد"""
        self.login('reception', '123456')
        
        start_time = time.time()
        
        response = self.session.get(f"{self.base_url}/reception/dashboard")
        
        end_time = time.time()
        duration = end_time - start_time
        
        self.assertIn(response.status_code, [200, 302], "Dashboard should load successfully")
        self.assertLess(duration, 3.0, f"Dashboard should load within 3 seconds, took {duration:.2f}s")
    
    def test_api_response_time(self):
        """اختبار وقت استجابة API"""
        self.login('reception', '123456')
        
        endpoints = [
            '/reception/patients',
            '/reception/visits',
            '/reception/queue'
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                start_time = time.time()
                
                response = self.session.get(f"{self.base_url}{endpoint}")
                
                end_time = time.time()
                duration = end_time - start_time
                
                self.assertIn(response.status_code, [200, 302], 
                             f"Endpoint {endpoint} should respond successfully")
                self.assertLess(duration, 2.0, 
                               f"Endpoint {endpoint} should respond within 2 seconds, took {duration:.2f}s")
    
    def test_concurrent_logins(self):
        """اختبار تسجيل الدخول المتزامن"""
        import threading
        import queue
        
        results = queue.Queue()
        
        def login_worker(username, password, result_queue):
            """عامل تسجيل الدخول"""
            session = requests.Session()
            
            # الحصول على CSRF token
            try:
                response = session.get(f"{self.base_url}/auth/login")
                if response.status_code == 200:
                    import re
                    csrf_match = re.search(r'name="csrf_token" value="([^"]*)"', response.text)
                    if csrf_match:
                        csrf_token = csrf_match.group(1)
                        
                        login_data = {
                            'username': username,
                            'password': password,
                            'csrf_token': csrf_token
                        }
                        
                        response = session.post(
                            f"{self.base_url}/auth/login",
                            data=login_data,
                            allow_redirects=False
                        )
                        
                        result_queue.put(response.status_code == 302)
                        return
            except:
                pass
            
            result_queue.put(False)
        
        # إنشاء عدة خيوط لتسجيل الدخول
        threads = []
        usernames = ['reception', 'dr_ahmed', 'manager', 'lab_tech', 'accountant']
        
        start_time = time.time()
        
        for username in usernames:
            thread = threading.Thread(target=login_worker, args=(username, '123456', results))
            threads.append(thread)
            thread.start()
        
        # انتظار انتهاء جميع الخيوط
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        duration = end_time - start_time
        
        # جمع النتائج
        success_count = 0
        while not results.empty():
            if results.get():
                success_count += 1
        
        self.assertEqual(success_count, len(usernames), 
                        f"All {len(usernames)} concurrent logins should succeed")
        self.assertLess(duration, 5.0, 
                       f"Concurrent logins should complete within 5 seconds, took {duration:.2f}s")
    
    def test_memory_usage(self):
        """اختبار استخدام الذاكرة"""
        import psutil
        import os
        
        # الحصول على استخدام الذاكرة الحالي
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # تنفيذ عدة طلبات
        self.login('reception', '123456')
        
        for _ in range(10):
            self.session.get(f"{self.base_url}/reception/dashboard")
            self.session.get(f"{self.base_url}/reception/patients")
            self.session.get(f"{self.base_url}/reception/visits")
        
        # الحصول على استخدام الذاكرة بعد الطلبات
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # التحقق من أن الزيادة في الذاكرة معقولة (أقل من 50 MB)
        self.assertLess(memory_increase, 50.0, 
                       f"Memory increase should be less than 50MB, increased by {memory_increase:.2f}MB")

if __name__ == '__main__':
    unittest.main()
