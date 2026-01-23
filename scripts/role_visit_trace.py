import os
import re
import time
import requests

BASE = os.getenv('BASE_URL', 'http://127.0.0.1:5001')
TIMEOUT = 15
RETRIES = 5

def _req(s, method, url, **kwargs):
    t = kwargs.pop('timeout', TIMEOUT)
    tries = RETRIES
    resp = None
    for _ in range(tries):
        try:
            if method == 'get':
                resp = s.get(url, timeout=t, **kwargs)
            else:
                resp = s.post(url, timeout=t, **kwargs)
            return resp
        except Exception:
            time.sleep(0.2)
    return resp

def _json(resp, default=None):
    try:
        return resp.json() if resp is not None else default
    except Exception:
        return default

def get_csrf(html: str) -> str:
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html or '')
    return m.group(1) if m else ''

def get_hidden_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token" value="([^"]+)"', html or '')
    return m.group(1) if m else ''

def login(user: str, password: str):
    s = requests.Session()
    p = _req(s, 'get', f'{BASE}/auth/login')
    html = p.text if p else ''
    csrf = get_hidden_csrf(html) or get_csrf(html)
    pw_candidates = [password, '123456']
    for pw in pw_candidates:
        r = _req(s, 'post', f'{BASE}/auth/login', data={'username': user, 'password': pw, 'csrf_token': csrf}, allow_redirects=False)
        if r is not None and r.status_code == 302:
            break
    return s, csrf

def wait_server_ready(path='/auth/login', max_wait=15):
    start = time.time()
    while time.time() - start < max_wait:
        try:
            r = requests.get(f'{BASE}{path}', timeout=3)
            if r.status_code in (200, 302):
                return True
        except Exception:
            time.sleep(0.3)
    return False

def create_patient_and_visit(s_rec):
    hp = _req(s_rec, 'get', f'{BASE}/reception/patients')
    hp_html = hp.text if hp else ''
    csrf_page = get_csrf(hp_html) or (s_rec.cookies.get('csrf_token') or '')
    nid = f'NID_TRACE_{int(time.time())}'
    ph = '059' + str(int(time.time()))[-7:]
    data = {'national_id': nid, 'phone': ph, 'first_name': 'سيناريو', 'last_name': 'تتبّع', 'gender': 'M', 'csrf_token': csrf_page}
    hdrs_rec = {'Accept': 'application/json', 'X-CSRFToken': csrf_page, 'X-Requested-With': 'XMLHttpRequest'}
    ap = _req(s_rec, 'post', f'{BASE}/reception/add_patient', data=data, headers=hdrs_rec)
    try:
        print('add_patient_status', ap.status_code if ap else 0)
        print('add_patient_body_snip', (ap.text[:200] if getattr(ap, 'text', None) else ''))
    except Exception:
        pass
    pid = None
    try:
        pid = _json(ap, {}).get('patient_id')
    except Exception:
        pid = None
    if not pid:
        try:
            s_doc, _ = login(os.getenv('DOCTOR_USERNAME', 'doctor'), os.getenv('DOCTOR_PASSWORD', 'Doctor@123'))
            sr = _req(s_doc, 'get', f'{BASE}/doctor/api/patient-search', params={'q': nid}, headers={'Accept': 'application/json'})
            jr = _json(sr, {})
            arr = jr.get('patients') or []
            pid = int(arr[0]['id']) if arr else None
        except Exception:
            pid = None
    if not pid:
        sp = _req(s_rec, 'get', f'{BASE}/reception/api/smart-patient-search', params={'q': nid}, headers={'Accept': 'application/json'})
        try:
            arr = _json(sp, {}).get('patients') or []
            pid = int(arr[0]['id']) if arr else None
        except Exception:
            pid = None
    if not pid:
        rp = _req(s_rec, 'get', f'{BASE}/reception/patients?search={nid}')
        html = rp.text if rp else ''
        m = re.search(r'/reception/view_patient/(\d+)', html or '')
        pid = int(m.group(1)) if m else None
    if not pid:
        raise RuntimeError('Failed to create/find patient')
    cv = _req(s_rec, 'get', f'{BASE}/reception/visits/create?patient_id={pid}')
    cv_html = cv.text if cv else ''
    csrf_create = get_hidden_csrf(cv_html) or get_csrf(cv_html) or csrf_page
    dept_id = None
    try:
        mdept = re.search(r'<option value="(\d+)"', cv_html or '')
        dept_id = int(mdept.group(1)) if mdept else 1
    except Exception:
        dept_id = 1
    ad = _req(s_rec, 'get', f'{BASE}/booking/api/available-doctors', headers={'Accept': 'application/json'})
    doc_id = 1
    try:
        js = _json(ad, {})
        arr = js.get('doctors') or []
        doc_id = int(arr[0]['id']) if arr else 1
    except Exception:
        doc_id = 1
    form = {
        'patient_id': pid,
        'department_id': dept_id,
        'doctor_id': doc_id,
        'visit_type': 'REGULAR',
        'symptoms': 'Headache',
        'notes': 'Trace',
        'payment_method': 'cash',
        'is_emergency': 'on',
        'amount_paid': '10',
        'csrf_token': csrf_create
    }
    cr = _req(s_rec, 'post', f'{BASE}/reception/visits/create', data=form, headers={'X-CSRFToken': csrf_create}, allow_redirects=True)
    cr_html = cr.text if cr else ''
    rx = re.compile(r'data-visit-id="(\d+)"', re.IGNORECASE)
    m = rx.search(cr_html or '')
    visit_id = int(m.group(1)) if m else None
    if not visit_id:
        vs = _req(s_rec, 'get', f'{BASE}/reception/visits?search={nid}')
        vs_html = vs.text if vs else ''
        m = rx.search(vs_html or '')
        visit_id = int(m.group(1)) if m else None
    if not visit_id:
        alt = re.search(r'/payment/process/(\d+)', (cr_html or '') + (vs_html or ''), re.IGNORECASE)
        visit_id = int(alt.group(1)) if alt else None
    if not visit_id:
        raise RuntimeError('Failed to parse visit_id')
    return pid, visit_id

def main():
    # Proceed even if readiness check fails, to allow running against already-warm servers
    try:
        wait_server_ready()
    except Exception:
        pass
    s_rec, csrf_rec = login(os.getenv('RECEPTION_USERNAME', 'reception'), os.getenv('RECEPTION_PASSWORD', 'Reception@123'))
    pid, visit_id = create_patient_and_visit(s_rec)
    print('patient_id', pid)
    print('visit_id', visit_id)
    results = {}
    s_doc, _ = login(os.getenv('DOCTOR_USERNAME', 'doctor'), os.getenv('DOCTOR_PASSWORD', 'Doctor@123'))
    r_doc = _req(s_doc, 'get', f'{BASE}/doctor/patient-details/{visit_id}')
    results['doctor_patient_details'] = r_doc.status_code if r_doc else 0
    s_mgr, _ = login(os.getenv('MANAGER_USERNAME', 'manager'), os.getenv('MANAGER_PASSWORD', 'Manager@12345'))
    r_mgr = _req(s_mgr, 'get', f'{BASE}/reception/view_visit/{visit_id}')
    results['manager_view_visit'] = r_mgr.status_code if r_mgr else 0
    s_acc, _ = login(os.getenv('ACCOUNTANT_USERNAME', 'accountant'), os.getenv('ACCOUNTANT_PASSWORD', '123456'))
    r_acc = _req(s_acc, 'get', f'{BASE}/payment/process/{visit_id}')
    results['accountant_payment_process'] = r_acc.status_code if r_acc else 0
    s_ph, _ = login(os.getenv('PHARMACIST_USERNAME', 'pharmacist'), os.getenv('PHARMACIST_PASSWORD', 'Pharmacist@123'))
    r_ph = _req(s_ph, 'get', f'{BASE}/medication/api/prescriptions', params={'visit_id': visit_id}, headers={'Accept': 'application/json'})
    results['pharmacist_prescriptions_api'] = r_ph.status_code if r_ph else 0
    s_lab, _ = login(os.getenv('LAB_USERNAME', 'lab'), os.getenv('LAB_PASSWORD', 'Lab@123'))
    r_lab = _req(s_lab, 'get', f'{BASE}/lab/api/worklist', params={'visit_id': visit_id}, headers={'Accept': 'application/json'})
    results['lab_worklist_api'] = r_lab.status_code if r_lab else 0
    s_rad, _ = login(os.getenv('RAD_USERNAME', 'radiology'), os.getenv('RAD_PASSWORD', 'Radiology@123'))
    r_rad = _req(s_rad, 'get', f'{BASE}/radiology/api/worklist', params={'visit_id': visit_id}, headers={'Accept': 'application/json'})
    results['radiology_worklist_api'] = r_rad.status_code if r_rad else 0
    s_nurse, _ = login(os.getenv('NURSE_USERNAME', 'nurse'), os.getenv('NURSE_PASSWORD', 'Nurse@123'))
    r_nurse = _req(s_nurse, 'get', f'{BASE}/nurse/patients')
    results['nurse_medical_history'] = r_nurse.status_code if r_nurse else 0
    s_super, _ = login(os.getenv('SUPER_USERNAME', 'super'), os.getenv('SUPER_PASSWORD', 'Super@123'))
    r_super = _req(s_super, 'get', f'{BASE}/reception/view_visit/{visit_id}')
    results['super_reception_view_visit'] = r_super.status_code if r_super else 0
    for k, v in results.items():
        print(k, v)

if __name__ == '__main__':
    main()
