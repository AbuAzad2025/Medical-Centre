import os, traceback
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app
app = create_app()

with app.app_context():
    from models.visit import Visit
    try:
        c = Visit.query.count()
        print('OK:', c)
    except Exception as e:
        # Get the actual original error
        import sys
        exc_type, exc_value, exc_tb = sys.exc_info()
        
        with open('error_full.txt', 'w', encoding='utf-8') as f:
            f.write('Type: ' + str(exc_type) + '\n')
            f.write('Value: ' + str(exc_value) + '\n')
            f.write('Orig: ' + str(getattr(exc_value, 'orig', 'none')) + '\n')
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
