@echo off
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/medical_local
set SECRET_KEY=local-dev-secret-key-for-jwt-hs256-min32chars
set APP_ENV=development
set FLASK_ENV=development
set RLS_BYPASS_ALLOWED=1
set TENANT_DEFAULT_SLUG=platform
set TERMINOLOGY_PATH=D:\recovers\data\medical\data\terminology
set FLASK_APP=wsgi:app

D:\recovers\data\medical\.venv\Scripts\python.exe -c "from app_factory import create_app; app = create_app('development'); app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)"