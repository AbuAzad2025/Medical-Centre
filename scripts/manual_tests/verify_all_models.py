"""مطابقة جميع الموديلز مع قاعدة البيانات"""
import os, sys, traceback
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app, db
from sqlalchemy import inspect, text

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    
    # Get all model classes from db.Model registry
    all_missing = {}
    all_extra = {}
    
    # Iterate through all mapped classes
    for mapper in db.Model.registry.mappers:
        cls = mapper.class_
        # Skip non-table mapped classes or abstract classes
        if not hasattr(cls, '__tablename__') or cls.__tablename__ is None:
            continue
        table_name = cls.__tablename__
        
        # Skip if table doesn't exist in DB
        if table_name not in inspector.get_table_names():
            print(f"[MISSING TABLE] {table_name} — table does not exist in database!")
            continue
        
        # Get model columns
        model_columns = {c.name for c in cls.__table__.columns}
        
        # Get DB columns
        db_columns = {c['name'] for c in inspector.get_columns(table_name)}
        
        missing = model_columns - db_columns
        extra = db_columns - model_columns
        
        if missing:
            all_missing[table_name] = sorted(missing)
        if extra:
            all_extra[table_name] = sorted(extra)
    
    print("=" * 70)
    print("نتائج المطابقة بين الموديلز وقاعدة البيانات")
    print("=" * 70)
    
    if all_missing:
        print(f"\n عدد الجداول بأعمدة ناقصة: {len(all_missing)}")
        for table, cols in sorted(all_missing.items()):
            print(f"\n  {table}:")
            for col in cols:
                print(f"    - MISSING: {col}")
    else:
        print("\n لا توجد أعمدة ناقصة — جميع الأعمدة موجودة!")
    
    if all_extra:
        print(f"\n عدد الجداول بأعمدة زائدة: {len(all_extra)}")
        for table, cols in sorted(all_extra.items()):
            print(f"\n  {table}:")
            for col in cols:
                print(f"    + EXTRA: {col}")
    else:
        print("\n لا توجد أعمدة زائدة في قاعدة البيانات")
    
    print("\n" + "=" * 70)
    total_missing = sum(len(c) for c in all_missing.values())
    print(f"إجمالي الأعمدة الناقصة: {total_missing}")
    print("=" * 70)
