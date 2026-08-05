# عقد نماذج التخصص الديناميكية — Dynamic Specialty Forms

> التوثيق الرسمي لملف `routes/specialty_forms.py` ونماذج `models/specialty_form.py`. آخر تحقق من الكود: **5 أغسطس 2026**.

---

## 1. الغرض

نموذج تخصص (مثال: استبيان العظام، تقييم جلدية، سجل متابعة قلبية) يُبنى ديناميكياً **دون كود**، ليجمع بيانات منظمة عبر زيارة، ويُربط بالمريض. هذا تطبيق **UX1-005** ويعمل ضمن وحدة `doctor` (المسار `/specialty-forms`).

---

## 2. نموذج البيانات

| الجدول | الوصف |
|--------|-------|
| `specialty_forms` | تعريف النموذج: `name`, `slug`, `specialty`, `is_active`, `latest_published_version_id` |
| `specialty_form_versions` | نسخة النموذج: `version_number`, `status` (`draft` / `published` / `archived`) |
| `specialty_form_fields` | حقل: `name`, `label`, `field_type`, `required`, `options`, `default_value`, `validation_rules`, `sort_order` |
| `specialty_form_submissions` | تعبئة: `answers` (JSON), `patient_id`, `visit_id`, `submitted_by` |

**قواعد فريدة إلزامية:**
- `(tenant_id, slug)` — معرّف فريد لكل مستأجر.
- `(form_id, version_number)` — ترقيم متسلسل.
- `(version_id, name)` — اسم حقل فريد داخل النسخة.

جميع الجداول ترث `TenantMixin` و `__tenant_migration__ = True` (تخضع لـ RLS).

---

## 3. أنواع الحقول (مغلقة)

فقط هذه الأنواع — أي نوع آخر يُرفض عند الحفظ (`ALLOWED_TYPES`):

| `field_type` | الوصف | `options`؟ | `validation_rules` مثال |
|--------------|-------|-----------|--------------------------|
| `text` | نص حر | لا | — |
| `number` | رقم | لا | `{"min": 0, "max": 100}` |
| `date` | تاريخ | لا | — |
| `select` | قائمة منسدلة | نعم (قائمة خيارات) | — |
| `checkbox` | اختيار متعدد | نعم | — |
| `textarea` | نص متعدد الأسطر | لا | — |

---

## 4. دورة حياة النسخة

```
draft ──publish──▶ published ──(الأحدث فقط يُعبّأ)
   ▲                  │
   └────── edit ──────┘   (نسخة جديدة تبدأ draft)
draft / published ──▶ archived
```

- أي تعديل يُنشئ **نسخة جديدة** لا تعديل النشر.
- `latest_published_version_id` يحدد النسخة النشطة لملء النموذج.
- الحذف: النسخة `CASCADE`، الحقول `CASCADE`، التعبئات `RESTRICT` (لا حذف لنسخة عليها تعبئات).

---

## 5. المسارات (Blueprint: `specialty_forms`)

| الطريقة | المسار | الوصول | الوظيفة |
|---------|--------|--------|---------|
| GET | `/specialty-forms` | أي مستخدم مسجّل | قائمة النماذج النشطة |
| GET/POST | `/specialty-forms/new` | `manager`, `admin`, `super_admin` | إنشاء نموذج + نسخة draft |
| GET | `/specialty-forms/<form_id>` | مسجّل | عرض النموذج ونسخه |
| GET/POST | `/specialty-forms/<form_id>/versions/<version_id>/edit` | `manager`/`admin`/`super_admin` | تعديل حقول نسخة (draft) |
| POST | `/specialty-forms/<form_id>/versions/<version_id>/publish` | `manager`/`admin`/`super_admin` | نشر النسخة |
| GET/POST | `/specialty-forms/<form_id>/fill` | طبيب/فريق سريري | تعبئة النموذج لمريض/زيارة |
| GET | `/specialty-forms/<form_id>/submissions` | مسجّل | قائمة التعبئات |
| GET | `/specialty-forms/submissions/<submission_id>` | مسجّل | عرض تعبئة محددة |

> التفويض الأساسي عبر `@login_required` + `@role_required`. التحكم الدقيق لكل مستأجر تفرضه RLS (الصفوف مقيدة بـ `tenant_id`).

---

## 6. اتفاقيات التخزين

- `answers` هو JSON خريطة: `{ "field_name": value }` — المفاتيح هي `name` الحقول (فريدة داخل النسخة).
- `options` قائمة نصوص لـ `select`/`checkbox`.
- `default_value` نص يُملأ مسبقاً.
- لا تُخزن بيانات PHI في الـ `slug` أو `name` — فقط في قيم التعبئة.
- التعبئة مرتبطة إجبارياً بـ `patient_id` (CASCADE عند حذف المريض) وقد ترتبط بـ `visit_id`.

---

## 7. القواعد التشغيلية

1. **لا يوجد قالب HTML صارم:** يتم توفير قوالب العرض في `templates/specialty_forms/` وتُرتّب الحقول حسب `sort_order`.
2. **التعديل بعد النشر:** دائماً نسخة جديدة — لا تعديل مباشر على `published`.
3. **التعطيل:** `is_active=false` يخفي النموذج من القائمة ويوقف التعبئة الجديدة.
4. **سياق المتصفح:** النموذج متاح من لوحة الطبيب؛ تُفتح التعبئة بمريض محدد.
5. **التتبع:** `created_at`/`updated_at`/`created_by`/`submitted_by` تسجل التدقيق.

---

## 8. الاختبارات والتحقق

- النماذج و المسارات مشمولة في 139 ملف اختبار (بحث: `specialty_form`).
- عند إضافة حقل جديد: أضف نوعه إلى `ALLOWED_TYPES` ونموذج التعبئة لعرضه.
- أي تغيير في النموذج يجب أن يُراجع عبر `npx cspell` (نصوص ثنائية اللغة AR/EN).
