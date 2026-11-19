import os

os.environ['DATABASE_URL'] = 'postgresql://postgres:testpass@localhost:5433/Medical2026'
os.environ['SECRET_KEY'] = 'local-dev-secret-key-for-jwt-hs256-min32chars'
os.environ['APP_ENV'] = 'development'
os.environ['FLASK_ENV'] = 'development'
os.environ['RLS_BYPASS_ALLOWED'] = '1'
os.environ['TENANT_DEFAULT_SLUG'] = 'platform'
# SaaS mode enables multi-tenant provisioning: creating tenants, toggling
# their modules and cross-tenant owner operations. The owner dashboard shows
# these controls but the APIs are gated behind SaaS mode.
os.environ['ENABLE_SAAS_MODE'] = 'true'
os.environ['TERMINOLOGY_PATH'] = 'D:\\recovers\\data\\medical\\data\\terminology'
# Allow the platform bootstrap to create the master owner account and the
# base catalogue on a fresh install. It is idempotent and cheap after the
# first run, so it must not be skipped on a day-one database.
os.environ.pop('SKIP_PLATFORM_BOOTSTRAP', None)

from waitress import serve

from app_factory import create_app

app = create_app('development')
serve(app, host='0.0.0.0', port=8000, threads=200, connection_limit=2000, channel_timeout=120)
