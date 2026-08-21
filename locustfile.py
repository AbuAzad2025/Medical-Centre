"""Load test script for the Medical System using Locust.

Tests basic radiology and authentication endpoints under load.
"""

from locust import HttpUser, task, between, events
import json


# Configuration
HOST = 'http://localhost:5000'
# Wait time between tasks
wait_time = between(1, 3)


class MedicalUser(HttpUser):
    """Simulates a medical staff user performing typical operations."""

    @task(10)
    def auth_login(self):
        """Simulate user login."""
        self.client.post(
            '/auth/login',
            data={'username': 'doctor_user', 'password': 'ValidPass123!'},
            catch_errors=True,
        )

    @task(15)
    def view_worklist(self):
        """Simulate technician viewing the radiology worklist."""
        self.client.get('/radiology/worklist?status=REQUESTED', catch_errors=True)

    @task(5)
    def view_templates(self):
        """Simulate manager viewing templates."""
        self.client.get('/radiology/api/report-templates', catch_errors=True)

    @task(3)
    def claim_request(self):
        """Simulate technician claiming a request."""
        import random

        req_id = random.randint(1, 100)
        self.client.post(
            f'/radiology/worklist/claim/{req_id}',
            headers={'Accept': 'application/json'},
            catch_errors=True,
        )

    @task(8)
    def complete_request(self):
        """Simulate technician completing a request."""
        import random

        req_id = random.randint(1, 100)
        self.client.post(
            f'/radiology/worklist/complete/{req_id}',
            headers={'Accept': 'application/json'},
            json={'findings': 'No acute findings', 'impression': 'Normal'},
            catch_errors=True,
        )

    @task(3)
    def create_request(self):
        """Simulate doctor creating a radiology request."""
        self.client.post(
            '/doctor/radiology-request/1',
            data={'modality': 'XRAY', 'body_part': 'Chest', 'notes': 'PA view'},
            catch_errors=True,
        )

    @task(2)
    def create_template(self):
        """Simulate manager creating a template."""
        self.client.post(
            '/radiology/api/report-templates',
            json={
                'name': 'Load Test Template',
                'modality': 'XRAY',
                'findings': 'Test findings',
                'impression': 'Test impression',
            },
            catch_errors=True,
        )


# Events
@events.test_start.adddef
def on_test_start(environment, **kwargs):
    """Called when the test starts."""
    environment.runner.inject_ramp_users(users_count=10, spawn_rate=2)
    print(f'\\n=== Load test started ===')
    print(f'Target host: {HOST}')
    print(f'Users: 10, spawn rate: 2/s')


@events.test_stop.adddef
def on_test_stop(environment, **kwargs):
    """Called when the test stops."""
    print('\\n=== Load test stopped ===')
    print(f'Total requests: {environment.stats.total}')
    print(f'Average response time: {environment.stats.avg_response_time:.2f}ms')


# Hook to report failures
@events.test_request_failure.adddef
def on_request_failure(request_type, name, response_time, response_length, exception, **kwargs):
    """Log failed requests."""
    print(f'FAIL: {request_type} {name} - {exception}')


# Summary report hook
@events.test_stop.adddef
def on_test_stop_debug(environment, **kwargs):
    """Print detailed statistics at test stop."""
    print('\\n=== Response Time Distribution ===')
    for pct, ms in environment.stats.get_percents().items():
        print(f'  {pct}th percentile: {ms:.1f}ms')
