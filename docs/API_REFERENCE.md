# مرجع API — API Reference (OpenAPI 3.0)

**الإصدار:** 3.3 | **التاريخ:** 25 أكتوبر 2026 | **إجمالي المسارات:** 753 (GET: 514, POST: 329, PUT: 2, DELETE: 2)

> تم إنشاء هذا المستند تلقائياً من `app.url_map` في بيئة الاختبار — يعكس المسارات الفعلية المسجلة في `app_factory.py`.

---

## المصادقة (Authentication)

### تسجيل الدخول / الجلسة

| الطريقة | المسار | الوصف | الأدوار |
|---------|-------|---------|---------|
| `GET,POST` | `/auth/login` | تسجيل دخول (نموذج / JSON) | الكل |
| `POST` | `/auth/logout` | تسجيل خروج | المسجلين |
| `GET,POST` | `/auth/register` | تسجيل مستخدم جديد (في وضع المركز الواحد) | — |
| `GET,POST` | `/auth/forgot-password` | طلب إعادة تعيين كلمة المرور | — |
| `GET,POST` | `/auth/reset-password/<token>/<int:user_id>` | إعادة تعيين بكلمة جديدة | — |
| `POST` | `/auth/change-password` | تغيير كلمة المرور | المسجلين |
| `GET,POST` | `/auth/profile` | الملف الشخصي | المسجلين |
| `POST` | `/auth/impersonate/<int:user_id>` | انتحال شخصية (super_admin فقط) | super_admin |
| `POST` | `/auth/impersonate/exit` | الخروج من الانتحال | super_admin |
| `GET` | `/auth/api/tenants-list` | قائمة المستأجرين المتاحة | المسجلين |

### MFA / WebAuthn

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET,POST` | `/mfa/setup` | إعداد MFA / WebAuthn |
| `POST` | `/mfa/api/check` | التحقق من رمز MFA |
| `POST` | `/mfa/verify` | التحقق النهائي |
| `POST` | `/mfa/disable` | تعطيل MFA |
| `GET` | `/mfa/status` | حالة MFA |

### SSO (OIDC)

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET,POST` | `/sso/config` | إعداد SSO (super_admin) |
| `POST` | `/sso/toggle/<int:config_id>` | تفعيل/تعطيل تكوين SSO |

---

## المستأجرون والباقات (SaaS / Multi-tenant)

### التسجيل الذاتي

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET,POST` | `/saas/signup` | تسجيل مركز جديد (عامة) |
| `POST` | `/api/saas/register` | API تسجيل مستأجر جديد |

### لوحة المالك (Owner / Platform Admin)

| الطريقة | المسار | الوصف | الأدوار |
|---------|-------|---------|---------|
| `GET` | `/owner/dashboard` | لوحة المالك | owner, super_admin |
| `GET,POST` | `/owner/tenants/` | عرض/إنشاء مستأجرين | owner |
| `GET,POST` | `/owner/tenants/<int:tenant_id>` | عرض/تعديل مستأجر | owner |
| `POST` | `/owner/tenants/<int:tenant_id>/activate` | تفعيل مستأجر | owner |
| `POST` | `/owner/tenants/<int:tenant_id>/suspend` | تعليق مستأجر | owner |
| `POST` | `/owner/tenants/<int:tenant_id>/renew` | تجديد اشتراك | owner |
| `POST` | `/owner/tenants/<int:tenant_id>/edit` | تعديل بيانات مستأجر | owner |
| `POST` | `/owner/tenants/<int:tenant_id>/activate-modules` | تفعيل وحدات | owner |
| `GET,POST` | `/owner/tenants/create` | إنشاء مستأجر يدوي | owner |
| `GET` | `/owner/api/tenants` | API قائمة المستأجرين | owner |
| `GET` | `/owner/api/tenants/<int:tenant_id>/modules` | وحدات مستأجر | owner |
| `POST` | `/owner/api/tenants/<int:tenant_id>/modules/<module_name>/activate` | تفعيل وحدة | owner |
| `POST` | `/owner/api/tenants/<int:tenant_id>/modules/<module_name>/deactivate` | تعطيل وحدة | owner |
| `GET` | `/owner/api/bundles` | كتالوج الباقات | owner |
| `POST` | `/owner/api/bundles` | إنشاء باقة | owner |
| `GET` | `/owner/bundles` | واجهة إدارة الباقات | owner |
| `GET,POST` | `/owner/packages` | إدارة الحزم القابلة للبيع | owner |
| `POST` | `/owner/control/toggle` | مفاتيح طوارئ المنصة | owner |
| `GET` | `/owner/analytics` | مؤشرات المنصة الكلية | owner |
| `GET` | `/owner/system-stats` | إحصائيات النظام | owner |

---

## الوحدات السريرية (Clinical Modules)

### الاستقبال (Reception) — `/reception/`

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/reception/dashboard` | لوحة الاستقبال (widgets: queue_live, visits_today, appointments_pending) |
| `GET,POST` | `/reception/add_patient` | تسجيل مريض جديد |
| `GET,POST` | `/reception/edit_patient/<int:patient_id>` | تعديل بيانات مريض |
| `POST` | `/reception/delete_patient/<int:patient_id>` | حذف مريض (نادر) |
| `GET` | `/reception/patients` | قائمة المرضى |
| `GET` | `/reception/view_patient/<int:patient_id>` | عرض مريض |
| `GET,POST` | `/reception/visits/new` | فتح زيارة جديدة |
| `GET,POST` | `/reception/visits/create` | إنشاء زيارة |
| `GET` | `/reception/visits` | قائمة الزيارات |
| `GET` | `/reception/view_visit/<int:visit_id>` | عرض زيارة |
| `GET,POST` | `/reception/edit_visit/<int:visit_id>` | تعديل زيارة |
| `POST` | `/reception/visits/<int:visit_id>/end` | إنهاء زيارة |
| `POST` | `/reception/visits/<int:visit_id>/archive` | أرشفة زيارة |
| `POST` | `/reception/visits/<int:visit_id>/transfer` | تحويل زيارة |
| `POST` | `/reception/visits/<int:visit_id>/send-to-accounting` | إرسال للمحاسبة |
| `GET,POST` | `/reception/appointments` | إدارة المواعيد |
| `POST` | `/reception/appointments/<int:appointment_id>/checkin` | تسجيل حضور |
| `POST` | `/reception/appointments/<int:appointment_id>/confirm` | تأكيد موعد |
| `POST` | `/reception/appointments/<int:appointment_id>/cancel` | إلغاء موعد |
| `POST` | `/reception/appointments/<int:appointment_id>/no-show` | عدم حضور |
| `GET` | `/reception/queue` | طابور الانتظار |
| `POST` | `/reception/queue/add-patient` | إضافة لطابور |
| `POST` | `/reception/queue/call-next/<int:department_id>` | استدعاء التالي |
| `POST` | `/reception/queue/skip-patient/<int:ticket_id>` | تخطي مريض |
| `POST` | `/reception/queue/start-treatment/<int:ticket_id>` | بدء علاج |
| `POST` | `/reception/queue/complete-treatment/<int:ticket_id>` | إكمال علاج |
| `GET,POST` | `/reception/cash-register` | الصندوق النقدي (يتطلب billing) |
| `GET` | `/reception/print_invoice/<int:invoice_id>` | طباعة فاتورة |
| `GET` | `/reception/print_prescription/<int:prescription_id>` | طباعة روشتة |

**API الاستقبال (AJAX):**
| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/reception/api/queue-snapshot` | لقطة طابور حية |
| `GET` | `/reception/api/queue-status/<int:department_id>` | حالة قسم |
| `GET` | `/reception/api/available-times` | أوقات متاحة للمواعيد |
| `GET` | `/reception/api/patient-queue-position/<int:patient_id>/<int:department_id>` | موقع مريض في الطابور |
| `GET` | `/reception/api/smart-patient-search` | بحث ذكي مرضى |
| `POST` | `/reception/api/patients/<int:patient_id>/allergies/add` | إضافة حساسية |
| `POST` | `/reception/api/patients/<int:patient_id>/problems/add` | إضافة مشكلة طبية |

### الطبيب (Doctor) — `/doctor/`

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/doctor/dashboard` | لوحة الطبيب (widgets: my_queue, patients_waiting, lab_pending, radiology_pending) |
| `GET` | `/doctor/visits` | زياراتي |
| `GET` | `/doctor/patient-queue` | طابور مرضي |
| `GET` | `/doctor/patients` | مرضي |
| `GET` | `/doctor/patient-details/<int:visit_id>` | تفاصيل زيارة |
| `GET,POST` | `/doctor/prescription/<int:visit_id>` | كتابة روشتة |
| `GET` | `/doctor/prescriptions` | الروشيتات |
| `GET` | `/doctor/medical-records` | السجلات الطبية |
| `GET,POST` | `/doctor/notes/<int:visit_id>` | ملاحظات SOAP |
| `GET,POST` | `/doctor/diagnosis/<int:visit_id>` | تشخيص ICD-10/CPT |
| `GET,POST` | `/doctor/lab-request/<int:visit_id>` | طلب مختبر |
| `GET,POST` | `/doctor/radiology-request/<int:visit_id>` | طلب أشعة |
| `GET` | `/doctor/lab-results/<int:patient_id>` | نتائج مختبر |
| `GET` | `/doctor/radiology-results/<int:patient_id>` | نتائج أشعة |
| `POST` | `/doctor/start-treatment/<int:visit_id>` | بدء علاج |
| `POST` | `/doctor/end-treatment/<int:visit_id>` | إنهاء علاج |
| `POST` | `/doctor/save-visit-summary/<int:visit_id>` | حفظ ملخص |
| `GET` | `/doctor/print-prescription/<int:prescription_id>` | طباعة روشتة |

### طبيب الطوارئ (ER Doctor) — `/emergency/`

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/emergency/dashboard` | لوحة الطوارئ (widgets: critical_count, triage_board, emergency_waitlist) |
| `GET` | `/emergency/queue` | طابور الطوارئ |
| `GET,POST` | `/emergency/triage/<int:emergency_id>` | فرز ESI |
| `POST` | `/emergency/cases/create` | إنشاء حالة طوارئ |
| `GET,POST` | `/emergency/cases/<int:id>/edit` | تعديل حالة |
| `POST` | `/emergency/cases/<int:id>/resolve` | حل حالة |
| `POST` | `/emergency/start-treatment/<int:emergency_id>` | بدء علاج طارئ |
| `POST` | `/emergency/end-treatment/<int:emergency_id>` | إنهاء علاج طارئ |
| `GET,POST` | `/emergency/lab-request/<int:emergency_id>` | طلب مختبر عاجل |
| `GET,POST` | `/emergency/radiology-request/<int:emergency_id>` | طلب أشعة عاجل |
| `POST` | `/emergency/emergency-visits/<int:visit_id>/complete` | إكمال زيارة طوارئ |

### المختبر (Lab) — `/lab/`

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/lab/dashboard` | لوحة المختبر |
| `GET` | `/lab/worklist` | قائمة العمل (widgets: lab_pending, lab_recent) |
| `POST` | `/lab/worklist/claim/<int:request_id>` | استلام طلب |
| `POST` | `/lab/worklist/complete/<int:request_id>` | إكمال طلب |
| `GET,POST` | `/lab/worklist/request/<int:request_id>` | عرض/تعديل طلب |
| `GET` | `/lab/requests` | جميع الطلبات |
| `GET` | `/lab/results` | النتائج |
| `GET,POST` | `/lab/quality-control` | ضبط الجودة (QC) |
| `GET,POST` | `/lab/test-catalog` | كتالوج التحاليل |
| `POST` | `/lab/test-catalog/add` | إضافة تحليل |
| `POST` | `/lab/test-panels/add` | إضافة باقة تحاليل |

### الأشعة (Radiology) — `/radiology/`

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/radiology/dashboard` | لوحة الأشعة |
| `GET` | `/radiology/worklist` | قائمة العمل |
| `POST` | `/radiology/worklist/claim/<int:request_id>` | استلام طلب |
| `POST` | `/radiology/worklist/complete/<int:request_id>` | إكمال طلب |
| `GET` | `/radiology/requests` | الطلبات |
| `GET` | `/radiology/results` | النتائج |
| `POST` | `/radiology/results/<int:result_id>/second-review` | مراجعة ثانية |
| `GET` | `/radiology/api/report-templates` | قوالب التقارير |
| `POST` | `/radiology/api/report-templates` | إنشاء قالب |
| `GET` | `/radiology/api/report-macros` | ماكروات |

### الصيدلية (Pharmacy) — `/medication/`

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/medication/dashboard` | لوحة الصيدلية |
| `GET` | `/medication/pos` | نقطة البيع (POS) |
| `POST` | `/medication/pos/sell` | بيع مباشر |
| `POST` | `/medication/prescriptions/dispense/<int:prescription_id>` | صرف روشتة |
| `GET` | `/medication/prescriptions` | الروشيتات الواردة |
| `GET` | `/medication/inventory` | المخزون |
| `GET,POST` | `/medication/suppliers/add` | إضافة مورد |
| `GET` | `/medication/stock-alerts` | تنبيهات مخزون منخفض |
| `GET` | `/medication/interactions` | التفاعلات الدوائية |

### التمريض (Nursing) — `/nurse/`

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/nurse/dashboard` | لوحة التمريض (widget: nurse_assigned) |
| `GET,POST` | `/nurse/record-vital-signs/<int:patient_id>` | تسجيل علامات حيوية |
| `GET` | `/nurse/medication-administration` | eMAR إدارة أدوية |
| `POST` | `/nurse/administer-medication/<int:prescription_item_id>` | تأكيد صرف دواء |
| `GET` | `/nurse/patient-care` | رعاية المرضى |
| `GET,POST` | `/nurse/tasks/create` | إنشاء مهمة تمريض |

---

## الفوترة والمحاسبة (Billing / Accounting)

### المحاسب (Accountant) — `/accountant/`

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/accountant/dashboard` | لوحة المحاسب (widgets: finance_overview, revenue_today, pending_payments) |
| `GET` | `/accountant/invoices` | الفواتير |
| `POST` | `/accountant/invoices/new` | إنشاء فاتورة |
| `GET` | `/accountant/payments` | الدفعات |
| `POST` | `/accountant/payments/new` | تسجيل دفعة |
| `GET` | `/accountant/receipts` | الإيصالات |
| `GET` | `/accountant/insurance-claims` | مطالبات التأمين |
| `GET` | `/accountant/reports` | التقارير المالية |
| `GET` | `/accountant/pricing` | قائمة الأسعار |

### المدير (Manager) — `/manager/`

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/manager/dashboard` | لوحة المدير (widgets: kpi_strip, manager_finance, manager_hr, queue_live) |
| `GET` | `/manager/unit-control` | التحكم في الوحدات (تفعيل/تعطيل) |
| `GET` | `/manager/staff` | إدارة الطاقم |
| `GET,POST` | `/manager/settings` | إعدادات المركز |
| `GET` | `/manager/reports` | التقارير الإدارية |
| `GET` | `/manager/kpi-dashboard` | مؤشرات الأداء |

---

## بوابة المريض (Patient Portal) — `/portal/`

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/portal/dashboard` | لوحة المريض |
| `GET` | `/portal/appointments` | مواعيدي |
| `GET,POST` | `/portal/book-appointment` | حجز موعد جديد |
| `GET` | `/portal/lab-results` | نتائج المختبر |
| `GET` | `/portal/radiology-results` | نتائج الأشعة |
| `GET` | `/portal/medical-records` | ملفي الطبي |
| `GET` | `/portal/prescriptions` | روشتاتي |
| `GET` | `/portal/bills` | فواتيري |
| `GET` | `/portal/documents` | مستنداتي |
| `GET,POST` | `/portal/feedback` | استبيان رضا |
| `GET,POST` | `/portal/settings` | إعدادات الحساب |

---

## API البرمجية (Programmatic API)

### FHIR R4

| الطريقة | المسار | المورد |
|---------|-------|---------|
| `GET` | `/api/fhir/Patient` | البحث عن مرضى |
| `GET` | `/api/fhir/Patient/<int:patient_id>` | مريض واحد |
| `GET` | `/api/fhir/Encounter` | الزيارات |
| `GET` | `/api/fhir/Observation` | الملاحظات (نتائج مختبر/أشعة) |
| `GET` | `/api/fhir/Observation/lab/<int:result_id>` | نتيجة مختبر |
| `GET` | `/api/fhir/DiagnosticReport/radiology/<int:result_id>` | تقرير أشعة |

### البحث (Search)

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/api/search` | بحث عام |
| `GET` | `/api/search/patients` | بحث مرضى (يدعم ngram 3+) |
| `GET` | `/api/tenants/search` | بحث مستأجرين (owner) |

### Webhooks

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `POST` | `/api/billing/stripe/webhook` | Stripe webhook |
| `POST` | `/hl7/ingest` | استيراد HL7 |
| `POST` | `/lab/api/hl7/import` | استيراد HL7 للمختبر |

---

## الصحة والمراقبة (Health / Monitoring)

| الطريقة | المسار | الوصف |
|---------|-------|---------|
| `GET` | `/health` | فحص صحة أساسي (load balancer) |
| `GET` | `/__health` | فحص صحة مفصل (DB, Redis, Migrations) |
| `GET` | `/metrics` | مقاييس Prometheus |
| `GET` | `/finance/slow-queries` | استعلامات بطيئة |
| `GET` | `/finance/slow-queries/weekly` | تقرير أسبوعي بطيء |

---

## رموز الحالة (HTTP Status Codes)

| الكود | المعنى |
|------|--------|
| `200` | نجاح (GET, PUT, POST مع إرجاع بيانات) |
| `201` | تم الإنشاء (POST مع Location header) |
| `302` | تحويل (form submissions مع redirect) |
| `400` | طلب خاطئ (validation error) — JSON: `{"success": false, "message": "..."}` |
| `401` | غير مصادق (جلسة منتهية) |
| `403` | ممنوع (دور/وحدة غير مسموحة) — `ModuleNotEnabledError` |
| `404` | غير موجود |
| `500` | خطأ خادم (مُسجل في Sentry/logs) |

---

## تنسيق الأخطاء (Error Format)

```json
{
  "success": false,
  "message": "رسالة خطأ بالعربية",
  "errors": { "field": ["تفاصيل"] }  // اختياري، لأخطاء validation
}
```

---

## التصفية والترقيم (Pagination)

للأ endpoints التي تُرجع قوائم:
- `?page=1&per_page=20` (افتراضي 20، حد أقصى 100)
- الاستجابة تحتوي على: `items`, `total`, `page`, `per_page`, `pages`

---

## الترخيص

هذا المرجع يغطي المسارات الفعلية المسجلة في الكود (commit `e69c81c0`). للمسارات الداخلية/الخاصة بالواجهة (templates، static) راجع الكود مباشرة.