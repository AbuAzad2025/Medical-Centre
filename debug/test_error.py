import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app
app = create_app()

with app.app_context():
    from models.visit import Visit
    try:
        c = Visit.query.count()
        print('Visit count OK:', c)
    except Exception as e:
        print('ERROR:', type(e).__name__)
        msg = str(e)
        # Find the actual error message
        if 'column' in msg.lower():
            idx = msg.lower().find('column')
            print('MSG:', msg[idx:idx+500])
        else:
            print('MSG:', msg[-500:])
