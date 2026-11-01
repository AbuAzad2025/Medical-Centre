import os

os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/medical_local'
os.environ['SECRET_KEY'] = 'local-dev-secret-key-for-jwt-hs256-min32chars'
os.environ['APP_ENV'] = 'development'
os.environ['FLASK_ENV'] = 'development'
os.environ['RLS_BYPASS_ALLOWED'] = '1'
os.environ['TENANT_DEFAULT_SLUG'] = 'platform'
os.environ['TERMINOLOGY_PATH'] = 'D:\\recovers\\data\\medical\\data\\terminology'

from waitress import serve

from app_factory import create_app

app = create_app('development')
serve(app, host='0.0.0.0', port=8000, threads=200, connection_limit=2000, channel_timeout=120)
