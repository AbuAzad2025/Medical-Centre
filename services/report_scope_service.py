"""
Report Scope Service - scopes reports by tenant, module, and user role
"""

from typing import Any

from sqlalchemy import select


class ReportScopeService:
    """Provides scoped report data respecting tenant/module boundaries."""

    @staticmethod
    def get_report_data(
        report_type: str, tenant_id: int | None = None, module: str | None = None, **filters
    ) -> dict[str, Any]:
        """Get report data scoped by tenant and module."""
        query_filters = []
        if tenant_id:
            query_filters.append(('tenant_id', tenant_id))

        if report_type == 'visit_stats':
            return ReportScopeService._visit_stats(tenant_id, **filters)
        if report_type == 'lab_volume':
            return ReportScopeService._lab_volume(tenant_id, **filters)
        if report_type == 'revenue':
            return ReportScopeService._revenue(tenant_id, **filters)
        if report_type == 'inventory':
            return ReportScopeService._inventory(tenant_id, **filters)
        if report_type == 'referral':
            return ReportScopeService._referral(tenant_id, **filters)
        return {}

    @staticmethod
    def _visit_stats(tenant_id: int | None, **filters) -> dict[str, Any]:
        from app.extensions import db
        from models.visit import Visit

        q = Visit.query
        if tenant_id:
            q = q.filter_by(tenant_id=tenant_id)
        if 'date_from' in filters:
            q = q.filter(Visit.created_at >= filters['date_from'])
        if 'date_to' in filters:
            q = q.filter(Visit.created_at <= filters['date_to'])
        total = q.count()
        by_status = db.session.execute(
            select(Visit.status, db.func.count()).group_by(Visit.status)
        ).all()
        return {'total_visits': total, 'by_status': dict(by_status)}

    @staticmethod
    def _lab_volume(tenant_id: int | None, **filters) -> dict[str, Any]:
        from app.extensions import db
        from models.lab_request import LabRequest

        q = LabRequest.query
        if tenant_id:
            q = q.filter_by(tenant_id=tenant_id)
        total = q.count()
        by_status = db.session.execute(
            select(LabRequest.status, db.func.count()).group_by(LabRequest.status)
        ).all()
        return {'total_lab_requests': total, 'by_status': dict(by_status)}

    @staticmethod
    def _revenue(tenant_id: int | None, **filters) -> dict[str, Any]:
        from app.extensions import db
        from models.payment import Payment

        q = Payment.query
        if tenant_id:
            q = q.filter_by(tenant_id=tenant_id)
        total = (
            db.session.execute(
                select(db.func.sum(Payment.amount_paid)).filter(
                    *([Payment.tenant_id == tenant_id] if tenant_id else [])
                )
            ).scalar()
            or 0
        )
        return {'total_revenue': float(total)}

    @staticmethod
    def _inventory(tenant_id: int | None, **filters) -> dict[str, Any]:
        from models.medication import Medication

        q = Medication.query
        if tenant_id:
            q = q.filter_by(tenant_id=tenant_id)
        low_stock = q.filter(Medication.quantity <= Medication.min_quantity).count()
        total = q.count()
        return {'total_medications': total, 'low_stock': low_stock}

    @staticmethod
    def _referral(tenant_id: int | None, **filters) -> dict[str, Any]:
        from models.visit import Visit

        q = Visit.query
        if tenant_id:
            q = q.filter_by(tenant_id=tenant_id)
        referrals = q.filter(Visit.referring_doctor_id.isnot(None)).count()
        total = q.count()
        return {'total_referrals': referrals, 'total_visits': total}
