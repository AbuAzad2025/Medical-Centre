# تقرير الموقع الحي — مستأجرين تجريبيين

**التاريخ:** 3 سبتمبر 2026 — **الرأس:** `s3_009_pending_financial_settlement`  
**البيئة:** `medical_system` على `127.0.0.1:5432` مع `postgres:123`

---

## المستأجرون التجريبيون

| المستأجر | Slug | الباقة | الوحدات | الحالة |
|----------|------|--------|---------|--------|
| صيدلية الدواء الشافي | `demo-pharmacy` | `standalone_pharmacy` | `pharmacy` `inventory` `billing` (3) | `active` |
| مستشفى الشفاء العام | `demo-hospital` | `hospital` | 14 وحدة (`reception` `doctor` `nursing` `billing` `appointments` `lab` `radiology` `pharmacy` `emergency` `reporting` `inventory` `portal` `ai_imaging` `integration`) | `active` |

**التحقق:**
```bash
SELECT slug, product_profile_code, status FROM tenants WHERE slug LIKE 'demo-%';
# demo-pharmacy | standalone_pharmacy | active
# demo-hospital | hospital | active
SELECT tenant_id, module_name FROM tenant_modules WHERE tenant_id IN (1,2) ORDER BY tenant_id;
# 3 + 14 صفوف
```

---

## مسارات العرض الحي

1. **صيدلية:** `http://localhost:8080/t/demo-pharmacy/medication/dashboard` — `pharmacist` يرى `pharmacy_dispense` فقط (مقيد `pharmacy`), `reception` لا يرى `lab`.
2. **مستشفى:** `http://localhost:8080/t/demo-hospital/manager/dashboard` — `kpi_strip` + `manager_finance` + `manager_hr`, و `http://localhost:8080/t/demo-hospital/reception/dashboard` — `queue_live` + `visits_today`.

---

## الفحوصات

- `flask db heads` → `s3_009` وحيد
- `audit_rls_coverage.py` → 181 بسياسات
- `check_no_cjk.py` → 0
- `pytest tests/test_hub_and_spoke_financial_gate.py -q` → 3 passed (Hub-and-Spoke)

---

## الروابط

- لوحة المالك: `/owner/dashboard` (platform_owner `azad`)
- تسجيل مستأجر جديد: `/saas/signup` → يختار `standalone_pharmacy` أو `hospital`
