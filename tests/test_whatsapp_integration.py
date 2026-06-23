"""WhatsApp integration tests — fully mocked, no real network.

`requests.post` is monkeypatched; the client raises without credentials, and
the notification service is verified to compose Arabic bodies and delegate to
its injected client.
"""

from __future__ import annotations

import pytest

import app.integrations.whatsapp.client as client_mod
from app.integrations.whatsapp.client import WhatsAppClient
from app.integrations.whatsapp.service import WhatsAppNotificationService


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {"messages": [{"id": "wamid.TEST"}]}
        self.raised = False

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests import HTTPError
            raise HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture
def captured_post(monkeypatch):
    """Capture requests.post calls and return a controllable fake response."""
    calls = []
    holder = {"response": _FakeResponse()}

    def _fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return holder["response"]

    monkeypatch.setattr(client_mod.requests, "post", _fake_post)
    return calls, holder


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("WHATSAPP_API_TOKEN", "tok-123")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "999")
    return WhatsAppClient()


# ---------------------------------------------------------------------------
# Client construction
# ---------------------------------------------------------------------------
class TestClientInit:
    def test_raises_without_credentials(self, monkeypatch):
        monkeypatch.delenv("WHATSAPP_API_TOKEN", raising=False)
        monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
        with pytest.raises(RuntimeError):
            WhatsAppClient()

    def test_raises_with_partial_credentials(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_API_TOKEN", "tok")
        monkeypatch.delenv("WHATSAPP_PHONE_NUMBER_ID", raising=False)
        with pytest.raises(RuntimeError):
            WhatsAppClient()

    def test_explicit_args_override_env(self):
        c = WhatsAppClient(api_token="a", phone_number_id="b")
        assert c.api_token == "a"
        assert c.phone_number_id == "b"
        assert c._url("messages") == f"{WhatsAppClient.BASE_URL}/b/messages"

    def test_headers_carry_bearer_token(self):
        c = WhatsAppClient(api_token="secret", phone_number_id="1")
        headers = c._headers()
        assert headers["Authorization"] == "Bearer secret"
        assert headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# Client send_* payloads
# ---------------------------------------------------------------------------
class TestClientSend:
    def test_send_text_payload_shape(self, client, captured_post):
        calls, _ = captured_post
        out = client.send_text(to="+970590000000", body="مرحبا")
        assert out == {"messages": [{"id": "wamid.TEST"}]}
        payload = calls[0]["json"]
        assert payload["type"] == "text"
        assert payload["to"] == "+970590000000"
        assert payload["text"]["body"] == "مرحبا"
        assert calls[0]["url"].endswith("/999/messages")

    def test_send_template_includes_components(self, client, captured_post):
        calls, _ = captured_post
        client.send_template(to="+1", template_name="reminder", language_code="ar",
                             components=[{"type": "body"}])
        payload = calls[0]["json"]
        assert payload["type"] == "template"
        assert payload["template"]["name"] == "reminder"
        assert payload["template"]["language"]["code"] == "ar"
        assert payload["template"]["components"] == [{"type": "body"}]

    def test_send_document_payload(self, client, captured_post):
        calls, _ = captured_post
        client.send_document(to="+1", document_url="http://x/y.pdf", caption="فاتورة")
        payload = calls[0]["json"]
        assert payload["type"] == "document"
        assert payload["document"]["link"] == "http://x/y.pdf"
        assert payload["document"]["caption"] == "فاتورة"

    def test_http_error_propagates(self, client, captured_post):
        from requests import HTTPError
        _, holder = captured_post
        holder["response"] = _FakeResponse(status_code=500)
        with pytest.raises(HTTPError):
            client.send_text(to="+1", body="x")


# ---------------------------------------------------------------------------
# Notification service — body composition + delegation
# ---------------------------------------------------------------------------
class _SpyClient:
    def __init__(self):
        self.sent = []

    def send_text(self, to, body):
        self.sent.append({"to": to, "body": body})
        return {"ok": True}


class TestNotificationService:
    def test_appointment_reminder_body(self):
        spy = _SpyClient()
        svc = WhatsAppNotificationService(client=spy)
        svc.send_appointment_reminder("+1", "أحمد", "2026-07-01", "10:00", "خالد")
        assert spy.sent[0]["to"] == "+1"
        body = spy.sent[0]["body"]
        assert "أحمد" in body and "2026-07-01" in body and "خالد" in body

    def test_lab_results_with_link(self):
        spy = _SpyClient()
        svc = WhatsAppNotificationService(client=spy)
        svc.send_lab_results_ready("+1", "سارة", "V-100", login_link="http://x/login")
        assert "http://x/login" in spy.sent[0]["body"]

    def test_lab_results_without_link_omits_url(self):
        spy = _SpyClient()
        svc = WhatsAppNotificationService(client=spy)
        svc.send_lab_results_ready("+1", "سارة", "V-100")
        assert "http" not in spy.sent[0]["body"]

    def test_invoice_message(self):
        spy = _SpyClient()
        svc = WhatsAppNotificationService(client=spy)
        svc.send_invoice("+1", "علي", "250 ILS", receipt_link="http://x/r")
        body = spy.sent[0]["body"]
        assert "250 ILS" in body and "http://x/r" in body

    def test_medication_reminder(self):
        spy = _SpyClient()
        svc = WhatsAppNotificationService(client=spy)
        svc.send_medication_reminder("+1", "هدى", "Amoxicillin", "500mg")
        body = spy.sent[0]["body"]
        assert "Amoxicillin" in body and "500mg" in body

    def test_service_defaults_to_real_client_when_none(self, monkeypatch):
        monkeypatch.setenv("WHATSAPP_API_TOKEN", "tok")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1")
        svc = WhatsAppNotificationService()
        assert isinstance(svc.client, WhatsAppClient)
