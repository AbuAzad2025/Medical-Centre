# سيناريو: رحلة مريض كاملة — من دخوله للمركز حتى خروجه

> **الحزمة:** `doctor_clinic_full` (reception, doctor, billing, lab, radiology, appointments, pharmacy, reporting)
> **الأدوار:** reception → doctor → lab → radiology → pharmacy → accountant → manager
> **الوحدات المطلوبة:** reception, doctor, lab, radiology, pharmacy, billing
> **RLS:** كل خطوة تُقرأ/تُكتب ضمن `tenant_id` + `app.tenant_id` (FORCE RLS)
> **المرجع:** `docs/API_REFERENCE.md` (753 مسار فعلي)

---

## 0. تمهيد: إعداد المركز (مرة واحدة)

```bash
# 1. نشر نظام
# 2. ترحيل قاعدة البيانات
flask db upgrade

# 3. بذر RBAC + الحزم + الوحدات
python -c "from app_factory import create_app; from app.core.tenant.models import seed_default_bundles; from app.bootstrap.rbac_seed import seed_rbac_and_catalogs; from seeds.production_baseline import platform_tenant_scope; from app.core.platform_bootstrap import ensure_module_definitions; app=create_app('production'); exec(open('scripts/ops/bootstrap_platform.py').read())"

# 4. إنشاء مستأجر (مركز) — via API
POST /api/saas/register
{
  "slug": "clinic-1",
  "name": "عيادة الشفاء",
  "contact_email": "admin@clinic-1.com",
  "admin_username": "admin",
  "admin_password": "AdminPass123!",
  "admin_full_name": "مدير العيادة",
  "package_version_id": 1,
  "billing_type": "monthly"
}
# → 201: tenant_id=1, modules activated: reception, doctor, billing, lab, radiology, appointments, pharmacy, reporting
```

---

## 1. مرحلة الاستقبال (Reception) — 08:00

### 1.1. تسجيل الدخول
```
POST /auth/login  { "username": "receptionist", "password": "RecPass123!", "tenant_slug": "clinic-1" }
# → 200 OK → redirect /reception/dashboard (module 'reception' active ✓)
```

### 1.2. تسجيل مريض جديد
```
POST /reception/add_patient
{
  "first_name": "أحمد", "last_name": "محمد",
  "national_id": "1234567890", "phone": "0501234567",
  "date_of_birth": "1985-03-15", "gender": "male",
  "allergies": ["penicillin"]
}
# → 302 Redirect: /reception/patients
# DB writes: patients (tenant_id=1, first_name AES-SIV encrypted, national_id_hash HMAC blind index)
# RLS: tenant_id=1 enforced
```

### 1.3. فتح زيارة
```
POST /reception/visits/create
{ "patient_id": 1, "department": "عيادة عامة", "doctor_id": 2, "visit_type": "consultation", "chief_complaint": "ألم في الصدر منذ 3 أيام" }
# → 302 Redirect: /reception/queue
# DB writes: visits (tenant_id=1, status=OPEN), queue_tickets (status=WAITING)
```

### 1.4. إضافة لطابور
```
POST /reception/queue/add-patient  { "patient_id": 1, "department_id": 1, "priority": "normal" }
# → 200 OK {"success": true, "ticket_id": 1}
# DB writes: queue_tickets (tenant_id=1, ticket_number=1, status=WAITING)
```

**الاستقبال يرى:** لوحة `/reception/dashboard` — widget: `queue_live` (الطابور الحي)، `visits_today`. المريض في الطابور بحالة `WAITING`.

---

## 2. مرحلة العيادة (Doctor) — 08:30

### 2.1. طبيب يرى الطابور
```
POST /auth/login (doctor) → redirect /doctor/dashboard
GET /doctor/dashboard
# widgets: my_queue, patients_waiting, appointments_pending, lab_pending, radiology_pending
GET /doctor/patient-queue  → قائمة الزيارات المعلقة (status=OPEN/CHECKED_IN)
```

### 2.2. بدء العلاج
```
POST /doctor/start-treatment/1
# → 200 OK {"success": true}
# DB: visits.status=IN_PROGRESS, started_at=now(); queue_tickets.status=IN_TREATMENT
```

### 2.3. فحص SOAP + تشخيص
```
GET /doctor/patient-details/1  → datos المريض (اسم، عمر، حساسيات، سجل طبي)

POST /doctor/notes/1
{
  "subjective": "ألم في الصدر منذ 3 أيام، يتفاقم مع المجهود، يخف بالراحة.",
  "objective": "BP 130/85، HR 78، RR 16، SpO2 98%. ECG: NSR، no ST changes.",
  "assessment": "ألم صدري للاستقصاء (chest pain for investigation). استبعاد ACS.",
  "plan": "ECG، troponin، CBC، lipid panel. تقييم مخاطر cardiovascular."
}
# DB writes: medical_records (tenant_id=1, visit_id=1, SOAP JSON)

POST /doctor/diagnosis/1  { "icd10_code": "R07.9", "diagnosis_type": "primary" }
# DB writes: diagnoses (tenant_id=1, ICD-10 code)
```

### 2.4. طلب مختبر
```
POST /doctor/lab-request/1
{ "tests": ["CBC", "Troponin I", "Lipid Panel", "BMP"], "priority": "urgent", "clinical_notes": "chest pain workup — rule out ACS" }
# → 200 OK {"success": true, "request_id": 1}
# DB writes: lab_requests (tenant_id=1, visit_id=1, status=REQUESTED, priority=urgent)
#            lab_request_items: CBC, Troponin I, Lipid Panel, BMP
```

### 2.5. طلب أشعة
```
POST /doctor/radiology-request/1
{ "modality": "XRAY", "body_part": "Chest", "clinical_notes": "PA view — rule out cardiomegaly" }
# → 200 OK {"success": true, "request_id": 1}
# DB writes: radiology_requests (tenant_id=1, visit_id=1, status=REQUESTED, modality=XRAY)
```

### 2.6. كتابة روشتة (e-prescription)
```
POST /doctor/prescription/1
{
  "items": [
    {"medication_id": 5, "dosage": "10mg", "frequency": "once daily", "duration_days": 30, "quantity": 30},
    {"medication_id": 12, "dosage": "81mg", "frequency": "once daily", "duration_days": 30, "quantity": 30}
  ],
  "notes": "Aspirin + Atorvastatin. Monitor for interactions."
}
# → 200 OK {"success": true, "prescription_id": 1}
# DB writes: prescriptions (tenant_id=1, status=PENDING), prescription_items (2 items)
#            drug_interaction_check: فحص تلقائي → لا تفاعلات حرجة
```

### 2.7. إنهاء العلاج
```
POST /doctor/end-treatment/1
# → 200 OK {"success": true}
# DB: visits.status=COMPLETED, completed_at=now(); queue_tickets.status=COMPLETED
```

---

## 3. مرحلة المختبر (Lab) — 09:15

### 3.1. فني المختبر يرى قائمة العمل
```
POST /auth/login (lab technician) → redirect /lab/dashboard
GET /lab/worklist  → قائمة الطلبات (status=REQUESTED، priority=urgent)
# widget: lab_pending, lab_recent
```

### 3.2. استلام طلب + سحب عينة
```
POST /lab/worklist/claim/1
# → 200 OK {"success": true}
# DB: lab_requests.status=IN_PROGRESS, claimed_by=lab_tech_id

POST /lab/barcode/scan/SAMPLE-001
# → 200 OK {"success": true, "request_id": 1}
# DB: lab_specimens (tenant_id=1, barcode="SAMPLE-001", collected_at=now())
```

### 3.3. إدخال النتائج
```
POST /lab/worklist/request/1
{
  "results": {
    "CBC": {"WBC": 7.2, "RBC": 4.8, "HGB": 14.2, "PLT": 250},
    "Troponin I": {"value": 0.02, "unit": "ng/mL"},
    "Lipid Panel": {"Total Chol": 210, "LDL": 130, "HDL": 45, "TG": 150},
    "BMP": {"Glucose": 95, "Na": 140, "K": 4.2, "Cl": 102, "BUN": 15, "Cr": 0.9}
  },
  "notes": "All within normal range except LDL slightly elevated"
}
# → 200 OK {"success": true}
# DB: lab_results (tenant_id=1, results JSONB, entered_by=lab_tech_id)
#     lab_result_values: كل قيمة مع نطاق مرجعي + flag (normal/abnormal)
```

### 3.4. اعتماد النتيجة (Validation)
```
POST /lab/worklist/complete/1
# → 200 OK {"success": true}
# DB: lab_results.status=VALIDATED, validated_by=lab_tech_id, validated_at=now()
```

**النتيجة:** النتائج متاحة للطبيب وللبوابة (بعد الموافقة).

---

## 4. مرحلة الأشعة (Radiology) — 09:45

### 4.1. فني الأشعة يرى الطلب
```
POST /auth/login (radiology tech) → redirect /radiology/dashboard
GET /radiology/worklist  → طلبات الأشعة (status=REQUESTED)
# widget: radiology_pending
```

### 4.2. استلام + التقاط صورة
```
POST /radiology/worklist/claim/1
# → 200 OK {"success": true}
# DB: radiology_requests.status=IN_PROGRESS, claimed_by=radiology_tech_id

POST /radiology/api/ai-assist
{ "request_id": 1, "image_data": "base64-encoded-dicom" }
# → 200 OK {"success": true, "ai_analysis": {...}}
# DB: radiology_ai_results (ai_findings, ai_impression — إذا فُعّلت AI Imaging)
```

### 4.3. كتابة تقرير + توقيع
```
POST /radiology/worklist/complete/1
{
  "findings": "No cardiomegaly. Lungs clear. No infiltrates. Costophrenic angles sharp.",
  "impression": "Normal chest X-ray. No acute cardiopulmonary pathology.",
  "is_critical": false
}
# → 200 OK {"success": true}
# DB: radiology_results (tenant_id=1, findings, impression, signed_by=radiology_tech_id)
#     radiology_request.status=DONE
```

---

## 5. مرحلة الصيدلية (Pharmacy) — 10:15

### 5.1. صيدلي يرى الروشيتة
```
POST /auth/login (pharmacist) → redirect /medication/dashboard
GET /medication/prescriptions  → قائمة الروشيتات (status=PENDING)
# widget: pharmacy_prescriptions, pharmacy_dispense
```

### 5.2. صرف الروشيتة
```
POST /medication/prescriptions/dispense/1
{
  "items": [
    {"item_id": 1, "quantity_dispensed": 30, "batch_number": "BATCH-001", "expiry_date": "2027-06-30"},
    {"item_id": 2, "quantity_dispensed": 30, "batch_number": "BATCH-002", "expiry_date": "2027-12-31"}
  ],
  "notes": "Patient counselled on side effects"
}
# → 200 OK {"success": true}
# DB writes:
#   prescription_dispense_logs (tenant_id=1, dispensed_by=pharmacist_id)
#   medication_stock: quantity decremented for both items
#   stock_movements: OUT (dispense) for each item
#   prescriptions: status=DISPENSED
#   drug_interaction_check: فحص تلقائي (passed)
```

### 5.3. بيع مباشر (POS) — إن وُجد
```
POST /medication/pos/sell
{ "items": [{"medication_id": 10, "quantity": 1, "price": 15.00}], "payment_method": "cash", "customer_name": "أحمد محمد" }
# → 200 OK {"success": true, "sale_id": 1}
# DB: pharmacy_sales (tenant_id=1, total=15.00), pharmacy_sale_items, medication_stock decremented, invoices auto-generated
```

---

## 6. مرحلة الفوترة (Billing) — 10:45

### 6.1. محاسب يرى الفواتير
```
POST /auth/login (accountant) → redirect /accountant/dashboard
GET /accountant/invoices  → فواتير الزيارة (status=PENDING)
# widget: finance_overview, revenue_today, pending_payments
```

### 6.2. إنشاء فاتورة
```
POST /accountant/invoices/new
{
  "visit_id": 1, "patient_id": 1,
  "services": [
    {"service_code": "CONS-001", "description": "استشارة عامة", "price": 150.00, "quantity": 1},
    {"service_code": "LAB-001", "description": "CBC + Troponin + Lipid + BMP", "price": 80.00, "quantity": 1},
    {"service_code": "RAD-001", "description": "Chest X-ray PA", "price": 120.00, "quantity": 1},
    {"service_code": "MED-001", "description": "Aspirin 10mg × 30", "price": 25.00, "quantity": 1},
    {"service_code": "MED-002", "description": "Atorvastatin 81mg × 30", "price": 45.00, "quantity": 1}
  ],
  "insurance_provider": "شركة التأمين (اختياري)", "discount_percent": 0
}
# → 200 OK {"success": true, "invoice_id": 1, "total": 420.00}
# DB: invoices (tenant_id=1, visit_id=1, total=420.00, status=PENDING)
#     invoice_items (5 items), invoice_audit (created_by=accountant_id)
```

### 6.3. تسجيل دفعة
```
POST /accountant/payments/new
{ "invoice_id": 1, "amount": 420.00, "payment_method": "cash", "received_by": "receptionist", "notes": "دفع نقدي كامل" }
# → 200 OK {"success": true, "payment_id": 1, "receipt_number": "RCP-0001"}
# DB: payments (tenant_id=1, invoice_id=1, amount=420.00, method=cash)
#     invoices.status=PAID, paid_at=now()
#     receipts (tenant_id=1, payment_id=1, receipt_number="RCP-0001")
#     cash_register: cash in +420.00
```

### 6.4. طباعة إيصال
```
GET /reception/print_receipt/1  → PDF/EHTML إيصال: RCP-0001، المريض، الخدمات، المبلغ، التاريخ
```

---

## 7. مرحلة التقارير (Reporting) — 11:30

### 7.1. تقرير زيارة
```
GET /doctor/print-medical-report/1  → PDF: SOAP + ICD-10 + نتائج مختبر + أشعة + روشتة + توقيع
```

### 7.2. تقرير مالي يومي (مدير/محاسب)
```
GET /accountant/reports?type=daily&date=2026-10-25
# → إيرادات اليوم: 420.00 (زيارة #1)
# → widget: revenue_today = 420.00
```

### 7.3. تقرير أداء (مدير)
```
GET /manager/kpi-dashboard
# → KPI: visits_today=1, revenue_today=420.00, patients_waiting=0
# → widget: kpi_strip, manager_finance, manager_hr
```

---

## 8. مرحلة الخروج (Patient Exit) — 12:00

### 8.1. بوابة المريض (Portal)
```
POST /auth/login (patient) → redirect /portal/dashboard
GET /portal/dashboard  → widgets: appointments_pending
GET /portal/lab-results  → Troponin I: 0.02 ng/mL (normal) + باقي التحاليل
GET /portal/radiology-results  → Chest X-ray: Normal
GET /portal/prescriptions  → Aspirin 10mg × 30، Atorvastatin 81mg × 30
GET /portal/bills  → Invoice #1: 420.00 (PAID) — RCP-0001
```

### 8.2. إغلاق الزيارة (تلقائي)
```
# visits: status=COMPLETED (end-treatment + صرف + دفع)
# queue_tickets: status=COMPLETED
# invoices: status=PAID
# prescriptions: status=DISPENSED
```

---

## 9. ملخص RLS / العزل في كل خطوة

| الخطوة | جدول | tenant_id | RLS | ملاحظة |
|--------|-------|-----------|-----|--------|
| تسجيل مريض | `patients` | 1 | ✅ FORCE | AES-SIV encrypted، HMAC blind index |
| فتح زيارة | `visits` | 1 | ✅ FORCE | status: OPEN → IN_PROGRESS → COMPLETED |
| طلب مختبر | `lab_requests` | 1 | ✅ FORCE | priority=urgent |
| طلب أشعة | `radiology_requests` | 1 | ✅ FORCE | modality=XRAY |
| كتابة روشتة | `prescriptions` | 1 | ✅ FORCE | drug_interaction_check auto |
| إدخال نتائج | `lab_results` | 1 | ✅ FORCE | validated_by=lab_tech |
| تقرير أشعة | `radiology_results` | 1 | ✅ FORCE | signed_by=radiology_tech |
| صرف روشتة | `prescription_dispense_logs` | 1 | ✅ FORCE | stock decremented |
| فاتورة | `invoices` | 1 | ✅ FORCE | total=420.00 |
| دفعة | `payments` | 1 | ✅ FORCE | method=cash |
| إيصال | `receipts` | 1 | ✅ FORCE | RCP-0001 |
| تقرير مالي | `audit_trails` | 1 | ✅ FORCE | immutable (NO DELETE) |
| بحث مريض | `patient_search_ngrams` | 1 | ✅ FORCE | trigram 3+ chars |

**العزل (Cross-tenant isolation):**
- مستأجر آخر (`tenant_id=2`) يحاول `SELECT * FROM patients` → RLS returns 0 rows
- مستأجر آخر يحاول `INSERT INTO patients (tenant_id=1, ...)` → WITH CHECK fails → 422/403
- مستأجر مع وحدة `pharmacy` مطفأة يحاول `SELECT * FROM prescriptions` → `filter(false())` → 0 rows

---

## 10. الجدول الزمني (Timeline)

| الوقت | المرحلة | الدور | الإجراء الرئيسي |
|-------|---------|-------|------------------|
| 08:00 | استقبال | Reception | تسجيل مريض + فتح زيارة |
| 08:15 | استقبال | Reception | إضافة لطابور |
| 08:30 | عيادة | Doctor | بدء علاج + SOAP + تشخيص |
| 08:45 | عيادة | Doctor | طلب مختبر + أشعة + روشتة |
| 09:00 | عيادة | Doctor | إنهاء علاج |
| 09:15 | مختبر | Lab Tech | استلام + سحب عينة + نتائج + اعتماد |
| 09:45 | أشعة | Radiology Tech | استلام + صورة + تقرير + توقيع |
| 10:15 | صيدلية | Pharmacist | صرف روشتة + خصم مخزون |
| 10:45 | فوترة | Accountant | فاتورة + دفعة + إيصال |
| 11:30 | تقارير | Manager | KPI + تقرير مالي |
| 12:00 | بوابة | Patient | عرض نتائج + فواتير + روشتات |

---

## 11. حالات الحافة (Edge Cases)

| السيناريو | المعالجة |
|-----------|----------|
| **المريض يلغي الزيارة** | `POST /reception/visits/<id>/cancel` → status=CANCELLED، طابور يُلغى، فاتورة ملغاة |
| **طبيب غير متاح** | `POST /reception/visits/<id>/transfer` → تحويل لطبيب آخر، queue ticket يُحدَّث |
| **نتيجة حرجة (Troponin > 0.5)** | `is_critical=true` → تنبيه فوري، إشعار للطبيب، `critical_alerts` |
| **تفاعل دوائي** | فحص تلقائي عند صرف → تحذير `drug_interaction_warning`، pharmacist يؤكد أو يرفض |
| **روشتة منتهية** | `prescription.status=EXPIRED` (بعد `expiry_date`)، صيدلي يرفض الصرف |
| **مريض بدون هوية** | `national_id` اختياري، بحث عبر `patient_search_ngrams` (اسم 3+ أحرف) |
| **مستأجر مع وحدة `pharmacy` مطفأة** | `/medication/*` → 403 `ModuleNotEnabledError`، `/doctor/prescription` → روشتة تُحفظ لكن لا تُصرف |

---

## 12. التحقق بعد السيناريو (Verification Queries)

```sql
-- 1. تحقق من عزل المستأجر
SELECT tenant_id, count(*) FROM patients GROUP BY tenant_id;
-- → tenant_id=1: 1 مريض (أحمد محمد)

-- 2. تحقق من RLS
SET LOCAL app.tenant_id = '2';
SELECT count(*) FROM patients;  -- → 0 (لا يرى مرضى clinic-1)

-- 3. تحقق من الوحدات النشطة
SELECT module_name, is_active FROM tenant_modules WHERE tenant_id = 1;
-- → reception, doctor, billing, lab, radiology, appointments, pharmacy, reporting (8 active)

-- 4. تحقق من الفاتورة
SELECT invoice_number, total, status FROM invoices WHERE tenant_id = 1;
-- → INV-0001, 420.00, PAID

-- 5. تحقق من audit trail (immutable)
SELECT action, table_name, created_at FROM audit_trails WHERE tenant_id = 1 ORDER BY created_at;
-- → INSERT patients, INSERT visits, INSERT lab_requests, INSERT radiology_requests,
--    INSERT prescriptions, INSERT invoices, INSERT payments, INSERT receipts
```

---

## 13. مراجع

- **API Reference:** `docs/API_REFERENCE.md` (753 مسار فعلي)
- **معمارية:** `docs/ARCHITECTURE.md` (Multi-tenancy، Module System، RBAC، RLS)
- **دليل المستخدم:** `docs/USER_GUIDE.md` (أدوار، واجهات، سيناريوهات)
- **حالة المنصة:** `docs/PLATFORM_STATUS.md` (أرقام متحققة)
- **النشر:** `docs/DEPLOYMENT.md` (Docker، CI/CD، secrets)
- **العمليات:** `docs/OPERATIONS.md` (مراقبة، نسخ احتياطي، استكشاف أخطاء)

---

*هذا السيناريو يوضح رحلة مريض كاملة في حزمة `doctor_clinic_full`. للحزم الأخرى (standalone_pharmacy، standalone_lab، hospital...)، اتبع نفس النمط مع تفعيل/تعطيل الوحدات حسب الباقة.*