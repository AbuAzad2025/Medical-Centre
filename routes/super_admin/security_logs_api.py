"""Security logs API — real audit data for the super-admin security console.

Replaces the legacy static demo table with server-side paginated queries
over AuditTrail + LoginAttempt.  All responses are JSON and tenant-scoped
by construction (both models are TenantMixin-backed).
"""

from datetime import UTC, datetime

from flask import jsonify, request
from flask_login import login_required
from sqlalchemy import func, literal, literal_column, or_, select, union_all

from app.extensions import db
from models.audit_trail import AuditTrail, LoginAttempt
from models.user import User
from routes.super_admin import super_admin_bp
from utils.decorators import role_required_json

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25


SEVERITY_BY_ACTION = {
    'login_failed': 'high',
    'login_blocked': 'critical',
    'force_logout': 'high',
    'unauthorized_access': 'critical',
    'permission_denied': 'medium',
    'password_reset': 'high',
    'IMPERSONATE': 'critical',
    'security': 'high',
}


def _parse_date(value: str, end_of_day: bool = False):
    """Parse YYYY-MM-DD; for range ends include the whole day."""
    if not value:
        return None
    try:
        d = datetime.strptime(value.strip(), '%Y-%m-%d')
        if end_of_day:
            return d.replace(hour=23, minute=59, second=59)
        return d
    except ValueError:
        return None


def _severity(action: str) -> str:
    return SEVERITY_BY_ACTION.get(action or '', 'low')


@super_admin_bp.route('/api/security-logs', methods=['GET'])
@login_required
@role_required_json('super_admin', 'owner')
def list_security_logs():
    """Paginated, filtered security event feed (AuditTrail ∪ LoginAttempt).

    Query params: page, page_size, action, user_id, severity,
                  date_from, date_to, q (free text on username/description/notes).
    """
    page = max(1, request.args.get('page', 1, type=int))
    page_size = min(
        MAX_PAGE_SIZE, max(1, request.args.get('page_size', DEFAULT_PAGE_SIZE, type=int))
    )
    action = (request.args.get('action') or '').strip()
    user_id = request.args.get('user_id', type=int)
    severity = (request.args.get('severity') or '').strip()
    date_from = _parse_date(request.args.get('date_from', ''))
    date_to = _parse_date(request.args.get('date_to', ''), end_of_day=True)
    q = (request.args.get('q') or '').strip()

    audit_q = (
        select(
            AuditTrail.id.label('id'),
            literal('audit').label('source'),
            AuditTrail.action.label('action'),
            AuditTrail.created_at.label('created_at'),
            AuditTrail.user_ip.label('ip'),
            AuditTrail.description.label('description'),
            AuditTrail.notes.label('notes'),
            User.username.label('username'),
            AuditTrail.user_id.label('user_id'),
        )
        .outerjoin(User, AuditTrail.user_id == User.id)
        .where(AuditTrail.action != 'view')
    )

    login_q = select(
        LoginAttempt.id.label('id'),
        literal('login_attempt').label('source'),
        db.case((LoginAttempt.success.is_(True), 'login'), else_='login_failed').label('action'),
        LoginAttempt.created_at.label('created_at'),
        LoginAttempt.user_ip.label('ip'),
        literal('').label('description'),
        LoginAttempt.username.label('notes'),
        LoginAttempt.username.label('username'),
        LoginAttempt.user_id.label('user_id'),
    )

    if action:
        if action == 'login':
            audit_q = audit_q.where(AuditTrail.action == 'login')
            login_q = login_q.where(LoginAttempt.success.is_(True))
        elif action == 'login_failed':
            audit_q = audit_q.where(AuditTrail.action.in_(['login_failed', 'login_blocked']))
            login_q = login_q.where(LoginAttempt.success.is_(False))
        else:
            audit_q = audit_q.where(AuditTrail.action == action)

            login_q = login_q.where(literal_column('false'))

    if user_id:
        audit_q = audit_q.where(AuditTrail.user_id == user_id)
        login_q = login_q.where(LoginAttempt.user_id == user_id)

    if date_from:
        audit_q = audit_q.where(AuditTrail.created_at >= date_from)
        login_q = login_q.where(LoginAttempt.created_at >= date_from)
    if date_to:
        audit_q = audit_q.where(AuditTrail.created_at <= date_to)
        login_q = login_q.where(LoginAttempt.created_at <= date_to)

    if q:
        like = f'%{q}%'
        audit_q = audit_q.where(
            or_(
                User.username.ilike(like),
                AuditTrail.description.ilike(like),
                AuditTrail.notes.ilike(like),
            )
        )
        login_q = login_q.where(LoginAttempt.username.ilike(like))

    combined = union_all(audit_q, login_q).subquery()
    rows_q = select(combined)
    count_q = select(func.count()).select_from(combined)

    if severity:
        mapped = [a for a, s in SEVERITY_BY_ACTION.items() if s == severity]
        if severity == 'low':
            higher = [a for a, s in SEVERITY_BY_ACTION.items() if s != 'low']
            cond = combined.c.action.notin_(higher)
        elif mapped:
            cond = combined.c.action.in_(mapped)
        else:
            cond = literal_column('false')
        rows_q = rows_q.where(cond)
        count_q = count_q.where(cond)

    total = db.session.execute(count_q).scalar() or 0
    rows = (
        db.session.execute(
            rows_q.order_by(combined.c.created_at.desc(), combined.c.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .mappings()
        .all()
    )

    items = []
    for r in rows:
        created = r['created_at']
        items.append(
            {
                'id': f'{r["source"]}:{r["id"]}',
                'source': r['source'],
                'action': r['action'],
                'severity': _severity(r['action']),
                'username': r['username'] or '',
                'user_id': r['user_id'],
                'ip': r['ip'] or '',
                'description': r['description'] or '',
                'notes': r['notes'] or '',
                'created_at': (
                    created.strftime('%Y-%m-%d %H:%M:%S')
                    if isinstance(created, datetime)
                    else str(created or '')
                ),
            }
        )

    return jsonify(
        {
            'success': True,
            'items': items,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'pages': (total + page_size - 1) // page_size,
            },
        }
    )


@super_admin_bp.route('/api/security-logs/summary', methods=['GET'])
@login_required
@role_required_json('super_admin', 'owner')
def security_summary():
    """KPI tiles for the top of the console."""
    day_cut = _parse_date(datetime.now(UTC).strftime('%Y-%m-%d'))

    failed = (
        db.session.execute(
            select(func.count()).select_from(LoginAttempt).where(LoginAttempt.success.is_(False))
        ).scalar()
        or 0
    )
    blocked = (
        db.session.execute(
            select(func.count()).select_from(AuditTrail).where(AuditTrail.action == 'login_blocked')
        ).scalar()
        or 0
    )
    impersonations = (
        db.session.execute(
            select(func.count()).select_from(AuditTrail).where(AuditTrail.action == 'IMPERSONATE')
        ).scalar()
        or 0
    )
    logins_today = (
        db.session.execute(
            select(func.count())
            .select_from(LoginAttempt)
            .where(LoginAttempt.success.is_(True), LoginAttempt.created_at >= day_cut)
        ).scalar()
        or 0
    )

    return jsonify(
        {
            'success': True,
            'failed_logins': int(failed),
            'blocked_logins': int(blocked),
            'impersonations': int(impersonations),
            'logins_today': int(logins_today),
        }
    )
