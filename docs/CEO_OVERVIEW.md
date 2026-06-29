# الملخص التنفيذي — Azad Medical Platform

**التاريخ:** 29 يونيو 2026 · **الإصدار:** 3.1

---

## المنتج

منصة عربية (RTL) لإدارة المراكز الطبية — multi-tenant SaaS: استقبال، سريري، مالي، تأمين، طوارئ، اشتراكات Stripe.

---

## الجاهزية (من الكود — يونيو 2026)

| المحور | الحالة |
|--------|--------|
| Docker (PG16 + Redis + Celery) | ✅ |
| CI: migrate + bootstrap + pytest | ✅ |
| تسجيل `/saas/signup` + كتالوج باقات | ✅ |
| عزل ORM + RLS (31 جدول) | ✅ |
| Stripe checkout عند التسجيل | ✅ (يتطلب مفاتيح) |
| نسخ احتياطي Celery/pg_dump | 🟡 يحتاج `pg_dump` في worker |
| توحيد واجهات UX | 🟡 وظيفي — تحسين مستمر |

**التفاصيل التقنية:** [PLATFORM_STATUS.md](PLATFORM_STATUS.md)

---

## الباقات (الكتالوج الافتراضي — 23)

تُحمَّل عند `bootstrap_platform` إلى `product_bundles` و`packages`.  
**التحقق من إنتاجك:**

```sql
SELECT slug, name_ar, monthly_price, modules
FROM product_bundles WHERE is_active ORDER BY monthly_price;
```

| شريحة | أمثلة slug |
|-------|------------|
| صغيرة | `billing_only`, `private_doctor_clinic`, `small_clinic` |
| متوسطة | `clinic_with_lab`, `urgent_care`, `community_clinic` |
| كبيرة | `multi_department_center`, `polyclinic`, `hospital` |
| خاصة | `custom` (وحدات فارغة — إعداد يدوي) |

---

## SaaS

```
/saas/signup → TenantProvisioningService → [Stripe إن لزم] → ACTIVE/TRIAL
```

حالات: `TRIAL` · `ACTIVE` · `PENDING` · `SUSPENDED` · `CANCELLED`

---

## مراجع

- [دليل المستخدم](USER_GUIDE.md)
- [دليل النشر](DEPLOYMENT.md)
- [حالة المنصة](PLATFORM_STATUS.md)
