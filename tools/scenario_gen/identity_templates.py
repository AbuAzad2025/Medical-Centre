"""Identity, session and access-control templates.

Authentication is where a medical system fails loudest and where the route table
is widest relative to the test coverage, so these templates cover the whole
surface: registration and login, password reset, the MFA second factor,
biometric enrolment, SSO federation, session termination, impersonation and the
patient portal.

They are filed as ``rbac`` rather than ``clinical`` because a scenario over them
asserts an access decision. The clinical journey that depends on a role is
already written in the clinical family; duplicating it here to inflate either
count is exactly what the brief forbids.

The axes are the real ones the code branches on: the login outcome, the second
factor offered, the federation protocol, the permission level and category, and
the actor role.
"""

from __future__ import annotations

from templates import TEMPLATES, Template, _s

PATIENT = 'Patient'
RECEPTION = 'Reception'
DOCTOR = 'Doctor'
ACCOUNTANT = 'Accountant'
MANAGER = 'Manager'
OWNER = 'Owner'
SUPER_ADMIN = 'SuperAdmin'

IDENTITY_TEMPLATES: tuple[Template, ...] = (
    Template(
        key='IDENTITY_REGISTRATION_AND_LOGIN',
        family='rbac',
        axes=('login_outcome',),
        observed={
            'login_outcome': (
                'success',
                'bad_password',
                'unknown_user',
                'disabled_user',
                'locked_out',
            )
        },
        rule=(
            'Registration creates a User and a login creates a session, and every '
            'failed login writes a SecurityEvent while only a successful one '
            'writes an AuditLog row with action login. A disabled user and a '
            'wrong password are therefore distinguishable in the security table '
            'but not in the audit trail, because only the success path reaches '
            'the audit writer.'
        ),
        steps=(
            _s(PATIENT, 'POST /auth/register', 'account created'),
            _s(PATIENT, 'POST /auth/login', 'session opened'),
            _s(PATIENT, 'POST /auth/logout', 'session closed'),
            _s(PATIENT, 'POST /auth/profile', 'profile updated'),
        ),
    ),
    Template(
        key='IDENTITY_PASSWORD_LIFECYCLE',
        family='rbac',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'A user changes their own password and an owner or super_admin resets '
            'one for somebody else, which is the only difference between the two '
            'routes. reveal-password returns a stored password in clear, so the '
            'reset path and the reveal path are the two places a credential is '
            'ever readable after creation, and both are role gated rather than '
            'audit gated.'
        ),
        steps=(
            _s(RECEPTION, 'POST /auth/change-password', 'own password changed'),
            _s(PATIENT, 'POST /auth/forgot-password', 'reset token issued'),
            _s(PATIENT, 'POST /auth/reset-password/<token>/<int:user_id>', 'token consumed'),
            _s(OWNER, 'POST /owner/users/<int:user_id>/reset-password', 'reset by an operator'),
            _s(
                OWNER, 'POST /owner/users/<int:user_id>/reveal-password', 'stored password revealed'
            ),
        ),
    ),
    Template(
        key='IDENTITY_SECOND_FACTOR_ENROLMENT',
        family='rbac',
        axes=('mfa_method',),
        observed={'mfa_method': ('totp', 'sms', 'email')},
        rule=(
            'MFA is a four-route state machine: setup issues a secret, verify '
            'confirms a code, check reports whether it is on, and disable turns '
            'it off. The method is recorded at setup but the verify route checks '
            'the same TOTP path for all three methods, so choosing sms does not '
            'actually change how the code is checked.'
        ),
        steps=(
            _s(RECEPTION, 'POST /mfa/setup', 'second factor initiated'),
            _s(RECEPTION, 'POST /mfa/verify', 'code accepted, factor enabled'),
            _s(RECEPTION, 'POST /mfa/api/check', 'enrolment status reported'),
            _s(RECEPTION, 'POST /mfa/disable', 'second factor removed'),
        ),
    ),
    Template(
        key='IDENTITY_BIOMETRIC_ENROLMENT',
        family='rbac',
        axes=(),
        observed={},
        rule=(
            'Biometric enrolment is a three-step handshake: a register challenge, '
            'a register complete carrying the signed response, and an '
            'authenticate challenge that a removal makes invalid. A credential is '
            'only removed by its own id, so a credential whose device is lost is '
            'revoked one row at a time rather than all at once for the user.'
        ),
        steps=(
            _s(DOCTOR, 'POST /biometric/register-challenge', 'enrolment challenge issued'),
            _s(DOCTOR, 'POST /biometric/register-complete', 'credential stored'),
            _s(DOCTOR, 'POST /biometric/authenticate-challenge', 'assertion challenged'),
            _s(DOCTOR, 'POST /biometric/remove/<int:cred_id>', 'credential revoked'),
        ),
    ),
    Template(
        key='IDENTITY_SESSION_TERMINATION',
        family='rbac',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'terminate-others closes every session except the current one, which '
            'is the emergency lock-out button, and it is the only route that ends '
            'a session belonging to somebody else. It writes no SecurityEvent and '
            'no AuditLog row, so after a forced logout the audit trail shows an '
            'abrupt end rather than a revocation.'
        ),
        steps=(
            _s(DOCTOR, 'POST /auth/login', 'session opened'),
            _s(DOCTOR, 'POST /security/sessions/terminate-others', 'other sessions closed'),
            _s(DOCTOR, 'POST /auth/logout', 'current session closed'),
        ),
    ),
    Template(
        key='IDENTITY_IMPERSONATION',
        family='rbac',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'Impersonation enters another user context and exit leaves it, and it '
            'is the one route that makes a privileged user act with a lesser '
            'identity. The audit row it writes is the only record of who was '
            'really behind the write, because every row created afterwards carries '
            'the impersonated user rather than the operator.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /auth/impersonate/<int:user_id>', 'entered another user context'),
            _s(SUPER_ADMIN, 'GET /owner/users', 'read as the impersonated user'),
            _s(SUPER_ADMIN, 'POST /auth/impersonate/exit', 'own context restored'),
        ),
    ),
    Template(
        key='IDENTITY_SSO_FEDERATION',
        family='rbac',
        axes=('sso_protocol',),
        observed={'sso_protocol': ('saml', 'oidc')},
        rule=(
            'An SSO configuration is written once and toggled by id, and neither '
            'route validates that the identity provider is reachable, so a tenant '
            'can lock every staff member out by pointing SSO at an endpoint that '
            'does not answer while leaving the password path enabled underneath.'
        ),
        steps=(
            _s(OWNER, 'POST /sso/config', 'federation configured'),
            _s(OWNER, 'POST /sso/toggle/<int:config_id>', 'federation enabled or disabled'),
            _s(RECEPTION, 'POST /auth/login', 'staff sign-in resolved through the provider'),
        ),
    ),
    Template(
        key='IDENTITY_PERMISSION_MATRIX',
        family='rbac',
        axes=('permission_category', 'permission_level'),
        observed={
            'permission_category': (
                'user_management',
                'patient_management',
                'medical_records',
                'financial',
                'system_admin',
                'backup_restore',
                'reports',
                'settings',
                'security',
                'audit',
            ),
            'permission_level': ('read', 'write', 'delete', 'admin', 'super_admin'),
        },
        rule=(
            'The permissions matrix is built per category and level, and the role '
            'decorator checks the level string rather than the category, so a '
            'permission is effective as soon as its level string is recognised on '
            'any category. A category with no rows denies everything and is '
            'indistinguishable from a category nobody created.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/permissions/create', 'permission created'),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/permissions/<int:permission_id>/edit',
                'permission edited',
            ),
            _s(SUPER_ADMIN, 'POST /super-admin/permissions-matrix', 'matrix written'),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/permissions/<int:permission_id>/delete',
                'permission deleted',
            ),
        ),
    ),
    Template(
        key='IDENTITY_ROLE_DEPARTMENT_BINDING',
        family='rbac',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'A role grants permissions globally while a role can also be bound to '
            'a department, so the same role behaves differently in two '
            'departments. Adding staff to a department is a separate write from '
            'assigning them a role, which means a clinician can hold a role with '
            'no department and be reachable in none.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/roles/create', 'role created'),
            _s(SUPER_ADMIN, 'POST /super-admin/roles/<int:role_id>/edit', 'role edited'),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/roles/<int:role_id>/permissions',
                'permissions attached',
            ),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/roles/<int:role_id>/department-permissions',
                'permissions bound to one department',
            ),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/department-staff/<int:department_id>/add',
                'staff added to the department',
            ),
        ),
    ),
    Template(
        key='IDENTITY_STAFF_ACCOUNT_LIFECYCLE',
        family='rbac',
        axes=('actor_role',),
        observed={
            'actor_role': (
                'super_admin',
                'owner',
                'admin',
                'manager',
                'reception',
                'doctor',
                'nurse',
                'lab',
                'radiology',
                'pharmacist',
                'accountant',
            )
        },
        rule=(
            'An account is deactivated with toggle-active rather than deleted, '
            'which is the correct choice for a clinical system because a deleted '
            'user takes their attribution with them. Deactivation is checked at '
            'login but not on every request, so an open session survives the '
            'toggle until it expires.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/users', 'user created with an assignable role'),
            _s(OWNER, 'POST /owner/users/<int:user_id>/edit', 'details corrected'),
            _s(OWNER, 'POST /owner/users/<int:user_id>/toggle-active', 'account deactivated'),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/users/<int:user_id>/delete',
                'account removed at platform level',
            ),
        ),
    ),
    Template(
        key='IDENTITY_AUDIT_TRAIL_COVERAGE',
        family='rbac',
        axes=(),
        observed={},
        rule=(
            'The audit trail is written per entity and per action, so coverage is '
            'a matrix and a gap on one entity is invisible from another. '
            'force_logout is an action the session termination route does not '
            'emit, and permission_denied is emitted by the decorator rather than '
            'by the handler, so a route that denies nothing writes nothing.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/notes/<int:visit_id>', 'clinical write audited'),
            _s(DOCTOR, 'POST /emergency/prescription/<int:emergency_id>', 'prescription audited'),
            _s(RECEPTION, 'POST /accountant/refunds/<int:refund_id>/execute', 'refund attempted'),
            _s(RECEPTION, 'GET /super-admin/audit-trail', 'audit trail read back'),
        ),
    ),
    Template(
        key='IDENTITY_PATIENT_PORTAL_ACCOUNT',
        family='rbac',
        axes=('login_outcome',),
        observed={
            'login_outcome': (
                'success',
                'bad_password',
                'unknown_user',
                'disabled_user',
                'locked_out',
            )
        },
        rule=(
            'The portal is a patient-facing identity separate from the staff '
            'identity: link-account joins a portal login to a Patient row, and '
            'settings and feedback are writes the patient makes about themselves. '
            'Linking is the only route that asserts the two identities match, so a '
            'portal login linked to the wrong patient record would be accepted.'
        ),
        steps=(
            _s(PATIENT, 'POST /portal/link-account', 'portal login joined to a patient record'),
            _s(PATIENT, 'POST /portal/settings', 'portal preferences saved'),
            _s(PATIENT, 'POST /portal/feedback', 'feedback submitted'),
        ),
    ),
    Template(
        key='IDENTITY_USER_PREFERENCES',
        family='rbac',
        axes=('print_doc_type',),
        observed={
            'print_doc_type': (
                'invoice',
                'receipt',
                'prescription',
                'queue_ticket',
                'barcode_label',
                'lab_result',
                'radiology_report',
                'emergency_report',
                'report',
                'pharmacy_sale',
            )
        },
        rule=(
            'A user preference decides which documents a user prints by default '
            'and how they are laid out, so it is a per-user write with no tenant '
            'validation of its own. The preference is applied by the template '
            'renderer, which means the same clinical record prints differently '
            'for two users of the same tenant.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/prescription/<visit_id>', 'document produced'),
            _s(DOCTOR, 'POST /api/user/preferences', 'print and layout preference saved'),
            _s(
                DOCTOR,
                'GET /doctor/print-prescription/<int:prescription_id>',
                'document rendered with the preference',
            ),
        ),
    ),
)


def add_identity_templates() -> int:
    """Extend templates.TEMPLATES in place, idempotently. Returns how many were added."""
    existing = {t.key for t in TEMPLATES}
    added = 0
    for t in IDENTITY_TEMPLATES:
        if t.key not in existing:
            TEMPLATES.append(t)
            added += 1
    return added
