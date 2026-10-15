"""Tests for services.audit_cleanup_service.AuditCleanupService."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.extensions import db
from models.audit_trail import LoginAttempt, SecurityEvent, SystemLog
from models.phi_audit_log import PHIAuditLog
from services.audit_cleanup_service import RETENTION_CONFIG, AuditCleanupService


class TestAuditCleanupDryRun:
    def test_dry_run_returns_eligible_count_no_deletion(self, app, test_tenant):
        # Seed an old login_attempt
        old = LoginAttempt(
            tenant_id=test_tenant.id,
            username='old_user',
            success=False,
            created_at=datetime.now(UTC) - timedelta(days=40),
        )
        db.session.add(old)
        db.session.commit()

        result = AuditCleanupService.cleanup_table(
            table_name='login_attempts',
            retention_days=30,
            dry_run=True,
        )
        assert result['dry_run'] is True
        assert result['eligible'] >= 1
        assert result['deleted'] == 0
        assert result['error'] is None

        # Verify row still exists
        assert db.session.get(LoginAttempt, old.id) is not None


class TestAuditCleanupActualDeletion:
    def test_deletes_old_login_attempts(self, app, test_tenant):
        # Create old and new records
        old = LoginAttempt(
            tenant_id=test_tenant.id,
            username='old_user',
            success=False,
            created_at=datetime.now(UTC) - timedelta(days=40),
        )
        new = LoginAttempt(
            tenant_id=test_tenant.id,
            username='new_user',
            success=True,
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.session.add_all([old, new])
        db.session.commit()
        old_id, new_id = old.id, new.id

        result = AuditCleanupService.cleanup_table(
            table_name='login_attempts',
            retention_days=30,
            batch_size=100,
            sleep_ms=0,
            dry_run=False,
        )
        assert result['error'] is None
        assert result['deleted'] == 1
        assert result['eligible'] == 1

        assert db.session.get(LoginAttempt, old_id) is None
        assert db.session.get(LoginAttempt, new_id) is not None

    def test_deletes_old_system_logs(self, app, test_tenant):
        old = SystemLog(
            tenant_id=test_tenant.id,
            log_level='INFO',
            log_category='system',
            message='Old log',
            created_at=datetime.now(UTC) - timedelta(days=100),
        )
        new = SystemLog(
            tenant_id=test_tenant.id,
            log_level='INFO',
            log_category='system',
            message='New log',
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.session.add_all([old, new])
        db.session.commit()
        old_id, new_id = old.id, new.id

        result = AuditCleanupService.cleanup_table(
            table_name='system_logs',
            retention_days=90,
            batch_size=100,
            sleep_ms=0,
            dry_run=False,
        )
        assert result['deleted'] == 1
        assert db.session.get(SystemLog, old_id) is None
        assert db.session.get(SystemLog, new_id) is not None

    def test_deletes_old_security_events(self, app, test_tenant):
        old = SecurityEvent(
            tenant_id=test_tenant.id,
            event_type='login_failed',
            description='Old breach attempt',
            severity='medium',
            created_at=datetime.now(UTC) - timedelta(days=400),
        )
        new = SecurityEvent(
            tenant_id=test_tenant.id,
            event_type='login_failed',
            description='Recent attempt',
            severity='medium',
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.session.add_all([old, new])
        db.session.commit()
        old_id, new_id = old.id, new.id

        result = AuditCleanupService.cleanup_table(
            table_name='security_events',
            retention_days=365,
            batch_size=100,
            sleep_ms=0,
            dry_run=False,
        )
        assert result['deleted'] == 1
        assert db.session.get(SecurityEvent, old_id) is None
        assert db.session.get(SecurityEvent, new_id) is not None

    def test_no_rows_to_delete_returns_zero(self, app, test_tenant):
        # All records are recent
        recent = LoginAttempt(
            tenant_id=test_tenant.id,
            username='recent',
            success=True,
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.session.add(recent)
        db.session.commit()

        result = AuditCleanupService.cleanup_table(
            table_name='login_attempts',
            retention_days=30,
            batch_size=100,
            sleep_ms=0,
            dry_run=False,
        )
        assert result['deleted'] == 0
        assert result['eligible'] == 0

    def test_run_all_processes_multiple_tables(self, app, test_tenant):
        # Seed one old record in login_attempts and system_logs
        la = LoginAttempt(
            tenant_id=test_tenant.id,
            username='batch_old',
            success=False,
            created_at=datetime.now(UTC) - timedelta(days=40),
        )
        sl = SystemLog(
            tenant_id=test_tenant.id,
            log_level='ERROR',
            log_category='security',
            message='Batch old',
            created_at=datetime.now(UTC) - timedelta(days=100),
        )
        db.session.add_all([la, sl])
        db.session.commit()

        results = AuditCleanupService.run_all(
            tables=['login_attempts', 'system_logs'],
            batch_size=100,
            sleep_ms=0,
            dry_run=False,
        )
        assert len(results) == 2
        for r in results:
            assert r['error'] is None
            assert r['deleted'] == 1

    def test_phi_audit_logs_refuses_retention_deletion(self, app, test_tenant):
        """phi_audit_logs is immutable, so retention must refuse rather than delete.

        The app role holds no UPDATE/DELETE on the table (revoked in s2_003) and
        the RLS policies are `no_update` / `no_delete` (s2_007). The previous
        version of this test asserted `deleted == 1`, which could only ever pass
        if one of those two layers was removed.
        """
        old = PHIAuditLog(
            tenant_id=test_tenant.id,
            actor_id=None,
            target_model='Patient',
            target_id=1,
            action='CREATE',
            created_at=datetime.now(UTC) - timedelta(days=100),
        )
        new = PHIAuditLog(
            tenant_id=test_tenant.id,
            actor_id=None,
            target_model='Patient',
            target_id=2,
            action='CREATE',
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.session.add_all([old, new])
        db.session.commit()
        old_id, new_id = old.id, new.id

        result = AuditCleanupService.cleanup_table(
            table_name='phi_audit_logs',
            retention_days=90,
            batch_size=100,
            sleep_ms=0,
            dry_run=False,
        )
        # The refusal is explicit, not a silent zero.
        assert result['deleted'] == 0
        assert result['error'] is not None
        assert 'immutable' in result['error']

        # Both rows survive, including the one past the nominal 90-day window.
        assert db.session.get(PHIAuditLog, old_id) is not None
        assert db.session.get(PHIAuditLog, new_id) is not None

        # The database refuses the delete too, independently of this service.
        with pytest.raises(Exception):
            db.session.execute(text('DELETE FROM phi_audit_logs WHERE id = :i'), {'i': old_id})
        db.session.rollback()
        assert db.session.get(PHIAuditLog, old_id) is not None

    def test_batch_size_limits_deletion_per_pass(self, app, test_tenant):
        # Create 5 old records, batch_size=2
        records = []
        for i in range(5):
            records.append(
                LoginAttempt(
                    tenant_id=test_tenant.id,
                    username=f'batch_{i}',
                    success=False,
                    created_at=datetime.now(UTC) - timedelta(days=40),
                )
            )
        db.session.add_all(records)
        db.session.commit()

        # First pass with batch_size=2 should delete exactly 2
        result = AuditCleanupService.cleanup_table(
            table_name='login_attempts',
            retention_days=30,
            batch_size=2,
            sleep_ms=0,
            dry_run=False,
        )
        # The service loops until no more rows match, so total deleted = 5
        assert result['deleted'] == 5
        assert result['eligible'] == 5

    def test_retention_config_has_all_tables(self):
        expected = {
            'platform_audit_logs',
            'audit_trails',
            'system_logs',
            'security_events',
            'login_attempts',
            'slow_query_reports',
        }
        assert set(RETENTION_CONFIG.keys()) == expected
        for cfg in RETENTION_CONFIG.values():
            assert 'days' in cfg
            assert 'model_path' in cfg
            assert 'column' in cfg
            assert cfg['days'] > 0

    def test_immutable_tables_are_never_in_retention_config(self):
        """The immutable PHI trail must not reappear in the destructive config."""
        from services.audit_cleanup_service import IMMUTABLE_TABLES

        assert 'phi_audit_logs' in IMMUTABLE_TABLES
        assert not (IMMUTABLE_TABLES & set(RETENTION_CONFIG.keys()))
