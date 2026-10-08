"""Integration and operations templates: HL7, FHIR, IHE, the warehouse, reports,
telemedicine, pricing administration and the operational consoles.

These are the routes that make the system talk to something else or get looked at
by an operator. They are separated from the clinical-ops templates because the
assertion here is about a boundary rather than about a patient: a message is
parsed or it is not, a report runs or it does not, a teleconsultation connects or
it does not.

The file is filed as ``clinical`` where the journey reaches a clinical route and
``rbac`` or ``platform`` where it does not, because the generator has to be told
the truth about which of the two it is.
"""

from __future__ import annotations

from templates import TEMPLATES, Template, _s

RECEPTION = 'Reception'
DOCTOR = 'Doctor'
LAB = 'Lab'
ACCOUNTANT = 'Accountant'
MANAGER = 'Manager'
NURSE = 'Nurse'
SUPER_ADMIN = 'SuperAdmin'
OWNER = 'Owner'

INTEGRATION_TEMPLATES: tuple[Template, ...] = (
    Template(
        key='INTEGRATION_HL7_MESSAGE_INGEST',
        family='clinical',
        axes=('hl7_message_type',),
        observed={'hl7_message_type': ('ADT', 'ORM', 'ORU', 'SIU', 'VXU')},
        rule=(
            'HL7 v2 ingest acknowledges then dispatches, so a message with an '
            'unknown type is accepted with a 200 and dropped, which is the correct '
            'behaviour for an interface engine and the worst possible behaviour for '
            'an audit. The control route is the operational lever over the '
            'interface: pause and resume are writes over the same channel the '
            'messages arrive on.'
        ),
        steps=(
            _s(DOCTOR, 'POST /doctor/lab-request/<visit_id>', 'the order the message reports on'),
            _s(LAB, 'POST /hl7/ingest', 'message accepted and dispatched'),
            _s(LAB, 'POST /hl7/control/<action>', 'channel paused or resumed'),
            _s(SUPER_ADMIN, 'POST /ihe/atna/audit', 'ATNA audit record written'),
        ),
    ),
    Template(
        key='INTEGRATION_FHIR_OBSERVATION_EXPORT',
        family='clinical',
        axes=('lab_result_flag',),
        observed={'lab_result_flag': ('normal', 'abnormal', 'critical')},
        rule=(
            'The FHIR observation export is the only route that publishes a lab '
            'result outside the tenant, and it is a one-way push with no '
            'acknowledgement handling, so a downstream rejection is invisible here. '
            'Exporting a critical result therefore leaves the tenant with no '
            'record that anything was sent.'
        ),
        steps=(
            _s(LAB, 'POST /lab/worklist/complete/<int:request_id>', 'result recorded'),
            _s(LAB, 'POST /lab/api/fhir/observation', 'observation exported'),
            _s(
                DOCTOR,
                'GET /doctor/print-medical-report/<int:visit_id>',
                'result read back locally',
            ),
        ),
    ),
    Template(
        key='INTEGRATION_DATA_WAREHOUSE_SYNC',
        family='platform',
        axes=(),
        observed={},
        rule=(
            'The warehouse sync is one write for the whole tenant and it is the '
            'only route that copies the clinical corpus outside the application '
            'database. There is no incremental cursor, no per-entity selection and '
            'no record of which run copied what, so an interrupted sync leaves no '
            'way to tell which rows made it across.'
        ),
        steps=(
            _s(MANAGER, 'GET /data-warehouse/', 'warehouse configured'),
            _s(MANAGER, 'POST /data-warehouse/sync', 'warehouse synchronised'),
            _s(SUPER_ADMIN, 'POST /super-admin/export-data', 'full export taken alongside it'),
        ),
    ),
    Template(
        key='INTEGRATION_REPORT_BUILDER',
        family='rbac',
        axes=('report_execution_state',),
        observed={
            'report_execution_state': ('pending', 'running', 'completed', 'failed', 'cancelled')
        },
        rule=(
            'A saved report template is run and the run state is recorded on the '
            'saved report, so a failed run is visible only as a state and never as '
            'an exception to the caller. preview is a separate route from run, '
            'which means the rows an operator checked before publishing are not '
            'guaranteed to be the rows the run returns.'
        ),
        steps=(
            _s(MANAGER, 'POST /report-builder/templates', 'template saved'),
            _s(MANAGER, 'POST /report-builder/preview', 'preview rendered'),
            _s(MANAGER, 'POST /report-builder/templates/<int:template_id>/run', 'report executed'),
        ),
    ),
    Template(
        key='TELEMEDICINE_CONSULTATION_LIFECYCLE',
        family='clinical',
        axes=('telemedicine_outcome',),
        observed={'telemedicine_outcome': ('completed', 'no_show', 'cancelled', 'ended_early')},
        rule=(
            'A teleconsultation is started, ended, marked no-show or cancelled, '
            'and those are four routes over one status column rather than one route '
            'with a parameter, which is why the column has no state machine to '
            'reject an impossible transition. Ending and cancelling are '
            'indistinguishable downstream except by the value written.'
        ),
        steps=(
            _s(DOCTOR, 'POST /telemedicine/new', 'consultation opened'),
            _s(DOCTOR, 'POST /telemedicine/consult/<int:cid>/start', 'consultation started'),
            _s(DOCTOR, 'POST /telemedicine/consult/<int:cid>/end', 'outcome written'),
            _s(DOCTOR, 'POST /telemedicine/consultations', 'list read back'),
        ),
    ),
    Template(
        key='TELEMEDICINE_NON_ATTENDANCE',
        family='clinical',
        axes=('telemedicine_outcome',),
        observed={'telemedicine_outcome': ('completed', 'no_show', 'cancelled', 'ended_early')},
        rule=(
            'A no-show and a cancellation are different outcomes with different '
            'consequences for the bill and for the waiting clinician, and both are '
            'single writes with no reason field. Nothing in either route releases '
            'the slot, so a no-show slot stays occupied until somebody edits the '
            'schedule.'
        ),
        steps=(
            _s(DOCTOR, 'POST /telemedicine/new', 'consultation opened'),
            _s(DOCTOR, 'POST /telemedicine/consult/<int:cid>/no-show', 'recorded as a no-show'),
            _s(DOCTOR, 'POST /telemedicine/consult/<int:cid>/cancel', 'recorded as cancelled'),
        ),
    ),
    Template(
        key='MANAGER_PRICING_ADMINISTRATION',
        family='financial',
        axes=('insurance_coverage',),
        observed={'insurance_coverage': ('50', '60', '70', '75', '80', '85', '90', '95', '100')},
        rule=(
            'Pricing is seeded and then maintained per service, and the seed route '
            'is the only way a fresh tenant gets a price list at all, which is why '
            'a walk-in visit prices at zero before it is run. Deleting a price is '
            'allowed, and a deleted price makes the service free rather than '
            'unserviceable, because nothing checks for a service with no price.'
        ),
        steps=(
            _s(MANAGER, 'POST /manager/seed-pricing', 'price list seeded'),
            _s(MANAGER, 'PUT /manager/api/pricing/services/<int:id>', 'price updated'),
            _s(MANAGER, 'DELETE /manager/api/pricing/services/<int:id>', 'price removed'),
            _s(RECEPTION, 'POST /reception/visits/create', 'visit priced from the new list'),
        ),
    ),
    Template(
        key='MANAGER_FINANCE_AND_BUDGET',
        family='financial',
        axes=('invoice_status',),
        observed={'invoice_status': ('DRAFT', 'ISSUED', 'POSTED', 'PAID', 'VOID')},
        rule=(
            'Archiving a visit is the reconciliation step: it requires the invoice '
            'line sum to equal visit.total_amount, so the check is a comparison of '
            'two aggregates that were written by two different code paths. Budget '
            'entry is the same shape, which is why a budget that balances against '
            'the ledger and a visit that archives against the invoice can disagree.'
        ),
        steps=(
            _s(
                ACCOUNTANT,
                'POST /finance/visits/<int:visit_id>/archive',
                'visit archived once the lines reconcile',
            ),
            _s(MANAGER, 'POST /manager/budget', 'budget recorded'),
            _s(MANAGER, 'POST /finance/slow-queries/capture', 'slow query captured for review'),
        ),
    ),
    Template(
        key='MANAGER_FORCE_PAYMENT_REVIEW',
        family='financial',
        axes=('force_payment_ratio',),
        observed={'force_payment_ratio': ('0', '2', '4', '5', '8')},
        rule=(
            'A manager can reject a force payment after the fact, and rejecting it '
            'is the only correction path for a payment the gate let through. The '
            'gate counts force payments over the last thirty days against all '
            'visits and refuses at five percent, so the ratio is what decides '
            'whether a visit needs a manager at all.'
        ),
        steps=(
            _s(RECEPTION, 'POST /payment/process/<visit_id>', 'payment collected'),
            _s(
                MANAGER,
                'POST /manager/reject-force-payment/<int:visit_id>',
                'force payment rejected by the manager',
            ),
            _s(
                ACCOUNTANT,
                'GET /accountant/payment-documentation/<int:payment_id>',
                'payment read back',
            ),
        ),
    ),
    Template(
        key='MANAGER_SETTINGS_AND_INTEGRATIONS',
        family='financial',
        axes=('config_category',),
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
            )
        },
        rule=(
            'Settings are written per tenant while the exchange rate is global, so '
            'a rate change reaches every tenant at once and nothing records which '
            'tenant saw which rate on a historical invoice. test-sms is the only '
            'route that verifies a channel actually works, and it is manual.'
        ),
        steps=(
            _s(MANAGER, 'POST /manager/settings', 'tenant settings written'),
            _s(MANAGER, 'POST /manager/settings/test-sms', 'SMS channel tested by hand'),
            _s(MANAGER, 'POST /manager/exchange-rates/fetch-api', 'rates fetched'),
            _s(
                MANAGER, 'POST /manager/exchange-rates/deactivate/<int:rate_id>', 'rate deactivated'
            ),
            _s(MANAGER, 'POST /manager/api/units/toggle', 'unit display toggled'),
        ),
    ),
    Template(
        key='MANAGER_WHAT_IF_MODELLING',
        family='financial',
        axes=('payment_method',),
        observed={'payment_method': ('CASH', 'CARD', 'visa', 'mada', 'WIRE', 'INSURANCE', 'FORCE')},
        rule=(
            'The what-if endpoint is a model, not an operation: it answers a '
            'question about a hypothetical price list and writes an assumption. '
            'revoke is how the assumption is withdrawn, and because the projection '
            'is recomputed from the assumption rather than from a stored total, '
            'revoking it changes the answer without leaving a trace of what the '
            'answer used to be.'
        ),
        steps=(
            _s(MANAGER, 'POST /what-if/new', 'scenario modelled'),
            _s(MANAGER, 'POST /manager/api/what-if', 'projection computed'),
            _s(OWNER, 'POST /owner/api/assumptions', 'assumption recorded'),
            _s(
                OWNER,
                'POST /owner/api/assumptions/<int:assumption_id>/revoke',
                'assumption revoked',
            ),
        ),
    ),
    Template(
        key='INSURANCE_CLAIM_ADJUDICATION',
        family='financial',
        axes=('insurance_claim_outcome',),
        observed={'insurance_claim_outcome': ('approved', 'partially_approved', 'rejected')},
        rule=(
            'Adjudication is a single write that records the outcome on the claim, '
            'and the payout that follows is recorded on the claim too. Neither '
            'reaches the general ledger, so an approved claim clears the insurer '
            'receivable without a journal entry and the accounts receivable '
            'account never moves.'
        ),
        steps=(
            _s(
                RECEPTION,
                'POST /reception/visits/<int:visit_id>/send-to-accounting',
                'claim raised',
            ),
            _s(
                ACCOUNTANT,
                'POST /payment/api/insurance/claims/<int:claim_id>/adjudicate',
                'outcome written',
            ),
            _s(ACCOUNTANT, 'POST /api/claims/<claim_id>/payout', 'insurer payout recorded'),
            _s(ACCOUNTANT, 'GET /payment/api/insurance/claims/<int:claim_id>', 'claim read back'),
        ),
    ),
    Template(
        key='ACCOUNTANT_REFUND_EXECUTION',
        family='financial',
        axes=('journal_status',),
        observed={'journal_status': ('POSTED', 'VOID')},
        rule=(
            'A refund is requested, approved and executed, and the execute route '
            'is on a different blueprint from the request and approve routes, so '
            'the one console that can collect a payment cannot execute its own '
            'refund. VOID is the ledger correction path and it reverses lines '
            'rather than deleting them.'
        ),
        steps=(
            _s(ACCOUNTANT, 'POST /payment/refund-requests/<refund_id>/approve', 'refund approved'),
            _s(ACCOUNTANT, 'POST /accountant/refunds/<int:refund_id>/execute', 'refund executed'),
            _s(ACCOUNTANT, 'GET /accountant/refunds', 'refund queue read back'),
        ),
    ),
    Template(
        key='PAYMENT_INSURANCE_ADJUDICATION_API',
        family='financial',
        axes=('insurance_claim_status',),
        observed={
            'insurance_claim_status': (
                'DRAFT',
                'SUBMITTED',
                'UNDER_REVIEW',
                'APPROVED',
                'PARTIALLY_APPROVED',
                'REJECTED',
                'SETTLED',
            )
        },
        rule=(
            'The insurance claim machine runs DRAFT to SETTLED and only SETTLED '
            'should mean money arrived. Adjudication can write APPROVED, '
            'PARTIALLY_APPROVED or REJECTED directly, so a claim can be settled by '
            'a payout write without passing through the status the machine would '
            'have required.'
        ),
        steps=(
            _s(ACCOUNTANT, 'POST /api/claims/<claim_id>/submit', 'claim submitted'),
            _s(ACCOUNTANT, 'POST /api/claims/<claim_id>/adjudicate', 'claim adjudicated'),
            _s(ACCOUNTANT, 'POST /api/claims/<claim_id>/settle', 'claim settled'),
            _s(
                ACCOUNTANT,
                'POST /payment/api/insurance/claims/<int:claim_id>/adjudicate',
                'outcome written from the payment console',
            ),
        ),
    ),
    Template(
        key='LEDGER_JOURNAL_REVERSAL',
        family='financial',
        axes=('journal_source_type',),
        observed={
            'journal_source_type': (
                'visit',
                'invoice',
                'payment',
                'pharmacy_sale',
                'expense',
                'refund',
                'procurement',
            )
        },
        rule=(
            'Idempotency in the ledger is per source type and source id, so a '
            'payment posted twice under two different source types is two valid '
            'journals rather than a double entry the guard catches. VOID is how '
            'the mistake is undone, and the reversal is the only audit of it.'
        ),
        steps=(
            _s(ACCOUNTANT, 'POST /payment/process/<visit_id>', 'payment journal posted'),
            _s(ACCOUNTANT, 'GET /accountant/journals', 'ledger read back'),
            _s(MANAGER, 'POST /manager/settings', 'corrective settings applied'),
        ),
    ),
    Template(
        key='PHARMACY_SALE_POSTS_TO_LEDGER',
        family='financial',
        axes=('journal_source_type',),
        observed={
            'journal_source_type': (
                'visit',
                'invoice',
                'payment',
                'pharmacy_sale',
                'expense',
                'refund',
                'procurement',
            )
        },
        rule=(
            'A pharmacy sale is its own source type rather than a visit payment, '
            'which is how a retail sale avoids needing a Visit row at all. The '
            'consequence is that the pharmacy ledger and the visit ledger are two '
            'streams over the same cash account, so a reconciliation between them '
            'is what catches a sale that was recorded in one and not the other.'
        ),
        steps=(
            _s(MANAGER, 'POST /manager/seed-pricing', 'drug prices present'),
            _s(ACCOUNTANT, 'POST /medication/pos/charge', 'sale posted'),
            _s(ACCOUNTANT, 'GET /accountant/journals', 'sale journal read back'),
        ),
    ),
    Template(
        key='PROCUREMENT_SUPPLY_CHAIN',
        family='clinical',
        axes=('supply_request_status',),
        observed={'supply_request_status': ('DRAFT', 'APPROVED', 'FULFILLED', 'CANCELLED')},
        rule=(
            'A supply request moves DRAFT to APPROVED to FULFILLED and the '
            'inventory ledger records the receipt, but the ledger movement type is '
            'chosen by the caller and nothing ties it to the request that caused '
            'it, so the stock on hand and the purchase history are two records of '
            'the same event.'
        ),
        steps=(
            _s(MANAGER, 'POST /medication/purchases/add', 'stock received'),
            _s(MANAGER, 'POST /medication/suppliers/add', 'supplier on file'),
            _s(NURSE, 'POST /nurse/api/protocols', 'supply protocol recorded'),
        ),
    ),
    Template(
        key='INTEGRATION_API_KEY_CONSUMER',
        family='rbac',
        axes=(),
        observed={},
        rule=(
            'The platform API is consumed with a key rather than a session, so the '
            'whole access decision rests on the scopes string stored in a JSON '
            'blob. Because the key list is truncated on save, a revoked key can '
            'reappear: once the hundred and first key pushes it off the end of '
            'the list, there is no longer a row to revoke.'
        ),
        steps=(
            _s(SUPER_ADMIN, 'POST /owner/api-keys', 'key minted'),
            _s(ACCOUNTANT, 'POST /api/user/preferences', 'API write attempted with the key'),
            _s(SUPER_ADMIN, 'POST /owner/api-keys/<int:key_id>/delete', 'key revoked'),
        ),
    ),
)


def add_integration_templates() -> int:
    """Extend templates.TEMPLATES in place, idempotently. Returns how many were added."""
    existing = {t.key for t in TEMPLATES}
    added = 0
    for t in INTEGRATION_TEMPLATES:
        if t.key not in existing:
            TEMPLATES.append(t)
            added += 1
    return added
