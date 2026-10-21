# FX and Currency Design

**Status:** architectural decision, not yet implemented.
**Owner:** Lead Systems Architect
**Findings addressed:** B3 (currency conversion applied inconsistently across the money path).

---

## 1. The problem, stated precisely

The platform stores money in a currency and reports on it in a currency, and
today those two are the same thing. The tables that hold money are:

| Table | Amount columns | Currency column | Default |
|---|---|---|---|
| `payments` | `amount` | `currency` | `ILS` |
| `invoices` | `total_amount`, `paid_amount` | `currency` | `ILS` |
| `visits` | `total_amount`, `paid_amount` | `currency` | `ILS` |
| `service_prices` | price columns | `currency` | `SAR` |

None of them carries an amount in a base currency, and no table says what the
base currency of a tenant is. `tenants` has no `base_currency` column at all.

`models/exchange_rate.py` holds a tenant-scoped `ExchangeRate` with
`from_currency`, `to_currency`, `buy_rate`, `sell_rate`, `effective_date`,
`source` (`MANUAL` / `API` / `EXTERNAL`) and `is_active`, and
`models/exchange_rate.py::CurrencySettings` lists the ten supported
currencies (`ILS`, `USD`, `EUR`, `JOD`, `SAR`, `AED`, `QAR`, `KWD`, `BHD`,
`OMR`).

`services/currency_service.py` holds `CurrencyConverter.get_rate()` and
`CurrencyConverter.convert()`. **Nothing calls them.** The service is
reachable, is well written, and is dead: `get_rate` prefers a `MANUAL` rate,
then an `API` rate less than 24 hours old, then the inverse pair, and returns
`sell_rate`; `convert` returns `None` when no rate is found.

The finding B3 raised was that conversion is applied to `visit.paid_amount`
and not to the payment, the invoice or the general ledger. The accurate
statement of what is in the repository is the opposite and worse: **no
conversion is applied anywhere.** A visit paid in USD and invoiced in ILS
adds two numbers that mean different things, and the platform reports the
sum.

That is why this is documented as a design decision rather than patched.
Which of the several defensible designs is right depends on facts the
repository does not hold: what a tenant's base currency is, who may change
it, and whether a posted ledger row may be re-valued when a rate changes.
Those are decisions, and the decision is taken here.

---

## 2. Decision 1 — the base currency of a tenant

**A tenant has exactly one base currency, and it is stated on the tenant.**

### 2.1 The rule

`tenants.base_currency` is a `CHAR(3)` column, `NOT NULL`, holding an
ISO-4217 code drawn from `CurrencySettings.SUPPORTED_CURRENCIES`.

* A tenant's base currency is **the currency its general ledger is written
  in**. Every ledger amount, every total in a report that mixes tenants'
  data, and every consolidated figure is in the base currency of the tenant
  that owns the row.
* A tenant's base currency **may not change** once the tenant has posted a
  financial transaction. Before that point it may be changed freely.
* A tenant's base currency is **not** the currency of the country the clinic
  is in and **not** the currency of the platform. It is a property of the
  tenant, and a deployment may host tenants whose base currencies differ.

### 2.2 Why a column and not a derivation

The candidate derivations were each rejected for a specific reason:

* **Derive from the majority of the tenant's transactions.** Rejected: the
  answer changes as the clinic trades, so the same historical row would be
  in two different currencies depending on when it is read. A ledger cannot
  have that property.
* **Derive from the platform default.** Rejected: it makes a multi-currency
  deployment impossible, and the platform already hosts tenants that bill in
  different currencies.
* **Derive from the tenant's country or locale.** Rejected: the country is
  not a financial fact. A clinic in one country may bill in another
  currency, and the schema has no country field that is trustworthy for
  this.

A stated column is the only derivation that is stable, auditable, and
queryable. It also makes the "which currency is this row in" question
answerable without joining anything.

### 2.3 The immutability rule, and how it is enforced

The immutability is enforced in the database, not only in the application.
The check is that the column may not change once a financial transaction
exists for the tenant:

```sql
CREATE TRIGGER trg_tenants_base_currency_immutable
BEFORE UPDATE OF base_currency ON tenants
FOR EACH ROW
WHEN (
    OLD.base_currency IS DISTINCT FROM NEW.base_currency
    AND EXISTS (
        SELECT 1 FROM payments p WHERE p.tenant_id = OLD.id
    )
)
EXECUTE FUNCTION raise_immutable_base_currency();
```

The reason it is a trigger and not a route check: the same rule has to hold
for the seed, for a console, for a support engineer with `psql`, and for
anything that writes through the ORM. A rule that only the web routes
enforce is a rule that is one script away from being broken.

The error is raised as a distinct exception so the application can say
"this tenant's base currency cannot change because it has posted
transactions", rather than a generic constraint violation.

### 2.4 Migration and backfill

1. Add `tenants.base_currency` as nullable.
2. Backfill: `UPDATE tenants SET base_currency = <the currency the tenant's
   existing money is in>`. The backfill is **not** a guess from a majority.
   It is taken from the tenant's own rows: the currency of the tenant's
   invoices, and where the tenant has invoices in more than one currency,
   the currency of the most recent invoice, with the exception written to
   the migration's log. A tenant with money in two currencies is a tenant
   whose history cannot be represented by one base currency, and it is
   listed for review rather than silently assigned.
3. `SET NOT NULL`.
4. Add the trigger.
5. The platform default (`SAR`, which is the current default on
   `service_prices`) is used for tenants created after the migration and
   that have not chosen one.

The default currency on `payments`, `invoices` and `visits` stays as it is
today. Those defaults are wrong in general — the column should hold the
currency the transaction was *made in*, which is not always the base — and
the migration plan below addresses that separately.

---

## 3. Decision 2 — the rate is snapshotted at transaction time

**A money row carries the rate that was used to convert it, and never
re-reads a live rate.**

### 3.1 The rule

When a payment, invoice or visit is written with an amount in a currency
that is not the tenant's base currency, the row stores:

* the amount in the transaction currency (as today),
* the currency (as today),
* the amount in the base currency,
* the rate that was used to get there,
* the identity of the rate: the `exchange_rates.id` it came from, or the
  literal rate and its source when the rate was entered by hand.

`convert()` is called **once**, at write time. Nothing re-derives the base
amount afterwards.

### 3.2 Why snapshot rather than look up live

A live lookup makes a ledger that changes while it is being read. The
consequences are concrete:

* A report run on the 1st of the month and the same report run on the 2nd
  disagree, with no change in the data and no change in the code. The rate
  table is edited in between.
* A row that is written twice — once for the transaction and once for a
  correction — converts to two different base amounts, and the difference
  is indistinguishable from a real movement of money.
* When a rate is corrected after the fact, a live lookup silently
  restates history. There is no record that the restatement happened,
  because nothing was written when it happened.
* Auditors cannot reproduce a figure. The rate that produced it is gone.

The snapshot removes the whole class: the base amount of a transaction is a
fact about the transaction, and the rate that produced it is part of the
row.

### 3.3 What a live rate lookup is still for

Live lookup remains correct for **hypothetical** figures — "what is this
invoice worth in the base currency if it were paid today", a quote, a
dashboard card that shows the current value of an outstanding balance. The
rule is that a *hypothetical* may use a live rate, and a *posted* figure
may not. Every call site is therefore either a write (snapshot) or is
explicitly labelled as a live valuation, and the latter is never summed
into a financial report.

### 3.4 Which rate

`CurrencyConverter.get_rate()` already encodes the right precedence for the
clinic's side of the trade: a `MANUAL` rate first (the clinic's own
negotiated rate), then an `API` rate less than 24 hours old, then the
inverse pair, and it returns `sell_rate` — the rate at which the clinic
sells the foreign currency, which is the rate at which it receives the
foreign currency from a patient. That logic is kept.

Two changes are required to it:

* **`convert()` may not return `None`.** A caller that has to handle `None`
  will handle it by skipping the conversion, and the amount silently stays
  in the wrong currency. `convert()` raises instead, with a distinct error
  naming the currency pair that has no rate, and the caller decides whether
  to refuse the transaction. There is no "conversion failed, carry on
  without it" path.
* **The rate is returned as a value with its provenance**, not as a bare
  `Decimal`. The snapshot needs to know which row the rate came from.

---

## 4. Decision 3 — the base-currency ledger columns

**Every money row carries its base amount, and the general ledger is written
in base currency only.**

### 4.1 The columns

Added to `payments`, `invoices` and `visits`:

| Column | Type | Meaning |
|---|---|---|
| `amount_base_currency` | `NUMERIC(18, 2)` | the amount in the tenant's base currency, at the snapshotted rate |
| `base_currency` | `CHAR(3)` | the tenant's base currency at the time of the write |
| `exchange_rate` | `NUMERIC(18, 6)` | the rate used (`amount_base_currency = amount × exchange_rate`) |
| `exchange_rate_id` | `INTEGER` | the `exchange_rates` row used, when the rate came from the table |
| `exchange_rate_source` | `VARCHAR(16)` | `MANUAL`, `API` or `EXTERNAL` |

`exchange_rate_id` is a plain integer, not a foreign key with `ON DELETE
CASCADE`: a rate row that is deleted must not take the transactions that
used it with it. It is `ON DELETE SET NULL`, and the rate columns beside it
carry the values that were applied, so the provenance survives the deletion
of the rate.

`base_currency` is stored on the row rather than joined from the tenant
because the tenant's base currency is immutable after posting (§2.3) — the
join would always give the same answer, and storing it makes a row
self-describing and lets a bulk report read one table.

### 4.2 The invariant

```
amount_base_currency = ROUND(amount × exchange_rate, 2)
```

checked by a `CHECK` constraint to the cent, in the same way
`CHECK` constraints already carry the arithmetic rules on these tables. The
rounding is half-up, matching `CurrencyConverter.convert()`, and it is
applied once — to the base amount — and never to the transaction amount.

The base amount is the one that is summed. The transaction amount is the
one that is displayed on the receipt. Both are correct; they are answers to
different questions, and a report that adds the transaction amounts of
transactions in different currencies is wrong in a way no amount of
formatting will fix.

### 4.3 The general ledger

The general ledger is written in base currency only. A transaction in a
foreign currency produces a base-currency journal with the foreign amount
and the rate in the journal's own reference fields, so the ledger adds up
without a conversion at report time.

`gl_journals` gains the same `exchange_rate` provenance columns, because a
journal line that cannot be traced back to the rate that produced it is
exactly the problem this design exists to remove.

### 4.4 What is *not* converted

* **A refund** is written in the base currency of the original payment, at
  the rate of the original payment. It is not re-converted at today's rate.
  A refund that does not match the payment it refunds is a new movement of
  money, and it must be recorded as one — not silently absorbed.
* **A transfer between tenants** is a sale and a purchase: the selling
  tenant converts at its own rate, the buying tenant at its own, and the
  difference between them is a real gain or loss.
* **An insurance claim** is settled in the base currency of the tenant that
  holds the policy, at the rate of the invoice it settles.

---

## 5. What has to be true before any of this is implemented

This document is a decision, not a delivery. The following are the
conditions for implementing it, and each of them is a piece of work that has
not been done:

1. **The base currency of every existing tenant is known**, and the tenants
   whose money is in more than one currency have been reviewed. The
   backfill in §2.4 needs a reviewed list, not a query.
2. **The rate's provenance is carried** — `get_rate` returns the row it
   used, not just a number (§3.4).
3. **The rate table's editing is audited.** A manual rate that is edited
   without a record is a rate that can be changed after the fact. The
   `ExchangeRate` table has `created_by` and `notes` but no change trail;
   the rate is a financial input, so it needs the same treatment as the
   payment it affects.
4. **Every money write goes through one place.** The base amount is
   computed inside the write, not by each caller. Today the writes are
   spread over the payment route, the invoice service, the refund service
   and the POS. A conversion computed by four callers is a conversion
   computed four different ways.
5. **The reports are re-pointed at the base columns** before the first
   tenant has a mixed-currency history, because a report that changes its
   meaning after the fact cannot be compared with its own past.

## 6. How this will be tested

The decisions above are only worth anything if they are enforced by tests
that fail when the enforcement is removed:

* **A tenant with a base currency of X** — a payment of 100 USD against a
  base of ILS writes an `amount_base_currency` equal to 100 × the
  snapshotted rate, and the row carries the rate and its source.
* **The rate changes after the transaction.** The base amount of the
  transaction does not change. This is the test that the snapshot exists
  for, and it is the one that would have failed before.
* **A transaction with no rate for the pair** is refused with a message
  naming the pair. It is not accepted with the amount unconverted.
* **A tenant with transactions cannot change its base currency**, and the
  change is refused by the database, not only by the route. The test
  attempts the change over raw SQL.
* **A report that sums money across currencies** uses the base columns, and
  the figure it produces is the sum of the base amounts. The test
  constructs a tenant with two payments in different currencies and checks
  the report.
* **A refund equals its payment** in base currency, at the original rate.

## 7. Related

* [Allergy and Drug-Class Mapping Design](ALLERGY_MAPPING_DESIGN.md) — the
  other finding that needed a design decision rather than a patch, and the
  reason for it is the same: the repository does not hold the fact that the
  finding depends on.
