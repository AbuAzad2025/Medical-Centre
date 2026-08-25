"""
Load-test suite Ã¢â‚¬â€ Locust (professional rewrite).

Design
Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
Ã¢â‚¬Â¢ Role-based virtual users mirroring real usage mix:
    ReceptionUser  50%  Ã¢â‚¬â€œ patients search, queue views, visit lists
    DoctorUser     30%  Ã¢â‚¬â€œ dashboard, patient queue, own visits
    PharmacistUser 10%  Ã¢â‚¬â€œ medication dashboard / inventory
    ManagerUser    10%  Ã¢â‚¬â€œ manager + financial dashboards
Ã¢â‚¬Â¢ Login happens ONCE per simulated user in on_start (realistic sessions);
  a failed login stops that user instead of spamming the endpoint.
Ã¢â‚¬Â¢ Read-dominated profile (~90% GET) Ã¢â‚¬â€ safe to run against a seeded env.

Run (smoke profile)
Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    locust -f locustfile.py --headless \
        -H http://127.0.0.1:8080 -u 25 -r 5 --run-time 90s \
        --csv artifacts/load --only-summary --exit-code-on-error 2%

Credentials default to the accounts created by scripts/seed_load_users.py;
override via LOAD_PASSWORD env if needed.
"""

import os
import random
import re

import gevent

from locust import HttpUser, between, task

PASSWORD = os.getenv('LOAD_PASSWORD', 'ValidPass123!')

_CSRF_RE = re.compile(
    r'name="csrf_token"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*name="csrf_token"'
)


def _extract_csrf(html: str) -> str | None:
    m = _CSRF_RE.search(html)
    if not m:
        return None
    return m.group(1) or m.group(2)


class _RoleUser(HttpUser):
    """Base: one realistic login per simulated user, then read-heavy tasks."""

    abstract = True
    wait_time = between(1.0, 3.0)

    role_username: str = ''

    def on_start(self):
        # Stagger logins: 25 users spawning at once from one IP would spike
        # the auth rate limiter in the first second (thundering herd).
        gevent.sleep(random.uniform(0, 3))
        # Fetch the login page to obtain a CSRF token (realistic browser flow)
        page = self.client.get('/auth/login', name='[login-page]')
        token = _extract_csrf(page.text) if page.status_code == 200 else None

        # The backend treats a request as AJAX only when Content-Type is
        # application/json (auth_routes.py:96) â€” send JSON like the real UI.
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        if token:
            headers['X-CSRFToken'] = token
        resp = self.client.post(
            '/auth/login',
            json={
                'username': self.role_username,
                'password': PASSWORD,
                'csrf_token': token or '',
            },
            headers=headers,
            name=f'[login:{self.role_username}]',
        )
        # Success = JSON success payload (AJAX path) OR redirect (form path).
        ok = resp.status_code == 302 or (
            resp.status_code == 200
            and (b'"success": true' in resp.content or b'"success":true' in resp.content)
        )
        if not ok:
            # Diagnostics go to stdout so CI logs reveal the root cause.
            print(  # noqa: T201
                f'LOGIN FAILED [{self.role_username}] '
                f'http={resp.status_code} token_found={bool(token)} '
                f'body={resp.content[:600]!r}',
                flush=True,
            )
            self.environment.runner.quit()

    # Shared lightweight probes available to every role -------------------
    @task(2)
    def health(self):
        self.client.get('/health', name='[health]', catch_response=True)


class ReceptionUser(_RoleUser):
    abstract = False
    weight = 50
    role_username = 'reception'

    @task(8)
    def patients_search(self):
        q = random.choice(['a', 'm', 'Ã˜Â³', '05'])
        self.client.get(
            f'/reception/patients?search={q}',
            name='/reception/patients?search',
            catch_response=True,
        )

    @task(6)
    def queue_view(self):
        self.client.get('/reception/queue', name='/reception/queue', catch_response=True)

    @task(5)
    def visits_list(self):
        self.client.get('/reception/visits', name='/reception/visits', catch_response=True)

    @task(3)
    def appointments(self):
        self.client.get(
            '/reception/appointments', name='/reception/appointments', catch_response=True
        )


class DoctorUser(_RoleUser):
    abstract = False
    weight = 30
    role_username = 'doctor'

    @task(7)
    def dashboard(self):
        self.client.get('/doctor/dashboard', name='/doctor/dashboard', catch_response=True)

    @task(5)
    def patient_queue(self):
        self.client.get('/doctor/patient_queue', name='/doctor/patient_queue', catch_response=True)

    @task(3)
    def visits(self):
        self.client.get('/doctor/visits', name='/doctor/visits', catch_response=True)


class PharmacistUser(_RoleUser):
    abstract = False
    weight = 10
    role_username = 'pharmacist'

    @task(6)
    def med_dashboard(self):
        self.client.get('/medication/dashboard', name='/medication/dashboard', catch_response=True)

    @task(4)
    def inventory(self):
        self.client.get('/medication/inventory', name='/medication/inventory', catch_response=True)


class ManagerUser(_RoleUser):
    abstract = False
    weight = 10
    role_username = 'manager'

    @task(5)
    def manager_dashboard(self):
        self.client.get('/manager/dashboard', name='/manager/dashboard', catch_response=True)

    @task(4)
    def financial(self):
        self.client.get('/manager/financial', name='/manager/financial', catch_response=True)
