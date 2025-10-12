"""
فحص شامل نهائي للنظام
Final Comprehensive System Check
"""
import os
import re
from pathlib import Path
from colorama import init, Fore, Style

init(autoreset=True)

def print_header(text):
    print(f"\n{Fore.CYAN}{'='*70}")
    print(f"{Fore.CYAN}{text:^70}")
    print(f"{Fore.CYAN}{'='*70}\n")

def print_success(text):
    print(f"{Fore.GREEN}✅ {text}")

def print_warning(text):
    print(f"{Fore.YELLOW}⚠️  {text}")

def print_error(text):
    print(f"{Fore.RED}❌ {text}")

def print_info(text):
    print(f"{Fore.BLUE}ℹ️  {text}")

# ==================== فحص المسارات (Routes) ====================

def check_routes():
    """فحص جميع ملفات المسارات"""
    print_header("فحص ملفات المسارات (Routes)")
    
    routes_dir = Path('routes')
    route_files = list(routes_dir.glob('*.py'))
    
    print_info(f"عدد ملفات المسارات: {len(route_files)}")
    
    routes_data = {}
    
    for route_file in route_files:
        if route_file.name == '__init__.py':
            continue
            
        with open(route_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # استخراج Blueprint
        bp_match = re.search(r"(\w+)_bp\s*=\s*Blueprint\(['\"](\w+)['\"]", content)
        if bp_match:
            bp_name = bp_match.group(1)
            
            # استخراج جميع المسارات
            route_patterns = re.findall(r"@\w+_bp\.route\(['\"]([^'\"]+)['\"]", content)
            
            routes_data[route_file.name] = {
                'blueprint': bp_name,
                'routes': route_patterns,
                'count': len(route_patterns)
            }
            
            print_success(f"{route_file.name}: {len(route_patterns)} مسار")
    
    return routes_data

# ==================== فحص القوالب (Templates) ====================

def check_templates():
    """فحص جميع ملفات القوالب"""
    print_header("فحص ملفات القوالب (Templates)")
    
    templates_dir = Path('templates')
    
    # حساب القوالب حسب الوحدة
    template_counts = {}
    
    for unit_dir in templates_dir.iterdir():
        if unit_dir.is_dir() and unit_dir.name != '__pycache__':
            html_files = list(unit_dir.glob('*.html'))
            template_counts[unit_dir.name] = len(html_files)
            print_info(f"{unit_dir.name}: {len(html_files)} قالب")
    
    return template_counts

# ==================== فحص النماذج (Models) ====================

def check_models():
    """فحص جميع ملفات النماذج"""
    print_header("فحص ملفات النماذج (Models)")
    
    models_dir = Path('models')
    model_files = list(models_dir.glob('*.py'))
    
    models_data = {}
    
    for model_file in model_files:
        if model_file.name == '__init__.py':
            continue
            
        with open(model_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # استخراج أسماء الكلاسات
        class_matches = re.findall(r"class\s+(\w+)\(", content)
        
        models_data[model_file.name] = {
            'classes': class_matches,
            'count': len(class_matches)
        }
        
        print_success(f"{model_file.name}: {len(class_matches)} كلاس")
    
    return models_data

# ==================== فحص الخدمات (Services) ====================

def check_services():
    """فحص جميع ملفات الخدمات"""
    print_header("فحص ملفات الخدمات (Services)")
    
    services_dir = Path('services')
    
    if not services_dir.exists():
        print_warning("مجلد services غير موجود")
        return {}
    
    service_files = list(services_dir.glob('*.py'))
    
    services_data = {}
    
    for service_file in service_files:
        if service_file.name == '__init__.py':
            continue
            
        with open(service_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # استخراج الكلاسات والدوال
        class_matches = re.findall(r"class\s+(\w+)\(", content)
        func_matches = re.findall(r"def\s+(\w+)\(", content)
        
        services_data[service_file.name] = {
            'classes': class_matches,
            'functions': func_matches,
            'count': len(class_matches) + len(func_matches)
        }
        
        print_success(f"{service_file.name}: {len(class_matches)} كلاس، {len(func_matches)} دالة")
    
    return services_data

# ==================== فحص التكرار ====================

def check_duplicates():
    """فحص التكرار في الملفات"""
    print_header("فحص التكرار")
    
    # فحص ملفات متشابهة
    all_files = []
    
    for root, dirs, files in os.walk('.'):
        # تجاهل المجلدات غير المهمة
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', '.venv', 'venv', 'instance', 'backups']]
        
        for file in files:
            if file.endswith(('.py', '.html')):
                all_files.append(os.path.join(root, file))
    
    # فحص أسماء مشابهة
    similar_files = {}
    
    for i, file1 in enumerate(all_files):
        base1 = os.path.basename(file1)
        
        for file2 in all_files[i+1:]:
            base2 = os.path.basename(file2)
            
            # تحقق من التشابه
            if base1 == base2 and file1 != file2:
                if base1 not in similar_files:
                    similar_files[base1] = []
                similar_files[base1].append((file1, file2))
    
    if similar_files:
        print_warning("ملفات متشابهة وجدت:")
        for filename, pairs in similar_files.items():
            print_error(f"  {filename}:")
            for file1, file2 in pairs:
                print(f"    - {file1}")
                print(f"    - {file2}")
    else:
        print_success("لا توجد ملفات متشابهة")
    
    return similar_files

# ==================== فحص الملفات اليتيمة ====================

def check_orphan_files():
    """فحص الملفات اليتيمة"""
    print_header("فحص الملفات اليتيمة")
    
    # قائمة الملفات المتوقعة
    expected_patterns = [
        'test_*.py',
        '*_test.py',
        'comprehensive_test.py',
        'final_comprehensive_check.py',
        'seed_*.py'
    ]
    
    orphan_files = []
    
    # فحص الجذر
    for file in Path('.').glob('*.py'):
        is_expected = False
        for pattern in expected_patterns:
            if file.match(pattern):
                is_expected = True
                break
        
        if not is_expected and file.name not in ['app.py', 'app_factory.py', 'config.py']:
            orphan_files.append(str(file))
    
    if orphan_files:
        print_warning("ملفات يتيمة محتملة:")
        for orphan in orphan_files:
            print_warning(f"  {orphan}")
    else:
        print_success("لا توجد ملفات يتيمة")
    
    return orphan_files

# ==================== فحص الاستيرادات ====================

def check_imports():
    """فحص الاستيرادات"""
    print_header("فحص الاستيرادات")
    
    routes_dir = Path('routes')
    import_issues = []
    
    for route_file in routes_dir.glob('*.py'):
        if route_file.name == '__init__.py':
            continue
            
        with open(route_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # فحص استيرادات متكررة
        imports = re.findall(r"^from .+ import .+$", content, re.MULTILINE)
        
        # فحص التكرار
        import_counts = {}
        for imp in imports:
            if imp in import_counts:
                import_counts[imp] += 1
            else:
                import_counts[imp] = 1
        
        duplicates = {k: v for k, v in import_counts.items() if v > 1}
        
        if duplicates:
            import_issues.append({
                'file': str(route_file),
                'duplicates': duplicates
            })
    
    if import_issues:
        print_warning("استيرادات مكررة وجدت:")
        for issue in import_issues:
            print_warning(f"  {issue['file']}:")
            for imp, count in issue['duplicates'].items():
                print(f"    {imp} ({count} مرات)")
    else:
        print_success("لا توجد استيرادات مكررة")
    
    return import_issues

# ==================== التقرير النهائي ====================

def generate_final_report():
    """إنشاء التقرير النهائي"""
    print(f"\n{Fore.MAGENTA}{'='*70}")
    print(f"{Fore.MAGENTA}{'تقرير الفحص الشامل النهائي':^70}")
    print(f"{Fore.MAGENTA}{'='*70}\n")
    
    # فحص المسارات
    routes_data = check_routes()
    
    # فحص القوالب
    template_counts = check_templates()
    
    # فحص النماذج
    models_data = check_models()
    
    # فحص الخدمات
    services_data = check_services()
    
    # فحص التكرار
    duplicates = check_duplicates()
    
    # فحص الملفات اليتيمة
    orphans = check_orphan_files()
    
    # فحص الاستيرادات
    imports = check_imports()
    
    # ==================== الملخص النهائي ====================
    
    print_header("الملخص النهائي")
    
    print(f"{Fore.CYAN}📊 إحصائيات النظام:")
    print(f"  • ملفات المسارات: {len(routes_data)}")
    print(f"  • وحدات القوالب: {len(template_counts)}")
    print(f"  • إجمالي القوالب: {sum(template_counts.values())}")
    print(f"  • ملفات النماذج: {len(models_data)}")
    print(f"  • ملفات الخدمات: {len(services_data)}")
    
    print(f"\n{Fore.YELLOW}⚠️  المشاكل المكتشفة:")
    print(f"  • ملفات متشابهة: {len(duplicates)}")
    print(f"  • ملفات يتيمة: {len(orphans)}")
    print(f"  • ملفات بها استيرادات مكررة: {len(imports)}")
    
    # النتيجة النهائية
    total_issues = len(duplicates) + len(orphans) + len(imports)
    
    print(f"\n{Fore.MAGENTA}{'='*70}")
    
    if total_issues == 0:
        print(f"{Fore.GREEN}{'🎉 النظام نظيف وجاهز للإنتاج!':^70}")
    elif total_issues < 5:
        print(f"{Fore.YELLOW}{'⚠️  النظام جيد مع بعض التحسينات البسيطة':^70}")
    else:
        print(f"{Fore.RED}{'❌ النظام يحتاج إلى تحسينات':^70}")
    
    print(f"{Fore.MAGENTA}{'='*70}\n")

if __name__ == "__main__":
    generate_final_report()


