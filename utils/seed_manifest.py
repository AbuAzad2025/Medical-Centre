"""Single source of truth for foundational data and boot-time datasets.

Before this module the foundational records were spread across
``app/core/platform_bootstrap.py`` (developer config, storage paths, admin
settings), ``app/core/reference_data.py`` (departments),
``seeds/production_baseline.py`` (platform tenant, master account) and
``scripts/fresh_setup.py`` (which turned out to own nothing: it imported roles
and permissions from ``models/permissions.py`` and only seeded demo patients).
Four places to remember, and they had already drifted.

Everything the boot sequence needs is now declared here, once:

* the *data* -- departments, developer configuration, runtime directories, admin
  settings;
* the *registry* -- :data:`DATASETS`, an ordered list of
  :class:`Dataset` entries, which the engine walks.

Adding a dataset is therefore a data change, not a code change: append a
``Dataset`` and the engine picks it up, runs it inside its own error boundary
and reports it in the boot summary.

Scope of what belongs here
--------------------------
Structural clinical and platform reference data whose content is stable and
verifiable. Deliberately excluded, because seeding them would be fabrication or
a security hazard:

* **Staff and doctor accounts.** An account with a known password is an
  unauthenticated backdoor. Staff are created by an administrator.
* **Patients and visits.** Fabricated clinical records are a safety hazard.
* **Insurance companies.** Commercial entities that differ per country.
* **Wards, rooms, beds.** Physical inventory of one specific building; inventing
  them makes occupancy reporting lie.
* **LOINC / CPT / national drug codes.** Must come from a maintained terminology
  source. A plausible but wrong code gets billed and reported as fact.

Rules encoded below, and the reasons they are not negotiable:

* **No fixed default password, ever.** A password derived from a predictable
  input (a date, a username, a hostname) is not a secret. It was previously
  derived from the current date in two places; both are gone.
* **Never reset an existing account.** Re-running a seed must not lock anyone
  out or silently change a working credential.
* **Never invent schema.** Alembic owns the schema.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Platform identity
# ---------------------------------------------------------------------------

#: Role that grants platform-wide access. Matches utils.decorators and
#: services.access_control_service, which is the single naming convention.
PLATFORM_ADMIN_ROLE = 'super_admin'
PLATFORM_ADMIN_USERNAME = os.environ.get('PLATFORM_ADMIN_USERNAME', 'superadmin')
PLATFORM_ADMIN_EMAIL = os.environ.get('PLATFORM_ADMIN_EMAIL', 'admin@localhost')

#: Directories the app writes to at runtime. All are in .gitignore, which is
#: exactly why they are missing on a fresh clone and why provisioning them here
#: is correct. A test asserts every entry is gitignored, so this list can never
#: grow a path the repository tracks.
RUNTIME_DIRECTORIES: tuple[str, ...] = (
    'instance',
    'logs',
    'backups',
    'flask_session',
    'static/uploads',
    'static/reports',
)

# ---------------------------------------------------------------------------
# Clinical reference data
# ---------------------------------------------------------------------------

#: (english name, arabic name). The English name is the department's identity:
#: it is what the rest of the system matches on, so changing it would create a
#: second department rather than rename one.
DEFAULT_DEPARTMENTS: tuple[tuple[str, str], ...] = (
    ('General Clinic', 'العيادة العامة'),
    ('Emergency', 'الطوارئ'),
    ('Internal Medicine', 'الباطنية'),
    ('General Surgery', 'الجراحة العامة'),
    ('Orthopedics', 'العظام'),
    ('Cardiology', 'القلبية'),
    ('Pediatrics', 'الأطفال'),
    ('Gynecology', 'النسائية'),
    ('ENT', 'أنف وأذن وحنجرة'),
    ('Ophthalmology', 'العيون'),
    ('Dermatology', 'الجلدة'),
    ('Urology', 'المسالك البولية'),
    ('Neurology', 'الأعصاب'),
    ('Radiology', 'الأشعة'),
    ('Lab', 'المختبر'),
)

#: A clinical unit cannot operate without these. The readiness check uses them to
#: report a deployment that seeded nothing as not-ready instead of quietly
#: serving an unusable system.
ESSENTIAL_DEPARTMENTS: frozenset[str] = frozenset(
    {'General Clinic', 'Emergency', 'Internal Medicine', 'Radiology', 'Lab'}
)

# ---------------------------------------------------------------------------
# Platform configuration
# ---------------------------------------------------------------------------

DEVELOPER_CONFIG: tuple[dict[str, str], ...] = (
    {'key': 'developer_company', 'value': 'شركة آزاد للأنظمة الذكية', 'type': 'string'},
    {'key': 'developer_name', 'value': 'المهندس أحمد غنام', 'type': 'string'},
    {'key': 'developer_logo_url', 'value': '', 'type': 'string'},
    {'key': 'developer_mobile', 'value': '+ --------', 'type': 'string'},
    {'key': 'developer_location', 'value': 'رام الله - فلسطين', 'type': 'string'},
)


def resolve_admin_password() -> str:
    """Return the configured admin password, or generate a random one.

    An explicit ``PLATFORM_ADMIN_PASSWORD`` is honoured so an operator can drive
    a deployment from a secret store. Otherwise a random password is generated;
    it is returned exactly once, at creation time, and never derived from
    anything guessable.
    """
    configured = os.environ.get('PLATFORM_ADMIN_PASSWORD')
    if configured and configured.strip():
        return configured
    return secrets.token_urlsafe(18)


# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Dataset:
    """One boot-time check or seed, declared so the engine can be generic.

    ``summary_key`` is the name the step reports under in the boot summary, and
    ``summary_key`` values for the three original counters are part of this
    function's published contract -- they are asserted by tests and printed by
    the first-run tooling, so they keep their historical names.
    """

    key: str
    provider: Callable[[], Any]
    scope: str  # 'platform' | 'tenant' | 'filesystem' | 'schema'
    summary_key: str
    description: str
    required: bool = True
    tags: tuple[str, ...] = field(default_factory=tuple)


def build_registry() -> tuple[Dataset, ...]:
    """Return the ordered dataset registry.

    The providers live in :mod:`app.core.platform_bootstrap` and are imported
    here at call time rather than at module import. That is deliberate: the
    bootstrap module imports the *data* from this manifest, so importing its
    providers eagerly would be a circular import. Keeping the indirection behind
    a function lets the data table itself be imported with no app, no Flask and
    no models -- usable from scripts, tests and audits.
    """
    from app.core import platform_bootstrap as engine

    return (
        Dataset(
            key='schema',
            provider=engine.check_schema_health,
            scope='schema',
            summary_key='schema',
            description='Verify tables exist. Never invents schema; Alembic owns it.',
        ),
        Dataset(
            key='storage',
            provider=engine.ensure_storage_directories,
            scope='filesystem',
            summary_key='storage',
            description='Create the gitignored runtime directories.',
            required=False,
            tags=('filesystem',),
        ),
        Dataset(
            key='module_definitions',
            provider=engine.ensure_module_definitions,
            scope='platform',
            summary_key='module_definitions_added',
            description='Register every MODULE_REGISTRY entry.',
        ),
        Dataset(
            key='product_bundles',
            provider=engine.ensure_product_bundles,
            scope='platform',
            summary_key='product_bundles',
            description='Seed the default ProductBundle catalogue.',
        ),
        Dataset(
            key='saas_packages',
            provider=engine.ensure_saas_packages,
            scope='platform',
            summary_key='saas_packages_added',
            description='Mirror bundles into packages and package versions.',
        ),
        Dataset(
            key='developer_config',
            provider=engine.ensure_developer_config,
            scope='platform',
            summary_key='developer_config',
            description='Seed developer identity into system_configs.',
        ),
        Dataset(
            key='departments',
            provider=engine.ensure_departments,
            scope='tenant',
            summary_key='departments',
            description='Seed the department catalogue for every tenant.',
        ),
        Dataset(
            key='reference_data',
            provider=engine.check_reference_data_readiness,
            scope='schema',
            summary_key='reference_data',
            description='Report a system missing essential clinical data as not-ready.',
        ),
        Dataset(
            key='terminology',
            provider=engine.load_terminology,
            scope='platform',
            summary_key='terminology',
            description=(
                'Load operator-supplied CPT/LOINC releases. Never invents codes; '
                'reports "not loaded" when no source is configured.'
            ),
            required=False,
            tags=('operator-supplied', 'never-fabricated'),
        ),
        Dataset(
            key='platform_admin',
            provider=engine.ensure_platform_admin,
            scope='platform',
            summary_key='admin',
            description='Ensure a superadmin exists. Random password, never reset.',
        ),
    )


#: Datasets whose failure means the deployment is not usable. Reported loudly by
#: the engine; the rest degrade to a log line.
REQUIRED_DATASETS: frozenset[str] = frozenset(
    {'schema', 'product_bundles', 'departments', 'reference_data'}
)
