"""E2E tests for critical flows using Playwright."""
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1280, "height": 720}}


class TestLoginFlow:
    def test_login_page_loads(self, page: Page):
        page.goto(f"{BASE_URL}/auth/login")
        title = page.title()
        assert "Login" in title or "تسجيل" in title or "AZAD" in title or "login" in title.lower() or "دخول" in title
        # Check for username and password fields
        expect(page.locator('input[name="username"], input[name="email"], input[type="text"]').first).to_be_visible()
        expect(page.locator('input[type="password"]').first).to_be_visible()

    def test_login_with_valid_credentials(self, page: Page):
        page.goto(f"{BASE_URL}/auth/login")
        # Fill credentials
        page.locator('input[name="username"], input[name="email"], input[type="text"]').first.fill("superadmin")
        page.locator('input[type="password"]').first.fill("Password@123")
        page.locator('button[type="submit"], input[type="submit"]').first.click()
        page.wait_for_load_state("networkidle")
        # Should redirect to dashboard
        expect(page).not_to_have_url(f"{BASE_URL}/auth/login")

    def test_login_with_invalid_credentials(self, page: Page):
        page.goto(f"{BASE_URL}/auth/login")
        page.locator('input[name="username"], input[name="email"], input[type="text"]').first.fill("invalid_user")
        page.locator('input[type="password"]').first.fill("wrong_password")
        page.locator('button[type="submit"], input[type="submit"]').first.click()
        page.wait_for_load_state("networkidle")
        # Should stay on login page or show error
        # Either way, should not be on dashboard
        assert "dashboard" not in page.url.lower() or page.url == f"{BASE_URL}/auth/login"

    def test_language_switcher(self, page: Page):
        page.goto(f"{BASE_URL}/auth/login")
        # Look for language switcher
        lang_switcher = page.locator('select[name="language"], .language-switcher, #language-switcher, [data-language]')
        if lang_switcher.count() > 0:
            expect(lang_switcher.first).to_be_visible()


class TestDashboard:
    def test_dashboard_loads_after_login(self, page: Page):
        page.goto(f"{BASE_URL}/auth/login")
        page.locator('input[name="username"], input[name="email"], input[type="text"]').first.fill("superadmin")
        page.locator('input[type="password"]').first.fill("Password@123")
        page.locator('button[type="submit"], input[type="submit"]').first.click()
        page.wait_for_load_state("networkidle")
        # Dashboard should load without errors
        expect(page).not_to_have_url(f"{BASE_URL}/auth/login")
        # Check no console errors
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.wait_for_timeout(2000)
        # Allow some errors but not critical ones
        critical_errors = [e for e in errors if "TypeError" in e or "ReferenceError" in e]
        assert len(critical_errors) == 0, f"Critical JS errors: {critical_errors}"


class TestResponsiveDesign:
    def test_mobile_viewport(self, page: Page):
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(f"{BASE_URL}/auth/login")
        expect(page.locator('body')).to_be_visible()
        # Page should not have horizontal scroll
        scroll_width = page.evaluate("document.documentElement.scrollWidth")
        client_width = page.evaluate("document.documentElement.clientWidth")
        assert scroll_width <= client_width + 5, f"Horizontal scroll detected: {scroll_width} > {client_width}"

    def test_tablet_viewport(self, page: Page):
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto(f"{BASE_URL}/auth/login")
        expect(page.locator('body')).to_be_visible()

    def test_desktop_viewport(self, page: Page):
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.goto(f"{BASE_URL}/auth/login")
        expect(page.locator('body')).to_be_visible()


class TestHealthEndpoints:
    def test_health_endpoint(self, page: Page):
        response = page.request.get(f"{BASE_URL}/health")
        assert response.status == 200
        data = response.json()
        assert data.get("status") == "ok"

    def test_health_detailed(self, page: Page):
        response = page.request.get(f"{BASE_URL}/__health")
        assert response.status == 200
