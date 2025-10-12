"""
Deep System Audit - فحص شامل للنظام الطبي
يفحص:
- Routes ↔ Templates ↔ Forms ↔ Models
- الملفات المكررة
- الملفات اليتيمة (Orphan files)
- الاتساق الكامل للنظام
"""

import os
import sys
import json
import csv
import re
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher
from collections import defaultdict
import ast
import importlib.util

# إضافة المشروع للمسار
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


class DeepAudit:
    """محرك الفحص الشامل"""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.routes = []
        self.templates = []
        self.forms = []
        self.models = []
        self.duplicates = []
        self.orphans = []
        self.mappings = []
        
    def run_full_audit(self):
        """تنفيذ الفحص الكامل"""
        print("🔍 بدء الفحص الشامل للنظام الطبي...")
        print("=" * 80)
        
        # المرحلة 1: فحص المسارات
        print("\n📍 المرحلة 1/7: فحص المسارات (Routes)...")
        self.analyze_routes()
        
        # المرحلة 2: فحص القوالب
        print("\n📄 المرحلة 2/7: فحص القوالب (Templates)...")
        self.analyze_templates()
        
        # المرحلة 3: فحص النماذج
        print("\n📝 المرحلة 3/7: فحص النماذج (Forms)...")
        self.analyze_forms()
        
        # المرحلة 4: فحص قاعدة البيانات
        print("\n🗄️ المرحلة 4/7: فحص نماذج قاعدة البيانات (Models)...")
        self.analyze_models()
        
        # المرحلة 5: اكتشاف الملفات المكررة
        print("\n🔄 المرحلة 5/7: اكتشاف الملفات المكررة...")
        self.detect_duplicates()
        
        # المرحلة 6: اكتشاف الملفات اليتيمة
        print("\n👻 المرحلة 6/7: اكتشاف الملفات اليتيمة...")
        self.detect_orphans()
        
        # المرحلة 7: ربط المكونات
        print("\n🔗 المرحلة 7/7: ربط المكونات...")
        self.map_components()
        
        # إنشاء التقارير
        print("\n📊 إنشاء التقارير...")
        self.generate_reports()
        
        print("\n" + "=" * 80)
        print("✅ اكتمل الفحص الشامل!")
        print(f"📂 التقارير محفوظة في: {PROJECT_ROOT / 'audit_reports'}")
    
    def analyze_routes(self):
        """فحص جميع المسارات"""
        routes_dir = self.project_root / 'routes'
        
        if not routes_dir.exists():
            print("⚠️ مجلد routes غير موجود!")
            return
        
        for route_file in routes_dir.glob('*.py'):
            if route_file.name.startswith('_'):
                continue
            
            try:
                with open(route_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # استخراج المسارات
                # البحث عن @bp.route أو @blueprint.route
                route_pattern = r"@\w+\.route\(['\"]([^'\"]+)['\"](?:,\s*methods=\[([^\]]+)\])?\)"
                routes_found = re.findall(route_pattern, content)
                
                # استخراج أسماء الدوال
                function_pattern = r"def\s+(\w+)\s*\([^)]*\):"
                functions = re.findall(function_pattern, content)
                
                # استخراج render_template calls
                template_pattern = r"render_template\(['\"]([^'\"]+)['\"]"
                templates_used = re.findall(template_pattern, content)
                
                # استخراج استيراد النماذج
                form_imports = re.findall(r"from\s+forms\.(\w+)\s+import\s+([\w,\s]+)", content)
                model_imports = re.findall(r"from\s+models\.(\w+)\s+import\s+([\w,\s]+)", content)
                
                # تسجيل المعلومات
                for i, (path, methods) in enumerate(routes_found):
                    route_info = {
                        'file': str(route_file.relative_to(self.project_root)),
                        'path': path,
                        'methods': methods.replace("'", "").replace('"', '').split(',') if methods else ['GET'],
                        'function': functions[i] if i < len(functions) else 'unknown',
                        'templates': templates_used,
                        'forms': [imp[1].strip() for imp in form_imports],
                        'models': [imp[1].strip() for imp in model_imports]
                    }
                    self.routes.append(route_info)
                
                print(f"  ✅ {route_file.name}: {len(routes_found)} مسار")
                
            except Exception as e:
                print(f"  ❌ خطأ في {route_file.name}: {str(e)}")
        
        print(f"\n📊 إجمالي المسارات المكتشفة: {len(self.routes)}")
    
    def analyze_templates(self):
        """فحص جميع القوالب"""
        templates_dir = self.project_root / 'templates'
        
        if not templates_dir.exists():
            print("⚠️ مجلد templates غير موجود!")
            return
        
        for template_file in templates_dir.rglob('*.html'):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # استخراج url_for calls
                url_for_pattern = r"url_for\(['\"]([^'\"]+)['\"]"
                url_fors = re.findall(url_for_pattern, content)
                
                # استخراج form fields
                form_fields = re.findall(r"name=['\"]([^'\"]+)['\"]", content)
                
                # استخراج extends/includes
                extends = re.findall(r"{%\s*extends\s+['\"]([^'\"]+)['\"]", content)
                includes = re.findall(r"{%\s*include\s+['\"]([^'\"]+)['\"]", content)
                
                template_info = {
                    'file': str(template_file.relative_to(self.project_root)),
                    'url_fors': list(set(url_fors)),
                    'form_fields': list(set(form_fields)),
                    'extends': extends,
                    'includes': includes,
                    'size': template_file.stat().st_size
                }
                self.templates.append(template_info)
                
            except Exception as e:
                print(f"  ❌ خطأ في {template_file.name}: {str(e)}")
        
        print(f"📊 إجمالي القوالب المكتشفة: {len(self.templates)}")
    
    def analyze_forms(self):
        """فحص جميع النماذج"""
        forms_dir = self.project_root / 'forms'
        
        if not forms_dir.exists():
            print("⚠️ مجلد forms غير موجود!")
            return
        
        for form_file in forms_dir.glob('*.py'):
            if form_file.name.startswith('_'):
                continue
            
            try:
                with open(form_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # استخراج الـ classes
                class_pattern = r"class\s+(\w+)\s*\([^)]*\):"
                classes = re.findall(class_pattern, content)
                
                # استخراج الحقول
                field_pattern = r"(\w+)\s*=\s*(StringField|IntegerField|FloatField|DateField|TextAreaField|SelectField|BooleanField)"
                fields = re.findall(field_pattern, content)
                
                form_info = {
                    'file': str(form_file.relative_to(self.project_root)),
                    'classes': classes,
                    'fields': [f[0] for f in fields],
                    'total_fields': len(fields)
                }
                self.forms.append(form_info)
                
                print(f"  ✅ {form_file.name}: {len(classes)} نموذج")
                
            except Exception as e:
                print(f"  ❌ خطأ في {form_file.name}: {str(e)}")
        
        print(f"📊 إجمالي Forms المكتشفة: {len(self.forms)}")
    
    def analyze_models(self):
        """فحص نماذج قاعدة البيانات"""
        models_dir = self.project_root / 'models'
        
        if not models_dir.exists():
            print("⚠️ مجلد models غير موجود!")
            return
        
        for model_file in models_dir.glob('*.py'):
            if model_file.name.startswith('_'):
                continue
            
            try:
                with open(model_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # استخراج الـ classes
                class_pattern = r"class\s+(\w+)\s*\([^)]*\):"
                classes = re.findall(class_pattern, content)
                
                # استخراج الأعمدة
                column_pattern = r"(\w+)\s*=\s*db\.Column"
                columns = re.findall(column_pattern, content)
                
                # استخراج العلاقات
                relationship_pattern = r"(\w+)\s*=\s*db\.relationship"
                relationships = re.findall(relationship_pattern, content)
                
                model_info = {
                    'file': str(model_file.relative_to(self.project_root)),
                    'classes': classes,
                    'columns': columns,
                    'relationships': relationships,
                    'total_columns': len(columns)
                }
                self.models.append(model_info)
                
                print(f"  ✅ {model_file.name}: {len(classes)} نموذج")
                
            except Exception as e:
                print(f"  ❌ خطأ في {model_file.name}: {str(e)}")
        
        print(f"📊 إجمالي Models المكتشفة: {len(self.models)}")
    
    def detect_duplicates(self):
        """اكتشاف الملفات المكررة - نسخة سريعة"""
        print("  🔍 فحص الملفات المكررة (فقط routes/, models/, services/)...")
        
        # فحص فقط المجلدات المهمة لتسريع العملية
        important_dirs = ['routes', 'models', 'services', 'forms']
        duplicates_found = []
        
        for dir_name in important_dirs:
            dir_path = self.project_root / dir_name
            if not dir_path.exists():
                continue
            
            py_files = list(dir_path.glob('*.py'))
            py_files = [f for f in py_files if not f.name.startswith('_')]
            
            # فحص الأسماء المتشابهة فقط
            for i, file1 in enumerate(py_files):
                for file2 in py_files[i+1:]:
                    # فحص سريع بالاسم أولاً
                    name1 = file1.stem
                    name2 = file2.stem
                    
                    # تخطي إذا الأسماء مختلفة جداً
                    name_similarity = SequenceMatcher(None, name1, name2).ratio()
                    if name_similarity < 0.5:
                        continue
                    
                    try:
                        # قراءة الملفات
                        with open(file1, 'r', encoding='utf-8') as f:
                            content1 = f.read()
                        with open(file2, 'r', encoding='utf-8') as f:
                            content2 = f.read()
                        
                        # فحص سريع بالحجم
                        if abs(len(content1) - len(content2)) > len(content1) * 0.5:
                            continue
                        
                        # حساب التشابه للملفات الصغيرة فقط
                        if len(content1) > 50000:  # تخطي الملفات الكبيرة
                            continue
                        
                        similarity = SequenceMatcher(None, content1, content2).ratio()
                        
                        if similarity >= 0.80:  # 80% تشابه
                            duplicates_found.append({
                                'file1': str(file1.relative_to(self.project_root)),
                                'file2': str(file2.relative_to(self.project_root)),
                                'similarity': round(similarity * 100, 2),
                                'recommendation': 'merge_to_primary'
                            })
                            
                    except Exception as e:
                        continue
        
        self.duplicates = duplicates_found
        print(f"📊 ملفات مكررة محتملة: {len(duplicates_found)}")
        
        if duplicates_found:
            print("\n🔍 أمثلة على الملفات المكررة:")
            for dup in duplicates_found[:5]:
                print(f"  - {dup['file1']} ↔ {dup['file2']} ({dup['similarity']}%)")
    
    def detect_orphans(self):
        """اكتشاف الملفات اليتيمة"""
        orphans_found = []
        
        # فحص ملفات Python
        py_files = list(self.project_root.rglob('*.py'))
        py_files = [f for f in py_files if '__pycache__' not in str(f) and '.venv' not in str(f)]
        
        # البحث عن الاستيرادات
        all_imports = set()
        for py_file in py_files:
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    imports = re.findall(r"from\s+([\w.]+)\s+import", content)
                    imports += re.findall(r"import\s+([\w.]+)", content)
                    all_imports.update(imports)
            except:
                continue
        
        # فحص القوالب غير المستخدمة
        templates_dir = self.project_root / 'templates'
        if templates_dir.exists():
            all_template_refs = set()
            
            # جمع كل render_template calls
            for py_file in py_files:
                try:
                    with open(py_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        templates = re.findall(r"render_template\(['\"]([^'\"]+)['\"]", content)
                        all_template_refs.update(templates)
                except:
                    continue
            
            # فحص القوالب
            for template_file in templates_dir.rglob('*.html'):
                template_path = str(template_file.relative_to(templates_dir))
                
                if template_path not in all_template_refs:
                    # التحقق من extends/includes
                    is_base = False
                    is_partial = False
                    
                    try:
                        with open(template_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # قد يكون base template أو partial
                            if 'block content' in content or 'block body' in content:
                                is_base = True
                            if template_path.startswith('partials/') or template_path.startswith('_'):
                                is_partial = True
                    except:
                        pass
                    
                    if not is_base and not is_partial:
                        orphans_found.append({
                            'file': str(template_file.relative_to(self.project_root)),
                            'type': 'template',
                            'reason': 'No render_template() call found',
                            'severity': 'medium'
                        })
        
        self.orphans = orphans_found
        print(f"📊 ملفات يتيمة محتملة: {len(orphans_found)}")
        
        if orphans_found:
            print("\n👻 أمثلة على الملفات اليتيمة:")
            for orphan in orphans_found[:5]:
                print(f"  - {orphan['file']} ({orphan['reason']})")
    
    def map_components(self):
        """ربط المكونات (Route → Template → Form → Model)"""
        print("🔗 ربط المكونات...")
        
        for route in self.routes:
            mapping = {
                'route_path': route['path'],
                'route_file': route['file'],
                'function': route['function'],
                'templates': route['templates'],
                'forms': route['forms'],
                'models': route['models'],
                'confidence_score': 0
            }
            
            # حساب نقاط الثقة
            if route['file']:
                mapping['confidence_score'] += 25  # الملف موجود
            
            if route['templates']:
                # التحقق من وجود القالب
                for template in route['templates']:
                    template_exists = any(t['file'].endswith(template) for t in self.templates)
                    if template_exists:
                        mapping['confidence_score'] += 25
                    else:
                        mapping['confidence_score'] -= 10  # قالب مفقود
            
            if route['forms']:
                mapping['confidence_score'] += 20
            
            if route['models']:
                mapping['confidence_score'] += 15
            
            # التأكد من عدم تجاوز 100
            mapping['confidence_score'] = min(100, max(0, mapping['confidence_score']))
            
            self.mappings.append(mapping)
        
        print(f"✅ تم ربط {len(self.mappings)} مكون")
    
    def generate_reports(self):
        """إنشاء جميع التقارير"""
        # إنشاء مجلد التقارير
        reports_dir = self.project_root / 'audit_reports'
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 1. تقرير المسارات (JSON)
        with open(reports_dir / f'route_audit_report_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'total_routes': len(self.routes),
                'routes': self.routes,
                'mappings': self.mappings
            }, f, ensure_ascii=False, indent=2)
        
        # 2. تقرير المسارات (CSV)
        with open(reports_dir / f'route_audit_report_{timestamp}.csv', 'w', encoding='utf-8-sig', newline='') as f:
            if self.mappings:
                writer = csv.DictWriter(f, fieldnames=self.mappings[0].keys())
                writer.writeheader()
                writer.writerows(self.mappings)
        
        # 3. تقرير الملفات المكررة
        with open(reports_dir / f'duplication_report_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'total_duplicates': len(self.duplicates),
                'duplicates': self.duplicates
            }, f, ensure_ascii=False, indent=2)
        
        # 4. تقرير الملفات اليتيمة
        with open(reports_dir / f'orphan_files_report_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump({
                'generated_at': datetime.now().isoformat(),
                'total_orphans': len(self.orphans),
                'orphans': self.orphans
            }, f, ensure_ascii=False, indent=2)
        
        # 5. ملخص نصي
        summary_content = self.generate_summary_markdown()
        with open(reports_dir / f'route_audit_summary_{timestamp}.md', 'w', encoding='utf-8') as f:
            f.write(summary_content)
        
        # 6. قائمة الإجراءات
        followups = self.generate_followup_actions()
        with open(reports_dir / f'followups_{timestamp}.txt', 'w', encoding='utf-8') as f:
            f.write(followups)
        
        print(f"\n✅ تم إنشاء 6 تقارير في: {reports_dir}")
    
    def generate_summary_markdown(self):
        """إنشاء ملخص Markdown"""
        content = f"""# 🔍 تقرير الفحص الشامل للنظام الطبي
## Deep Audit Report - Medical System

**تاريخ الفحص:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📊 الإحصائيات العامة

| المكون | العدد |
|--------|-------|
| المسارات (Routes) | {len(self.routes)} |
| القوالب (Templates) | {len(self.templates)} |
| النماذج (Forms) | {len(self.forms)} |
| النماذج DB (Models) | {len(self.models)} |
| ملفات مكررة | {len(self.duplicates)} |
| ملفات يتيمة | {len(self.orphans)} |

---

## 🎯 نقاط الثقة (Confidence Scores)

"""
        # إحصائيات نقاط الثقة
        if self.mappings:
            high_confidence = len([m for m in self.mappings if m['confidence_score'] >= 75])
            medium_confidence = len([m for m in self.mappings if 50 <= m['confidence_score'] < 75])
            low_confidence = len([m for m in self.mappings if m['confidence_score'] < 50])
            
            content += f"""
- **عالية (≥75):** {high_confidence} مسار
- **متوسطة (50-74):** {medium_confidence} مسار
- **منخفضة (<50):** {low_confidence} مسار

"""
        
        # الملفات المكررة
        if self.duplicates:
            content += f"""
## ⚠️ الملفات المكررة ({len(self.duplicates)})

| الملف الأول | الملف الثاني | التشابه |
|-------------|--------------|----------|
"""
            for dup in self.duplicates[:10]:
                content += f"| {dup['file1']} | {dup['file2']} | {dup['similarity']}% |\n"
            
            if len(self.duplicates) > 10:
                content += f"\n*...و {len(self.duplicates) - 10} ملفات أخرى*\n"
        
        # الملفات اليتيمة
        if self.orphans:
            content += f"""
## 👻 الملفات اليتيمة ({len(self.orphans)})

| الملف | النوع | السبب |
|-------|------|-------|
"""
            for orphan in self.orphans[:10]:
                content += f"| {orphan['file']} | {orphan['type']} | {orphan['reason']} |\n"
            
            if len(self.orphans) > 10:
                content += f"\n*...و {len(self.orphans) - 10} ملفات أخرى*\n"
        
        content += """
---

## ✅ التوصيات

1. **دمج الملفات المكررة** في الملف الأساسي
2. **حذف الملفات اليتيمة** بعد التأكد
3. **تحسين نقاط الثقة المنخفضة** بإضافة القوالب أو النماذج المفقودة

---

**تم بواسطة:** Deep Audit System  
**النسخة:** 2.0
"""
        return content
    
    def generate_followup_actions(self):
        """إنشاء قائمة الإجراءات المطلوبة"""
        actions = f"""# 📋 قائمة الإجراءات المطلوبة
## Follow-up Actions

تاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## ✅ إجراءات فورية

"""
        
        if self.duplicates:
            actions += f"""
### 1. دمج الملفات المكررة ({len(self.duplicates)} ملف)

```powershell
# مراجعة الملفات المكررة يدوياً ثم دمجها
"""
            for dup in self.duplicates[:3]:
                actions += f"# قارن: {dup['file1']} مع {dup['file2']}\n"
            actions += "```\n"
        
        if self.orphans:
            actions += f"""
### 2. مراجعة الملفات اليتيمة ({len(self.orphans)} ملف)

```powershell
# حذف الملفات غير المستخدمة
"""
            for orphan in self.orphans[:3]:
                actions += f"# Remove-Item '{orphan['file']}'\n"
            actions += "```\n"
        
        actions += """
### 3. تحديث Git

```powershell
git add -A
git commit -m "تنظيف: دمج الملفات المكررة وحذف اليتيمة"
git push origin main
```

---

تم إنشاء هذه القائمة تلقائياً. راجع التقارير التفصيلية قبل التنفيذ.
"""
        return actions


def main():
    """نقطة البداية"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║  🏥 فحص شامل للنظام الطبي - Deep System Audit             ║
║  Medical Center Management System - Integrity Check         ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    auditor = DeepAudit()
    auditor.run_full_audit()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║  ✅ اكتمل الفحص بنجاح!                                     ║
║  📂 راجع التقارير في مجلد: audit_reports/                 ║
╚══════════════════════════════════════════════════════════════╝
""")


if __name__ == '__main__':
    main()

