"""Execute the drug interaction catalogue, and check who it belongs to.

Phase 7e. A drug interaction is a fact about drugs, so a shared table is a
reasonable shape on its face. The question this module asks is about the write
path: a clinic that learns something about two drugs is writing into that shared
table, and the shape stops being reasonable the moment the writer is a tenant.

Driven through:

  GET|POST /medication/interactions
  POST /medication/interactions/<id>/toggle

What execution established:

  * The normalisation and clamping are correct. A pair is ordered so that A/B and
    B/A cannot both exist, severity is clamped to LOW/MODERATE/HIGH, and re-posting
    an existing pair updates it rather than duplicating it.

  * DrugInteraction has no tenant_id, no TenantMixin and no RLS policy. The
    catalogue is global in the strict sense: one row set for every tenant.

  * The consequences are on both sides of the route, and they are different.

    The medication dropdown is filtered to the caller's tenant. The interaction
    table beside it is not filtered at all — `select(DrugInteraction)` with no
    predicate. So a pharmacist sees their own formulary and, below it, every
    interaction any other clinic has recorded, naming drugs from that clinic's
    formulary. That is a disclosure of another tenant's clinical configuration,
    and it is not a list of ids: the template renders the drug names.

    The write side compounds it. `created_by` records who added the row, but a
    pharmacist can switch on a pair and thereby impose that interaction on every
    other clinic, which cannot see, scope or undo it.
"""

from __future__ import annotations

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.drug_interaction import DrugInteraction
from models.medication import Medication
from tests.scenario_execution_registry import covers


def _medication(tenant_id, suffix, price='10.00'):
    return Medication(
        tenant_id=tenant_id,
        trade_name=f'{suffix} Tablet',
        scientific_name=f'{suffix.lower()}-sci',
        generic_name=f'{suffix.lower()}-gen',
        dosage_form='tablet',
        strength='10mg',
        price=price,
        is_active=True,
    )


@pytest.fixture
def two_pharmacies(app, test_tenant):
    """A pharmacist in this tenant, and two medications that are only theirs."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['pharmacy'])
    pharmacist = ensure_test_user(db, test_tenant, username='e2e_inter_pharm', role='pharmacist')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, pharmacist, test_tenant)

    # The medications are keyed on a hash of the tenant and a suffix, so they belong
    # to this tenant and to no other. Two tenants, two distinct drugs.
    ours_a = _medication(test_tenant.id, 'E2E Clot')
    ours_b = _medication(test_tenant.id, 'E2E Warf')
    db.session.add_all([ours_a, ours_b])
    db.session.commit()
    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'pharmacist_id': pharmacist.id,
        'a_id': ours_a.id,
        'b_id': ours_b.id,
    }


def _interactions():
    return db.session.execute(select(DrugInteraction)).scalars().all()


@covers('MEDICATION_CATALOG_AND_INTERACTIONS')
class TestTheCatalogueNormalises:
    def test_a_pair_is_stored_once_in_a_fixed_order(self, two_pharmacies):
        """A/B and B/A are the same interaction, so one row is enough.

        min/max on the two ids is what makes that true, and it is worth pinning
        because the rest of this file is about the row's missing tenant — and a
        table that cannot even hold one row per pair would be a different problem.
        """
        client, a_id, b_id = (
            two_pharmacies['client'],
            two_pharmacies['a_id'],
            two_pharmacies['b_id'],
        )

        client.post(
            '/medication/interactions',
            data={
                'medication_a_id': a_id,
                'medication_b_id': b_id,
                'severity': 'HIGH',
                'description': 'bleeding risk',
                'is_active': 'on',
            },
            follow_redirects=False,
        )
        client.post(
            '/medication/interactions',
            data={
                'medication_a_id': b_id,
                'medication_b_id': a_id,
                'severity': 'LOW',
                'description': 'revised severity',
                'is_active': 'on',
            },
            follow_redirects=False,
        )

        rows = [
            r for r in _interactions() if {r.medication_a_id, r.medication_b_id} == {a_id, b_id}
        ]
        assert len(rows) == 1, (
            f'the same pair is stored {len(rows)} times: {[(r.id, r.severity) for r in rows]}'
        )
        assert rows[0].medication_a_id == min(a_id, b_id), (
            'the pair was not normalised to a fixed order'
        )
        assert rows[0].severity == 'LOW', (
            f're-posting the pair in the other order did not update it; severity is '
            f'still {rows[0].severity!r}'
        )

    def test_an_unrecognised_severity_is_clamped_not_rejected(self, two_pharmacies):
        """A typo in severity becomes MODERATE rather than an error or a bad value."""
        client, a_id, b_id = (
            two_pharmacies['client'],
            two_pharmacies['a_id'],
            two_pharmacies['b_id'],
        )

        client.post(
            '/medication/interactions',
            data={
                'medication_a_id': a_id,
                'medication_b_id': b_id,
                'severity': 'CATASTROPHIC',
                'description': 'bad severity input',
                'is_active': 'on',
            },
            follow_redirects=False,
        )

        row = next(
            r for r in _interactions() if {r.medication_a_id, r.medication_b_id} == {a_id, b_id}
        )
        assert row.severity in {'LOW', 'MODERATE', 'HIGH'}, (
            f'severity was stored as {row.severity!r}, which is not one of the three '
            f'values the interaction screen knows how to read'
        )
        assert row.severity == 'MODERATE', (
            f'an unrecognised severity became {row.severity!r}; the clamp is to '
            f'MODERATE, and a value that falls through to LOW would understate a '
            f'conflict somebody typed deliberately'
        )


@covers('MEDICATION_CATALOG_AND_INTERACTIONS')
class TestTheCatalogueBelongsToEveryone:
    @pytest.mark.xfail(
        strict=True,
        reason=(
            'known defect: DrugInteraction has no tenant_id and no RLS, so an '
            'interaction one tenant records blocks dispensing in every other tenant '
            'and cannot be scoped back by the clinic that added it'
        ),
    )
    def test_an_interaction_recorded_by_one_tenant_is_scoped_to_that_tenant(self, two_pharmacies):
        """A clinic's own clinical decision must not become a global rule.

        The row is keyed on two medication ids that belong to this tenant, and
        created_by names this pharmacist. The prescription screen consults this
        table for every tenant, so turning a pair on here turns it on for every
        clinic that happens to stock the same two drugs — and the clinic that
        decided it has no way to scope or withdraw it.
        """
        from app.core.tenant.models import Tenant

        other = Tenant(
            slug='e2e-inter-other',
            name='Interaction Other',
            contact_email='inter@example.com',
            status='ACTIVE',
            product_profile_code=None,
        )
        db.session.add(other)
        db.session.commit()

        # The pair is global. There is no column that could make it otherwise.
        row = DrugInteraction(
            medication_a_id=two_pharmacies['a_id'],
            medication_b_id=two_pharmacies['b_id'],
            severity='HIGH',
            description='recorded by one clinic only',
            is_active=True,
            # created_by is a FK to users.id, not to tenants.
            created_by=two_pharmacies['pharmacist_id'],
        )
        db.session.add(row)
        db.session.commit()

        assert hasattr(row, 'tenant_id'), (
            'DrugInteraction has no tenant_id, so this row is shared by every '
            'tenant. It was recorded by one clinic, against two medications from that '
            "clinic's own formulary, and it will now be consulted by the dispense "
            'screen for every other tenant that stocks the same two drugs — with no '
            'way for the clinic that recorded it to scope it or withdraw it. Add the '
            'column, scope the writes and the reads to it, and seed genuine global '
            'interactions through a separate table that tenants cannot write to.'
        )

    def test_the_interaction_list_shows_only_this_tenants_interactions(self, two_pharmacies):
        """The dropdown is scoped and the table under it is not.

        The handler filters the medication list to `tenant_id == current_user.tenant_id`
        and then renders `select(DrugInteraction)` with no predicate at all, so the
        page shows this tenant's formulary and every clinic's interaction decisions
        in the same breath. The names in those rows are other tenants' drugs.
        """
        from app.core.tenant.models import Tenant
        from tests.tenant_context import tenant_test_context

        other = Tenant(
            slug='e2e-inter-leak',
            name='Interaction Leak',
            contact_email='leak@example.com',
            status='ACTIVE',
            product_profile_code=None,
        )
        db.session.add(other)
        db.session.flush()

        # Create the other tenant's medications and interaction in their RLS scope.
        with tenant_test_context(two_pharmacies['app'], other):
            their_drug_a = _medication(other.id, 'Their Drug A')
            their_drug_b = _medication(other.id, 'Their Drug B')
            db.session.add_all([their_drug_a, their_drug_b])
            db.session.flush()
            db.session.add(
                DrugInteraction(
                    medication_a_id=their_drug_a.id,
                    medication_b_id=their_drug_b.id,
                    severity='HIGH',
                    description='another clinic decided this pair is dangerous',
                    is_active=True,
                )
            )
            db.session.commit()

        resp = two_pharmacies['client'].get('/medication/interactions', follow_redirects=False)
        assert resp.status_code == 200, f'interactions page answered {resp.status_code}'

        body = resp.get_data(as_text=True)
        assert 'Their Drug A' not in body, (
            "this tenant's interaction page names 'Their Drug A', a medication that "
            "belongs to another tenant's formulary. The medication dropdown is "
            "filtered to the caller's tenant and the interaction table is not "
            'filtered at all, so the page leaks another clinic formulary and its '
            'interaction decisions together'
        )
