"""
نموذج المريض - Patient (نسخة نهائية)
"""

from datetime import UTC, date, datetime

from sqlalchemy import Index, distinct, event, func, or_, select, text
from sqlalchemy.orm import validates

from app.extensions import db
from app.shared.encrypted_type import (
    EncryptedSearchableString,
    EncryptedString,
    blind_index_value,
    normalize_for_index,
)
from app.shared.mixins import TenantMixin


class Patient(TenantMixin, db.Model):
    __tablename__ = 'patients'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)

    # Identity columns are stored with non-deterministic AES-GCM (maximum
    # confidentiality) and matched through a keyed blind index. The previous
    # `unique=True` on the ciphertext was a false guarantee: because every write
    # produced different ciphertext it never fired, so unlimited patients could
    # share one national id. Uniqueness now lives on the hash, via a partial
    # unique index on (tenant_id, national_id_hash) created by migration
    # s3_014_searchable_phi_blind_index.
    national_id = db.Column(EncryptedString(32), nullable=True, index=True)
    national_id_hash = db.Column(db.String(64), nullable=True, index=True)

    # Name and address must be searchable and sortable, so they use
    # deterministic AES-SIV. Equality is then observable to a key holder, which
    # is the accepted trade-off for a searchable PHI store; rows stay
    # tenant-scoped by RLS and identity never depends on this property.
    first_name = db.Column(EncryptedSearchableString(200), nullable=False, index=True)
    last_name = db.Column(EncryptedSearchableString(200), nullable=False, index=True)
    first_name_ar = db.Column(EncryptedSearchableString(200), nullable=True)
    last_name_ar = db.Column(EncryptedSearchableString(200), nullable=True)

    # Deterministic encryption (above) restores equality, ordering and index
    # selectivity, but it cannot restore `LIKE '%term%'`: a plaintext substring
    # has no relationship to the ciphertext, so SQL substring search over an
    # encrypted column can never match. These blind indexes are what make name
    # search actually work, and they leak nothing about the value.
    first_name_hash = db.Column(db.String(64), nullable=True, index=True)
    last_name_hash = db.Column(db.String(64), nullable=True, index=True)
    first_name_ar_hash = db.Column(db.String(64), nullable=True, index=True)
    last_name_ar_hash = db.Column(db.String(64), nullable=True, index=True)

    @property
    def full_name(self):
        """الاسم الكامل للمريض"""
        if self.first_name_ar and self.last_name_ar:
            return f'{self.first_name_ar} {self.last_name_ar}'
        return f'{self.first_name} {self.last_name}'

    def get_gender_display(self):
        g = (self.gender or '').strip().upper()
        if not g:
            return 'غير محدد'
        if g in {'M', 'MALE', 'ذكر'}:
            return 'ذكر'
        if g in {'F', 'FEMALE', 'انثى', 'أنثى'}:
            return 'أنثى'
        return 'آخر'

    phone = db.Column(EncryptedString(20), nullable=True, index=True)
    phone_hash = db.Column(db.String(64), nullable=True, index=True)
    birth_date = db.Column(db.Date, nullable=True, index=True)
    gender = db.Column(db.String(10), nullable=True)  # M/F/Other
    address = db.Column(EncryptedSearchableString(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    insurance_company_id = db.Column(
        db.Integer,
        db.ForeignKey('insurance_companies.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    insurance_member_number = db.Column(EncryptedString(60), nullable=True)
    marital_status = db.Column(db.String(20), nullable=True)
    is_pregnant = db.Column(db.Boolean, default=False)
    pregnancy_weeks = db.Column(db.Integer, nullable=True)
    last_menstruation_date = db.Column(db.Date, nullable=True)
    pregnancy_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index('idx_patient_name', 'first_name', 'last_name'),
        Index('idx_patient_name_birthdate', 'first_name', 'last_name', 'birth_date'),
        Index('idx_patient_insurance_created', 'insurance_company_id', 'created_at'),
    )

    # ------------------------------------------------------------------
    # Blind-index maintenance
    #
    # Derived columns are filled by mapper events rather than by callers, so
    # that every existing write path (reception forms, kiosk, imports, services,
    # tests) keeps the digest in sync without being touched. A digest that drifts
    # from its plaintext would silently break duplicate detection, which is
    # worse than the original bug because it fails open.
    # ------------------------------------------------------------------
    _BLIND_INDEX_FIELDS = (
        ('national_id', 'national_id_hash'),
        ('phone', 'phone_hash'),
        ('first_name', 'first_name_hash'),
        ('last_name', 'last_name_hash'),
        # Arabic name columns are the ones reception actually searches, so they
        # get digests too -- otherwise Patient.search could not find a patient
        # by the name shown on their ID card.
        ('first_name_ar', 'first_name_ar_hash'),
        ('last_name_ar', 'last_name_ar_hash'),
    )

    @classmethod
    def _sync_blind_indexes(cls, target) -> None:
        for source, digest in cls._BLIND_INDEX_FIELDS:
            setattr(target, digest, blind_index_value(getattr(target, source)))

    #: Columns that get trigram rows, mapped to the source label stored with them.
    #: phone and national_id are included because reception searches by a partial
    #: number too ("050222" for "0502222222"), and an exact blind-index match
    #: cannot answer that.
    _NGRAM_FIELDS = (
        ('first_name', 'first_name'),
        ('last_name', 'last_name'),
        ('first_name_ar', 'first_name_ar'),
        ('last_name_ar', 'last_name_ar'),
        ('phone', 'phone'),
        ('national_id', 'national_id'),
    )

    @classmethod
    def _sync_search_ngrams(cls, connection, target) -> None:
        """Rebuild this patient's trigram rows from the current name columns.

        Deliberately done with plain SQL on the flush ``connection`` rather than
        by mutating an ORM collection: collection changes made inside a
        ``before_*`` mapper event are not applied reliably, and an ORM
        relationship here would also add a SELECT to every patient load.

        Each source column is replaced wholesale. Deleting first is what makes a
        rename drop the trigrams of the old name -- a stale trigram would keep
        matching a name the patient no longer has.
        """
        from app.shared import search_index

        if not search_index.is_available():
            return
        for column, source in cls._NGRAM_FIELDS:
            digests = search_index.digests_for(normalize_for_index(getattr(target, column, None)))
            connection.execute(
                text(
                    'DELETE FROM patient_search_ngrams WHERE patient_id = :pid AND source = :source'
                ),
                {'pid': target.id, 'source': source},
            )
            if digests:
                connection.execute(
                    text(
                        'INSERT INTO patient_search_ngrams '
                        '(patient_id, source, digest, tenant_id) '
                        'VALUES (:pid, :source, :digest, :tid)'
                    ),
                    [
                        {'pid': target.id, 'source': source, 'digest': d, 'tid': target.tenant_id}
                        for d in digests
                    ],
                )

    @classmethod
    def _search_by_ngrams(cls, term, *, tenant_id=None, limit=50):
        """Substring search through the blind trigram index.

        Two phases on purpose. The digest query only narrows the field down to
        rows that plausibly contain the term; because the trigrams of a term are
        not necessarily contiguous in the stored value, the candidates are then
        decrypted and re-checked for a real substring match. Skipping that
        second phase would return false positives, which for a patient lookup is
        worse than returning nothing.
        """
        from app.shared import search_index

        normalised = normalize_for_index(term)
        if not search_index.is_indexable(normalised):
            return []
        digests = search_index.term_digests(normalised)
        if not digests:
            return []

        ngram = PatientSearchNgram
        matched_patient_ids = (
            select(ngram.patient_id)
            .where(ngram.digest.in_(digests))
            .group_by(ngram.patient_id)
            .having(func.count(distinct(ngram.digest)) == len(digests))
        )
        stmt = select(cls).where(cls.id.in_(matched_patient_ids))
        if tenant_id is not None:
            stmt = stmt.where(cls.tenant_id == tenant_id)
        candidates = db.session.execute(
            stmt.order_by(cls.id).limit(search_index.DEFAULT_CANDIDATE_LIMIT)
        ).scalars()

        matches = []
        for patient in candidates:
            for column, _source in cls._NGRAM_FIELDS:
                value = getattr(patient, column, None)
                if value and normalised in normalize_for_index(value):
                    matches.append(patient)
                    break
            if len(matches) >= limit:
                break
        return matches[:limit]

    @classmethod
    def _identity_lookup(cls, column, digest_column, value, *, tenant_id=None):
        """Resolve *value* to a patient, encrypted or not.

        Under encryption the ciphertext cannot be compared, so the lookup goes
        through the blind index. Without a key the column genuinely holds
        plaintext, and the digest is NULL, so a blind-index-only lookup would
        silently match nothing -- which would quietly turn duplicate detection
        off in development and CI. That fallback is why the unencrypted path
        still rejects duplicates.
        """
        from services.field_encryption_service import FieldEncryptionService

        digest = blind_index_value(value)
        if digest:
            stmt = select(cls).where(digest_column == digest)
        elif not FieldEncryptionService.is_active():
            stmt = select(cls).where(column == value)
        else:
            # Encrypted, but nothing indexable to search on.
            return None
        if tenant_id is not None:
            stmt = stmt.where(cls.tenant_id == tenant_id)
        return db.session.execute(stmt.limit(1)).scalars().first()

    @classmethod
    def find_by_national_id(cls, national_id, *, tenant_id=None):
        """Exact lookup by national id, through the blind index when encrypted."""
        return cls._identity_lookup(
            cls.national_id, cls.national_id_hash, national_id, tenant_id=tenant_id
        )

    @classmethod
    def find_by_phone(cls, phone, *, tenant_id=None):
        """Exact lookup by phone, through the blind index when encrypted."""
        return cls._identity_lookup(cls.phone, cls.phone_hash, phone, tenant_id=tenant_id)

    @classmethod
    def search(cls, term, *, tenant_id=None, limit=50):
        """Search patients by name or identity, encrypted or not.

        Three strategies, in order of precision:

        1. Unencrypted database -> a substring ``ILIKE``, exactly as before any
           of this existed.
        2. Exact match on a whole normalised field, through the blind index.
           Handles multi-word terms as "first last" and folds case, Arabic-Indic
           digits, Unicode form and separators.
        3. Substring match, through the blind trigram index
           (:meth:`_search_by_ngrams`). This is what actually replaces the
           ``ILIKE '%term%'`` queries that silently returned nothing on an
           encrypted column.

        Results are de-duplicated, so a patient matching by more than one
        strategy is still listed once.
        """
        from app.shared import search_index
        from services.field_encryption_service import FieldEncryptionService

        text = (term or '').strip()
        if not text:
            return []
        if not FieldEncryptionService.is_active():
            like = f'%{text}%'
            stmt = select(cls).where(
                or_(
                    cls.first_name.ilike(like),
                    cls.last_name.ilike(like),
                    cls.first_name_ar.ilike(like),
                    cls.last_name_ar.ilike(like),
                    cls.phone.ilike(like),
                    cls.national_id.ilike(like),
                )
            )
            if tenant_id is not None:
                stmt = stmt.where(cls.tenant_id == tenant_id)
            return list(db.session.execute(stmt.order_by(cls.id).limit(limit)).scalars().all())

        found: dict[int, object] = {}
        for patient in cls._search_exact(text, tenant_id=tenant_id, limit=limit):
            found[patient.id] = patient
        if search_index.is_indexable(normalize_for_index(text)):
            for patient in cls._search_by_ngrams(text, tenant_id=tenant_id, limit=limit):
                found.setdefault(patient.id, patient)
        return sorted(found.values(), key=lambda p: p.id)[:limit]

    @classmethod
    def _search_exact(cls, term, *, tenant_id=None, limit=50):
        """Whole-field match on the normalised name columns, via blind index."""
        parts = [p for p in term.split() if p]
        first_cols = (cls.first_name_hash, cls.first_name_ar_hash)
        last_cols = (cls.last_name_hash, cls.last_name_ar_hash)
        stmt = None
        if len(parts) >= 2:
            first_digest = blind_index_value(parts[0])
            last_digest = blind_index_value(parts[-1])
            if first_digest and last_digest:
                stmt = select(cls).where(
                    or_(*(c == first_digest for c in first_cols)),
                    or_(*(c == last_digest for c in last_cols)),
                )
        else:
            digest = blind_index_value(parts[0])
            if digest:
                stmt = select(cls).where(or_(*(c == digest for c in first_cols + last_cols)))
        if stmt is None:
            return []
        if tenant_id is not None:
            stmt = stmt.where(cls.tenant_id == tenant_id)
        stmt = stmt.order_by(cls.id).limit(limit)
        return list(db.session.execute(stmt).scalars().all())

    visits = db.relationship(
        'Visit',
        back_populates='patient',
        cascade='all, delete-orphan',
        passive_deletes=True,
        lazy='selectin',
    )

    appointments = db.relationship(
        'Appointment',
        back_populates='patient',
        cascade='all, delete-orphan',
        passive_deletes=True,
        lazy='selectin',
    )

    insurance_company = db.relationship(
        'InsuranceCompany', foreign_keys=[insurance_company_id], lazy='selectin'
    )

    lab_results = db.relationship(
        'LabResult', back_populates='patient', lazy='selectin', passive_deletes=True
    )
    radiology_results = db.relationship(
        'RadiologyResult', back_populates='patient', lazy='selectin', passive_deletes=True
    )

    prescriptions = db.relationship(
        'Prescription', back_populates='patient', lazy='selectin', passive_deletes=True
    )
    medical_records = db.relationship('MedicalRecord', back_populates='patient', lazy='selectin')
    patient_satisfaction_surveys = db.relationship(
        'PatientSatisfactionSurvey', back_populates='patient', lazy='selectin'
    )

    ai_recommendations = db.relationship('AIRecommendation', back_populates='patient')
    patient_insights = db.relationship('PatientInsight', back_populates='patient')
    model_predictions = db.relationship('ModelPrediction', back_populates='patient')
    admissions = db.relationship('Admission', back_populates='patient')
    bed_transfers = db.relationship('BedTransfer', back_populates='patient')
    cds_alerts = db.relationship('CDSFiredAlert', back_populates='patient')
    care_plans = db.relationship('PatientCarePlan', back_populates='patient')
    dicom_studies = db.relationship('DICOMStudy', back_populates='patient')
    emar_administrations = db.relationship('eMARAdministration', back_populates='patient')
    emergency_cases = db.relationship('EmergencyCase', back_populates='patient')
    fhir_patient = db.relationship('FHIRPatient', back_populates='patient')
    coded_diagnoses = db.relationship('CodedDiagnosis', back_populates='patient')
    coded_procedures = db.relationship('CodedProcedure', back_populates='patient')
    pharmacy_sales = db.relationship('PharmacySale', back_populates='patient')
    medication_reconciliations = db.relationship(
        'MedicationReconciliation', back_populates='patient'
    )
    vital_signs = db.relationship('VitalSigns', back_populates='patient')
    online_bookings = db.relationship('OnlineBooking', back_populates='patient')
    surgeries = db.relationship('SurgerySchedule', back_populates='patient')
    allergies = db.relationship('PatientAllergy', back_populates='patient')
    disease_registries = db.relationship('DiseaseRegistry', back_populates='patient')
    problems = db.relationship('PatientProblem', back_populates='patient')
    allergy_intolerances = db.relationship('AllergyIntolerance', back_populates='patient')
    queue_items = db.relationship('QueueManagement', back_populates='patient')
    referrals = db.relationship('Referral', back_populates='patient')
    immunizations = db.relationship('Immunization', back_populates='patient')
    whatsapp_messages = db.relationship('WhatsAppMessage', back_populates='patient')
    workflows = db.relationship('PatientWorkflow', back_populates='patient')
    workflow_queue_items = db.relationship('WorkflowQueue', back_populates='patient')

    @property
    def visit_count(self):
        try:
            from models.patient_visit_counter import PatientVisitCounter

            pvc = (
                db.session.execute(select(PatientVisitCounter).filter_by(patient_id=self.id))
                .scalars()
                .first()
            )
            if pvc:
                return int(pvc.visit_count or 0)
            from models.visit import Visit

            return db.session.execute(
                select(func.count()).select_from(Visit).filter_by(patient_id=self.id)
            ).scalar()
        except Exception:
            from models.visit import Visit

            return db.session.execute(
                select(func.count()).select_from(Visit).filter_by(patient_id=self.id)
            ).scalar()

    def __repr__(self) -> str:
        return f'<Patient {self.first_name} {self.last_name}>'

    @property
    def age(self):
        try:
            if not self.birth_date:
                return None
            today = date.today()
            years = today.year - self.birth_date.year
            if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
                years -= 1
            return years
        except Exception:
            return None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'phone': self.phone,
            'gender': self.gender,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    @validates('phone')
    def validate_phone(self, key, value):
        if value is not None:
            cleaned = ''.join(c for c in value if c.isdigit() or c in '+-() ')
            if len(cleaned) < 7:
                raise ValueError(f'رقم الهاتف قصير جداً: {value}')
            if len(cleaned) > 20:
                raise ValueError(f'رقم الهاتف طويل جداً: {value}')
            digits_only = ''.join(c for c in cleaned if c.isdigit())
            if len(digits_only) < 7:
                raise ValueError(f'رقم الهاتف قصير جداً: {value}')
            return cleaned
        return value


@event.listens_for(Patient, 'before_insert', propagate=True)
@event.listens_for(Patient, 'before_update', propagate=True)
def _patient_sync_blind_index(mapper, connection, target) -> None:
    """Keep national_id_hash / phone_hash aligned with their plaintext columns.

    Runs on every INSERT and UPDATE regardless of which code path issued it.
    A stale digest would make duplicate detection fail open, so the digests are
    always recomputed from the current plaintext rather than patched
    conditionally.
    """
    Patient._sync_blind_indexes(target)


@event.listens_for(Patient, 'after_insert', propagate=True)
@event.listens_for(Patient, 'after_update', propagate=True)
def _patient_sync_search_ngrams(mapper, connection, target) -> None:
    """Rebuild the blind trigram rows after the patient row itself is written.

    ``after_*`` rather than ``before_*``: the rows need ``patients.id``, and a
    relationship cannot be mutated during the flush execution stage. Keeping
    this out of ``before_flush`` also means a patient whose columns did not
    change does not rewrite its index.
    """
    Patient._sync_search_ngrams(connection, target)


class PatientSearchNgram(TenantMixin, db.Model):
    """One row per distinct trigram of a patient name, as a keyed digest.

    This is the index that makes substring search possible over encrypted
    columns. See :mod:`app.shared.search_index` for the design and the
    security trade-off. The plaintext trigram is never stored â€” only its HMAC â€”
    so the table is safe to query directly and safe to index.
    """

    __tablename__ = 'patient_search_ngrams'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(
        db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True
    )
    #: Which column the trigram came from, so the exact re-check knows where to
    #: look and a rename only rewrites one column's rows.
    source = db.Column(db.String(32), nullable=False)
    digest = db.Column(db.String(64), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            'tenant_id',
            'patient_id',
            'source',
            'digest',
            name='uq_patient_ngram',
        ),
        db.Index('ix_patient_ngram_lookup', 'tenant_id', 'digest'),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f'<PatientSearchNgram patient={self.patient_id} source={self.source}>'


class PatientAllergy(TenantMixin, db.Model):
    __tablename__ = 'patient_allergies'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(
        db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True
    )
    allergen = db.Column(db.String(200), nullable=False, index=True)
    severity = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    patient = db.relationship('Patient', back_populates='allergies')

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'allergen': self.allergen,
            'severity': self.severity,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
