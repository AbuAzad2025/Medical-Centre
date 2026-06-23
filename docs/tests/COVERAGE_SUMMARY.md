# ملخص تغطية الاختبارات

> آخر قياس محلي: `pytest tests/ --cov=app --cov=routes --cov=services --cov=models --cov=utils`

## العدد

| المقياس | القيمة |
|---------|--------|
| ملفات الاختبار | **49** (`tests/test_*.py` + `conftest.py`) |
| حالات الاختبار | **327** (326 ناجح + 1 متخطى) |
| متخطى | `test_auth.py::test_logout` — تسريب جلسة Flask-Login بين الاختبارات |

## تغطية الأسطر (line coverage)

| الحزمة | التغطية | أسطر مغطاة |
|--------|---------|------------|
| **app** | ~52% | منطق SaaS، dashboards، nav، تفضيلات، POS |
| **routes** | ~38% | مسارات نشطة: manager، medication/pos، lab/barcode، portal |
| **services** | ~32% | دفع، استرداد، باركود، SMS، PDF، state machine |
| **models** | ~82% | تعريفات ORM (تغطية عالية طبيعياً) |
| **utils** | ~35% | decorators |
| **المجموع** | **~44%** | 15,132 / 34,626 سطر |

## تغطية حسب المجال الوظيفي (اختبارات)

| المجال | الملفات الرئيسية | تقريب الاختبارات |
|--------|------------------|------------------|
| SaaS / S0 | `test_saas_*`, `test_product_profile_*` | ~34 |
| UX / Command Center | `test_ux1_*`, `test_phase11–14` | ~55 |
| دفع / فواتير | `test_payment_*`, `test_refund_*`, `test_phase35_pos` | ~32 |
| صيدلية | `test_pharmacy`, `test_prescription_*` | ~27 |
| مختبر / أشعة | `test_lab_*`, `test_radiology_*` | ~24 |
| استقبال / زيارات | `test_visit_*`, vertical slices | ~18 |
| أمان / عزل | `test_tenant_*`, `test_background_*` | ~19 |
| بنية تحتية | `test_route_inventory`, `test_migrations_*`, `test_debug_*` | ~28 |
| بوابة مريض | `test_patient_portal*` | ~16 |

## مناطق ضعيفة (أولوية توسيع لاحقاً)

- `services/pricing_service.py`, `services/queue_management_service.py` — **0–6%**
- `routes/reception/visits.py`, `routes/booking_routes.py` — مسارات ضخمة قليلة التغطية
- `services/smart_ai_engine.py`, `services/ai_validation_service.py` — غير مغطاة
- `app/modules/workflows/*` — تدفقات workflow

## CI

- job **migrate**: `scripts/verify_migrations.py` على DB فارغ
- job **test**: `pytest tests/` + تقرير تغطية في سجل GitHub Actions

## تشغيل محلي

```powershell
$env:SECRET_KEY="test"
$env:FLASK_ENV="testing"
$env:SUPPRESS_BACKGROUND_WORKER="1"
python -m pytest tests/ -q --cov=app --cov=routes --cov=services --cov=models --cov=utils --cov-report=term-missing:skip-covered
```
