# المطبوعات الورقية والتكامل بين الوحدات — Printed Forms & Cross-Module Integration

> **آخر تحقق:** 25 أكتوبر 2026 — الإصدار 3.3 (commit `5fe283a9`)
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

### 1.2. بنية نظام الطباعة (`templates/print/`)

```
templates/print/
├── print_base.html              # قالب أساسي (header, footer, watermark, QR)
├── print_base_minimal.html      # نسخة مصغّرة (thermal printer)
├── _print_header_default.html   # رأس افتراضي (اسم المركز، شعار، عنوان)
├── _print_header_slot.html      # رأس مخصص (لـ letterhead)
├── _print_footer_slot.html      # تذييل (تاريخ، صفحة X of Y)
├── _print_qr_barcode.html       # QR code / barcode slot
├── _print_watermark.html        # علامة مائية (DRAFT, COPY, ORIGINAL)
└── _print_platform_stamp.html   # ختم المنصة (SaaS)
```

**الميزات:**
- **RTL كامل:** `dir="rtl"`، خطوط عربية
- **QR Code:** `/reception/print_receipt/<id>` يحتوي QR للتحقق
- **Barcode:** `/lab/barcode/print/<id>` يطبع barcode للعينة (Code 128)
- **Watermark:** `DRAFT` (مسودة)، `COPY` (نسخة)، `ORIGINAL` (أصلي)
- **Thermal printer:** `print_base_minimal.html` للطابعات الحرارية (80mm)
- **PDF export:** `/lab/print_request/<id>/pdf`، `/radiology/print_report/<id>/pdf` (WeasyPrint)

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

## 4. المطبوعات (Printed Forms) — تفاصيل تقنية

### 4.1. قالب الطباعة (`print_base.html`)

```html
<!-- templates/print/print_base.html -->
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/print.css') }}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Header Slot -->
    {% include 'print/_print_header_default.html' %}
    {% block header_slot %}{% endblock %}

    <!-- Watermark (DRAFT/COPY/ORIGINAL) -->
    {% if watermark %}
        {% include 'print/_print_watermark.html' %}
    {% endif %}

    <!-- Content -->
    <main class="print-content">
        {% block content %}{% endblock %}
    </main>

    <!-- Footer Slot -->
    {% include 'print/_print_footer_slot.html' %}

    <!-- QR / Barcode -->
    {% if qr_code %}
        {% include 'print/_print_qr_barcode.html' %}
    {% endif %}

    <!-- Platform Stamp (SaaS) -->
    {% include 'print/_print_platform_stamp.html' %}
</body>
</html>
```

### 4.2. أنواع المطبوعات (Print Types)

| النوع | المسار | المُنشئ | الميزات |
|------|--------|---------|---------|
| **روشتة (Prescription)** | `/doctor/print-prescription/<id>` | Doctor | QR code، توقيع إلكتروني، تفاعل دوائي |
| **روشتة طوارئ** | `/emergency/print-prescription/<id>` | ER Doctor | علامة `EMERGENCY`، priority high |
| **تقرير طبي** | `/doctor/print-medical-report/<visit_id>` | Doctor | SOAP، ICD-10، CPT، توقيع |
| **تقرير طوارئ** | `/emergency/print-emergency-report/<id>` | ER Doctor | فرز، علامات حيوية، علاج |
| **تقرير أشعة (HTML)** | `/radiology/print_report/<id>` | Radiology | صورة، نتائج، توقيع |
| **تقرير أشعة (PDF)** | `/radiology/print_report/<id>/pdf` | Radiology | WeasyPrint → PDF |
| **فاتورة** | `/reception/print_invoice/<id>` | Reception/Billing | بنود، ضريبة، خصم، QR |
| **إيصال** | `/reception/print_receipt/<visit_id>` | Reception/Billing | QR code، رقم إيصال، تفاصيل دفع |
| **إيصال صيدلية** | `/medication/sales/<id>/print` | Pharmacy | POS receipt، thermal printer |
| **باركود عينة** | `/lab/barcode/print/<id>` | Lab | Code 128 barcode، معرّف عينة |
| **طلب مختبر (HTML)** | `/lab/print_request/<id>` | Lab | طلب، تحاليل، ملاحظات |
| **طلب مختبر (PDF)** | `/lab/print_request/<id>/pdf` | Lab | WeasyPrint → PDF |
| **تقرير مختبر** | `/lab/reports` | Lab | إحصائيات، أوقات تسليم |
| **تقرير استهلاك** | `/medication/consumption-report` | Pharmacy | استهلاك أدوية، مخزون |
| **تقرير مالي** | `/accountant/reports` | Billing | إيرادات، مصروفات، تدفقات |

### 4.3. دعم الطابعات (Printer Support)

| نوع الطابعة | القالب | الاستخدام |
|-------------|--------|-----------|
| **A4 (Laser/Inkjet)** | `print_base.html` | تقارير، فواتير، روشتات (A4) |
| **Thermal (80mm)** | `print_base_minimal.html` | إيصالات POS، receipts (thermal) |
| **PDF (WeasyPrint)** | `print_base.html` + WeasyPrint | تقارير مختبر/أشعة (PDF download) |
| **Barcode (Zebra)** | `lab/barcode_print.html` | Code 128 barcode للعينات |

---

## 5. التكامل (Integration) — الخلاصة

### 5.1. التكامل (Integration) — API/Service Layer

التكامل بين الوحدات يجري عبر 4 آليات:

1. **ORM Relationships** — `db.relationship()` (e.g., `Visit.patient`, `LabRequest.visit`)
2. **Service Layer** — خدمات مشتركة (`queue_management_service`, `clinical_context_service`)
3. **Event Bus** — إشعارات عبر `signals.py` (`patient_registered` → إشعار reception)
4. **Route Guards** — `guard_module()` في `before_request` (403 إذا الوحدة مطفأة)

### 5.2. التكامل (Integration) — Data Flow

```
reception → doctor → lab/radiology → pharmacy → billing → portal
    │          │         │              │         │         │
    ▼          ▼         ▼              ▼         ▼         ▼
patients    visits    lab_requests   prescriptions invoices  results
visits      SOAP      radiology_     dispense_     payments  bills
queue       ICD-10    requests       logs          receipts  records
```

### 5.3. التكامل (Integration) — Module Data Isolation

| الوحدة | تقرأ من | تُكتب في | عزل (Isolation) |
|--------|---------|----------|-----------------|
| `doctor` | patients, visits (reception) | visits (update status), prescriptions, lab_requests, radiology_requests | ✅ module filter |
| `lab` | lab_requests (doctor) | lab_results, lab_specimens | ✅ module filter |
| `radiology` | radiology_requests (doctor) | radiology_results | ✅ module filter |
| `pharmacy` | prescriptions (doctor) | dispense_logs, stock_movements, sales | ✅ module filter |
| `billing` | visits, patients (reception/doctor) | invoices, payments, receipts | ✅ module filter |
| `nursing` | patients, visits (reception/doctor) | vital_signs, emar, nursing_notes | ✅ module filter |
| `emergency` | patients, visits (reception) | emergency_cases, emergency_treatments | ✅ module filter |
| `inpatient` | patients, visits, beds (reception/nursing) | admissions, bed_transfers | ✅ module filter |
| `reporting` | **جميع الجداول** (read-only) | reports, analytics | ✅ module filter (read-only) |

---

## 6. الخلاصة

### المطبوعات (Printed Forms)
- **15 نوع مطبوع** (روشتات، تقارير، فواتير، إيصالات، باركودات)
- **4 أنواع طابعات** (A4، Thermal 80mm، PDF WeasyPrint، Barcode Zebra)
- **9 قوالب print** (base، minimal، header، footer، QR، watermark، platform stamp)
- **RTL كامل** + QR code + barcode + watermark + thermal printer support

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