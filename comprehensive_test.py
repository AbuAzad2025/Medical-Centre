"""
اختبار شامل لجميع وحدات النظام الصحي
Comprehensive Testing for Medical System
"""
import requests
from bs4 import BeautifulSoup
import json
from colorama import init, Fore, Style
import time

init(autoreset=True)

BASE_URL = "http://127.0.0.1:5001"
session = requests.Session()

def print_header(text):
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{text:^60}")
    print(f"{Fore.CYAN}{'='*60}\n")

def print_success(text):
    print(f"{Fore.GREEN}✅ {text}")

def print_error(text):
    print(f"{Fore.RED}❌ {text}")

def print_info(text):
    print(f"{Fore.YELLOW}ℹ️  {text}")

def login():
    """تسجيل الدخول"""
    print_header("تسجيل الدخول")
    
    # الحصول على CSRF token
    response = session.get(f"{BASE_URL}/auth/login")
    soup = BeautifulSoup(response.text, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrf_token'})['value']
    
    # تسجيل الدخول
    login_data = {
        'username': 'admin',
        'password': 'admin123',
        'csrf_token': csrf_token
    }
    
    response = session.post(f"{BASE_URL}/auth/login", data=login_data, allow_redirects=False)
    
    if response.status_code == 302:
        print_success("تم تسجيل الدخول بنجاح")
        return True
    else:
        print_error("فشل تسجيل الدخول")
        return False

def test_super_admin_routes():
    """اختبار مسارات السوبر أدمن"""
    print_header("اختبار وحدة السوبر أدمن")
    
    routes = [
        ('/super-admin/dashboard', 'لوحة التحكم'),
        ('/super-admin/users', 'إدارة المستخدمين'),
        ('/super-admin/analytics', 'التحليلات'),
        ('/super-admin/system-config', 'إعدادات النظام'),
        ('/super-admin/system-backup', 'النسخ الاحتياطي'),
        ('/super-admin/roles', 'إدارة الأدوار'),
    ]
    
    passed = 0
    failed = 0
    
    for route, name in routes:
        try:
            response = session.get(f"{BASE_URL}{route}")
            if response.status_code == 200:
                print_success(f"{name}: {route}")
                passed += 1
            else:
                print_error(f"{name}: {route} (Status: {response.status_code})")
                failed += 1
        except Exception as e:
            print_error(f"{name}: {route} (Error: {str(e)})")
            failed += 1
    
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def test_user_management():
    """اختبار إدارة المستخدمين"""
    print_header("اختبار إدارة المستخدمين")
    
    tests = []
    
    # اختبار عرض صفحة المستخدمين
    response = session.get(f"{BASE_URL}/super-admin/users")
    if response.status_code == 200:
        print_success("عرض صفحة المستخدمين")
        tests.append(True)
    else:
        print_error("عرض صفحة المستخدمين")
        tests.append(False)
    
    # اختبار صفحة إنشاء مستخدم
    response = session.get(f"{BASE_URL}/super-admin/users/create")
    if response.status_code == 200:
        print_success("صفحة إنشاء مستخدم")
        tests.append(True)
    else:
        print_error("صفحة إنشاء مستخدم")
        tests.append(False)
    
    # اختبار صفحة تعديل مستخدم
    response = session.get(f"{BASE_URL}/super-admin/users/3/edit")
    if response.status_code == 200:
        print_success("صفحة تعديل مستخدم")
        tests.append(True)
    else:
        print_error(f"صفحة تعديل مستخدم (Status: {response.status_code})")
        tests.append(False)
    
    passed = sum(tests)
    failed = len(tests) - passed
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def test_manager_routes():
    """اختبار مسارات المدير"""
    print_header("اختبار وحدة المدير")
    
    routes = [
        ('/manager/dashboard', 'لوحة التحكم'),
        ('/manager/reports', 'التقارير'),
        ('/manager/pricing', 'التسعير'),
        ('/manager/departments', 'الأقسام'),
    ]
    
    passed = 0
    failed = 0
    
    for route, name in routes:
        try:
            response = session.get(f"{BASE_URL}{route}")
            if response.status_code in [200, 302, 403]:  # 403 لأن المستخدم super_admin
                print_success(f"{name}: {route}")
                passed += 1
            else:
                print_error(f"{name}: {route} (Status: {response.status_code})")
                failed += 1
        except Exception as e:
            print_error(f"{name}: {route} (Error: {str(e)})")
            failed += 1
    
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def test_reception_routes():
    """اختبار مسارات الاستقبال"""
    print_header("اختبار وحدة الاستقبال")
    
    routes = [
        ('/reception/dashboard', 'لوحة التحكم'),
        ('/reception/patients', 'المرضى'),
        ('/reception/visits', 'الزيارات'),
        ('/reception/visits/create', 'إنشاء زيارة'),
        ('/reception/queue', 'الطابور'),
    ]
    
    passed = 0
    failed = 0
    
    for route, name in routes:
        try:
            response = session.get(f"{BASE_URL}{route}")
            if response.status_code in [200, 302, 403]:
                print_success(f"{name}: {route}")
                passed += 1
            else:
                print_error(f"{name}: {route} (Status: {response.status_code})")
                failed += 1
        except Exception as e:
            print_error(f"{name}: {route} (Error: {str(e)})")
            failed += 1
    
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def test_doctor_routes():
    """اختبار مسارات الطبيب"""
    print_header("اختبار وحدة الطبيب")
    
    routes = [
        ('/doctor/dashboard', 'لوحة التحكم'),
        ('/doctor/patients', 'المرضى'),
        ('/doctor/appointments', 'المواعيد'),
        ('/doctor/prescriptions', 'الروشتات'),
    ]
    
    passed = 0
    failed = 0
    
    for route, name in routes:
        try:
            response = session.get(f"{BASE_URL}{route}")
            if response.status_code in [200, 302, 403]:
                print_success(f"{name}: {route}")
                passed += 1
            else:
                print_error(f"{name}: {route} (Status: {response.status_code})")
                failed += 1
        except Exception as e:
            print_error(f"{name}: {route} (Error: {str(e)})")
            failed += 1
    
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def test_emergency_routes():
    """اختبار مسارات الطوارئ"""
    print_header("اختبار وحدة الطوارئ")
    
    routes = [
        ('/emergency/dashboard', 'لوحة التحكم'),
        ('/emergency/cases', 'الحالات'),
        ('/emergency/triage', 'الفرز'),
    ]
    
    passed = 0
    failed = 0
    
    for route, name in routes:
        try:
            response = session.get(f"{BASE_URL}{route}")
            if response.status_code in [200, 302, 403]:
                print_success(f"{name}: {route}")
                passed += 1
            else:
                print_error(f"{name}: {route} (Status: {response.status_code})")
                failed += 1
        except Exception as e:
            print_error(f"{name}: {route} (Error: {str(e)})")
            failed += 1
    
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def test_lab_routes():
    """اختبار مسارات المختبر"""
    print_header("اختبار وحدة المختبر")
    
    routes = [
        ('/lab/dashboard', 'لوحة التحكم'),
        ('/lab/requests', 'الطلبات'),
        ('/lab/results', 'النتائج'),
    ]
    
    passed = 0
    failed = 0
    
    for route, name in routes:
        try:
            response = session.get(f"{BASE_URL}{route}")
            if response.status_code in [200, 302, 403]:
                print_success(f"{name}: {route}")
                passed += 1
            else:
                print_error(f"{name}: {route} (Status: {response.status_code})")
                failed += 1
        except Exception as e:
            print_error(f"{name}: {route} (Error: {str(e)})")
            failed += 1
    
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def test_radiology_routes():
    """اختبار مسارات الأشعة"""
    print_header("اختبار وحدة الأشعة")
    
    routes = [
        ('/radiology/dashboard', 'لوحة التحكم'),
        ('/radiology/requests', 'الطلبات'),
        ('/radiology/results', 'النتائج'),
    ]
    
    passed = 0
    failed = 0
    
    for route, name in routes:
        try:
            response = session.get(f"{BASE_URL}{route}")
            if response.status_code in [200, 302, 403]:
                print_success(f"{name}: {route}")
                passed += 1
            else:
                print_error(f"{name}: {route} (Status: {response.status_code})")
                failed += 1
        except Exception as e:
            print_error(f"{name}: {route} (Error: {str(e)})")
            failed += 1
    
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def test_accountant_routes():
    """اختبار مسارات المحاسب"""
    print_header("اختبار وحدة المحاسب")
    
    routes = [
        ('/accountant/dashboard', 'لوحة التحكم'),
        ('/accountant/payments', 'المدفوعات'),
        ('/accountant/invoices', 'الفواتير'),
        ('/accountant/reports', 'التقارير'),
    ]
    
    passed = 0
    failed = 0
    
    for route, name in routes:
        try:
            response = session.get(f"{BASE_URL}{route}")
            if response.status_code in [200, 302, 403]:
                print_success(f"{name}: {route}")
                passed += 1
            else:
                print_error(f"{name}: {route} (Status: {response.status_code})")
                failed += 1
        except Exception as e:
            print_error(f"{name}: {route} (Error: {str(e)})")
            failed += 1
    
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def test_nurse_routes():
    """اختبار مسارات التمريض"""
    print_header("اختبار وحدة التمريض")
    
    routes = [
        ('/nurse/dashboard', 'لوحة التحكم'),
        ('/nurse/tasks', 'المهام'),
        ('/nurse/patients', 'المرضى'),
    ]
    
    passed = 0
    failed = 0
    
    for route, name in routes:
        try:
            response = session.get(f"{BASE_URL}{route}")
            if response.status_code in [200, 302, 403]:
                print_success(f"{name}: {route}")
                passed += 1
            else:
                print_error(f"{name}: {route} (Status: {response.status_code})")
                failed += 1
        except Exception as e:
            print_error(f"{name}: {route} (Error: {str(e)})")
            failed += 1
    
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def test_medication_routes():
    """اختبار مسارات الصيدلية"""
    print_header("اختبار وحدة الصيدلية")
    
    routes = [
        ('/medication/dashboard', 'لوحة التحكم'),
        ('/medication/list', 'قائمة الأدوية'),
        ('/medication/prescriptions', 'الروشتات'),
    ]
    
    passed = 0
    failed = 0
    
    for route, name in routes:
        try:
            response = session.get(f"{BASE_URL}{route}")
            if response.status_code in [200, 302, 403]:
                print_success(f"{name}: {route}")
                passed += 1
            else:
                print_error(f"{name}: {route} (Status: {response.status_code})")
                failed += 1
        except Exception as e:
            print_error(f"{name}: {route} (Error: {str(e)})")
            failed += 1
    
    print_info(f"النتيجة: {passed} نجح، {failed} فشل")
    return passed, failed

def main():
    """الدالة الرئيسية"""
    print(f"\n{Fore.MAGENTA}{'='*60}")
    print(f"{Fore.MAGENTA}{'اختبار شامل للنظام الصحي المتكامل':^60}")
    print(f"{Fore.MAGENTA}{'Comprehensive Medical System Testing':^60}")
    print(f"{Fore.MAGENTA}{'='*60}\n")
    
    # تسجيل الدخول
    if not login():
        print_error("فشل تسجيل الدخول. إنهاء الاختبار.")
        return
    
    time.sleep(1)
    
    # اختبار جميع الوحدات
    total_passed = 0
    total_failed = 0
    
    results = []
    
    # السوبر أدمن
    passed, failed = test_super_admin_routes()
    total_passed += passed
    total_failed += failed
    results.append(('السوبر أدمن', passed, failed))
    time.sleep(0.5)
    
    # إدارة المستخدمين
    passed, failed = test_user_management()
    total_passed += passed
    total_failed += failed
    results.append(('إدارة المستخدمين', passed, failed))
    time.sleep(0.5)
    
    # المدير
    passed, failed = test_manager_routes()
    total_passed += passed
    total_failed += failed
    results.append(('المدير', passed, failed))
    time.sleep(0.5)
    
    # الاستقبال
    passed, failed = test_reception_routes()
    total_passed += passed
    total_failed += failed
    results.append(('الاستقبال', passed, failed))
    time.sleep(0.5)
    
    # الطبيب
    passed, failed = test_doctor_routes()
    total_passed += passed
    total_failed += failed
    results.append(('الطبيب', passed, failed))
    time.sleep(0.5)
    
    # الطوارئ
    passed, failed = test_emergency_routes()
    total_passed += passed
    total_failed += failed
    results.append(('الطوارئ', passed, failed))
    time.sleep(0.5)
    
    # المختبر
    passed, failed = test_lab_routes()
    total_passed += passed
    total_failed += failed
    results.append(('المختبر', passed, failed))
    time.sleep(0.5)
    
    # الأشعة
    passed, failed = test_radiology_routes()
    total_passed += passed
    total_failed += failed
    results.append(('الأشعة', passed, failed))
    time.sleep(0.5)
    
    # المحاسب
    passed, failed = test_accountant_routes()
    total_passed += passed
    total_failed += failed
    results.append(('المحاسب', passed, failed))
    time.sleep(0.5)
    
    # التمريض
    passed, failed = test_nurse_routes()
    total_passed += passed
    total_failed += failed
    results.append(('التمريض', passed, failed))
    time.sleep(0.5)
    
    # الصيدلية
    passed, failed = test_medication_routes()
    total_passed += passed
    total_failed += failed
    results.append(('الصيدلية', passed, failed))
    
    # عرض النتائج النهائية
    print_header("النتائج النهائية")
    
    print(f"\n{Fore.CYAN}{'الوحدة':<20} {'نجح':>10} {'فشل':>10} {'النسبة':>10}")
    print(f"{Fore.CYAN}{'-'*60}")
    
    for unit, passed, failed in results:
        total = passed + failed
        percentage = (passed / total * 100) if total > 0 else 0
        color = Fore.GREEN if percentage >= 80 else Fore.YELLOW if percentage >= 50 else Fore.RED
        print(f"{color}{unit:<20} {passed:>10} {failed:>10} {percentage:>9.1f}%")
    
    print(f"\n{Fore.CYAN}{'-'*60}")
    total_tests = total_passed + total_failed
    total_percentage = (total_passed / total_tests * 100) if total_tests > 0 else 0
    print(f"{Fore.MAGENTA}{'الإجمالي':<20} {total_passed:>10} {total_failed:>10} {total_percentage:>9.1f}%")
    
    print(f"\n{Fore.MAGENTA}{'='*60}\n")
    
    if total_percentage >= 80:
        print(f"{Fore.GREEN}🎉 النظام يعمل بشكل ممتاز!")
    elif total_percentage >= 50:
        print(f"{Fore.YELLOW}⚠️  النظام يحتاج بعض التحسينات")
    else:
        print(f"{Fore.RED}❌ النظام يحتاج إصلاحات كبيرة")

if __name__ == "__main__":
    main()
