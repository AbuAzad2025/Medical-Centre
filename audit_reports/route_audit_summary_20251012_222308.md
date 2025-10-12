# 🔍 تقرير الفحص الشامل للنظام الطبي
## Deep Audit Report - Medical System

**تاريخ الفحص:** 2025-10-12 22:23:08

---

## 📊 الإحصائيات العامة

| المكون | العدد |
|--------|-------|
| المسارات (Routes) | 227 |
| القوالب (Templates) | 120 |
| النماذج (Forms) | 16 |
| النماذج DB (Models) | 40 |
| ملفات مكررة | 1 |
| ملفات يتيمة | 16 |

---

## 🎯 نقاط الثقة (Confidence Scores)


- **عالية (≥75):** 0 مسار
- **متوسطة (50-74):** 0 مسار
- **منخفضة (<50):** 227 مسار


## ⚠️ الملفات المكررة (1)

| الملف الأول | الملف الثاني | التشابه |
|-------------|--------------|----------|
| models\medical_record.py | models\medical_report.py | 90.42% |

## 👻 الملفات اليتيمة (16)

| الملف | النوع | السبب |
|-------|------|-------|
| templates\auth\login.html | template | No render_template() call found |
| templates\errors\403.html | template | No render_template() call found |
| templates\errors\404.html | template | No render_template() call found |
| templates\errors\500.html | template | No render_template() call found |
| templates\includes\role_sidebar.html | template | No render_template() call found |
| templates\macros\forms.html | template | No render_template() call found |
| templates\partials\_csrf_meta.html | template | No render_template() call found |
| templates\partials\_flash.html | template | No render_template() call found |
| templates\partials\_footer.html | template | No render_template() call found |
| templates\partials\_navbar.html | template | No render_template() call found |

*...و 6 ملفات أخرى*

---

## ✅ التوصيات

1. **دمج الملفات المكررة** في الملف الأساسي
2. **حذف الملفات اليتيمة** بعد التأكد
3. **تحسين نقاط الثقة المنخفضة** بإضافة القوالب أو النماذج المفقودة

---

**تم بواسطة:** Deep Audit System  
**النسخة:** 2.0
