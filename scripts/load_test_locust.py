"""
Locust Load-Testing Baseline Script

Simulates concurrent active users performing the most common operations:
  1. Login (POST /auth/login)
  2. OTP request (GET /mfa/verify or POST to OTP endpoint)
  3. Patient lookup (GET /api/patients/search)
  4. Payment creation (POST /payment/process/{visit_id})

Usage:
  pip install locust
  locust -f scripts/load_test_locust.py --host=http://localhost:5000 -u 50 -r 5

Environment overrides:
  LOCUST_USERNAME   default: accountant_test
  LOCUST_PASSWORD   default: ValidPass123!
  LOCUST_TENANT     default: pharmacy-shifa
"""

from __future__ import annotations

import os
import random
from datetime import datetime

from locust import HttpUser, between, task


class MedicalPlatformUser(HttpUser):
    """Simulates a medical platform user (receptionist/accountant)."""

    wait_time = between(1, 5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username = os.getenv('LOCUST_USERNAME', 'accountant_test')
        self.password = os.getenv('LOCUST_PASSWORD', 'ValidPass123!')
        self.tenant_slug = os.getenv('LOCUST_TENANT', 'pharmacy-shifa')
        self._csrf_token: str | None = None
        self._logged_in = False

    def on_start(self):
        """Login and extract CSRF token before any tasks run."""
        self._do_login()

    def on_stop(self):
        """Logout at end of session."""
        if self._logged_in:
            self.client.get('/auth/logout', name='logout')

    def _do_login(self):
        """Authenticate via standard form login."""
        # 1. GET login page to grab CSRF token
        resp = self.client.get('/auth/login', name='login_page')
        if resp.status_code != 200:
            return

        # Extract csrf token from hidden input
        import re

        match = re.search(r'name="csrf_token"[^>]+value="([^"]+)"', resp.text)
        csrf = match.group(1) if match else ''

        # 2. POST credentials
        login_resp = self.client.post(
            '/auth/login',
            data={
                'username': self.username,
                'password': self.password,
                'tenant_slug': self.tenant_slug,
                'csrf_token': csrf,
            },
            name='login_post',
            allow_redirects=True,
        )
        if login_resp.status_code in (200, 302):
            self._logged_in = True
            self._csrf_token = csrf

    @task(5)
    def patient_search(self):
        """Search for patients — high-frequency operation."""
        if not self._logged_in:
            return
        search_terms = ['أحمد', 'محمد', 'علي', 'فاطمة', 'Ahmad', 'test']
        term = random.choice(search_terms)
        self.client.get(
            f'/api/patients/search?q={term}',
            name='patient_search',
        )

    @task(3)
    def visit_list(self):
        """List today's visits."""
        if not self._logged_in:
            return
        today = datetime.now().strftime('%Y-%m-%d')
        self.client.get(
            f'/reception/visits?date={today}',
            name='visit_list_today',
        )

    @task(2)
    def payment_creation(self):
        """Simulate creating a payment for a random visit."""
        if not self._logged_in:
            return
        # In a real load test you would first fetch a visit_id from the list
        # and then POST payment. Here we POST with a likely-nonexistent ID
        # which returns 404 — that still exercises the auth + tenant
        # middleware + DB lookup path, which is the valuable load metric.
        visit_id = random.randint(1, 10000)
        self.client.post(
            f'/payment/process/{visit_id}',
            data={
                'paid_amount': str(random.randint(10, 500)),
                'payment_method': random.choice(['cash', 'card']),
                'payment_currency': 'ILS',
                'csrf_token': self._csrf_token or '',
            },
            name='payment_process',
            allow_redirects=True,
        )

    @task(1)
    def otp_request_simulation(self):
        """Simulate OTP request (if MFA is enabled for the test user)."""
        # This is a lightweight GET to the verify page; actual OTP sending
        # would require Twilio credentials and cost money per request.
        if not self._logged_in:
            return
        self.client.get('/mfa/verify', name='mfa_verify_page')

    @task(1)
    def dashboard_load(self):
        """Load the main dashboard — heavy template with many DB queries."""
        if not self._logged_in:
            return
        self.client.get('/', name='dashboard')


class AnonymousUser(HttpUser):
    """Simulates unauthenticated traffic (login page, static assets)."""

    wait_time = between(5, 15)

    @task(1)
    def login_page(self):
        self.client.get('/auth/login', name='anon_login_page')

    @task(1)
    def health_check(self):
        self.client.get('/health', name='health_check')
