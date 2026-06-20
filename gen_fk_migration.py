import sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
from app_factory import create_app
app = create_app()

SUPPRESS_TABLES = {'alembic_version', 'spatial_ref_sys'}

with app.app_context():
    from sqlalchemy import inspect, text
    from app_factory import db
    
    # Get current FK info from DB
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    tables = [t for t in tables if t not in SUPPRESS_TABLES]
    
    # Get model FK info from SQLAlchemy metadata
    db.reflect()
    
    changes = []
    skipped_patient_visit = []  # These are intentional RESTRICT
    
    for table_name in sorted(tables):
        try:
            db_fks = inspector.get_foreign_keys(table_name)
        except:
            continue
        
        for fk in db_fks:
            fk_name = fk['name']
            cols = fk['constrained_columns']
            ref_table = fk['referred_table']
            ref_cols = fk['referred_columns']
            opts = fk.get('options', {})
            current_ondelete = opts.get('ondelete', '')
            
            # Skip PKs (no ondelete needed for PKs)
            if not cols:
                continue
            
            col_name = cols[0]
            
            # Determine what ondelete the MODEL wants by checking nullable
            # This is a simplified heuristic
            try:
                col_info = inspector.get_columns(table_name)
                col_nullable = None
                for c in col_info:
                    if c['name'] == col_name:
                        col_nullable = c.get('nullable', True)
                        break
            except:
                col_nullable = None
            
            # Check the actual model file for ondelete
            model_path = os.path.join(r'D:\Data\MED-2-7-2025\medical_system\models', table_name + '.py')
            if not os.path.exists(model_path):
                # Try other conventions
                continue
            
            # Check if the relationship is a protected clinical one
            is_clinical = ref_table in ('patients', 'visits', 'prescriptions', 'medical_records', 'medications', 'emergency_cases', 'appointments')
            is_optional_user = col_name.endswith(('_by', '_id')) and ref_table == 'users'
            
            if current_ondelete == '' and not is_clinical:
                changes.append((table_name, fk_name, col_name, 'current: none', col_nullable))
            elif current_ondelete == '':
                skipped_patient_visit.append((table_name, col_name, ref_table))
    
    print('=== FKs needing migration (currently no ondelete, not clinical) ===')
    for t, fk, col, cur, null in changes:
        print(f'  {t}.{col} FK={fk} nullable={null}')
    
    print(f'\nTotal to alter: {len(changes)}')
    print(f'\n=== Intentional RESTRICT (clinical references, kept as-is) ===')
    for t, col, ref in skipped_patient_visit:
        print(f'  {t}.{col} -> {ref}')
    print(f'Total skipped: {len(skipped_patient_visit)}')
