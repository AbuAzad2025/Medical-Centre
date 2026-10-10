# المسارات المستحيلة — موثّقة بدل تلفيقها

هذه journeys **لا يمكن تنفيذها عبر النظام الحالي** لأن الكود لا يحتوي ما يلزمها.
وُثِّقت هنا عمداً: توليد سيناريو وهمي في هذه الحالات سيعطي انطباعاً بأن
النظام يغطي دورة سريرية ومالية كاملة، وهو غير صحيح.

لكل بند: **الدليل** · **ما ينقص** · **البديل المتاح فعلاً**.

---

## `BLOCKED-01` — يوم جراحي / جراحة

| | |
|---|---|
| **الدليل** | `routes/or_management_routes.py` = 53 سطراً، مساران `GET` فقط (`or.schedule`, `or.surgery_detail`). **صفر** `POST/PUT/DELETE`. لا `SurgeryService`. استنساخ `SurgerySchedule(` لا يعطي أي نتيجة خارج الاختبارات. |
| **ما ينقص** | كاتب للجدولة، آلة حالات للتشغيل، تسجيل الموافقة، قائمة WHO قابلة للكتابة، جولة جراحية (بست)، وتقرير جراحي. |
| **النموذج موجود** | `models/or_management.py:12` `SurgerySchedule` كامل: `procedure_name`، `cpt_code_id`، `icd10_code_id`، `or_room`، 5 أعضاء فريق، `consent_signed`، `actual_start/end`، `outcome`، `complications`، `estimated_blood_loss`. و`models/or_management.py:101` `SurgeryChecklist` بقائمة WHO كاملة (8+8+5). |
| **البديل** | تسجيل الإجراء كنص في `Visit.diagnosis` + `Visit.notes` عبر `POST /doctor/diagnosis/<visit_id>`. أجرة الجراحة تُسجَّل كصنف `ServiceMaster` عام عبر `add-service`. |
| **فجوة إضافية** | `or` غير مُقيَّد بأي module في `app/core/module/registry.py` ⇒ `/or/schedule` متاح حتى على باقة `billing_only`. |

---

## `BLOCKED-02` — دورة جرعات الدواء (eMAR) — **مُغلق**

| | |
|---|---|
| **الحالة** | **مُغلق.** كانت هذه الملاحظة تقول إن eMAR لا يمكن الوصول إليه؛ لم تعد صحيحة. |
| **ماذا تغيّر** | أضيفت ثلاثة مسارات: `GET /emar/dashboard` و`GET /emar/patient/<patient_id>` و`POST /emar/administer/<admin_id>` (`routes/emar_routes.py:22,48,72`). مسار الـadminister يستدعي `NursingService.record_emar_administration`، أي الخدمة الغنية نفسها التي كانت موصوفة بأنها غير قابلة للوصول. |
| **لماذا كانت خاطئة** | كُتبت بقراءة الكود قبل إضافة المسارات. لم تُراجَع منذ ذلك الحين. اكتُشف الآن بواسطة `tools/scenario_gen/verify_blocked.py` الذي يفحص كل ادعاء قابل للتحقق مقابل الكود عند كل تشغيل. |
| **ما يبقى | الخلل Authentication Handbook لأن eMAR كان غير قابل للوصول؛ المسار موجود الآن والالتزامات خارجه. |

---

## `BLOCKED-03` — ملخص خروج منظم

| | |
|---|---|
| **الدليل** | `grep -ri "discharge_summary\|DischargeSummary\|exit_summary"` ← **صفر نتيجة** في `models/` و`routes/` و`services/` و`migrations/`. |
| **ما ينقص** | النموذج، والمسار، والقالب، وحقول: الأدوية عند الخروج، حالة الخروج، خطة المتابعة، تعليمات المريض. |
| **المتاح** | `services/admission_service.py:135` يكتب `Admission.discharge_diagnosis = summary_notes` — **نص حر واحد**. |
| **فجوة مصاحبة** | `ensure_completed` على `Visit` مغلّف بـ`contextlib.suppress(ValueError)` (`services/admission_service.py:150`) ⇒ فشل آلة الحالة **يصمت بلا خطأ ولا أثر**. |
| **البديل** | نص حر في `Admission.discharge_diagnosis` + تقرير الطباعة عبر `GET /reception/print_receipt/<id>` (قيمه أتعاب الطبيب **عرضية فقط**، لا تُكتب في أي عمود). |

---

## `BLOCKED-04` — أي باقة سريرية

| | |
|---|---|
| **الدليل** | صفر `class \w*(Package\|Bundle)\w*` في `models/` لشيء سريري. `grep "out_of_package\|package_price\|included_services\|package_cap\|maternity_package"` ← **صفر** في كامل المستودع. |
| **ما هو موجود فعلاً** | `Package` و`PackageVersion` و`PackageVersionEntitlement` و`PackageVersionPricing` في `app/core/saas/models.py` — **اشتراكات المنصة في المستأجرين** (Stripe). و`ProductBundle` في `app/core/tenant/models.py:727` — حِزمة وحدات برمجية. |
| **ما ينقص** | سعر باقة سريرية، عناصر مشمولة، نافذة صلاحية، مفهوم «خارج الباقة»، سقف إنفاق. |
| **أقرب شيء** | `LabTestPanel` (`models/lab_test_catalog.py:45`) — يجمع فحوصاً، لكن **بلا سعر**، و`LabRequest` **بلا مفتاح panel** ⇒ لا يمكن فوترة اللوحة كوحدة. |
| **الأثر المالي** | لا خصم حزمة، ولا سعر مجمّع، ولا تفصيل «مشمول / غير مشمول» في أي فاتورة. الفاتورة = أسطر `InvoiceService` مستقلة بسعر كل منها. |

---

## `BLOCKED-05` — تحمّل / فرنشيز / استثناءات تأمين

| | |
|---|---|
| **الدليل** | `grep -ri "deductible\|copay\|exclusion"` عبر كل `*.py` ← **صفر نتيجة**. |
| **ما هو منفَّذ** | `models/visit.py:285` `calculate_insurance_amounts()` فقط: `patient_share = total × (1 − coverage/100)`، و`insurance_amount = total × (coverage/100)`. |
| **ما ينقص** | جدول خطط، فرنشيز يُخصم قبل النسبة، مبلغ تحمّل ثابت، سقف منفعة، قوائم استثناءات، جدول رسوم مسموح (allowed amount)، تحقّق أهلية، وتصريح مسبق. |
| **المصدر غير الموثوق** | `GatekeeperService.validate_insurance` (`services/gatekeeper_service.py:571`) يرفض التغطية `< 50` أو `> 100` ⇒ **شركة تأمين تغطي 30% لا يمكن تسجيلها أصلاً**. |
| **الكود الميت** | `models/pricing.py:188` `InsuranceProvider` يحمل `coverage_percentage` و`max_coverage_amount` — **السقف الوحيد الحقيقي في النظام** — و`calculate_coverage()` فيه تنفيذ صحيح مقيَّد بالسقف. **صفر مستدعين**. |
| **الأثر** | «السقف التأميني» غير موجود عملياً؛ الموجود هو حدّ تحقّق رقمي على نسبة يكتبها موظف. |

---

## `BLOCKED-06` — رموز تشريحية مُولّدة (LOINC / CPT / ICD)

| | |
|---|---|
| **الدليل** | `utils/seed_manifest.py:26-35` قائمة استثناء صريحة: *"Must come from a maintained terminology source. A plausible but wrong code gets billed and reported as fact."* و`app/core/platform_bootstrap.py:456` نفس المبدأ. |
| **النماذج موجودة** | `models/icd_coding.py` — `ICD10Code`، `CPTCode`، `DRGCode` (وهي من 4 نماذج فقط بلا `tenant_id`). |
| **المشكلة** | لا تُبذر ولا ينشئها أي مسار. `LabRequest` و`RadiologyRequest` **بلا أي مفتاح تشخيصي**. |
| **الأثر** | لا يمكن ربط نتيجة مخبرية برمز LOINC، ولا تشخيص برمز ICD. **السجل الطبي غير قابل للترميز الدولي.** |

---

## `BLOCKED-07` — إنشاء Ward / Room / Bed — **مُغلق جزئياً**

| | |
|---|---|
| **الحالة** | **مُغلق جزئياً.** المسارات موجودة؛ ما زال ما يُنشئ الصفوف غائباً. |
| **ماذا تغيّر** | `GET /bed/wards` و`GET /bed/ward/<id>` و`GET /bed/room/<id>` موجودة الآن، إضافةً إلى `POST /bed/api/admissions/admit`. Previously the note said no route served these at all. |
| **ما يبقى | لا يوجد مسار `POST` لإنشاء Ward أو Room أو Bed. Admissions تُنشأ عبر `admit`، لكن Ward وRoom لا تُنشأان إلا من `Ward(` و`Bed(` مباشرة في `tests/test_admission_service.py`. |
| **لماذا يهم** | Ward وRoom بيانات مرجعية مطلوبة لوضع المريض داخلها. مستودع جديد يبدأ بلا صفوف، وشاشة السكن تعرض قائمة فارغة حتى تُنشأ الصفوف يدوياً في الصدفة. |

---

## `BLOCKED-11` — تجاوز بوابة الدفع للطوارئ — **مُاكَدDead path**

| | |
|---|---|
| **الحالة** | **مؤكَّد بالتنفيذ.** ليس افتراضاً من قراءة الشيفرة؛ `tests/test_scenarios_executable_isolation.py` ينفّذ الرحلة كاملة. |
| **ما كان يُفترض** | أن `POST /reception/queue/approve-emergency-debt/<ticket_id>` هو الاستثناء الموثَّق الذي يسمح بدخول مريض غير مدفوع. |
| **ما يحدث فعلاً** | المسار يأخذ **رقم تذكرة**، والتذكرة لا توجد إلا إذا admitted الطابور المريض، والطابور لا admits إلا زيارة `PAID`. فالمسار يطلب الموافقة على تذكرة تجعل بوابة الدفع مستحيل إنشاءها. النتيجة العملية: لا المسار ولا أي مسار آخر يخلق تذكرة لمريض غير مدفوع. |
| **لماذا لا يوجد مدخل آخر** | كان `force_entry` مدخلاً، وأُزيل: `add_patient_to_queue` لم يعد يقبله (`services/queue_management_service.py`، Ticket 1). فلم يبقَ ما يخلق تذكرة لغير المدفوع. |
| **الأثر** | **مريض طوارئ غير مدفوع لا يستطيع المرور عبر الطابور إطلاقاً.** أما مسار `force_entry` فكذلك غير قابل للوصول لأن التذكرة التي ينشئها لا يمكن أن توجد أصلاً. |
| **الإصلاح المقترح** | إمّا يعيد `add_patient_to_queue` قبول `force_entry` محكوماً بدور مدير، أو يقبل `approve_emergency_debt` رقم **زيارة** فينشئ التذكرة ويضبط `EMERGENCY_DEBT` مع تسجيل من وافق. الحالة الثانية أوسع لأن إدارة الدَّين لا تحتاج تذكرة سابقة. |
| **كيف يُغلق الاكتشاف** | الاختبار `test_emergency_debt_approval_is_unreachable_for_an_unpaid_visit` يفشل عندصبح المسار قابلاً للوصول، وهذه هي اللحظة التي تُعاد فيها كتابة هذه الملاحظة. |

---

## `BLOCKED-08`

--- — إنشاء إحالة صادرة / تحصين

| | |
|---|---|
| **الدليل** | `routes/referral_routes.py` فيه `list` و`detail` فقط — **قراءة**. `Referral(` لا يُنشأ في أي موضع. `routes/vaccination_routes.py` كذلك قراءة فقط، و`Immunization(` لا يُنشأ خارج النموذج. |
| **النماذج موجودة** | `models/referral.py:12` `Referral` بحالات كاملة (PENDING/SENT/ACCEPTED/SCHEDULED/COMPLETED/CANCELLED/DECLINED) + `referring_facility` + `urgency` + `tracking_number`. و`models/vaccination.py:39` `Immunization`. |
| **الأثر** | لا يمكن تحويل مريض فعلياً إلى جهة أخرى، ولا تسجيل لقاح منفرد — رغم أن النموذجين مكتملان. |

---

## `BLOCKED-09` — تحويل ER ← ward

| | |
|---|---|
| **الدليل** | `AdmissionService` لا يُستدعى من أي مسار في `routes/emergency/`. grep = صفر مستدعٍ هناك. |
| **المفارقة** | `POST /emergency/cases/<id>/convert` موجود ومحجوب بـ`role_required('reception')` — وهو **تحويل ER←ward** منطقياً، لكنه لا ينشئ `Admission`. |
| **البديل المتاح** | `POST /bed/api/admissions/admit` بـ`admission_type='EMERGENCY'` يقبل الترقيم المباشر من حالة طوارئ — لكنه مسار تمريضي، بلا ربط تلقائي بحالة الطوارئ. |

---

## `BLOCKED-10` — هوية الدافع المؤسسي (Corporate Payer)

| | |
|---|---|
| **الدليل** | لا نموذج `CorporateAccount` ولا `Employer` ولا `Contract`. `InsuranceCompany` (`models/insurance.py:14`) يحمل الاسم والهاتف والبريد فقط. |
| **ما ينقص** | علاقة موظف/الم-beneficiary، تسوية شهرية، حد ائتماني، عدّاد استخدام، وفاتورة واحدة لكامل الشركة. |
| **البديل المتاح** | تسجيل شركة التأمين كـ`InsuranceCompany` وكتابة نسبة التغطية يدوياً — أي أن **الدفع المؤسسي في النظام فعلياً تأمين يدوي.** |

---

## خلاصة: ما تغطيه المصفوفة فعلاً

| مرحلة دورة الحياة | الحالة |
|---|---|
| الدخول والتسجيل | ✅ **منفَّذ** — مع فجوة: الكشك غير محمي |
| الفرز | ⚠️ **يدوي فقط** — RED/YELLOW/GREEN، بلا ESI |
| الاستشارة | ✅ **منفَّذ** — حالة visits محمية بآلة حالات |
| المختبر والأشعة | ✅ **منفَّذ** — دورة حياة كاملة |
| الأدوية والصرف | ✅ **منفَّذ** — مع فجوة eMAR |
| **الباقات** | ❌ **غير موجودة** |
| **التأمين المتقدّم** | ⚠️ **نسبة خطية فقط** |
| **الدفتر المحاسبي** | ✅ **مزدوج-entry صحيح** — مع فجوات ترحيل |
| الرعاية الداخلية ADT | ⚠️ **الجزء الأساسي فقط** — بلا تسعير ليلي |
| **الجراحة** | ❌ **بلا كاتب** |
| **الملخصات والتوثيق** | ❌ **غير موجودة** |
