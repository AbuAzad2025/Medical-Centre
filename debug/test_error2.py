import os
os.environ['DATABASE_URL'] = 'postgresql://postgres:123@localhost:5432/medical_system'
os.environ['SECRET_KEY'] = 'dev-secret-key-change-in-production'

from app_factory import create_app
app = create_app()

with app.app_context():
    from models.visit import Visit
    try:
        c = Visit.query.count()
        with open('error_result.txt', 'w') as f:
            f.write('OK: ' + str(c))
    except Exception as e:
        with open('error_result.txt', 'w') as f:
            f.write('ERROR: ' + type(e).__name__ + '\n')
            msg = str(e)
            # Write last 1000 chars which usually have the actual error
            f.write(msg[-2000:])
