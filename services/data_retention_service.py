"""
Data Retention Service — enforce regulatory retention and purge policies
GDPR, HIPAA, and local medical record retention compliance
"""
from sqlalchemy import select

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from app.extensions import db

logger = logging.getLogger(__name__)


class RetentionCategory(Enum):
    MEDICAL_RECORD = "medical_record"
    LAB_RESULT = "lab_result"
    RADIOLOGY_RESULT = "radiology_result"
    PRESCRIPTION = "prescription"
    AUDIT_LOG = "audit_log"
    SESSION_LOG = "session_log"
    PATIENT_PHI = "patient_phi"
    BILLING_RECORD = "billing_record"
    COMMUNICATION = "communication"
    BACKUP = "backup"


@dataclass
class RetentionPolicy:
    """Defines how long a category of data must be retained and what happens after."""
    category: RetentionCategory
    retain_years: int  # Minimum retention period
    jurisdiction: str  # e.g., 'GDPR', 'HIPAA', 'MOH-SA', 'MOH-AE'
    action_after_retention: str  # 'archive', 'anonymize', 'delete', 'review'
    requires_approval: bool = False
    description: str = ""


class DataRetentionService:
    """
    Manages data lifecycle policies for regulated healthcare data.
    
    Default policies (customizable per tenant):
    - Medical records: 10 years (many jurisdictions)
    - Lab results: 7 years
    - Audit logs: 7 years (then archive)
    - Session logs: 2 years (then delete)
    - Billing: 7 years (tax/regulatory)
    - Communication (WhatsApp/SMS): 1 year
    """

    DEFAULT_POLICIES: List[RetentionPolicy] = [
        RetentionPolicy(RetentionCategory.MEDICAL_RECORD, 10, "default", "archive", True,
                        "Medical records must be retained for 10 years minimum"),
        RetentionPolicy(RetentionCategory.LAB_RESULT, 7, "default", "archive", True,
                        "Lab results retained for 7 years"),
        RetentionPolicy(RetentionCategory.RADIOLOGY_RESULT, 7, "default", "archive", True,
                        "Radiology images retained for 7 years (consider PACS archival)"),
        RetentionPolicy(RetentionCategory.PRESCRIPTION, 5, "default", "archive", False,
                        "Prescriptions retained for 5 years"),
        RetentionPolicy(RetentionCategory.AUDIT_LOG, 7, "default", "archive", True,
                        "Audit logs retained for 7 years then moved to cold storage"),
        RetentionPolicy(RetentionCategory.SESSION_LOG, 2, "default", "delete", False,
                        "Session logs purged after 2 years"),
        RetentionPolicy(RetentionCategory.PATIENT_PHI, 0, "GDPR", "review", True,
                        "Patient PHI held until consent withdrawal or legal obligation ends"),
        RetentionPolicy(RetentionCategory.BILLING_RECORD, 7, "default", "archive", True,
                        "Billing records retained for 7 years (tax compliance)"),
        RetentionPolicy(RetentionCategory.COMMUNICATION, 1, "default", "anonymize", False,
                        "Communication logs anonymized after 1 year"),
        RetentionPolicy(RetentionCategory.BACKUP, 3, "default", "delete", False,
                        "Backups older than 3 years removed"),
    ]

    def __init__(self, policies: Optional[List[RetentionPolicy]] = None):
        self.policies = policies or list(self.DEFAULT_POLICIES)
        self._policy_map = {p.category: p for p in self.policies}

    def get_policy(self, category: RetentionCategory) -> Optional[RetentionPolicy]:
        return self._policy_map.get(category)

    def set_policy(self, policy: RetentionPolicy) -> None:
        self._policy_map[policy.category] = policy
        # Update list to reflect changes
        self.policies = list(self._policy_map.values())

    def calculate_retention_deadline(self, category: RetentionCategory, created_at: datetime) -> datetime:
        """Calculate the date after which retention policy action applies."""
        policy = self.get_policy(category)
        years = policy.retain_years if policy else 7
        try:
            from dateutil.relativedelta import relativedelta
            return created_at + relativedelta(years=years)
        except ImportError:
            import calendar
            import calendar
            target_year = created_at.year + years
            day = min(created_at.day, calendar.monthrange(target_year, created_at.month)[1])
            return created_at.replace(year=target_year, day=day)

    def is_eligible_for_action(self, category: RetentionCategory, created_at: datetime) -> bool:
        """Check if a record's retention period has expired."""
        deadline = self.calculate_retention_deadline(category, created_at)
        return datetime.now(timezone.utc) >= deadline

    def identify_expired_records(
        self,
        tenant_id: int,
        batch_size: int = 1000,
    ) -> Dict[RetentionCategory, List[Dict]]:
        """
        Scan tenant data and identify records that have exceeded retention.
        
        Returns dict mapping category -> list of {id, created_at, action}.
        Does NOT modify data — returns audit-ready list for review.
        """
        expired: Dict[RetentionCategory, List[Dict]] = {}
        now = datetime.now(timezone.utc)

        # Medical records
        try:
            from models.medical_record import MedicalRecord
            policy = self.get_policy(RetentionCategory.MEDICAL_RECORD)
            if policy:
                cutoff = now - timedelta(days=policy.retain_years * 365)
                records = db.session.execute(select(MedicalRecord).filter(
                    MedicalRecord.tenant_id == tenant_id,
                    MedicalRecord.created_at < cutoff,
                ).limit(batch_size)).scalars().all()
                expired[RetentionCategory.MEDICAL_RECORD] = [
                    {
                        'id': r.id,
                        'created_at': r.created_at.isoformat() if r.created_at else None,
                        'patient_id': r.patient_id,
                        'action': policy.action_after_retention,
                        'requires_approval': policy.requires_approval,
                    }
                    for r in records
                ]
        except Exception as exc:
            logger.exception("Failed to scan medical records for retention: %s", exc)

        # Audit logs
        try:
            from models.audit_trail import AuditTrail
            policy = self.get_policy(RetentionCategory.AUDIT_LOG)
            if policy:
                cutoff = now - timedelta(days=policy.retain_years * 365)
                records = db.session.execute(select(AuditTrail).filter(
                    AuditTrail.tenant_id == tenant_id,
                    AuditTrail.created_at < cutoff,
                ).limit(batch_size)).scalars().all()
                expired[RetentionCategory.AUDIT_LOG] = [
                    {
                        'id': r.id,
                        'created_at': r.created_at.isoformat() if r.created_at else None,
                        'action': policy.action_after_retention,
                        'requires_approval': policy.requires_approval,
                    }
                    for r in records
                ]
        except Exception as exc:
            logger.exception("Failed to scan audit logs for retention: %s", exc)

        # Session logs
        try:
            from models.digital_signature import SessionLog
            policy = self.get_policy(RetentionCategory.SESSION_LOG)
            if policy:
                cutoff = now - timedelta(days=policy.retain_years * 365)
                records = db.session.execute(select(SessionLog).filter(
                    SessionLog.tenant_id == tenant_id,
                    SessionLog.created_at < cutoff,
                ).limit(batch_size)).scalars().all()
                expired[RetentionCategory.SESSION_LOG] = [
                    {
                        'id': r.id,
                        'created_at': r.created_at.isoformat() if r.created_at else None,
                        'action': policy.action_after_retention,
                        'requires_approval': policy.requires_approval,
                    }
                    for r in records
                ]
        except Exception as exc:
            logger.exception("Failed to scan session logs for retention: %s", exc)

        return expired

    def anonymize_patient_data(self, patient_id: int, tenant_id: int, approved_by: int) -> bool:
        """
        Anonymize a patient's PII while preserving medical records for research/statistics.
        This implements GDPR Right to Erasure with medical exception (keep clinical data).
        """
        try:
            from models.patient import Patient
            from models.audit_trail import AuditTrail

            patient = db.session.execute(select(Patient).filter_by(id=patient_id, tenant_id=tenant_id)).scalars().first()
            if not patient:
                return False

            # Anonymize identifying fields
            patient.first_name = "ANONYMIZED"
            patient.last_name = "ANONYMIZED"
            patient.first_name_ar = "ANONYMIZED"
            patient.last_name_ar = "ANONYMIZED"
            patient.phone = None
            patient.national_id = None
            patient.address = None
            patient.email = None
            patient.insurance_member_number = None
            patient.admin_notes = "[ANONYMIZED]"

            # Audit the action
            db.session.add(AuditTrail(
                entity_type='patient',
                entity_id=patient_id,
                action='anonymize',
                user_id=approved_by,
                description='Patient data anonymized per retention/GDPR policy',
            ))

            db.session.commit()
            logger.info("Patient %s anonymized by user %s", patient_id, approved_by)
            return True
        except Exception as exc:
            logger.exception("Failed to anonymize patient %s: %s", patient_id, exc)
            return False

    def delete_expired_session_logs(self, tenant_id: int, dry_run: bool = True) -> Tuple[int, List[int]]:
        """
        Delete session logs that have exceeded retention.
        
        Returns:
            (count_deleted, list_of_deleted_ids)
        """
        from models.user import SessionLog

        policy = self.get_policy(RetentionCategory.SESSION_LOG)
        if not policy:
            return 0, []

        cutoff = datetime.now(timezone.utc) - timedelta(days=policy.retain_years * 365)
        query = select(SessionLog)

        if dry_run:
            records = query.limit(1000).all()
            return len(records), [r.id for r in records]

        # Actual deletion
        records = query.all()
        deleted_ids = [r.id for r in records]
        for r in records:
            db.session.delete(r)
        db.session.commit()
        logger.info("Deleted %s expired session logs for tenant %s", len(deleted_ids), tenant_id)
        return len(deleted_ids), deleted_ids

    def generate_retention_report(self, tenant_id: int) -> Dict:
        """Generate a compliance report of retention status for a tenant."""
        expired = self.identify_expired_records(tenant_id)
        report = {
            'tenant_id': tenant_id,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'policies': [
                {
                    'category': p.category.value,
                    'retain_years': p.retain_years,
                    'jurisdiction': p.jurisdiction,
                    'action': p.action_after_retention,
                    'requires_approval': p.requires_approval,
                }
                for p in self.policies
            ],
            'expired_records': {
                cat.value: {
                    'count': len(records),
                    'sample_ids': [r['id'] for r in records[:5]],
                    'action': records[0]['action'] if records else None,
                    'requires_approval': records[0]['requires_approval'] if records else None,
                }
                for cat, records in expired.items()
            },
        }
        return report
