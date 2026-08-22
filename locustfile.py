"""
Load-test suite — Locust (professional rewrite).

Design
──────
• Role-based virtual users mirroring real usage mix:
    ReceptionUser  50%  – patients search, queue views, visit lists
    DoctorUser     30%  – dashboard, patient queue, own visits
    PharmacistUser 10%  – medication dashboard / inventory
    ManagerUser    10%  – manager + financial dashboards
• Login happens ONCE per simulated user in on_start (realistic sessions);
  a failed login stops that user instead of spamming the endpoint.
• Read-dominated profile (~90% GET) — safe to run against a seeded env.

Run (smoke profile)
───────────────────
    locust -f locustfile.py --headless \
        -H http://127.0.0.1:8080 -u 25 -r 5 --run-time 90s \
        --csv artifacts/load --only-summary --exit-code-on-error 2%

Credentials default to the accounts created by scripts/seed_load_users.py;
override via LOAD_PASSWORD env if needed.
"""

import os
import random

from locust import HttpUser, between, task

PASSWORD = os.getenv('LOAD_PASSWORD', 'ValidPass123!')


class _RoleUser(HttpUser):
    """Base: one realistic login per simulated user, then read-heavy tasks."""

    abstract = True
    wait_time = between(1.0, 3.0)

    role_username: str = ''

    def on_start(self):
        resp = self.client.post(
            '/auth/login',
            data={'username': self.role_username, 'password': PASSWORD},
            headers={'X-Requested-With': 'XMLHttpRequest'},
            catch_response=True,
            name=f'[login:{self.role_username}]',
        )
        if resp.status_code != 200 or b'"success": true' not in resp.content:
            resp.failure(f'login failed for {self.role_username}: HTTP {resp.status_code}')
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
        q = random.choice(['a', 'm', 'س', '05'])
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
