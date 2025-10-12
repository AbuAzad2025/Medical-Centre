# -*- coding: utf-8 -*-
"""
404 Scout: يفحص خادم حيّ ويبلغك فوريًا عن كل 404 مع نصائح إصلاح.
بيئة التشغيل:
    BASE_URL=http://127.0.0.1:5001  python scripts/404_scout.py
"""
import os
import re
import requests

BASE = os.getenv("BASE_URL", "http://127.0.0.1:5001")
LOGIN_URL = f"{BASE}/auth/login"
OK = {200,201,204}

USERS = {
    "reception": {"username":"reception","password":"reception123"},
    "doctor": {"username":"doctor","password":"doctor123"},
    "manager": {"username":"manager","password":"manager123"},
}

TARGETS = {
    "reception": ["/", "/reception/dashboard", "/reception/add-patient"],
    "doctor": ["/doctor/dashboard", "/doctor/patient-queue"],
    "manager": ["/manager/dashboard", "/manager/monitoring"],
}

def suggest(path, urlmap_text):
    tips = []
    if re.search(r"/doctor\b", path) and "/doctor" not in urlmap_text:
        tips.append("سجّل doctor_bp بـ '/doctor' في create_app وتأكد من اسم المتغير.")
    if re.search(r"/reception\b", path) and "/reception" not in urlmap_text:
        tips.append("سجّل reception_bp بـ '/reception' في create_app.")
    if path == "/" and not re.search(r"\s/\s", urlmap_text):
        tips.append("أضف @main_bp.get('/') أو سجّل main_bp على '/'.")
    tips += [
        "تحقق من GET/POST: عرّف الدالة بـ .get() أو methods=['GET'] حسب الطلب.",
        "انقل كل register_blueprint إلى create_app فقط.",
        "app.url_map.strict_slashes=False لتفادي /path/ مقابل /path.",
    ]
    return tips

def fetch_url_map():
    try:
        r = requests.get(f"{BASE}/__routes", timeout=5)
        return r.text if r.status_code in OK else ""
    except Exception:
        return ""

def login(sess, u, p):
    # قد تحتاج CSRF إن مفعّل؛ لبيئة الاختبار عادةً يكفي POST مباشر
    return sess.post(LOGIN_URL, data={"username":u,"password":p}, allow_redirects=True, timeout=7)

def main():
    urlmap = fetch_url_map()
    session = requests.Session()
    failed = []

    for role, creds in USERS.items():
        r = login(session, creds["username"], creds["password"])
        print(f"[login] {role}: {r.status_code}")

        for path in TARGETS.get(role, []):
            url = BASE + path
            try:
                resp = session.get(url, timeout=7, allow_redirects=True)
            except Exception as e:
                print(f"[❌] {role} GET {path}: EXC {e}")
                failed.append((role, path, "EXCEPTION"))
                continue

            code = resp.status_code
            if code not in OK:
                print("="*70)
                print(f"[❌] {role} GET {path} → {code}")
                print("-"*70)
                preview = (resp.text or "")[:500]
                print("Body preview:\n", preview)
                print("-"*70)
                print("🔎 URL Map (مختصر):")
                print("\n".join(line for line in urlmap.splitlines() if any(seg in line for seg in ["/reception","/doctor","/manager","/ "])))
                print("-"*70)
                print("🔧 نصائح إصلاح:")
                for tip in suggest(path, urlmap):
                    print(" - " + tip)
                print("="*70)
                failed.append((role, path, code))
            else:
                print(f"[OK ] {role} GET {path} → {code}")

    if failed:
        print("\n❌ انتهى الفحص بوجود 404/أخطاء في المسارات أعلاه.")
        raise SystemExit(1)
    print("\n✅ كل المسارات الأساسية رجعت 200/201/204.")

if __name__ == "__main__":
    main()


