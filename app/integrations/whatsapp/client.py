"""
WhatsApp Business API Client (Meta / Cloud API)
"""
import os
import json
import logging
from typing import Optional
import requests

logger = logging.getLogger(__name__)

class WhatsAppClient:
    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(self, api_token: Optional[str] = None, phone_number_id: Optional[str] = None):
        self.api_token = api_token or os.environ.get("WHATSAPP_API_TOKEN")
        self.phone_number_id = phone_number_id or os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
        if not self.api_token or not self.phone_number_id:
            raise RuntimeError("WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID are required")

    def _url(self, endpoint: str) -> str:
        return f"{self.BASE_URL}/{self.phone_number_id}/{endpoint}"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def send_text(self, to: str, body: str, preview_url: bool = False) -> dict:
        """Send a simple text message."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": preview_url, "body": body},
        }
        resp = requests.post(self._url("messages"), headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def send_template(self, to: str, template_name: str, language_code: str = "ar",
                        components: Optional[list] = None) -> dict:
        """Send a pre-approved template message."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components
        resp = requests.post(self._url("messages"), headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def send_document(self, to: str, document_url: str, caption: Optional[str] = None) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "document",
            "document": {"link": document_url, "caption": caption or ""},
        }
        resp = requests.post(self._url("messages"), headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
