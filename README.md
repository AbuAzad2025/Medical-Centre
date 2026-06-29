# Azad Medical Platform — منصة إدارة المراكز الطبية

**النسخة:** 3.1  
**آخر تحديث:** 28 يونيو 2026  
**التقنية:** Flask · SQLAlchemy 2 · PostgreSQL 16 · Redis 7 · Celery · Bootstrap 5 RTL  
**النشر:** Docker Compose · GitHub Actions CI

---

## نظرة عامة

منصة طبية متعددة المستأجرين (Multi-Tenant SaaS) لإدارة المراكز والعيادات: استقبال، زيارات، مختبر، أشعة، تمريض، صيدلية، مالية، تأمين، طوارئ، وحجز — مع عزل بيانات لكل منشأة.

| وضع التشغيل | الوصف |
|-------------|--------|
| **SaaS** | `ENABLE_SAAS_MODE=true` — تسجيل ذاتي، اشتراكات Stripe، عزل tenant |
| **Single-tenant** | نشر تقليدي لمركز واحد بدون بوابة SaaS |

---

## الميزات الرئيسية

- **استقبال وطوابير** — نقطة دخول موحدة، تحويل الزيارات بين الأقسام عبر الاستقبال فقط
- **سير عمل سريري** — طبيب، مختبر، أشعة، تمريض، صيدلية، طوارئ
- **مالية متكاملة** — فواتير، دفعات (نقدي/بطاقة/تأمين/قسري)، مصروفات، تسوية زيارات
- **تأمين** — شركات تأمين، مطالبات، تغطية تلقائية (قيود فريدة لكل tenant)
- **SaaS** — `/saas/signup`، باقات `PackageVersion`، فترة تجريبية أو دفع فوري عبر Stripe
- **عزل البيانات** — فلترة ORM + Row-Level Security على PostgreSQL (**80** جدولاً)
- **صلاحيات** — أدوار متعددة، `guard_module` مركزي، CSRF، rate limiting
- **بصمة/WebAuthn** — تسجيل بيانات اعتماد بيومترية في قاعدة البيانات
- **نسخ احتياطي** — Celery + `pg_dump` (يتطلب عميل PostgreSQL في بيئة التشغيل)

---

## البنية التقنية

```
medical_system/
├── app/                 # نواة SaaS (tenant, lifecycle, packages)
├── models/              # ~84 ملف نموذج ORM
├── routes/              # ~140 ملف مسارات (blueprints)
├── services/            # ~58 خدمة أعمال
├── templates/           # ~385 قالب HTML
├── migrations/          # Alembic — الرأس: s1_006_rls_phase3
├── scripts/
│   ├── ops/             # إنتاج — bootstrap
│   ├── ci/              # GitHub Actions — تهجيرات + RLS
│   └── dev/             # تطوير يدوي (مستبعد من Docker)
```

**Backend:** Flask 2.3+, SQLAlchemy 2, Flask-Login, Flask-Migrate, Stripe SDK  
**Frontend:** Bootstrap 5 RTL, AdminLTE, DataTables, Chart.js  
**قاعدة البيانات:** PostgreSQL 16 (إلزامي للإنتاج وCI) — SQLite للتطوير المحلي فقط

---

## التثبيت السريع

### Docker (موصى به — حزمة تشغيل كاملة)

```bash
cp .env.example .env
docker compose up -d --build
```

ينفّذ تلقائياً: `flask db upgrade` → `bootstrap_platform` → `gunicorn`.  
راجع `scripts/ops/README.md`.

### محلي (تطوير)

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows
pip install -r requirements.txt
set ENABLE_SAAS_MODE=true
set DATABASE_URL=postgresql://...
flask db upgrade
python scripts/ops/bootstrap_platform.py
flask run --port=5001
```

---

## متغيرات البيئة الأساسية

| المتغير | الغرض |
|---------|--------|
| `SECRET_KEY` | مفتاح الجلسات (إلزامي) |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | جلسات/كاش/Celery broker |
| `ENABLE_SAAS_MODE` | `true` لتفعيل multi-tenant |
| `STRIPE_SECRET_KEY` | جلسات دفع عند التسجيل والفوترة |
| `STRIPE_WEBHOOK_SECRET` | تحقق توقيع webhook |
| `SAAS_REQUIRE_PAYMENT_AT_SIGNUP` | إجبار الدفع قبل التفعيل |
| `SAAS_DEFAULT_PACKAGE_VERSION_ID` | الباقة الافتراضية للتسجيل |
| `CELERY_ENABLED` | `true` للمهام الخلفية |

راجع [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) للتفاصيل الكاملة.

---

## الأدوار

| الدور | المسؤوليات |
|-------|-------------|
| `super_admin` | إدارة المنصة، نسخ احتياطي، إعدادات عامة |
| `owner` | مالك المنصة — توفير tenants وباقات |
| `manager` | مدير المركز — موافقات، تقارير |
| `reception` | استقبال، زيارات، طوابير |
| `doctor` / `nurse` / `lab` / `radiology` | أقسام سريرية |
| `accountant` | فواتير، دفعات، مصروفات، تدقيق |
| `emergency` | حالات طوارئ |

---

## SaaS — التسجيل والفوترة

1. الزائر يفتح `/saas/signup` ويختار الباقة
2. `POST /api/saas/register` ينشئ tenant + مدير عبر `TenantProvisioningService`
3. إن وُجد `STRIPE_SECRET_KEY` ولا توجد فترة تجريبية (أو `SAAS_REQUIRE_PAYMENT_AT_SIGNUP=true`): الحالة `PENDING` وإعادة توجيه لـ Stripe Checkout
4. Webhook `checkout.session.completed` يفعّل الـ tenant → `ACTIVE`
5. الدخول عبر `/auth/login` أو `/t/<slug>/auth/login`

---

## الاختبارات وCI

```bash
set ENABLE_SAAS_MODE=true
python -m pytest tests/ -q
```

GitHub Actions: تهجيرات على PostgreSQL 16، pytest كامل مع `ENABLE_SAAS_MODE=true`، flake8، تغطية كود.

---

## التوثيق

| المستند | الجمهور |
|---------|---------|
| [docs/README.md](docs/README.md) | فهرس التوثيق |
| [docs/PLATFORM_STATUS.md](docs/PLATFORM_STATUS.md) | **حالة تقنية من الكود** |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | مستخدمو المركز |
| [docs/CEO_OVERVIEW.md](docs/CEO_OVERVIEW.md) | الإدارة |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | نشر إنتاجي |
| [scripts/ops/README.md](scripts/ops/README.md) | حزمة Docker |

---

## الجاهزية للإنتاج

| السيناريو | الحالة |
|-----------|--------|
| `docker compose up` (upgrade + bootstrap + gunicorn) | ✅ |
| SaaS + Stripe | ✅ يتطلب إعداد مفاتيح |
| عزل multi-tenant | ✅ ORM + RLS (80 جدول) |
| UX موحّد | 🟡 تحسين مستمر |

التفاصيل: [docs/PLATFORM_STATUS.md](docs/PLATFORM_STATUS.md)

---

## المساهمة والدعم

- **Issues:** https://github.com/AbuAzad2025/Med1/issues
- طوّر على الملفات الموجودة، اتبع أنماط المشروع، واختبر قبل الـ PR

**الترخيص:** مفتوح المصدر
