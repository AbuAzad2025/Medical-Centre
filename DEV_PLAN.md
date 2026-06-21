# خطة التطوير - Development Plan

## المبادئ
1. **لا نكسر النظام** — كل تغيير يتبعه اختبارات شاملة قبل الدمج
2. **كل مرحلة مستقلة** — إنجاز مرحلة لا يعطل المرحلة التالية
3. **Backend first** — نركز على الخلفية قبل الواجهات
4. **اختبارات قبل وبعد** — لكل مرحلة test suite خاص بها

---

## المرحلة 1: تكامل الرسائل النصية (SMS)
**المدة المقدرة: 2-3 أيام | المخاطرة: منخفضة**

### المشكلة
- `send_appointment_reminders()` يضيف رسائل SMS إلى `NotificationQueue` بـ `notification_type='sms'`
- لكن `process_notification_queue()` ليس لديه معالج لـ `'sms'` — يقع في `else` ويرسل إشعار داخلي فقط
- كذلك `send_email_message()` و `send_whatsapp_message()` لا يرسلان فعلياً — فقط يحفظان في قاعدة البيانات

### المهام
1. إضافة `TwilioSMSProvider` — خدمة إرسال SMS عبر Twilio (أو مزيل محلي)
2. تحديث `process_notification_queue()` — إضافة فرع `elif notification_type == 'sms'` يستدعي مزود SMS
3. إصلاح `send_email_message()` — ربطه بـ Flask-Mail لإرسال فعلي عبر SMTP
4. إضافة `SMS_CONFIG` في `SystemConfig` — تخزين credentials (Account SID, Auth Token, Sender Number)
5. إضافة route إعدادات SMS في `super_admin/system.py`
6. اختبارات: إرسال SMS تجريبي، تذكير موعد تلقائي

### لن يكسر
- لا يمس أي نموذج أو route موجود
- فقط يضيف معالجاً جديداً في `process_notification_queue()`
- الإشعارات الداخلية (Notifications) تبقى كما هي

---

## المرحلة 2: تقارير PDF للمختبر والأشعة
**المدة المقدرة: 3-4 أيام | المخاطرة: منخفضة**

### المشكلة
- `reportlab==4.0.4` مثبت و `PDFReportPrinter` موجود لكن غير مستخدم
- lab و radiology يخدمان HTML print فقط، لا يوجد PDF للتحميل

### المهام
1. إعادة بناء `PDFReportPrinter` في `app/integrations/printing/pdf.py` — دعم:
   - ترويسة المختبر/المركز الطبي
   - معلومات المريض والطبيب
   - جدول النتائج مع reference ranges
   - توقيع إلكتروني (base64 image)
   - QR code للتأكد من صحة التقرير
2. إضافة endpoint في lab: `/lab/print_request/<id>/pdf` — يُنشئ PDF ويُرجعه كـ `send_file`
3. إضافة endpoint في radiology: `/radiology/print_report/<id>/pdf`
4. إضافة زر "تحميل PDF" في قوالب الطباعة الموجودة
5. اختبارات: توليد PDF، محتوى صحيح، أحرف عربية

### لن يكسر
- HTML print الحالي يبقى كما هو
- PDF endpoint مضاف بجانب الموجود، لا يحل محله
- `PDFReportPrinter` الموجود حالياً غير مستخدم أصلاً

---

## المرحلة 3: كتالوج الفحوصات المخبرية (Test Catalog)
**المدة المقدرة: 2-3 أيام | المخاطرة: منخفضة**

### المشكلة
- `LabResult` له `test_code`, `test_name`, `unit`, `reference_range` — لكن تُدخل يدوياً كل مرة
- لا يوجد `LabTestDefinition` أو `TestCatalog` لتوحيد الفحوصات والنطاقات المرجعية

### المهام
1. إنشاء `LabTestCatalog` (model):
   - `code` (كود الفحص), `name_ar` / `name_en`
   - `category` (chemistry, hematology, microbiology, serology, etc.)
   - `unit`, `default_reference_range`, `critical_low`, `critical_high`
   - `price`, `preparation_instructions` (تعليمات ما قبل الفحص)
   - `is_active`, `tenant_id`
2. إنشاء `LabTestPanel` (model):
   - مجموعة فحوصات (مثل: CBC, Lipid Profile, LFT)
   - ربط Many-to-Many مع `LabTestCatalog`
3. routes CRUD: `/lab/test-catalog/`, `/lab/test-panels/`
4. تحديث `worklist.py` — عند إدخال نتيجة، auto-fill الـ unit و reference_range من الكتالوج
5. زر "إضافة فحص من الكتالوج" في واجهة إدخال النتائج
6. اختبارات: CRUD كتالوج، auto-fill في النتائج

### لن يكسر
- `LabResult` الحالي يبقى كما هو (فقط يُملأ تلقائياً)
- الفحوصات القديمة بدون كتالوج تبقى صالحة
- إضافة اختيارية، لا إجبارية

---

## المرحلة 4: نظام الباركود للعينات المخبرية
**المدة المقدرة: 2-3 أيام | المخاطرة: متوسطة**

### المشكلة
- `BarcodeRegistry` و `BarcodeScanLog` موجودان لكن غير مربوطين بالمختبر
- `LabRequest` ليس لديه `barcode` أو `qr_code` field
- لا تتبع لسلسلة العينة (sample chain of custody)

### المهام
1. إضافة `barcode` و `barcode_image` fields إلى `LabRequest`
2. عند إنشاء طلب مختبر — توليد باركود (Code128 أو QR) تلقائياً
3. تحديث `LabRequest.status` ليشمل حالات إضافية (مستوحاة من PathLab):
   - `REQUESTED` → `COLLECTED` → `RECEIVED` → `ANALYZING` → `REVIEWED` → `DONE`
   - حقل `collection_time`, `received_time`, `analyzed_by`
4. route: `/lab/barcode/scan/<barcode>` — مسح باركود وتحديث الحالة
5. route: `/lab/barcode/print/<request_id>` — طباعة باركود
6. ربط مع `BarcodeScanLog` — تسجيل كل مسح (من, متى, أين)
7. اختبارات: توليد باركود، مسح باركود، تحديث حالة

### لن يكسر
- حالات `LabRequest` القديمة (REQUESTED|IN_PROGRESS|DONE|CANCELLED) تبقى متوافقة
- إضافة حقول جديدة لا تؤثر على الاستعلامات القديمة
- المسح اختياري — العمل اليدوي لا يزال متاحاً

---

## المرحلة 5: جدولة أجهزة الأشعة (Modality Scheduling)
**المدة المقدرة: 4-5 أيام | المخاطرة: متوسطة**

### المشكلة
- لا يوجد جدولة لأجهزة الأشعة (CT, MRI, X-Ray, US)
- التقويم الحالي (`booking_routes.py`) مخصص لحجز مواعيد الأطباء فقط
- KloudRIS لديه تقويم سحب وإفلات للأجهزة

### المهام
1. إنشاء `Modality` (model):
   - `name`, `modality_type` (CT/MRI/US/XRAY/MAMMO), `room`, `is_active`, `tenant_id`
2. إنشاء `ModalitySchedule` (model):
   - `modality_id`, `date`, `start_time`, `end_time`, `status` (AVAILABLE/BOOKED/MAINTENANCE/BLOCKED)
   - `radiology_request_id` (nullable, يرتبط بطلب الأشعة إذا تم الحجز)
3. routes:
   - `GET /radiology/schedule?date=&modality_id=` — عرض مواعيد اليوم
   - `POST /radiology/schedule/book` — حجز موعد لجهاز لطلب معين
   - `POST /radiology/schedule/block` — حظر وقت (صيانة)
   - `DELETE /radiology/schedule/<id>` — إلغاء حجز
4. API للتقويم: `/radiology/api/schedule?week_start=` — بيانات أسبوع كامل
5. تحديث `worklist.py` — عند إنشاء طلب أشعة، ربطه بموعد جهاز
6. اختبارات: حجز، تعارض مواعيد، إلغاء، صيانة

### لن يكسر
- لا يؤثر على سير عمل الأشعة الحالي (worklist, results, reports)
- الجدولة إضافة فوقية — يمكن تجاهلها
- `RadiologyRequest` يرتبط اختيارياً بـ `ModalitySchedule`

---

## المرحلة 6: التقارير المهيكلة للأشعة (Structured Reporting)
**المدة المقدرة: 3-4 أيام | المخاطرة: منخفضة**

### المشكلة
- قوالب التقارير الحالية نصية بسيطة مع placeholders ({{BODY_PART}})
- لا يوجد BI-RADS, PI-RADS, LI-RADS أو أي تقارير مهيكلة

### المهام
1. إنشاء `StructuredReportTemplate` (model):
   - `name`, `modality_type`, `body_part`, `structure` (JSON Schema)
   - الحقول المهيكلة: findings مع coded elements, measurements, scoring
2. إضافة قوالب مسبقة لكل موديليتي:
   - **X-Ray**: الوصف العام (position, technique, findings by body part)
   - **CT**: بروتوكول, phase, measurements
   - **MRI**: sequence, contrast, findings with DICOM coordinates
   - **Mammo** (تحضيري): BI-RADS categories, breast density, calcifications
3. تحديث `radiology/templates.py` — إضافة `structure` field للـ JSON Schema
4. إضافة `structured_data` (JSON) إلى `RadiologyResult`
5. تحديث `worklist.py` — عند اختيار قالب مهيكل، عرض الحقول المنظمة بدلاً من النص الحر
6. اختبارات: إنشاء تقرير مهيكل، عرض، طباعة

### لن يكسر
- القوالب النصية القديمة تبقى وتعمل
- `structured_data` حقل JSON إضافي — لا يمس `findings`/`impression` الحالية
- يمكن التبديل بين النص الحر والقالب المهيكل

---

## المرحلة 7: النسخ الاحتياطي التلقائي
**المدة المقدرة: 2-3 أيام | المخاطرة: متوسطة**

### المشكلة
- واجهة جدولة النسخ الاحتياطي موجودة (`/backup/schedule`)
- لكن لا يوجد مشغل خلفي (background scheduler) ينفذ الجدولة فعلياً
- `celery==5.3.6` في `requirements.txt` لكنه غير مربوط

### المهام
1. تكوين Celery مع `app_factory.py` — إنشاء `celery_app` مع Redis broker
2. إنشاء `tasks/backup_tasks.py` — مهام الخلفية:
   - `scheduled_backup()` — ينفذ النسخ الاحتياطي حسب الجدول
   - `cleanup_old_backups()` — يحذف النسخ القديمة تلقائياً
3. تحديث `routes/super_admin/backup.py`:
   - بعد حفظ الجدولة، جدولة Celery beat task
   - إظهار حالة "آخر نسخ" في لوحة التحكم
4. إنشاء فولباك: إذا Redis غير متاح، استخدم `threading.Timer` كمؤقت بسيط
5. اختبارات: جدولة، تنفيذ، استعادة

### لن يكسر
- النسخ اليدوي الحالي يبقى كما هو
- الجدولة مجرد إضافة فوقية
- Celery يعمل كطبقة إضافية — النظام يعمل بدونه (manual fallback)

---

## المرحلة 8: تصحيح وإشعارات البريد الإلكتروني
**المدة المقدرة: 1-2 أيام | المخاطرة: منخفضة**

### المشكلة
- `send_email_message()` في `NotificationService` يحفظ فقط في `EmailMessage` ولا يرسل عبر SMTP
- `process_notification_queue()` لـ `'email'` يستدعي `send_email_message()` — loop لا نهائي!

### المهام
1. إنشاء `EmailService` يستخدم Flask-Mail لإرسال فعلي
2. تحديث `process_notification_queue()` — لـ `'email'` استدعاء SMTP مباشر
3. إضافة إعدادات SMTP في `SystemConfig` (host, port, username, password, use_tls)
4. route إعدادات SMTP في `super_admin/system.py`
5. تفعيل إشعارات البريد لنتائج المختبر (عند إكمال فحص، إرسال بريد للطبيب)
6. اختبارات: إرسال بريد تجريبي، إشعار نتيجة مختبر

### لن يكسر
- `EmailMessage` model يبقى — نضيف حقل `sent_at` فعلي
- جميع الإشعارات الحالية تبقى

---

## المرحلة 9: بوابة دفع إلكترونية
**المدة المقدرة: 4-5 أيام | المخاطرة: عالية (تعتمد على مزود الدفع)**

### المشكلة
- `PaymentTransaction` يُنشأ بحالة `pending` لكن لا معالجة فعلية
- لا يوجد Gateway حقيقي

### المهام
1. إنشاء `PaymentGatewayProvider` interface — يدعم:
   - Stripe, PayPal, PayLink (لفلسطين)
   - `charge()`, `refund()`, `webhook_handler()`
2. إضافة نموذج `PaymentGatewayConfig` في `SystemConfig`
3. تحديث `booking/payment/<id>` — إعادة التوجيه إلى بوابة الدفع
4. إضافة webhook endpoint: `/api/payments/webhook/<gateway>`
5. تحديث `OnlineBooking.payment_status` عند تأكيد الدفع
6. إضافة خيار الدفع عبر البوابة في الـ Pharmacy POS
7. اختبارات: وضع Sandbox مع Stripe/PayPal test keys

### لن يكسر
- الدفع النقدي/يدوي الحالي يبقى كما هو
- البوابة اختيارية — تُفعل بإعدادات
- `PaymentTransaction` الحالي يحصل على `gateway_reference` إضافي

---

## المرحلة 10: موديول TPA (Third Party Administration)
**المدة المقدرة: 5-7 أيام | المخاطرة: عالية (موديول جديد كلياً)**

### المشكلة
- TPA غير موجود إطلاقاً في النظام الحالي
- eMED Clinic عنده eMED TPA كميزة منفصلة

### المهام
1. إنشاء `models/tpa.py`:
   - `TPACompany`, `TPAContract`, `TPAClaim`, `TPAAuthorization`
2. إنشاء `routes/tpa/` blueprint كامل:
   - `claims.py` — تقديم وإدارة المطالبات
   - `authorizations.py` — إذن مسبق للخدمات
   - `reports.py` — تقارير TPA
   - `dashboard.py` — لوحة تحكم TPA
3. ربط مع `Visit`, `Invoice`, `InsuranceCompany` الموجودين
4. API للتبادل الإلكتروني مع شركات TPA
5. اختبارات: دورة حياة كاملة للمطالبة

### لن يكسر
- موديول جديد منفصل لا يمس أي موجود
- الارتباط مع النظام الحالي عبر FK إلى Visit/Invoice

---

## المرحلة 11: API للموبايل (تحضيري)
**المدة المقدرة: 3-5 أيام | المخاطرة: متوسطة**

### المهام
1. إنشاء `routes/api/v1/` blueprint:
   - JWT authentication (تسجيل دخول + refresh)
   - `GET /api/v1/appointments` — مواعيدي
   - `GET /api/v1/lab-results` — نتائج المختبر
   - `GET /api/v1/radiology-results` — نتائج الأشعة
   - `GET /api/v1/prescriptions` — وصفاتي
   - `POST /api/v1/book-appointment` — حجز موعد
2. `Flask-JWT-Extended` (موجود في requirements)
3. Rate limiting على API endpoints
4. توثيق Swagger/OpenAPI
5. اختبارات: جميع الـ endpoints مع JWT

### لن يكسر
- API جديد، لا يمس routes الموجودة
- البوابة الحالية (HTML) تبقى كما هي

---

## جدول الأولويات

| الأولوية | المرحلة | القيمة | الجهد | المخاطرة |
|---------|---------|--------|-------|---------|
| 1 | SMS | عالية (تقليل غياب المواعيد) | 2-3d | منخفضة |
| 2 | PDF | عالية (تحسين جودة التقارير) | 3-4d | منخفضة |
| 3 | كتالوج الفحوصات | عالية (توحيد العمل المخبري) | 2-3d | منخفضة |
| 4 | باركود العينات | عالية (سلامة المرضى) | 2-3d | متوسطة |
| 5 | جدولة الأجهزة | متوسطة | 4-5d | متوسطة |
| 6 | تقارير مهيكلة | متوسطة | 3-4d | منخفضة |
| 7 | نسخ احتياطي تلقائي | عالية (أمان البيانات) | 2-3d | متوسطة |
| 8 | إصلاح البريد | متوسطة | 1-2d | منخفضة |
| 9 | بوابة دفع | عالية | 4-5d | عالية |
| 10 | TPA | متوسطة | 5-7d | عالية |
| 11 | API موبايل | متوسطة | 3-5d | متوسطة |

---

## تحليل المخاطر

### لا نلمس أبداً
- `models/` الموجودة — فقط نضيف حقول `nullable=True` أو نماذج جديدة
- Routes الموجودة — لا نغير مساراتها
- `requirements.txt` — نضيف فقط ما نحتاج (لا نحذف شيئاً)

### نمط التطبيق لكل مهمة
1. **Model first** — نضيف/نعدل النموذج
2. **Migration** — `flask db migrate` + upgrade
3. **Service layer** — منطق العمل
4. **Routes** — endpoints جديدة
5. **Templates** (اختياري) — واجهات بسيطة
6. **Tests** — اختبارات (pytest)
7. **Manual test** — تشغيل السيرفر واختبار يدوي
8. **Run all existing tests** — التأكد من عدم كسر شيء

### في حالة الخطأ
- `git stash` — نرجع فوراً
- التحقق من أن جميع الـ 29 test تمر
- العودة إلى الخطة وإعادة التقييم
