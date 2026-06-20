"""
إنشاء 10 عملاء (Tenants) بحزم مختلفة عبر API مباشر
"""
import sys, os, json
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from app_factory import create_app, db
from app.core.tenant.models import Tenant
from app.shared.enums import ProductProfile, SubscriptionType, StorageMode, TenantStatus
from datetime import date, datetime, timezone
from flask import url_for

app = create_app()

TENANTS = [
    {"name": "عيادة الدكتور سمير", "name_ar": "عيادة الدكتور سمير", "slug": "clinic-samer", "contact_email": "samer@clinic.com", "contact_phone": "0599123456", "profile": ProductProfile.PRIVATE_DOCTOR_CLINIC},
    {"name": "عيادة الأسنان الحديثة", "name_ar": "عيادة الأسنان الحديثة", "slug": "clinic-alsnan", "contact_email": "alsnan@clinic.com", "contact_phone": "0599234567", "profile": ProductProfile.SMALL_CLINIC},
    {"name": "مختبر البراء الطبي", "name_ar": "مختبر البراء الطبي", "slug": "lab-albaraa", "contact_email": "albaraa@lab.com", "contact_phone": "0599345678", "profile": ProductProfile.STANDALONE_LAB},
    {"name": "مركز الضوء للتصوير الإشعاعي", "name_ar": "مركز الضوء للتصوير الإشعاعي", "slug": "radiology-daw", "contact_email": "daw@radiology.com", "contact_phone": "0599456789", "profile": ProductProfile.STANDALONE_RADIOLOGY},
    {"name": "صيدلية الشفاء", "name_ar": "صيدلية الشفاء", "slug": "pharmacy-shifa", "contact_email": "shifa@pharmacy.com", "contact_phone": "0599567890", "profile": ProductProfile.STANDALONE_PHARMACY},
    {"name": "مركز القدس الطبي", "name_ar": "مركز القدس الطبي", "slug": "quds-medical", "contact_email": "quds@medical.com", "contact_phone": "0599678901", "profile": ProductProfile.MULTI_DEPARTMENT_CENTER},
    {"name": "مجمع العيون التخصصي", "name_ar": "مجمع العيون التخصصي", "slug": "complex-eyes", "contact_email": "eyes@complex.com", "contact_phone": "0599789012", "profile": ProductProfile.CUSTOM},
    {"name": "عيادة القلب والأوعية", "name_ar": "عيادة القلب والأوعية", "slug": "clinic-heart", "contact_email": "heart@clinic.com", "contact_phone": "0599890123", "profile": ProductProfile.PRIVATE_DOCTOR_CLINIC},
    {"name": "مركز الباطنة والجهاز الهضمي", "name_ar": "مركز الباطنة والجهاز الهضمي", "slug": "center-digestive", "contact_email": "digestive@center.com", "contact_phone": "0599901234", "profile": ProductProfile.SMALL_CLINIC},
    {"name": "مختبر الأمل الطبي", "name_ar": "مختبر الأمل الطبي", "slug": "lab-amal", "contact_email": "amal@lab.com", "contact_phone": "0599012345", "profile": ProductProfile.STANDALONE_LAB},
]

def create_tenants():
    with app.app_context():
        existing = {t.slug for t in Tenant.query.all()}
        created = 0
        for data in TENANTS:
            if data["slug"] in existing:
                print(f"  SKIP {data['slug']} موجود مسبقاً")
                continue
            
            t = Tenant(
                slug=data["slug"],
                name=data["name"],
                name_ar=data.get("name_ar"),
                domain=None,
                subdomain=None,
                contact_email=data["contact_email"],
                contact_phone=data.get("contact_phone"),
                tax_number=None,
                product_profile_code=data["profile"],
                plan_id=None,
                subscription_type=SubscriptionType.MONTHLY,
                subscription_start=date.today(),
                subscription_end=date(2027, 6, 20),
                grace_period_end=None,
                storage_mode=StorageMode.CLOUD,
                status=TenantStatus.ACTIVE
            )
            db.session.add(t)
            db.session.flush()
            
            # Activate default modules for this profile
            from app.core.tenant.models import get_default_modules_for_profile
            default_modules = get_default_modules_for_profile(data["profile"].value)
            for mod_name in default_modules:
                from app.core.module.models import TenantModule
                tm = TenantModule(tenant_id=t.id, module_name=mod_name, is_active=True)
                db.session.add(tm)
            
            print(f"  OK {data['slug']} - {data['name']} ({data['profile'].value}) - modules: {default_modules}")
            created += 1
        
        db.session.commit()
        print(f"\nOK تم إنشاء {created} عملاء جدد")
        print(f"TOTAL إجمالي العملاء الآن: {Tenant.query.count()}")

if __name__ == "__main__":
    create_tenants()
