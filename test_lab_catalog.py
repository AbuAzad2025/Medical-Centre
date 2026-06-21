"""
Integration test for Phase 3: Lab Test Catalog and Panels.
Uses SQLite in-memory for full isolation.
"""
import os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ['APP_ENV'] = 'testing'
os.environ['FLASK_DEBUG'] = 'false'
os.environ['TEST_DATABASE_URL'] = 'sqlite:///:memory:'

from dotenv import load_dotenv
load_dotenv()

from app_factory import create_app, db as _db
from models.lab_test_catalog import LabTestCatalog, LabTestPanel, LabTestPanelItem
from models.user import User
from models.patient import Patient
from models.visit import Visit
from models.lab_request import LabRequest, LabResult
from services.lab_service import lab_service

app = create_app()

with app.app_context():
    _db.create_all()
    client = app.test_client()
    errors = 0

    def check(cond, msg):
        global errors
        if not cond:
            print(f"  FAIL: {msg}")
            errors += 1
        else:
            print(f"  OK: {msg}")

    uid = uuid.uuid4().hex[:8]
    tid = None

    from werkzeug.security import generate_password_hash
    user = User(username=f"labtech_{uid}", email=f"{uid}@test.com",
                password_hash=generate_password_hash("test123"),
                tenant_id=tid, role="lab", full_name="Lab Tech Cat")
    _db.session.add(user)
    _db.session.flush()

    patient = Patient(first_name="Test", last_name=f"Patient_{uid}",
                      tenant_id=tid, phone="01000000000")
    _db.session.add(patient)
    _db.session.flush()

    visit = Visit(patient_id=patient.id, tenant_id=tid)
    _db.session.add(visit)
    _db.session.flush()

    lab_req = LabRequest(visit_id=visit.id, patient_id=patient.id,
                         requested_by=user.id, tenant_id=tid,
                         request_number=f"CAT-{uid}", status="REQUESTED")
    _db.session.add(lab_req)
    _db.session.commit()

    with client.session_transaction() as sess:
        sess['csrf_token'] = 'test-csrftoken'

    resp = client.post('/auth/login', data={
        'username': user.username,
        'password': 'test123',
        'csrf_token': 'test-csrftoken',
    })
    check(resp.status_code == 302, f"Login returns 302 (got {resp.status_code})")

    print("\n=== Phase 3: Lab Test Catalog Tests ===\n")

    resp = client.get('/lab/test-catalog/')
    check(resp.status_code == 200, "GET /lab/test-catalog/ returns 200")
    text = resp.data.decode('utf-8')
    check("كتالوج الفحوصات المخبرية" in text, "Page title present")

    resp = client.post('/lab/test-catalog/add', data={
        'code': 'CBC',
        'name_ar': 'صورة دم كاملة',
        'name_en': 'Complete Blood Count',
        'category': 'hematology',
        'unit': '10^3/uL',
        'default_reference_range': '4.5-11.0',
        'critical_low': '2.0',
        'critical_high': '20.0',
        'price': '50.00',
        'preparation_instructions': 'لا حاجة لتحضير خاص',
        'sort_order': '1',
        'is_active': '1',
        'csrf_token': 'test-csrftoken',
    }, follow_redirects=True)
    check(resp.status_code == 200, "POST /lab/test-catalog/add redirects OK")
    check("CBC" in resp.data.decode('utf-8'), "Catalog shows CBC code")

    resp = client.post('/lab/test-catalog/add', data={
        'code': 'GLU',
        'name_ar': 'سكر صائم',
        'name_en': 'Fasting Glucose',
        'category': 'chemistry',
        'unit': 'mg/dL',
        'default_reference_range': '70-110',
        'price': '30.00',
        'sort_order': '2',
        'is_active': '1',
        'csrf_token': 'test-csrftoken',
    }, follow_redirects=True)
    check(resp.status_code == 200, "Added GLU entry")
    check("GLU" in resp.data.decode('utf-8'), "Catalog shows GLU code")

    count = LabTestCatalog.query.filter_by(tenant_id=tid).count()
    check(count == 2, f"2 catalog entries exist (got {count})")

    cbc = LabTestCatalog.query.filter_by(code='CBC', tenant_id=tid).first()
    check(cbc is not None, "CBC entry found")
    resp = client.post(f'/lab/test-catalog/{cbc.id}/edit', data={
        'code': 'CBC',
        'name_ar': 'صورة دم كاملة (معدل)',
        'name_en': 'Complete Blood Count',
        'category': 'hematology',
        'unit': '10^3/uL',
        'default_reference_range': '4.5-11.0',
        'price': '55.00',
        'sort_order': '1',
        'is_active': '1',
        'csrf_token': 'test-csrftoken',
    }, follow_redirects=True)
    check(resp.status_code == 200, "Edit CBC redirects OK")
    _db.session.refresh(cbc)
    check(cbc.name_ar == 'صورة دم كاملة (معدل)', "CBC name_ar updated")

    resp = client.get('/lab/api/test-catalog')
    check(resp.status_code == 200, "API returns 200")
    data = resp.get_json()
    check(len(data) == 2, f"API returns 2 items (got {len(data)})")
    cbc_api = [t for t in data if t['code'] == 'CBC']
    check(len(cbc_api) == 1, "CBC in API response")
    check(cbc_api[0]['unit'] == '10^3/uL', "CBC unit correct in API")

    resp = client.get(f'/lab/api/test-catalog/{cbc.id}')
    check(resp.status_code == 200, "Single item API returns 200")
    item = resp.get_json()
    check(item['code'] == 'CBC', "Single item API has correct code")
    check(item['price'] == 55.0, "Single item API has correct price")

    resp = client.post(f'/lab/test-catalog/{cbc.id}/delete', data={
        'csrf_token': 'test-csrftoken',
    }, follow_redirects=True)
    check(resp.status_code == 200, "Delete CBC redirects OK")
    deleted = _db.session.get(LabTestCatalog, cbc.id)
    check(deleted is None, "CBC entry deleted from DB")

    resp = client.get('/lab/test-panels/')
    check(resp.status_code == 200, "GET /lab/test-panels/ returns 200")

    glu = LabTestCatalog.query.filter_by(code='GLU', tenant_id=tid).first()
    resp = client.post('/lab/test-panels/add', data={
        'name_ar': 'فحص السكر',
        'name_en': 'Sugar Panel',
        'description': 'باقة فحوصات السكر',
        'is_active': '1',
        'test_ids': [str(glu.id)],
        'csrf_token': 'test-csrftoken',
    }, follow_redirects=True)
    check(resp.status_code == 200, "POST /lab/test-panels/add redirects OK")
    panel = LabTestPanel.query.filter_by(tenant_id=tid).first()
    check(panel is not None, "Panel created")
    check(panel.name_ar == 'فحص السكر', "Panel name_ar correct")
    check(len(panel.items) == 1, "Panel has 1 item")
    check(panel.items[0].test_id == glu.id, "Panel item points to GLU")

    resp = client.post(f'/lab/test-panels/{panel.id}/edit', data={
        'name_ar': 'فحص السكر (معدل)',
        'name_en': 'Sugar Panel',
        'description': 'باقة فحوصات السكر المحدثة',
        'is_active': '1',
        'test_ids': [str(glu.id)],
        'csrf_token': 'test-csrftoken',
    }, follow_redirects=True)
    check(resp.status_code == 200, "Edit panel redirects OK")
    _db.session.expire_all()
    panel = _db.session.get(LabTestPanel, panel.id)
    check(panel.name_ar == 'فحص السكر (معدل)', "Panel name_ar updated")
    check(panel.description == 'باقة فحوصات السكر المحدثة', "Panel description updated")

    resp = client.post(f'/lab/test-panels/{panel.id}/delete', data={
        'csrf_token': 'test-csrftoken',
    }, follow_redirects=True)
    check(resp.status_code == 200, "Delete panel redirects OK")
    deleted_panel = _db.session.get(LabTestPanel, panel.id)
    check(deleted_panel is None, "Panel deleted from DB")

    entry = lab_service.lookup_catalog_by_code('GLU', tenant_id=tid)
    check(entry is not None, "lookup_catalog_by_code finds GLU")
    check(entry.unit == 'mg/dL', f"Auto-fill unit = 'mg/dL' (got '{entry.unit}')")
    check(entry.default_reference_range == '70-110',
          f"Auto-fill range = '70-110' (got '{entry.default_reference_range}')")

    missing = lab_service.lookup_catalog_by_code('NONEXISTENT', tenant_id=tid)
    check(missing is None, "lookup_catalog_by_code returns None for unknown code")

    catalog_list = lab_service.get_active_catalog(tenant_id=tid)
    check(len(catalog_list) == 1, f"get_active_catalog returns 1 active (got {len(catalog_list)})")

    check(LabResult.query.filter_by(request_id=lab_req.id).count() == 0,
          "No results yet")
    from routes.lab.worklist import _process_lab_results_form
    from flask import request as flask_req
    with app.test_request_context(method='POST', data={
        'result_id[]': '',
        'test_code[]': 'GLU',
        'test_name[]': 'سكر صائم',
        'value[]': '95',
        'unit[]': '',
        'reference_range[]': '',
        'is_critical[]': '0',
        'status[]': 'PENDING',
        'notes[]': '',
    }):
        from flask_login import current_user
        any_change = _process_lab_results_form(lab_req, flask_req.form)
    check(any_change, "_process_lab_results_form returned True")
    _db.session.commit()
    result_count = LabResult.query.filter_by(request_id=lab_req.id).count()
    check(result_count >= 1, f"At least 1 result created (got {result_count})")
    if result_count >= 1:
        r = LabResult.query.filter_by(request_id=lab_req.id).first()
        check(r.unit == 'mg/dL', f"Auto-filled unit = 'mg/dL' (got '{r.unit}')")
        check(r.reference_range == '70-110',
              f"Auto-filled range = '70-110' (got '{r.reference_range}')")

    total = 14
    passed = total - errors
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed, {errors} failed")
    print(f"{'='*50}")

    _db.session.rollback()
    _db.drop_all()

    if errors:
        sys.exit(1)
