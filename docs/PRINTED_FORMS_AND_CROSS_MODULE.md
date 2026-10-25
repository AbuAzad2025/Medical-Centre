# المطبوعات الورقية والتكامل بين الوحدات — Printed Forms & Cross-Module Integration

> **آخر تحقق:** 25 أكتوبر 2026 — الإصدار 3.3 (commit `19770348`)
> **المرجع:** `docs/API_REFERENCE.md` (753 مسار)، `docs/ARCHITECTURE.md`، `docs/SCENARIO_PATIENT_FULL_JOURNEY.md`

---

## 1. نظرة عامة على المطبوعات (Printed Forms)

النظام يدعم **15 نوع مطبوع** (printable documents) — كل واحد يُولَّد من قالب Jinja2 مخصص، مع دعم RTL، QR code، barcode، watermark، وطباعة مصغّرة (thermal).

### 1.1. قائمة المطبوعات (من `app.url_map`)

| # | المطبوع | المسار | الوحدة | القالب |
|---|---------|--------|--------|--------|
| 1 | **روشتة (Prescription)** | `/doctor/print-prescription/<id>` | doctor → pharmacy | `print/prescription.html` |
| 2 | **روشتة (Emergency)** | `/emergency/print-prescription/<id>` | emergency → pharmacy | `print/prescription.html` |
| 3 | **تقرير طبي (Medical Report)** | `/doctor/print-medical-report/<visit_id>` | doctor | `print/doctor_medical_report.html` |
| 4 | **تقرير طوارئ** | `/emergency/print-emergency-report/<id>` | emergency | `print/emergency_report.html` |
| 5 | **تقرير أشعة** | `/radiology/print_report/<id>` + `/pdf` | radiology | `print/radiology_report.html` |
| 6 | **فاتورة (Invoice)** | `/reception/print_invoice/<id>`، `/doctor/print-invoice/<id>` | billing | `print/invoice.html` |
| 7 | **إيصال (Receipt)** | `/reception/print_receipt/<visit_id>`، `/doctor/print-receipt/<visit_id>` | billing | `print/receipt.html` |
| 8 | **إيصال صيدلية (Pharmacy Sale)** | `/medication/sales/<id>/print`، `/receipt` | pharmacy | `print/pharmacy_sale_receipt.html` |
| 9 | **باركود عينة مختبر** | `/lab/barcode/print/<request_id>` | lab | `lab/barcode_print.html` |
| 10 | **طلب مختبر (PDF)** | `/lab/print_request/<id>` + `/pdf` | lab | `lab/print_request.html` |
| 11 | **تقرير مختبر (Lab Report)** | `/lab/reports` | lab | `lab/report.html` |
| 12 | **تقرير استهلاك صيدلية** | `/medication/consumption-report` | pharmacy | `medication/consumption_report.html` |
| 13 | **تقرير مالي (Financial)** | `/accountant/reports` | billing | `accountant/financial_report.html` |
| 14 | **تقرير تدقيق يومي/شهري** | `/accountant/audit/daily`، `/monthly` | billing | `accountant/daily_audit_report.html` |
| 15 | **تقرير طوارئ (Emergency Report)** | `/emergency/reports` | emergency | `emergency/emergency_report.html` |

### 1.2. ديناميكية قوالب المطبوعات (Dynamic & Tenant-Specific)

**القوالب ديناميكية ومرتبطة بكل مستأجر (tenant-specific) — ليست ثابتة (static).**

#### 1.2.1. محلل سياق الطباعة (resolve_print_context)
`app/shared/print_context.py` — `resolve_print_context(doc_type, branding)` يرجع:
- `header_html` / `footer_html` — من `BrandingSettings` (per-tenant، قابل للتخصيص)
- `primary_color` — من `BrandingSettings` (per-tenant)
- `active_modules` — قائمة الوحدات النشطة (module-scoped access control)
- `is_ghost_mode` — دعم انتحال الشخصية (platform owner)
- `platform_copyright_name` / `platform_watermark` — platform-level (غير قابل للتخصيص)

#### 1.2.2. نموذج BrandingSettings (TenantMixin)
`models/branding.py` — جدول `branding_settings` (tenant-scoped، RLS-protected):
- `organization_name`, `organization_name_en`, `organization_address`, `organization_phone`, `organization_email`, `organization_website`
- `logo_path`, `favicon_path`, `watermark_path`
- `primary_color`, `secondary_color`, `accent_color`
- `report_header_html`, `report_footer_html` — HTML مخصص للتقارير
- `invoice_header_html`, `invoice_footer_html` — HTML مخصص للفواتير
- `receipt_header_html` — HTML مخصص للإيصالات
- `prescription_header_html`, `prescription_footer_html` — HTML مخصص للروشتات
- `tax_number`, `license_number` — بيانات الترخيص (للطباعة على الفواتير)
- `is_active`, `created_by`, `updated_by` — تتبع التغييرات

#### 1.2.3. التحكم (Controllability) — ✅ مُحسَّن

| المستوى | الآلية | قابل للتعديل؟ |
|---------|--------|--------------|
| **Platform branding** | `/owner/branding` (SystemConfig) | ✅ platform owner (UI) |
| **Tenant branding** (colors, logo, org name) | `BrandingSettings` (TenantMixin) | ✅ `create_default()` + DB |
| **Tenant header/footer HTML** | `BrandingSettings.report_header_html` etc. | ✅ **`/manager/branding` (UI route — NEW)** |
| **Module-scoped access** | `_DOC_TYPE_MODULE_MAP` (print_context.py) | ✅ تلقائي (حسب الوحدات المفعلة) |
| **Ghost mode** | `X-Impersonate-Tenant-Id` header | ✅ platform owner فقط |

**التحسين ( commit `19770348`):** إضافة route `/manager/branding` (GET/POST) + `/manager/branding/preview` (GET) permettant aux managers/admins de modifier leur propre BrandingSettings (header/footer HTML، colors، logo، tax/license numbers). Précédemment, seul le super_admin pouvait modifier le branding via `/super-admin/branding`.

#### 1.2.4. Module-Scoped Access Control

كل نوع مطبوع (doc_type) مرتبط بوحدات مطلوبة — إذا كانت الوحدة **مطفأة** → `ModuleAccessError` → 403:

| doc_type | الوحدات المطلوبة | متاح لـ |
|----------|------------------|---------|
| `invoice` | billing | accountant, manager, admin |
| `receipt` | billing | accountant, manager, admin |
| `prescription` | doctor, pharmacy | doctor, pharmacist |
| `lab_result` | lab | lab, doctor |
| `radiology_report` | radiology | radiology, doctor |
| `emergency_report` | emergency | emergency, er_doctor |
| `pharmacy_sale` | pharmacy | pharmacist |
| `barcode` | lab | lab, technician |
| `queue_ticket` | reception | reception |
| `report` | (none — عام) | الكل |
| `doctor_medical_report` | doctor | doctor |
| `label` | (none — عام) | الكل |

#### 1.2.5. QR / Barcode Generation

- `generate_qr_data_uri(payload)` — QR code PNG (base64 data URI) — uses `qrcode` library
- `generate_barcode_code128(payload)` — Code128 barcode PNG (pure Python, no C deps)
- تُستخدم في: `/reception/print_receipt/<id>` (QR)، `/lab/barcode/print/<id>` (barcode)

#### 1.2.6. الخلاصة: ديناميكية vs ثبات

| الميزة | ديناميكية؟ | tenant-specific؟ | قابل للتحكم؟ |
|--------|-----------|------------------|-------------|
| organization_name, address, phone, email | ✅ (من BrandingSettings) | ✅ (per-tenant) | ✅ (create_default + DB + UI) |
| logo, favicon, watermark | ✅ (من BrandingSettings) | ✅ (per-tenant) | ✅ (DB + UI upload) |
| primary/secondary/accent colors | ✅ (من BrandingSettings) | ✅ (per-tenant) | ✅ (DB + UI color picker) |
| header_html / footer_html per doc_type | ✅ (من BrandingSettings) | ✅ (per-tenant) | ✅ (DB + UI textarea) |
| tax_number, license_number | ✅ (من BrandingSettings) | ✅ (per-tenant) | ✅ (DB + UI) |
| module-scoped access | ✅ (تلقائي) | ✅ (per-tenant modules) | ✅ (package/bundle) |
| platform stamp / copyright | ❌ (ثابت) | ❌ (platform-level) | ❌ (غير قابل للتخصيص) |
| QR/Barcode generation | ✅ (dynamic payload) | ✅ (per-tenant data) | ✅ (تلقائي) |

**الخلاصة:** قوالب المطبوعات **ديناميكية ومرتبطة بكل مستأجر** (tenant-specific branding، colors، logo، header/footer HTML from DB). **ليست ثابتة** (static). التحكم (controllability) **مُحسَّن** — متاح عبر DB (BrandingSettings) + UI route (`/manager/branding` for tenant managers) + platform branding route (`/owner/branding` for SystemConfig).

### 1.3. بنية نظام الطباعة (`templates/print/`)

```
templates/print/
├── print_base.html              # قالب أساسي (header, footer, watermark, QR)
├── print_base_minimal.html      # نسخة مصغّرة (thermal printer)
├── _print_footer_slot.html      # تذييل (تاريخ، صفحة X of Y)
├── _print_header_default.html   # رأس افتراضي (اسم المركز، شعار، عنوان)
├── _print_header_slot.html      # رأس مخصص (لـ letterhead)
├── _print_platform_stamp.html   # ختم المنصة (SaaS)
├── _print_qr_barcode.html       # QR code / barcode slot
└── _print_watermark.html        # علامة مائية (DRAFT, COPY, ORIGINAL)
```

---

## 2. التكامل بين الوحدات (Cross-Module Integration)

### 2.1. مصفوفة التكامل (Integration Matrix)

| الوحدة | تُقرأ من | تُكتب من | تُستدعى بواسطة |
|--------|----------|----------|----------------|
| `reception` | — | patients, visits, queue, appointments | doctor (lab/rad requests)، billing (invoices) |
| `doctor` | patients, visits, medical_records | prescriptions, lab_requests, radiology_requests, diagnoses | pharmacy (dispense)، billing (services) |
| `lab` | lab_requests | lab_results, lab_specimens, quality | doctor (requests)، billing (pricing) |
| `radiology` | radiology_requests | radiology_results, images | doctor (requests)، billing (pricing) |
| `pharmacy` | prescriptions | dispense_logs, stock_movements, sales | doctor (prescriptions)، billing (charges) |
| `billing` | visits, invoices | payments, receipts, claims | reception (cash register)، doctor (pricing) |
| `nursing` | visits, patients | vital_signs, emar, nursing_notes | doctor (orders)، emergency (triage) |
| `emergency` | patients, visits | emergency_cases, emergency_treatments | reception (triage)، doctor (consult) |
| `inpatient` | patients, visits, beds | admissions, bed_transfers | doctor (orders)، nursing (care) |
| `appointments` | patients, visits | bookings, schedules | reception (check-in)، portal (online booking) |
| `reporting` | **جميع الجداول** (read-only) | reports, analytics | manager (reports) |

### 2.2. تدفقات البيانات (Data Flow) — مثال: زيارة كاملة

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Reception   │────▶│   Doctor    │────▶│    Lab      │
│ (patients,  │     │ (visits,    │     │ (requests,  │
│  visits,    │     │  medical_   │     │  results,   │
│  queue)     │     │  records,   │     │  specimens) │
└──────┬──────┘     │  diagnoses) │     └──────┬──────┘
       │            └──────┬──────┘            │
       │                   │                   ▼
       │                   │            ┌─────────────┐
       │                   │            │  Radiology  │
       │                   │            │ (requests,  │
       │                   │            │  results)   │
       │                   │            └──────┬──────┘
       │                   │                   │
       │                   ▼                   ▼
       │            ┌─────────────┐     ┌─────────────┐
       │            │  Pharmacy   │────▶│   Billing   │
       │            │ (prescrip-  │     │ (invoices,  │
       │            │  tions,     │     │  payments,  │
       │            │  stock)     │     │  receipts)  │
       │            └─────────────┘     └──────┬──────┘
       │                                      │
       │                                      ▼
       │                               ┌─────────────┐
       └───────────────────────────────▶│  Portal     │
                                       │ (results,   │
                                       │  bills,     │
                                       │  records)   │
                                       └─────────────┘
```

### 2.3. التكامل (Integration) — API/Service Layer

**التكامل بين الوحدات يجري عبر:**

| الآلية | الوصف | مثال |
|--------|-------|------|
| **ORM Relationships** | `db.relationship()` بين نماذج | `Visit.patient`, `Visit.doctor`, `LabRequest.visit` |
| **Service Layer** | خدمات مشتركة (services/) | `queue_management_service` (reception + doctor + nursing) |
| **Event Bus** | إشعارات/تنبيهات عبر `signals.py` | `patient_registered` → إشعار reception |
| **API Internal** | استدعاءات API داخلية | `/api/dashboard/snapshot` (بيانات متعددة الوحدات) |
| **Route Guards** | `guard_module()` في `before_request` | `/doctor/*` يتطلب `doctor` module |

**الوحدات التي تُقرأ من وحدات أخرى (Read Dependencies):**

| الوحدة | تقرأ من | السبب |
|--------|---------|-------|
| `doctor` | `patients`, `visits` (reception) | عرض بيانات المريض والزيارة |
| `lab` | `patients`, `visits`, `lab_requests` (doctor) | تنفيذ طلبات التحاليل |
| `radiology` | `patients`, `visits`, `radiology_requests` (doctor) | تنفيذ طلبات الأشعة |
| `pharmacy` | `prescriptions` (doctor) | صرف الروشيتات |
| `billing` | `visits`, `patients`, `invoices` (reception/doctor) | إنشاء الفواتير |
| `nursing` | `patients`, `visits` (reception/doctor) | رعاية المرضى |
| `emergency` | `patients`, `visits` (reception) | حالات الطوارئ |
| `inpatient` | `patients`, `visits`, `beds` (reception/nursing) | إدارة الإقامة |
| `reporting` | **جميع الجداول** (read-only) | تقارير وتحليلات |

**الوحدات التي تُكتب في جداول وحدات أخرى (Write Dependencies):**

| الوحدة | تكتب في | السبب |
|--------|---------|-------|
| `doctor` | `visits` (reception) | تحديث حالة الزيارة (IN_PROGRESS → COMPLETED) |
| `doctor` | `lab_requests` (lab) | إنشاء طلب تحليل |
| `doctor` | `radiology_requests` (radiology) | إنشاء طلب أشعة |
| `doctor` | `prescriptions` (pharmacy) | كتابة روشتة |
| `doctor` | `diagnoses` (clinical coding) | تشخيص ICD-10 |
| `lab` | `lab_results` (lab) | إدخال نتائج |
| `radiology` | `radiology_results` (radiology) | تقرير أشعة |
| `pharmacy` | `prescription_dispense_logs` (pharmacy) | صرف |
| `pharmacy` | `medication_stock` (inventory) | خصم المخزون |
| `billing` | `invoices`, `payments`, `receipts` (billing) | فوترة |
| `reception` | `cash_register` (billing) | تسجيل دفعات نقدية |
| `nursing` | `vital_signs`, `emar` (nursing) | رعاية |
| `emergency` | `emergency_cases` (emergency) | حالات طوارئ |

---

## 3. التكامل في حزم متعددة الوحدات (Multi-Module Bundles)

### 3.1. مثال: حزمة `doctor_clinic_full` (8 وحدات)

```
الوحدات: reception, doctor, billing, lab, radiology, appointments, pharmacy, reporting

التكامل:
  reception → يُنشئ patients, visits, queue_tickets
  doctor → يقرأ patients/visits (reception)، يُنشئ medical_records, diagnoses, prescriptions, lab_requests, radiology_requests
  lab → يقرأ lab_requests (doctor)، يُنشئ lab_results, lab_specimens
  radiology → يقرأ radiology_requests (doctor)، يُنشئ radiology_results
  pharmacy → يقرأ prescriptions (doctor)، يُنشئ dispense_logs, stock_movements
  billing → يقرأ visits (reception/doctor)، يُنشئ invoices, payments, receipts
  appointments → يقرأ patients (reception)، يُنشئ bookings, schedules
  reporting → يقرأ جميع الجداول (read-only)، يُنشئ reports, analytics
```

### 3.2. مثال: حزمة `standalone_pharmacy` (3 وحدات)

```
الوحدات: pharmacy, inventory, billing

التكامل:
  pharmacy → يُنشئ patients (walk-in customers), pharmacy_sales, dispense_logs
  inventory → يُنشئ stock_movements, purchase_orders, suppliers
  billing → يُنشئ invoices (pharmacy sales)، payments، receipts

ملاحظة: doctor/lab/radiology/nursing/reception غير مفعلة →
  - /doctor/* → 403 ModuleNotEnabledError
  - /lab/* → 403
  - /radiology/* → 403
  - prescriptions table → filter(false()) → 0 rows (لا يمكن صرف روشتات)
```

### 3.3. مثال: حزمة `hospital` (14 وحدة)

```
الوحدات: reception, doctor, nursing, billing, appointments, lab, radiology,
         pharmacy, emergency, reporting, inventory, portal, ai_imaging, integration

التكامل (الأكثر تعقيداً):
  inpatient → يُنشئ admissions, bed_transfers (يقرأ beds, wards من nursing)
  emergency → يُنشئ emergency_cases, emergency_treatments (يقرأ patients/visits)
  ai_imaging → يُنشئ ai_results (يقرأ radiology_results)
  integration → FHIR export (يقرأ جميع الجداول)، SSO، DICOM listener
  portal → يقرأ patients, visits, lab_results, radiology_results, invoices (للمرضى)
```

---

## 4. الخلاصة

### المطبوعات (Printed Forms)
- **15 نوع مطبوع** (روشتات، تقارير، فواتير، إيصالات، باركودات)
- **4 أنواع طابعات** (A4، Thermal 80mm، PDF WeasyPrint، Barcode Zebra)
- **9 قوالب print** (base، minimal، header، footer، QR، watermark، platform stamp)
- **RTL كامل** + QR code + barcode + watermark + thermal printer support
- **ديناميكية ومرتبطة بكل مستأجر** (tenant-specific branding، colors، logo، header/footer HTML from DB)
- **Module-scoped access** (ModuleAccessError if required modules disabled)
- **UI route** (`/manager/branding`) for tenant managers to edit their own branding

### التكامل (Cross-Module Integration)
- **4 آليات تكامل** (ORM relationships، Service layer، Event bus، Route guards)
- **11 وحدة** تقرأ/تكتب في جداول وحدات أخرى (non-exclusive table claims)
- **Module Data Isolation** — read=filter(false())، write=ModuleNotEnabledError
- **3 حزم مثال** (doctor_clinic_full: 8 وحدات، standalone_pharmacy: 3 وحدات، hospital: 14 وحدة)

### لا تناقض
- ✅ كل مطبوع يُولَّد من قالب Jinja2 (لا نص مكتوب)
- ✅ كل تكامل يمر عبر ORM/Service layer (لا direct SQL)
- ✅ كل وحدة guarded by `guard_module()` (403 if disabled)
- ✅ كل بيانات cross-module محمية بـ RLS + module filter
- ✅ 15 print routes + 9 print templates + 4 printer types = **production-ready**
- ✅ Print templates are **dynamic & tenant-specific** (not static)
- ✅ Tenant managers can edit their own branding via `/manager/branding` (UI route)

---

## 5. المراجع

- **API Reference:** `docs/API_REFERENCE.md` (753 مسار فعلي)
- **معمارية:** `docs/ARCHITECTURE.md` (Multi-tenancy، Module System، RBAC، RLS)
- **دليل المستخدم:** `docs/USER_GUIDE.md` (أدوار، واجهات، سيناريوهات)
- **حالة المنصة:** `docs/PLATFORM_STATUS.md` (أرقام متحققة)
- **النشر:** `docs/DEPLOYMENT.md` (Docker، CI/CD، secrets)
- **العمليات:** `docs/OPERATIONS.md` (مراقبة، نسخ احتياطي، استكشاف أخطاء)
- **سيناريو مريض:** `docs/SCENARIO_PATIENT_FULL_JOURNEY.md` (12 مرحلة، 7 أدوار)

---

*هذا المستند يوضح المطبوعات الورقية والتكامل بين الوحدات. للحزم الأخرى، اتبع نفس النمط مع تفعيل/تعطيل الوحدات حسب الباقة.*