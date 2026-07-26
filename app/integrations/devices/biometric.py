"""
Biometric authentication — delegates to BiometricCredential / BiometricAuthChallenge models.
"""
from __future__ import annotations
from sqlalchemy import select

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback

logger = logging.getLogger(__name__)


class BiometricAuth:
    """DB-backed biometric credential management (WebAuthn / device templates)."""

    def __init__(self, driver_name: Optional[str] = None, tenant_id: Optional[int] = None):
        self.driver_name = driver_name or 'db'
        self.tenant_id = tenant_id

    def _resolve_tenant_id(self, tenant_id: Optional[int] = None) -> Optional[int]:
        if tenant_id is not None:
            return tenant_id
        if self.tenant_id is not None:
            return self.tenant_id
        try:
            from flask import g
            return getattr(g, 'tenant_id', None)
        except Exception:
            return None

    def enroll(
        self,
        user_id: int,
        template: bytes | dict | None = None,
        *,
        credential_id: Optional[str] = None,
        public_key: Optional[str] = None,
        device_type: str = 'security_key',
        device_name: Optional[str] = None,
        tenant_id: Optional[int] = None,
        **kwargs: Any,
    ) -> bool:
        from models.biometric_auth import BiometricCredential

        payload = template if isinstance(template, dict) else {}
        cred_id = credential_id or payload.get('credential_id') or secrets.token_urlsafe(32)
        pub_key = public_key or payload.get('public_key') or ''
        if isinstance(template, bytes) and template and not pub_key:
            pub_key = template.decode('utf-8', errors='ignore')

        cred = BiometricCredential(
            user_id=user_id,
            tenant_id=self._resolve_tenant_id(tenant_id),
            credential_id=cred_id,
            public_key=pub_key,
            device_type=device_type or payload.get('device_type', 'security_key'),
            device_name=device_name or payload.get('device_name'),
            aaguid=kwargs.get('aaguid') or payload.get('aaguid'),
            authenticator_attachment=kwargs.get('authenticator_attachment') or payload.get('authenticator_attachment'),
            is_active=True,
        )
        db.session.add(cred)
        safe_commit(db.session, error_message="database commit failed", reraise=True)
        logger.info('Enrolled biometric credential user=%s cred=%s', user_id, cred_id)
        return True

    def verify(
        self,
        user_id: int,
        template: bytes | dict | None = None,
        *,
        credential_id: Optional[str] = None,
        sign_count: Optional[int] = None,
        tenant_id: Optional[int] = None,
    ) -> bool:
        from models.biometric_auth import BiometricCredential

        payload = template if isinstance(template, dict) else {}
        cred_id = credential_id or payload.get('credential_id')
        if not cred_id:
            return False

        query = select(BiometricCredential)
        tid = self._resolve_tenant_id(tenant_id)
        if tid is not None:
            query = query.filter_by(tenant_id=tid)

        cred = query.first()
        if not cred:
            return False

        new_count = sign_count if sign_count is not None else payload.get('sign_count')
        if new_count is not None and int(new_count) <= int(cred.sign_count or 0):
            return False

        if new_count is not None:
            cred.sign_count = int(new_count)
        cred.last_used_at = datetime.now(timezone.utc)
        safe_commit(db.session, error_message="database commit failed", reraise=True)
        return True

    def list_credentials(self, user_id: int, *, tenant_id: Optional[int] = None) -> list[dict]:
        from models.biometric_auth import BiometricCredential

        query = select(BiometricCredential)
        tid = self._resolve_tenant_id(tenant_id)
        if tid is not None:
            query = query.filter_by(tenant_id=tid)
        return [
            {
                'id': c.id,
                'credential_id': c.credential_id,
                'device_type': c.device_type,
                'device_name': c.device_name,
                'last_used_at': c.last_used_at.isoformat() if c.last_used_at else None,
                'created_at': c.created_at.isoformat() if c.created_at else None,
            }
            for c in query.order_by(BiometricCredential.created_at.desc()).all()
        ]

    def create_challenge(
        self,
        *,
        user_id: Optional[int] = None,
        challenge_type: str = 'authentication',
        ttl_minutes: int = 5,
        tenant_id: Optional[int] = None,
    ) -> str:
        from models.biometric_auth import BiometricAuthChallenge

        challenge = secrets.token_urlsafe(32)
        ch = BiometricAuthChallenge(
            user_id=user_id,
            tenant_id=self._resolve_tenant_id(tenant_id),
            challenge=challenge,
            challenge_type=challenge_type,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        )
        db.session.add(ch)
        safe_commit(db.session, error_message="database commit failed", reraise=True)
        return challenge

    def consume_challenge(self, challenge: str, *, challenge_type: Optional[str] = None) -> bool:
        from models.biometric_auth import BiometricAuthChallenge

        query = select(BiometricAuthChallenge)
        if challenge_type:
            query = query.filter_by(challenge_type=challenge_type)
        ch = query.first()
        if not ch:
            return False
        if ch.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return False
        ch.used = True
        safe_commit(db.session, error_message="database commit failed", reraise=True)
        return True

    def is_enabled(self, user_id: Optional[int] = None) -> bool:
        from models.biometric_auth import BiometricCredential

        query = select(BiometricCredential)
        if user_id is not None:
            query = query.filter_by(user_id=user_id)
        tid = self._resolve_tenant_id()
        if tid is not None:
            query = query.filter_by(tenant_id=tid)
        return query.count() > 0
