from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy.orm.attributes import get_history

from app.shared.mixins import TenantMixin
from app_factory import db

TRACKED_MODELS: set = set()

_SKIP_COLUMNS = {'created_at', 'updated_at', 'deleted_at', 'is_deleted'}


def _serialize(val):
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, time):
        return val.isoformat()
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, bytes):
        return val.decode('utf-8', errors='replace')
    return val


class PHIAuditLog(TenantMixin, db.Model):
    __tablename__ = 'phi_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    ip_address = db.Column(db.String(45), nullable=True)
    request_id = db.Column(db.String(36), nullable=True, index=True)
    target_model = db.Column(db.String(64), nullable=False, index=True)
    target_id = db.Column(db.Integer, nullable=False, index=True)
    action = db.Column(db.String(10), nullable=False, index=True)
    changes = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (
        db.Index('idx_phi_audit_target', 'target_model', 'target_id'),
        db.Index('idx_phi_audit_created', 'created_at'),
        db.CheckConstraint("action IN ('CREATE', 'UPDATE', 'DELETE')", name='ck_phi_audit_action'),
    )

    actor = db.relationship('User', foreign_keys=[actor_id], lazy='selectin')


def _redact_changes(model_name: str, changes: dict) -> dict:
    from app.core.audit.phi_config import redact_value

    redacted = {}
    for field, value in changes.items():
        if isinstance(value, dict) and 'old' in value and 'new' in value:
            redacted[field] = {
                'old': redact_value(model_name, field, value['old']),
                'new': redact_value(model_name, field, value['new']),
            }
        else:
            redacted[field] = redact_value(model_name, field, value)
    return redacted


def _build_changes_for_create(instance) -> dict:
    changes = {}
    for mapper_key in instance.__mapper__.c:
        if mapper_key in _SKIP_COLUMNS:
            continue
        col = getattr(instance.__mapper__.c, mapper_key)
        if col.primary_key or col.foreign_keys:
            continue
        val = getattr(instance, mapper_key, None)
        if val is not None:
            changes[mapper_key] = _serialize(val)
    model_name = type(instance).__name__
    return _redact_changes(model_name, changes)


def _build_changes_for_update(instance) -> dict:
    changes = {}
    ins_mapper = instance.__mapper__
    for attr in ins_mapper.column_attrs:
        key = attr.key
        if key in _SKIP_COLUMNS:
            continue
        hist = get_history(instance, key)
        if not hist.has_changes():
            continue
        old_vals = hist.deleted
        new_vals = hist.added
        if not old_vals and not new_vals:
            continue
        old_val = old_vals[0] if old_vals else None
        new_val = new_vals[0] if new_vals else None
        old_val = _serialize(old_val)
        new_val = _serialize(new_val)
        changes[key] = {'old': old_val, 'new': new_val}
    model_name = type(instance).__name__
    return _redact_changes(model_name, changes)


def _phi_audit_before_flush(session, flush_context, instances):
    from app.core.audit.audit_context import get_audit_context

    ctx = get_audit_context()
    pendings = []

    for obj in session.new:
        if type(obj) in TRACKED_MODELS and not isinstance(obj, PHIAuditLog):
            pendings.append(
                {
                    'ctx': ctx,
                    'obj': obj,
                    'action': 'CREATE',
                    'changes_fn': _build_changes_for_create,
                }
            )

    for obj in session.dirty:
        if type(obj) in TRACKED_MODELS and not isinstance(obj, PHIAuditLog):
            if not session.is_modified(obj, include_collections=False):
                continue
            changes = _build_changes_for_update(obj)
            if changes:
                pendings.append(
                    {
                        'ctx': ctx,
                        'obj': obj,
                        'action': 'UPDATE',
                        'changes': changes,
                    }
                )

    for obj in session.deleted:
        if type(obj) in TRACKED_MODELS and not isinstance(obj, PHIAuditLog):
            pendings.append(
                {
                    'ctx': ctx,
                    'obj': obj,
                    'action': 'DELETE',
                    'changes_fn': _build_changes_for_create,
                }
            )

    if pendings:
        session._phi_audit_pendings = pendings


def _phi_audit_after_flush(session, flush_context):
    pendings = getattr(session, '_phi_audit_pendings', None)
    if not pendings:
        return
    del session._phi_audit_pendings

    from app.shared.tenant_filter import _current_tenant_id

    for item in pendings:
        obj = item['obj']
        ctx = item['ctx']
        action = item['action']

        target_id = obj.id
        if target_id is None:
            continue

        # Resolve tenant from audit context, falling back to the active
        # tenant filter context (g.tenant_id / session.info). If no tenant
        # context exists at all, skip writing the record — the row would be
        # rejected by RLS (NULL tenant_id) and fail-closed auto-assign would
        # raise on it. Nothing tenant-scoped is legitimately auditable in a
        # no-tenant context.
        tenant_id = ctx['tenant_id']
        if tenant_id is None:
            tenant_id = _current_tenant_id(session=session)
        if tenant_id is None:
            continue

        changes = item.get('changes') or item['changes_fn'](obj)

        audit = PHIAuditLog(
            actor_id=ctx['actor_id'],
            ip_address=ctx['ip_address'],
            request_id=ctx['request_id'],
            tenant_id=tenant_id,
            target_model=type(obj).__name__,
            target_id=target_id,
            action=action,
            changes=changes,
        )
        session.add(audit)


def _raise_on_modify(mapper, connection, target):
    raise RuntimeError('PHIAuditLog records are immutable and cannot be modified or deleted.')
