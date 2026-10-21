# Allergy and Drug-Class Mapping Design

**Status:** architectural decision, not yet implemented.
**Owner:** Lead Systems Architect
**Findings addressed:** the clinical-safety finding that the allergy check
matches names and cannot see a class.

---

## 1. The problem, stated precisely

The platform refuses to prescribe a drug to a patient who has recorded an
allergy to it. The check is in
`services/clinical_safety_service.py::ClinicalSafetyService._check_allergies`,
and it works like this:

* the patient's `patient_allergies` rows are read (`models/patient.py::PatientAllergy`,
  with a free-text `allergen` column);
* for each proposed medication (`models/medication.py::Medication`), the
  allergen string is compared against three of the medication's name fields
  — `trade_name`, `generic_name` and `scientific_name`;
* the match is a substring test in both directions:
  `allergen in med_name or med_name in allergen`;
* a match raises a `SafetyAlert`, and a hard stop blocks the prescription.

That last part is right and stays. What is wrong is the **shape of the
comparison**, and the fix is not a better string comparison.

Consider a patient recorded as allergic to `penicillin`, and a proposed
medication whose trade name is `Amoxil` and whose generic name is
`amoxicillin`. The test asks whether `'penicillin'` is inside
`'amoxicillin'` — it is not — or whether `'amoxicillin'` is inside
`'penicillin'` — it is not. The prescription proceeds.

Amoxicillin *is* a penicillin. The patient is about to be given the very
substance they are recorded as allergic to, and the check that exists
precisely to prevent that does not fire.

No amount of string work fixes this. `penicillin` is a **class** and
`amoxicillin` is a **member** of it. The relationship between them is a
fact about pharmacology, it has to be stored somewhere, and it is not
stored anywhere in the repository:

* `Medication` has `scientific_name`, `trade_name`, `generic_name`,
  `dosage_form`, `strength`, `manufacturer`, `price`, `category` and
  `description`. There is **no ingredient column and no class column** —
  `category` is free text ("antibiotic", "painkiller") and is not a
  pharmacological relationship.
* `PatientAllergy` has a free-text `allergen` and a `severity`. There is
  no link to a drug or to a class.

The allergy check was already improved once, to compare all three name
fields rather than the trade name alone, and that closed the case of
"the patient is allergic to the generic name and the drug is sold under a
brand name". It did not close this one, and it could not: the information
it needs is not in the data.

## 2. Why the same treatment as B3

This is the same kind of finding as the currency one, and it is documented
the same way for the same reason. The check is not wrong in its logic; the
**fact it depends on is missing from the schema**. Writing a cleverer
comparison over a schema that does not hold the relationship produces code
that looks like it works and is wrong in the case that matters most — the
patient with a real, common, documented allergy.

---

## 3. Decision 1 — a drug class is a thing in the schema

**The platform stores the relation between a drug and the class it belongs
to, and the allergy check consults it.**

### 3.1 The model

Three tables, all tenant-scoped, all seeded from a terminology file rather
than hand-written:

**`drug_classes`** — the class itself.

| Column | Type | Meaning |
|---|---|---|
| `id` | PK | |
| `code` | `VARCHAR(32)` | stable code, e.g. `PENICILLIN`, `BETA_LACTAM`, `NSAID`, `SULFONAMIDE` |
| `name` | `VARCHAR(200)` | display name |
| `parent_class_id` | FK → `drug_classes.id` | the class this one is a member of |
| `is_contraindicated` | `BOOLEAN` | whether the class is a hard allergy on its own |

The hierarchy is what carries the pharmacology: `amoxicillin` is a member
of `penicillin`, and `penicillin` is a member of `beta-lactam`. A patient
allergic to `beta-lactam` is therefore matched by the same walk that
matches `penicillin`, without any pair being enumerated by hand.

**`drug_ingredients`** — the substance.

| Column | Type | Meaning |
|---|---|---|
| `id` | PK | |
| `code` | `VARCHAR(32)` | e.g. `AMOXICILLIN` |
| `name` | `VARCHAR(200)` | |
| `is_contraindicated` | `BOOLEAN` | a substance that is never given, whatever the class |

**`medication_ingredients`** — which substances a product contains.

| Column | Type | Meaning |
|---|---|---|
| `medication_id` | FK → `medications.id` | |
| `ingredient_id` | FK → `drug_ingredients.id` | |
| `is_primary` | `BOOLEAN` | the ingredient the product is named for |

**`drug_class_relations`** — the cross-reactivity between classes, which is
not the same as membership.

| Column | Type | Meaning |
|---|---|---|
| `from_class_id` | FK → `drug_classes.id` | |
| `to_class_id` | FK → `drug_classes.id` | |
| `relation` | `VARCHAR(24)` | `CROSS_REACTIVE` or `RELATED` |
| `risk` | `VARCHAR(16)` | `HIGH`, `MODERATE`, `LOW` |

This table is the one that stops the design from being dangerous.
`penicillin → amoxicillin` is not a cross-reaction; it is the same
substance, and it is a **block**. `penicillin → cephalosporin` is a
cross-reaction with a real but lower incidence, and it is a **warning with
a recorded severity** — not a block, because blocking every
cephalosporin for every penicillin-allergic patient drives clinicians to
override the system, and a system that is routinely overridden protects
nobody.

**`patient_allergies`** gains `class_id` (FK → `drug_classes.id`) and
`ingredient_id` (FK → `drug_ingredients.id`), both nullable, alongside the
existing free-text `allergen`. The text stays: it is what the clinician
typed, it is what the record shows, and it is what a class cannot express —
"rash after the yellow tablets in 2019" is a fact worth keeping.

### 3.2 The data comes from a file, and is never invented

The platform already has this rule and it is applied to terminology: when
`TERMINOLOGY_PATH` is not set, the bootstrap logs that *"CPT/LOINC codes
must come from the official release; none were invented"* and leaves the
catalogues empty.

**The same rule applies here.** The drug-class ontology is loaded from an
official release file (a drug classification such as ATC, or a curated
ingredient-to-class cross-reference). It is not hand-written into a
migration, and it is not guessed at runtime.

This is deliberate. An invented drug-class ontology is worse than none: it
would be applied to real patients, it would be wrong in ways nobody could
find, and it would look authoritative. An empty one produces an empty
terminology table, the same honest state the platform is already in for
CPT and LOINC.

The consequence for safety is handled in §4: with no ontology loaded, the
check cannot verify class membership, so it must say so — and "unable to
verify" is a hard stop, which the platform already does.

### 3.3 Recording an allergy

When a clinician records an allergy, the free text is resolved against the
ontology:

* exact ingredient match → `ingredient_id` is set;
* exact or ancestor class match → `class_id` is set;
* no match → neither is set, the free text is kept, and the record is
  flagged as **unresolved**.

An unresolved allergy is not a soft one. A patient with an unresolved
allergy record is a patient whose allergies cannot be checked against the
class ontology, and the prescription path treats that as a critical
condition until someone resolves it (§4).

## 4. Decision 2 — the check consults the class graph

**A proposed medication is blocked when it contains a substance the patient
is allergic to, and warned about when it contains a substance in a class
that cross-reacts with one of the patient's allergies.**

### 4.1 The algorithm

For each proposed medication and each of the patient's allergies:

1. **Direct match** (what the platform does today): the allergen string
   against `trade_name`, `generic_name` and `scientific_name`. A match is
   a **block** at the recorded severity.
2. **Ingredient match** (new): the medication's `medication_ingredients`
   rows joined to the patient's `ingredient_id`. A match is a **block** at
   the recorded severity.
3. **Class match** (new): the medication's ingredients' classes, walked
   **up** the `parent_class_id` chain, joined to the patient's `class_id`.
   A match is a **block** at the recorded severity.
4. **Cross-reactivity** (new): the medication's classes joined to the
   patient's class through `drug_class_relations` with
   `relation = 'CROSS_REACTIVE'`. A match is a **warning**, carrying the
   `risk` from the relation, and it says which class it came from and
   what the risk is — the clinician decides, and the record shows that the
   decision was made with the information in front of them.

Steps 2 and 3 are the ones that close the finding.

### 4.2 Severity and what a block means

The severity of the raised alert is the **higher** of the recorded severity
and the severity implied by the relation:

| Match | Severity | Effect |
|---|---|---|
| Direct name, ingredient, or class match | as recorded on the allergy | **block** the prescription |
| Cross-reactive class relation | `risk` from the relation, never above the recorded severity | **warning**, the clinician decides |
| Nothing matches | — | no alert |

The block is the existing mechanism: a `CRITICAL` safety alert stops the
prescription, and the "unable to verify" case — a failed check, a missing
ontology, an allergy that could not be resolved — is also `CRITICAL`. That
last part is what makes an empty ontology safe: the system refuses to
prescribe when it cannot check, rather than prescribing because it could
not check.

### 4.3 What is deliberately not done

* **No fuzzy matching.** A similarity score between "amoxicillin" and
  "penicillin" is a coin toss at the boundary, and a coin toss in an
  allergy check is a coin toss in the wrong direction.
* **No inference from the therapeutic class.** `Medication.category` says
  "antibiotic"; that is not the same class as "penicillin", and an
  antibiotic is not an allergy.
* **No blocking on `RELATED`.** A relation that is merely related is
  background, and a warning on every related class is noise that trains
  clinicians to dismiss warnings.

## 5. What has to be true before any of this is implemented

1. **An official drug classification file is available**, and the loader
   for it is written. Until it exists, the tables stay empty and the
   platform behaves as it does now, with the §4.2 rule that an
   unverifiable check is a hard stop.
2. **The existing tenant data is migrated**: each `patient_allergies` row
   is resolved against the ontology, and the unresolved ones are listed for
   review. A migration that guesses the class of an allergy is worse than
   one that leaves it unresolved.
3. **The medication catalogue is mapped to ingredients**, which is a data
   exercise over the tenant's own catalogue, not a code change.
4. **The cross-reactivity table is curated, not derived.** It is the one
   table in this design that encodes clinical judgement, and it is
   reviewed and versioned accordingly.

## 6. How this will be tested

* **The finding itself.** A patient allergic to `penicillin`, a medication
  whose generic name is `amoxicillin` and whose trade name is `Amoxil`:
  the check raises a **block**, and the prescription is refused. This test
  does not exist today and it is the reason for this document.
* **The hierarchy.** A patient allergic to `beta-lactam` and a medication
  whose ingredient is `amoxicillin`: the check raises a **block**, through
  the class walk and not through any hand-written pair.
* **Cross-reactivity is a warning, not a block.** A patient allergic to
  `penicillin` and a cephalosporin: the check raises a warning that names
  the class and the risk, and the prescription is not blocked.
* **The free-text match still works.** A patient allergic to `Amoxil` and
  a medication whose trade name is `Amoxil`: a **block**, as today.
* **An unresolved allergy blocks.** A patient with an allergy that matches
  no ingredient and no class: the check cannot clear it, so it is a hard
  stop until it is resolved.
* **An empty ontology blocks rather than passes.** With the terminology
  file absent, a prescription that needs a class check is refused with the
  "unable to verify" message, and the test asserts the refusal.
* **The negative case.** A patient with no allergies, and a medication in
  the ontology: no alert, and the prescription proceeds.

## 7. Related

* [FX and Currency Design](FX_CURRENCY_DESIGN.md) — the other finding that
  needed the fact to be in the schema before the check could be right.
