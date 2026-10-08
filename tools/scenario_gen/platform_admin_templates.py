"""Owner and super-admin platform templates.

Two consoles sit above the tenants. ``owner`` configures tenants, sells them
subscriptions and manages the catalogue of plans, bundles, packages, themes and
API keys. ``super-admin`` manages the platform itself: roles, permissions,
departments, the service catalogue, backups, maintenance and the seed tooling.

These are filed as ``platform``, never as clinical. A scenario over them never
touches a patient, and the brief is explicit that counting them as medical
coverage would overstate it.

Where the two consoles overlap they overlap in a way worth documenting: the same
package-version model is written by the owner and read by super-admin, tenant
status is written by owner while department activation is written by
super-admin, and neither console writes a clinical row.
"""

from __future__ import annotations

from templates import TEMPLATES, Template, _s

OWNER = 'Owner'
SUPER_ADMIN = 'SuperAdmin'
RECEPTION = 'Reception'

PLATFORM_ADMIN_TEMPLATES: tuple[Template, ...] = (
    # ---- owner: tenants ---------------------------------------------------
    Template(
        key='OWNER_TENANT_PROVISIONING',
        family='platform',
        axes=('tenant_status', 'product_profile'),
        observed={
            'tenant_status': (
                'active',
                'suspended',
                'pending',
                'trial',
                'expired',
                'cancelled',
                'deleted',
            ),
            'product_profile': (
                'private_doctor_clinic',
                'small_clinic',
                'standalone_lab',
                'standalone_radiology',
                'standalone_pharmacy',
                'multi_department_center',
                'custom',
            ),
        },
        rule=(
            'Provisioning is the single write that creates a tenant, and the '
            'product profile decides which modules are seeded with it, so the '
            'profile is the axis that actually determines what the tenant can do '
            'on day one. A profile of custom seeds nothing and leaves the tenant '
            'with no modules until an owner grants them individually. deleted is '
            'a status a tenant can be written into like any other, which is how a '
            'soft delete is expressed in the same column as a suspension.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/tenants/create', 'tenant created with a profile'),
            _s(OWNER, 'POST /owner/api/tenants/provision', 'tenant provisioned'),
            _s(OWNER, 'POST /owner/tenants/<int:tenant_id>', 'tenant record updated'),
            _s(OWNER, 'POST /owner/tenants/<int:tenant_id>/edit', 'tenant edited'),
            _s(OWNER, 'POST /owner/api/tenants/<int:tenant_id>/profile', 'profile written'),
        ),
    ),
    Template(
        key='OWNER_TENANT_STATUS_TRANSITIONS',
        family='platform',
        axes=('tenant_status',),
        observed={
            'tenant_status': (
                'active',
                'suspended',
                'pending',
                'trial',
                'expired',
                'cancelled',
                'deleted',
            )
        },
        rule=(
            'Suspend and activate are separate routes, which is the correct shape '
            'for a reversible gate, but there is no expiry route: a trial lapsing '
            'is either a status somebody writes or a subscription that ends and '
            'leaves the tenant active. The emergency switch is the blunt '
            'instrument and it is tenant-wide rather than module-wide.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/tenants/<int:tenant_id>/suspend', 'tenant suspended'),
            _s(OWNER, 'POST /owner/tenants/<int:tenant_id>/activate', 'tenant reactivated'),
            _s(OWNER, 'POST /owner/emergency-switches/toggle', 'platform-wide switch thrown'),
            _s(OWNER, 'POST /owner/control/toggle', 'owner control taken or released'),
        ),
    ),
    Template(
        key='OWNER_MODULE_ENTITLEMENT',
        family='platform',
        axes=('module_name', 'module_status'),
        observed={
            'module_name': (
                'reception',
                'doctor',
                'lab',
                'radiology',
                'pharmacy',
                'emergency',
                'nursing',
                'billing',
                'inventory',
                'reporting',
                'appointments',
                'owner',
                'portal',
                'ai_imaging',
                'accounting',
                'admin',
                'manager',
                'dicom',
            ),
            'module_status': ('enabled', 'disabled'),
        },
        rule=(
            'Module entitlement is per tenant and per module, so the same module '
            'can be live in one tenant and absent in the next. The feature gate '
            'reads TenantModule on every request and the gate itself is disabled '
            'entirely when ENABLE_SAAS_MODE is False, which means in a '
            'self-hosted deployment this axis has no effect at all.'
        ),
        steps=(
            _s(
                OWNER,
                'POST /owner/api/tenants/<int:tenant_id>/modules/<module_name>/activate',
                'module activated for the tenant',
            ),
            _s(
                OWNER,
                'POST /owner/api/tenants/<int:tenant_id>/modules/<module_name>/deactivate',
                'module deactivated for the tenant',
            ),
            _s(
                OWNER,
                'POST /owner/tenants/<int:tenant_id>/activate-modules',
                'module set applied in bulk',
            ),
            _s(
                OWNER,
                'POST /owner/tenants/<int:tenant_id>/feature/<path:feature_key>/toggle',
                'feature flag toggled',
            ),
        ),
    ),
    Template(
        key='OWNER_SUBSCRIPTION_BILLING_CYCLE',
        family='platform',
        axes=('subscription_type',),
        observed={'subscription_type': ('perpetual', 'monthly', 'yearly')},
        rule=(
            'The platform bills tenants and nothing else: renew, upgrade, addon '
            'and cancel all act on a tenant subscription, and none of them touch '
            'patient money. The Stripe path and the local path are separate code '
            'with separate state, so a tenant upgraded through one is not '
            'recognised as upgraded through the other.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/subscriptions/<int:tenant_id>/renew', 'subscription renewed'),
            _s(OWNER, 'POST /owner/subscriptions/<int:tenant_id>/addon', 'addon line added'),
            _s(
                OWNER,
                'POST /owner/subscriptions/<int:tenant_id>/upgrade',
                'subscription upgraded',
            ),
            _s(
                OWNER,
                'POST /owner/subscriptions/<int:tenant_id>/cancel',
                'subscription cancelled',
            ),
        ),
    ),
    Template(
        key='OWNER_PLAN_AND_BUNDLE_CATALOGUE',
        family='platform',
        axes=('subscription_type', 'bundle_kind'),
        observed={
            'subscription_type': ('perpetual', 'monthly', 'yearly'),
            'bundle_kind': ('custom', 'polyclinic', 'hospital', 'urgent_care'),
        },
        rule=(
            'A plan is sellable and a bundle is the module set inside it, and a '
            'bundle enforces max_users and max_patients at flush rather than at '
            'subscribe time, so the ceiling is checked after the tenant exists. '
            'The bundle table carries no tenant_id; the subscription line does, '
            'which is why deleting a bundle cannot orphan a subscription.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/plans/create', 'plan created'),
            _s(OWNER, 'POST /owner/plans/<int:plan_id>/edit', 'plan edited'),
            _s(OWNER, 'POST /owner/plans/<int:plan_id>/delete', 'plan deleted'),
            _s(OWNER, 'POST /owner/api/bundles', 'bundle created with a module array'),
            _s(OWNER, 'PUT /owner/api/bundles/<int:bundle_id>', 'bundle edited'),
            _s(OWNER, 'DELETE /owner/api/bundles/<int:bundle_id>', 'bundle deleted'),
        ),
    ),
    Template(
        key='OWNER_PACKAGE_VERSION_LIFECYCLE',
        family='platform',
        axes=(),
        observed={},
        rule=(
            'A package version is created, edited, deprecated or deleted, and '
            'deprecate and delete are different actions on the same row. The '
            'PackageVersion a subscription points at carries no tenant_id, so '
            'deprecating a version affects every tenant subscribed to it at once.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/packages/create', 'package created'),
            _s(OWNER, 'POST /owner/packages/<int:package_id>/edit', 'package edited'),
            _s(OWNER, 'POST /owner/packages/<int:package_id>/versions/create', 'version published'),
            _s(
                OWNER,
                'POST /owner/packages/versions/<int:version_id>/edit',
                'version edited after publication',
            ),
            _s(
                OWNER,
                'POST /owner/packages/versions/<int:version_id>/deprecate',
                'version deprecated',
            ),
            _s(OWNER, 'POST /owner/packages/versions/<int:version_id>/delete', 'version deleted'),
            _s(OWNER, 'POST /owner/packages/<int:package_id>/delete', 'package deleted'),
        ),
    ),
    Template(
        key='OWNER_SYSTEM_CONFIGURATION',
        family='platform',
        axes=('config_category', 'config_type'),
        observed={
            'config_category': (
                'general',
                'security',
                'notification',
                'backup',
                'system',
                'database',
                'email',
                'sms',
            ),
            'config_type': ('string', 'integer', 'boolean', 'json', 'file', 'password'),
        },
        rule=(
            'SystemConfig is a key, a string value, a category and a type, and the '
            'type decides how the string is coerced, so the same key with a '
            'different type is a different value. password is the one type that is '
            'redacted on read, which means a saved SMTP password is stored and '
            'never shown again. Reading a config by key is not tenant scoped by the '
            'key itself.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/system-config/save', 'configuration saved'),
            _s(OWNER, 'POST /owner/system-config/<config_key>/delete', 'configuration removed'),
            _s(SUPER_ADMIN, 'POST /super-admin/system-config', 'platform configuration saved'),
        ),
    ),
    Template(
        key='OWNER_NOTIFICATION_RULES',
        family='platform',
        axes=('notification_event_type', 'notification_channel'),
        observed={
            'notification_event_type': (
                'subscription_expiry',
                'trial_ending',
                'high_resource',
                'ticket_new',
            ),
            'notification_channel': ('email', 'webhook', 'sms'),
        },
        rule=(
            'Four event types across three channels are the whole rule engine, and '
            'the target is free text, so a webhook rule can be saved with a URL '
            'that never answers and nothing rejects it at save time. Toggling a '
            'rule off is the only way to stop it, and a delivery failure is not '
            'recorded on the rule.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/notifications/create', 'rule created'),
            _s(OWNER, 'POST /owner/notifications/<int:rule_id>/toggle', 'rule toggled'),
            _s(OWNER, 'POST /owner/notifications/<int:rule_id>/delete', 'rule deleted'),
            _s(OWNER, 'POST /owner/announcements', 'announcement published'),
            _s(
                OWNER,
                'POST /owner/announcements/<int:announcement_id>/delete',
                'announcement withdrawn',
            ),
        ),
    ),
    Template(
        key='OWNER_SUPPORT_TICKETS',
        family='platform',
        axes=('support_ticket_category',),
        observed={
            'support_ticket_category': (
                'general',
                'billing',
                'technical',
                'bug',
                'feature_request',
            )
        },
        rule=(
            'A support ticket is raised by tenant staff or by a super admin and '
            'its category is free text documented on the column, so the routing '
            'that would use it is not backed by a constraint. Updating a ticket is '
            'a single status write with no history, so a ticket that changed hands '
            'has no record of the handover.'
        ),
        steps=(
            _s(OWNER, 'GET /owner/support-tickets', 'tickets listed'),
            _s(OWNER, 'POST /owner/support-tickets/<int:ticket_id>/update', 'ticket updated'),
            _s(SUPER_ADMIN, 'GET /owner/support-tickets', 'platform side reads the same queue'),
        ),
    ),
    Template(
        key='OWNER_API_KEYS_AND_WEBHOOKS',
        family='platform',
        axes=(),
        observed={},
        rule=(
            'API keys are not a table: the whole key list is a JSON blob in one '
            'SystemConfig row, truncated to the first hundred entries on every '
            'save, so creating the hundred and first key silently drops the '
            'oldest. The scopes field is free text defaulting to read and nothing '
            'validates it, so a key with no scopes is still a working key.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/api-keys', 'key minted and shown once'),
            _s(OWNER, 'POST /owner/api-keys/<int:key_id>/delete', 'key revoked'),
            _s(OWNER, 'POST /owner/webhooks', 'webhook endpoint registered'),
            _s(OWNER, 'POST /owner/webhooks/<int:webhook_id>/delete', 'webhook removed'),
        ),
    ),
    Template(
        key='OWNER_BRANDING_AND_THEMES',
        family='platform',
        axes=('storage_mode',),
        observed={
            'storage_mode': ('cloud', 'local', 'hybrid'),
        },
        rule=(
            'Themes are per tenant and one can be made the default, which is a '
            'global switch for that tenant rather than a per-user preference. '
            'Branding is a separate write from theming, so a tenant can have a '
            'theme with no logo or a logo with no theme. Storage mode decides '
            'where DICOM objects live, and hybrid is the only mode where the '
            'backup path has to reconcile two stores.'
        ),
        steps=(
            _s(OWNER, 'POST /owner/themes', 'theme created'),
            _s(OWNER, 'POST /owner/themes/<int:theme_id>/set-default', 'theme made the default'),
            _s(OWNER, 'POST /owner/themes/<int:theme_id>/delete', 'theme deleted'),
            _s(OWNER, 'POST /owner/branding', 'branding updated'),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/branding/apply-theme/<int:theme_id>',
                'theme applied platform-wide',
            ),
        ),
    ),
    Template(
        key='OWNER_USAGE_AND_ASSUMPTIONS',
        family='platform',
        axes=(),
        observed={},
        rule=(
            'Usage is recorded per tenant and projected against the plan ceiling, '
            'and an assumption is a manual override of that projection. Revoking '
            'an assumption restores the computed figure, which is why the two are '
            'separate writes: a revoked assumption is not the same row as one '
            'that was never made.'
        ),
        steps=(
            _s(
                OWNER,
                'POST /owner/api/tenants/<int:tenant_id>/record-usage',
                'usage recorded against the plan',
            ),
            _s(OWNER, 'POST /owner/api/assumptions', 'assumption recorded'),
            _s(
                OWNER,
                'POST /owner/api/assumptions/<int:assumption_id>/revoke',
                'assumption revoked',
            ),
        ),
    ),
    Template(
        key='OWNER_TENANT_SELF_SERVICE_SIGNUP',
        family='platform',
        axes=('product_profile', 'tenant_status'),
        observed={
            'product_profile': (
                'private_doctor_clinic',
                'small_clinic',
                'standalone_lab',
                'standalone_radiology',
                'standalone_pharmacy',
                'multi_department_center',
                'custom',
            ),
            'tenant_status': (
                'active',
                'suspended',
                'pending',
                'trial',
                'expired',
                'cancelled',
                'deleted',
            ),
        },
        rule=(
            'Signup is the public write that creates a tenant, and register is the '
            'API twin of it. A self-registered tenant arrives pending, so it '
            'exists and is reachable by nobody until an owner activates it, which '
            'is the correct shape for a trial and also for a production tenant '
            'that was created by mistake.'
        ),
        steps=(
            _s(OWNER, 'POST /saas/signup', 'tenant self-registered'),
            _s(OWNER, 'POST /api/saas/register', 'tenant registered over the API'),
            _s(OWNER, 'POST /owner/provision', 'owner completes provisioning'),
        ),
    ),
    # ---- super-admin ------------------------------------------------------
    Template(
        key='SUPERADMIN_DEPARTMENT_AND_SERVICE_CATALOGUE',
        family='platform',
        axes=(),
        observed={},
        rule=(
            'Departments and services are activated and deactivated with separate '
            'routes rather than a status toggle, which means an inactive department '
            'still exists and can still be referenced by a visit. Service pricing '
            'is written by super-admin while a tenant may also carry its own price '
            'list, so the effective price depends on which console last wrote.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/departments/create', 'department created'),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/edit-department/<int:department_id>',
                'department edited',
            ),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/deactivate-department/<int:department_id>',
                'department deactivated',
            ),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/activate-department/<int:department_id>',
                'department reactivated',
            ),
            _s(SUPER_ADMIN, 'POST /super-admin/services/create', 'service created'),
            _s(SUPER_ADMIN, 'POST /super-admin/edit-service/<int:service_id>', 'service edited'),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/deactivate-service/<int:service_id>',
                'service deactivated',
            ),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/activate-service/<int:service_id>',
                'service reactivated',
            ),
            _s(SUPER_ADMIN, 'POST /super-admin/service-pricing/<int:service_id>', 'price written'),
        ),
    ),
    Template(
        key='SUPERADMIN_PLATFORM_OPERATIONS',
        family='platform',
        axes=('backup_schedule_type',),
        observed={'backup_schedule_type': ('daily', 'weekly', 'monthly', 'custom')},
        rule=(
            'Maintenance, cleanup, export and the seed tooling are the operations a '
            'clinical system should have least of and most need. export-data is the '
            'only route that leaves the system with the whole clinical corpus, and '
            'it is a single write with no confirmation step and no record of what '
            'was included. The seed routes are the reason a fresh database has demo '
            'users, which is worth knowing before trusting a staging dataset.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/system/cleanup', 'cleanup run'),
            _s(SUPER_ADMIN, 'POST /super-admin/maintenance/automation', 'automation rule written'),
            _s(SUPER_ADMIN, 'POST /super-admin/export-data', 'full export taken'),
            _s(SUPER_ADMIN, 'POST /super-admin/seed/users', 'demo users seeded'),
        ),
    ),
    Template(
        key='SUPERADMIN_BACKUP_LIFECYCLE',
        family='platform',
        axes=('backup_type',),
        observed={'backup_type': ('full', 'incremental', 'differential')},
        rule=(
            'Backup creation, deletion and restore are three routes over one table, '
            'and nothing in the backup path validates tenant scope, so a restore is '
            'platform wide and the guard that matters is who may trigger it. '
            'Deleting a backup row is how retention is enforced, so retention is a '
            'delete loop rather than a policy the job checks.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/backup/create', 'backup taken'),
            _s(SUPER_ADMIN, 'POST /backup/create', 'backup taken from the second console'),
            _s(SUPER_ADMIN, 'POST /backup/restore/<int:backup_id>', 'restore requested'),
            _s(SUPER_ADMIN, 'POST /backup/delete/<int:backup_id>', 'backup row removed'),
            _s(SUPER_ADMIN, 'POST /backup-restore/', 'restore wizard advanced'),
        ),
    ),
    Template(
        key='SUPERADMIN_NOTIFICATION_DELIVERY',
        family='platform',
        axes=('notification_priority', 'notification_state'),
        observed={
            'notification_priority': ('low', 'normal', 'high', 'urgent'),
            'notification_state': ('pending', 'sent', 'failed', 'read'),
        },
        rule=(
            'init-templates seeds the notification templates, run processes the '
            'queue and the queue can also be drained directly, so a notification '
            'can be sent twice by running both. A failed send is a state on the '
            'notification, not an error on the rule, which is why a broken webhook '
            'looks like a healthy rule with failed rows under it.'
        ),
        steps=(
            _s(
                SUPER_ADMIN,
                'POST /super-admin/system/notifications/init-templates',
                'templates seeded',
            ),
            _s(SUPER_ADMIN, 'POST /super-admin/system/notifications/run', 'queue processed'),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/system/notifications/queue/process',
                'queue drained directly, duplicating the run',
            ),
            _s(SUPER_ADMIN, 'POST /super-admin/system/sms/test', 'test SMS sent'),
            _s(SUPER_ADMIN, 'POST /super-admin/api/ai-assistant', 'assistant query executed'),
        ),
    ),
    Template(
        key='SUPERADMIN_BRANCH_AND_QUEUE_CONFIGURATION',
        family='platform',
        axes=(),
        observed={},
        rule=(
            'Queue settings are written per department by reception and globally by '
            'super-admin, so the effective configuration depends on which console '
            'wrote last and there is no precedence recorded anywhere. Branch '
            'templates are the platform-wide shape of a department tree, and '
            'applying one is a write with no undo.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/queue-settings', 'global queue settings written'),
            _s(SUPER_ADMIN, 'POST /super-admin/branch-templates', 'branch template created'),
            _s(
                RECEPTION,
                'POST /reception/queue/save-settings/<int:department_id>',
                'department settings override',
            ),
        ),
    ),
    Template(
        key='SUPERADMIN_SIMPLE_ROLE_AND_PERMISSION_WIZARDS',
        family='platform',
        axes=('permission_level',),
        observed={'permission_level': ('read', 'write', 'delete', 'admin', 'super_admin')},
        rule=(
            'create-role-simple and create-permission-simple are wizards beside the '
            'full routes, so there are two ways to make the same object and they do '
            'not guarantee the same shape. A role made by the wizard and a '
            'permission made by the wizard meet the same decorator, which checks a '
            'level string, so the level is what decides whether either is '
            'effective.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /super-admin/create-role-simple', 'role created by the wizard'),
            _s(
                SUPER_ADMIN, 'POST /super-admin/roles/create', 'role created through the full route'
            ),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/create-permission-simple',
                'permission created by the wizard',
            ),
            _s(SUPER_ADMIN, 'POST /super-admin/roles/<int:role_id>/delete', 'role deleted'),
        ),
    ),
    Template(
        key='SUPERADMIN_PLAN_CHANGE_FROM_PLATFORM',
        family='platform',
        axes=('subscription_type',),
        observed={'subscription_type': ('perpetual', 'monthly', 'yearly')},
        rule=(
            'change-plan validates the package family, so a tenant cannot move '
            'between unrelated families, but the same change is also reachable '
            'from the owner console and from the Stripe webhook, and each writes '
            'the subscription differently. Which console last wrote is the only '
            'way to tell, because there is one subscription and three writers.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'GET /owner/plans', 'the plan catalogue it will be changed to'),
            _s(SUPER_ADMIN, 'POST /super-admin/change-plan', 'plan changed, family validated'),
            _s(OWNER, 'POST /owner/plans/create', 'the plan family it was changed to'),
        ),
    ),
    Template(
        key='SUPERADMIN_DEPARTMENT_STAFF_BINDING',
        family='platform',
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
            'Binding a user to a department is separate from giving them a role, '
            'and the two are stored in different tables, so a user can be a doctor '
            'in no department. Removing the binding is the operation that leaves a '
            'scheduled visit pointing at a clinician who no longer appears in that '
            "department's work list, and the visit is not rewritten.",
        ),
        steps=(
            _s(
                SUPER_ADMIN,
                'POST /super-admin/department-staff/<int:department_id>/add',
                'clinician bound to the department',
            ),
            _s(
                SUPER_ADMIN,
                'POST /super-admin/department-staff/<int:department_id>/remove',
                'binding removed, scheduled visits untouched',
            ),
            _s(
                RECEPTION,
                'POST /reception/staff/schedule',
                'schedule written against the old binding',
            ),
        ),
    ),
)


def add_platform_admin_templates() -> int:
    """Extend templates.TEMPLATES in place, idempotently. Returns how many were added."""
    existing = {t.key for t in TEMPLATES}
    added = 0
    for t in PLATFORM_ADMIN_TEMPLATES:
        if t.key not in existing:
            TEMPLATES.append(t)
            added += 1
    return added
