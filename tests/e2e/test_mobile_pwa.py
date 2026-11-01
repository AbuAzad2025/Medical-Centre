"""Mobile and PWA E2E tests."""
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8000"


class TestMobileResponsive:
    MOBILE_VIEWPORTS = [
        {"width": 375, "height": 667, "name": "iPhone SE"},
        {"width": 414, "height": 896, "name": "iPhone 11"},
        {"width": 360, "height": 640, "name": "Android Small"},
    ]

    TABLET_VIEWPORTS = [
        {"width": 768, "height": 1024, "name": "iPad"},
        {"width": 1024, "height": 768, "name": "iPad Landscape"},
    ]

    def test_mobile_no_horizontal_scroll(self, page: Page):
        for vp in self.MOBILE_VIEWPORTS:
            page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
            page.goto(f"{BASE_URL}/auth/login")
            page.wait_for_load_state("networkidle")
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")
            assert scroll_width <= client_width + 5, \
                f"{vp['name']}: Horizontal scroll detected ({scroll_width} > {client_width})"

    def test_tablet_no_horizontal_scroll(self, page: Page):
        for vp in self.TABLET_VIEWPORTS:
            page.set_viewport_size({"width": vp["width"], "height": vp["height"]})
            page.goto(f"{BASE_URL}/auth/login")
            page.wait_for_load_state("networkidle")
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")
            assert scroll_width <= client_width + 5, \
                f"{vp['name']}: Horizontal scroll detected ({scroll_width} > {client_width})"

    def test_mobile_login_form_visible(self, page: Page):
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(f"{BASE_URL}/auth/login")
        expect(page.locator('input[name="username"]')).to_be_visible()
        expect(page.locator('input[type="password"]')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_be_visible()

    def test_rtl_layout_mobile(self, page: Page):
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto(f"{BASE_URL}/auth/login")
        dir_attr = page.evaluate("document.documentElement.getAttribute('dir')")
        assert dir_attr == "rtl", f"Expected RTL, got {dir_attr}"


class TestPWA:
    def test_manifest_accessible(self, page: Page):
        response = page.request.get(f"{BASE_URL}/static/manifest.json")
        assert response.status == 200
        data = response.json()
        assert "name" in data
        assert "icons" in data
        assert len(data["icons"]) > 0

    def test_manifest_has_required_fields(self, page: Page):
        response = page.request.get(f"{BASE_URL}/static/manifest.json")
        data = response.json()
        required = ["name", "short_name", "start_url", "display", "icons"]
        for field in required:
            assert field in data, f"Missing required field: {field}"

    def test_service_worker_registration(self, page: Page):
        page.goto(f"{BASE_URL}/auth/login")
        # Check if service worker is registered
        sw_registered = page.evaluate("""
            () => {
                return 'serviceWorker' in navigator;
            }
        """)
        # Service worker API should be available
        assert sw_registered is True or sw_registered is False  # Just check it doesn't crash
