@echo off
cd /d D:\recovers\data\medical
set SECRET_KEY=test-secret-key-for-testing
set FIELD_ENCRYPTION_KEY=s_M_Z3Ce6kEET1m2G9SnxzSJHOx91uetbhcFTJB_KIc=
set DATABASE_URL=postgresql://postgres:123@localhost:5432/medical_system_test
set APP_ENV=testing
set E2E_TESTING=1
python -m flask run --host 0.0.0.0 --port 8080 > C:\Users\azad1\AppData\Local\Temp\opencode\app_out.log 2> C:\Users\azad1\AppData\Local\Temp\opencode\app_err.log
