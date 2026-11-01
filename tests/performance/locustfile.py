"""Performance testing with Locust."""
import re

from locust import HttpUser, between, task


class MedicalUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """Login on start."""
        r = self.client.get("/auth/login")
        csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
        csrf = csrf_match.group(1) if csrf_match else ''
        self.client.post("/auth/login", data={
            "csrf_token": csrf,
            "username": "superadmin",
            "password": "Password@123",
        })

    @task(3)
    def health_check(self):
        self.client.get("/__health")

    @task(2)
    def home(self):
        self.client.get("/")

    @task(1)
    def owner_dashboard(self):
        self.client.get("/owner/dashboard")

    @task(1)
    def settings(self):
        self.client.get("/settings")

    @task(1)
    def metrics(self):
        self.client.get("/metrics")
