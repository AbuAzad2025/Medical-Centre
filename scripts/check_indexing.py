import os, sys, json, re

sys.path.insert(0, r'D:\recovers\data\medical')

os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-for-jwt-hs256-min32')
os.environ.setdefault('APP_ENV', 'testing')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('TEST_DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')
os.environ.setdefault('DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')

from app_factory import create_app
from sqlalchemy import inspect, text

app = create_app('testing')

print("=== الفهرسة (INDEXING) - فحص الفهارس في قاعدة البيانات ===")

with app.app_context():
    from app.extensions import db
    inspector = inspect(db.engine)
    
    # 1. جلب جميع الجداول
    tables = inspector.get_table_names()
    print(f"إجمالي الجداول: {len(tables)}")
    
    # 2. فحص الفهارس لكل جدول
    print("\n=== فهارس الجداول ===")
    tables_without_pk = []
    tables_without_fk_indexes = []
    total_indexes = 0
    
    for table in sorted(tables):
        indexes = inspector.get_indexes(table)
        pk_constraint = inspector.get_pk_constraint(table)
        foreign_keys = inspector.get_foreign_keys(table)
        
        total_indexes += len(indexes)
        
        # التحقق من وجود Primary Key
        if not pk_constraint['constrained_columns']:
            tables_without_pk.append(table)
        
        # التحقق من فهارس المفاتيح الأجنبية
        for fk in foreign_keys:
            fk_cols = fk['constrained_columns']
            has_index = False
            for idx in indexes:
                if list(idx['column_names'])[:len(fk_cols)] == fk_cols:
                    has_index = True
                    break
            if not has_index:
                tables_without_fk_indexes.append(f"{table}.{fk_cols} -> {fk['referred_table']}")
        
        # طباعة ملخص للجداول المهمة
        if table in ['patients', 'visits', 'prescriptions', 'lab_requests', 'radiology_requests', 
                     'invoices', 'payments', 'users', 'patients', 'medications', 'appointments',
                     'lab_requests', 'radiology_requests', 'invoices', 'payments', 'queue_management']:
            pk_cols = pk_constraint['constrained_columns']
            fk_count = len(foreign_keys)
            idx_count = len(indexes)
            print(f"  {table:30} PK: {pk_cols} | FKs: {fk_count} | Indexes: {idx_count}")
    
    print(f"\n=== ملخص الفهارس ===")
    print(f"إجمالي الفهارس: {total_indexes}")
    print(f"جداول بدون Primary Key: {len(tables_without_pk)}")
    if tables_without_pk:
        for t in tables_without_pk:
            print(f"  - {t}")
    
    print(f"\nمفاتيح أجنبية بدون فهارس: {len(tables_without_fk_indexes)}")
    for fk in tables_without_fk_indexes[:20]:
        print(f"  - {fk}")
    if len(tables_without_fk_indexes) > 20:
        print(f"  ... and {len(tables_without_fk_indexes) - 20} more")
    
    # 3. فحص الفهارس على حقول البحث الشائعة
    print("\n=== فهارس حقول البحث الشائعة ===")
    search_fields = ['patient_id', 'visit_id', 'tenant_id', 'created_at', 'status', 'email', 'phone', 'national_id']
    for table in ['patients', 'visits', 'prescriptions', 'lab_requests', 'radiology_requests', 
                  'invoices', 'payments', 'users', 'medications', 'appointments']:
        if table in inspector.get_table_names():
            indexes = inspector.get_indexes(table)
            columns = [c['name'] for c in inspector.get_columns(table)]
            for field in search_fields:
                if field in columns:
                    has_index = any(field in idx['column_names'] for idx in indexes)
                    status = "✅" if has_index else "❌"
                    print(f"  {table}.{field:20} {status}")