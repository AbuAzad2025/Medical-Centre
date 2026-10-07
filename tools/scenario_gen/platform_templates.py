"""Platform functional templates: owner, super-admin and the SaaS control plane.

These are not medical journeys. They configure tenants, sell subscriptions and
manage the platform itself, so they are kept in their own family rather than
folded into the clinical matrix. Mixing them would inflate the clinical count with
scenarios that never touch a patient, which is the padding the brief rules out.

The axes are the platform's own state machines: subscription state, module
activation, entitlement status and audit severity. All are read from the code.
"""

from __future__ import annotations

from templates import TEMPLATES, Template, _s

OWNER = 'Owner'
SUPER_ADMIN = 'SuperAdmin'

PLATFORM_TEMPLATES: tuple[Template, ...] = (
    Template(
        key='PLATFORM_SUBSCRIPTION_LIFECYCLE',
        family='platform',
        axes=('subscription_type', 'tenant_status'),
        observed={
            'subscription_type': ('monthly', 'yearly'),
            'tenant_status': ('active', 'suspended', 'expired', 'cancelled'),
        },
        rule=(
            'A tenant subscription runs through PackageVersion and SubscriptionLine. '
            'line_type is base or addon, billing_type is monthly or yearly, and '
            'effective_from and effective_to are separate from the trial and grace '
            'windows on the version. SubscriptionLine is one of the few models that '
            'carries tenant_id, so a subscription belongs to a tenant while the '
            'PackageVersion it points at does not.'
        ),
        steps=(
            _s(OWNER, 'GET /owner/plans', 'plans listed'),
            _s(OWNER, 'POST /owner/plans/create', 'plan created'),
            _s(OWNER, 'GET /owner/subscriptions', 'subscriptions listed'),
            _s(
                OWNER,
                'POST /owner/subscriptions/<int:subscription_id>/upgrade',
                'subscription upgraded',
            ),
            _s(
                OWNER,
                'POST /owner/subscriptions/<int:subscription_id>/cancel',
                'subscription cancelled',
            ),
        ),
    ),
    Template(
        key='PLATFORM_MODULE_ACTIVATION',
        family='platform',
        axes=('module_status',),
        observed={'module_status': ('enabled', 'disabled')},
        rule=(
            'A module is available to a tenant only when its TenantModule row is '
            'active. The same activation drives the feature gate in '
            'feature_gate_service, the doctor dashboard layout and the inbox '
            'entitlement filter, so disabling a module changes routing, menus and '
            'the work list at once. The gate is disabled entirely when '
            'ENABLE_SAAS_MODE is False.'
        ),
        steps=(
            _s(OWNER, 'GET /owner/modules', 'modules listed'),
            _s(OWNER, 'POST /owner/modules/<module_name>/toggle', 'module activated'),
            _s(
                OWNER,
                'POST /owner/api/tenants/<int:tenant_id>/modules/<module_name>/activate',
                'module activated for one tenant',
            ),
            _s(
                OWNER,
                'POST /owner/api/tenants/<int:tenant_id>/features/<feature_key>/toggle',
                'feature flag toggled',
            ),
        ),
    ),
    Template(
        key='PLATFORM_BUNDLE_AND_ENTITLEMENT',
        family='platform',
        axes=('bundle_kind',),
        observed={'bundle_kind': ('custom', 'polyclinic', 'hospital', 'urgent_care')},
        rule=(
            'A ProductBundle is a JSON array of module names with a monthly and '
            'yearly price, and it enforces two ceilings at ORM flush: max_users '
            'and max_patients. The bundle table itself carries no tenant_id; the '
            'subscription line does. A custom bundle with an empty modules array '
            'falls back to billing and reporting rather than granting nothing.'
        ),
        steps=(
            _s(OWNER, 'GET /owner/bundles', 'bundles listed'),
            _s(OWNER, 'POST /owner/api/bundles', 'bundle created with a module array'),
            _s(OWNER, 'GET /owner/packages', 'package versions listed'),
            _s(OWNER, 'POST /owner/packages/<int:package_id>/versions/create', 'version published'),
        ),
    ),
    Template(
        key='PLATFORM_AUDIT_AND_SECURITY_REVIEW',
        family='platform',
        axes=('security_severity', 'log_level'),
        observed={
            'security_severity': ('low', 'medium', 'high', 'critical'),
            'log_level': ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
        },
        rule=(
            'The PHI audit viewer reads PHIAuditLog with six filters and real '
            'pagination, so the record that was reported as orphaned is in place. '
            'Security events, login attempts and system logs are separate tables, '
            'and the security dashboard aggregates all three rather than the audit '
            'trail alone.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'GET /super-admin/audit-trail', 'PHI audit log filtered and paginated'),
            _s(SUPER_ADMIN, 'GET /super-admin/api/security-logs', 'security events listed'),
            _s(
                SUPER_ADMIN,
                'GET /super-admin/security-center',
                'dashboard aggregates the three log tables',
            ),
            _s(SUPER_ADMIN, 'GET /super-admin/api/audit-log', 'audit log listed'),
        ),
    ),
    Template(
        key='PLATFORM_USER_AND_ROLE_GOVERNANCE',
        family='platform',
        axes=('actor_role',),
        observed={'actor_role': ('super_admin', 'owner', 'admin', 'manager', 'reception')},
        rule=(
            'ASSIGNABLE_ROLES separates clinical staff from privileged operators, '
            'ELEVATED_ROLES may be granted only by a super_admin, and only '
            'super_admin or owner may manage users. owner can create an admin but '
            'not another owner, so the owner role is not self-reproducing.'
        ),
        steps=(
            _s(OWNER, 'GET /owner/users', 'users listed'),
            _s(OWNER, 'POST /owner/users', 'user created with an assignable role'),
            _s(OWNER, 'POST /owner/users/<int:user_id>/edit', 'role changed'),
            _s(SUPER_ADMIN, 'GET /super-admin/roles', 'role catalogue read'),
        ),
    ),
    Template(
        key='PLATFORM_BILLING_SUBSCRIPTION_PORTAL',
        family='platform',
        axes=('subscription_type',),
        observed={'subscription_type': ('monthly', 'yearly')},
        rule=(
            'Stripe checkout, the billing portal and plan changes all go through '
            'StripeBillingService, and the webhook is idempotent on event_id. The '
            'change_plan path validates the package family, so a tenant cannot move '
            'between unrelated families. The platform bills tenants; it does not '
            'bill patients, which is a separate and completely disconnected code path.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /api/billing/checkout', 'checkout session created'),
            _s(SUPER_ADMIN, 'POST /api/billing/stripe/webhook', 'webhook received idempotently'),
            _s(SUPER_ADMIN, 'POST /api/billing/portal', 'billing portal session created'),
            _s(
                SUPER_ADMIN,
                'POST /api/billing/subscription/change-plan',
                'plan changed, family validated',
            ),
            _s(SUPER_ADMIN, 'POST /api/billing/subscription/cancel', 'subscription cancelled'),
        ),
    ),
    Template(
        key='PLATFORM_BACKUP_RESTORE',
        family='platform',
        axes=('backup_type', 'backup_status'),
        observed={
            'backup_type': ('full', 'incremental', 'differential'),
            'backup_status': ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED'),
        },
        rule=(
            'Backups are scheduled and typed, and a restore is a separate action '
            'from a backup. Nothing in the backup path validates tenant scope, so a '
            'restore is a platform-wide operation and the guard that matters is who '
            'is allowed to trigger it.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'GET /super-admin/backup/settings', 'backup settings listed'),
            _s(SUPER_ADMIN, 'POST /super-admin/backup/schedule', 'backup scheduled'),
            _s(
                SUPER_ADMIN, 'POST /super-admin/backup/restore/<int:backup_id>', 'restore requested'
            ),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/backup/cancel/<int:backup_id>',
                'scheduled backup cancelled',
            ),
        ),
    ),
)


def add_platform_templates() -> int:
    """Extend templates.TEMPLATES in place, idempotently. Returns how many were added."""
    existing = {t.key for t in TEMPLATES}
    added = 0
    for t in PLATFORM_TEMPLATES:
        if t.key not in existing:
            TEMPLATES.append(t)
            added += 1
    return added
