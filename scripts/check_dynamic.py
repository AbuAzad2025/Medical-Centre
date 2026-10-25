import os, sys, re, json

sys.path.insert(0, r'D:\recovers\data\medical')

os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-for-jwt-hs256-min32')
os.environ.setdefault('APP_ENV', 'testing')
os.environ.setdefault('FLASK_ENV', 'testing')
os.environ.setdefault('TEST_DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')
os.environ.setdefault('DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')

from app_factory import create_app

app = create_app('testing')

print("=== الديناميكية (DYNAMIC BEHAVIOR) ===")

with app.app_context():
    from app.extensions import db
    from sqlalchemy import inspect
    
    # 1. النماذج الديناميكية (Specialty Forms)
    print("\n=== النماذج الديناميكية (Specialty Forms) ===")
    inspector = inspect(db.engine)
    
    if 'specialty_forms' in inspector.get_table_names():
        cols = [c['name'] for c in inspect(db.engine).get_columns('specialty_forms')]
        print(f"specialty_forms columns: {cols}")
    
    if 'specialty_form_versions' in inspector.get_table_names():
        cols = [c['name'] for c in inspect(db.engine).get_columns('specialty_form_versions')]
        print(f"specialty_form_versions columns: {cols}")
    
    if 'specialty_form_submissions' in inspector.get_table_names():
        cols = [c['name'] for c in inspect(db.engine).get_columns('specialty_form_submissions')]
        print(f"specialty_form_submissions columns: {cols}")
    
    # 2. حقول JSON الديناميكية
    print("\n=== حقول JSON الديناميكية ===")
    inspector = inspect(db.engine)
    for table in inspector.get_table_names():
        columns = inspect(db.engine).get_columns(table)
        for col in columns:
            col_type = str(col['type']).upper()
            if 'JSON' in col_type or 'JSONB' in col_type:
                print(f"  {table}.{col['name']}: {col_type}")
    
    # 3. التحقق من حقول البيانات الديناميكية في النماذج
    print("\n=== حقول البيانات الديناميكية في النماذج ===")
    
    # التحقق من specialty_form_versions مع حقل form_data أو schema
    if 'specialty_form_versions' in inspector.get_table_names():
        cols = [c for c in inspect(db.engine).get_columns('specialty_form_versions')]
        for c in cols:
            if 'form' in c['name'].lower() or 'schema' in c['name'].lower() or 'field' in c['name'].lower() or 'data' in c['name'].lower() or 'json' in str(c['type']).lower():
                print(f"  specialty_form_versions.{c['name']}: {c['type']}")
    
    # 4. تحقق من medical_record أو clinical notes
    dynamic_tables = ['medical_records', 'clinical_notes', 'progress_notes', 'nursing_assessments']
    for table in dynamic_tables:
        if table in inspector.get_table_names():
            cols = [c['name'] for c in inspect(db.engine).get_columns(table)]
            print(f"  {table}: {cols}")
    
    # 5. تحقق من patient_search_ngrams للبحث الديناميكي
    print("\n=== البحث الديناميكي (Patient Search Ngrams) ===")
    if 'patient_search_ngrams' in inspector.get_table_names():
        cols = [c for c in inspect(db.engine).get_columns('patient_search_ngrams')]
        for c in cols:
            print(f"  patient_search_ngrams.{c['name']}: {c['type']}")
        indexes = inspect(db.engine).get_indexes('patient_search_ngrams')
        print(f"  Indexes: {len(indexes)}")
        for idx in indexes:
            print(f"    - {idx['name']}: {idx['column_names']}")
    
    # 6. تحقق من إعدادات النظام الديناميكية
    print("\n=== الإعدادات الديناميكية (System Configs) ===")
    if 'system_configs' in inspector.get_table_names():
        cols = [c for c in inspect(db.engine).get_columns('system_configs')]
        for c in cols:
            print(f"  system_configs.{c['name']}: {c['type']}")

if __name__ == '__main__':
    from app_factory import create_app
    import os, sys
    
    sys.path.insert(0, r'D:\recovers\data\medical')
    os.environ.setdefault('SECRET_KEY', 'ci-test-secret-key-for-jwt-hs256-min32')
    os.environ.setdefault('APP_ENV', 'testing')
    os.environ.setdefault('FLASK_ENV', 'testing')
    os.environ.setdefault('TEST_DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')
    os.environ.setdefault('DATABASE_URL', 'postgresql://med_app:med_app@127.0.0.1:5432/medical_centre_platform_test')
    
    from app_factory import create_app
    from app.extensions import db
    from sqlalchemy import inspect
    
    app = create_app('testing')
    with app.app_context():
        # Run the checks
        pass