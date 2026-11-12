"""Coverage for the ``__repr__``/``to_dict`` surface of the smaller models.

Several models in this repository expose a ``__repr__`` and a ``to_dict``
that nothing ever called, so the lines that build the human-readable label
and the serialisation of a record were never executed. A model whose
``to_dict`` has never run is a model whose API contract has never been
checked: the key names and the value shapes are what the frontend and the
integrations depend on.

Each test class below is named after the module it covers.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

pytest_plugins = ['tests._isolated_tenant']


def _stamp():
    return datetime(2026, 3, 4, 5, 6, 7)


def _make_patient(db, tenant_id, first='Model', last='Patient'):
    """A patient row the FK-constrained models can point at."""
    from models.patient import Patient

    patient = Patient(
        tenant_id=tenant_id,
        first_name=first,
        last_name=last,
        phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
        gender='M',
    )
    db.session.add(patient)
    db.session.flush()
    return patient


def _make_medication(db, tenant_id, trade='ModelMed'):
    from models.medication import Medication

    medication = Medication(
        tenant_id=tenant_id,
        scientific_name='Scientific Name',
        trade_name=f'{trade}-{datetime.now(UTC).strftime("%H%M%S%f")}',
        generic_name='Generic',
        dosage_form='tablet',
        strength='500mg',
        price=Decimal('10.00'),
        category='analgesic',
        stock_quantity=10,
        is_active=True,
    )
    db.session.add(medication)
    db.session.flush()
    return medication


class TestExchangeRate:
    """models/exchange_rate.py"""

    def test_repr(self):
        from models.exchange_rate import ExchangeRate

        rate = ExchangeRate(
            from_currency='USD',
            to_currency='ILS',
            buy_rate=Decimal('3.750000'),
            sell_rate=Decimal('3.800000'),
        )
        assert repr(rate) == '<ExchangeRate USD->ILS 3.750000>'

    def test_to_dict(self, app, db, test_tenant):
        from models.exchange_rate import ExchangeRate

        rate = ExchangeRate(
            tenant_id=test_tenant.id,
            from_currency='USD',
            to_currency='ILS',
            buy_rate=Decimal('3.750000'),
            sell_rate=Decimal('3.800000'),
            effective_date=_stamp(),
            source='MANUAL',
            is_active=True,
            notes='manual rate',
        )
        db.session.add(rate)
        db.session.flush()

        data = rate.to_dict()
        assert data['from_currency'] == 'USD'
        assert data['to_currency'] == 'ILS'
        assert data['buy_rate'] == 3.75
        assert data['sell_rate'] == 3.8
        assert data['effective_date'] == '2026-03-04T05:06:07'
        assert data['source'] == 'MANUAL'
        assert data['is_active'] is True
        assert data['notes'] == 'manual rate'

    def test_currency_settings_symbol_and_name(self):
        from models.exchange_rate import CurrencySettings

        assert CurrencySettings.get_symbol('USD') == '$'
        assert CurrencySettings.get_name('USD') == 'دولار أمريكي'
        # An unknown code falls back to the code itself rather than raising.
        assert CurrencySettings.get_symbol('XXX') == 'XXX'
        assert CurrencySettings.get_name('XXX') == 'XXX'

    def test_currency_settings_get_all(self):
        from models.exchange_rate import CurrencySettings

        currencies = CurrencySettings.get_all()
        assert 'ILS' in currencies
        assert currencies['ILS']['symbol'] == '₪'


class TestDental:
    """models/dental.py"""

    def test_chart_and_tooth_to_dict(self, app, db, test_tenant):
        from models.dental import DentalChart, DentalTooth

        patient = _make_patient(db, test_tenant.id)

        chart = DentalChart(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            notes='check-up',
        )
        db.session.add(chart)
        db.session.flush()

        tooth = DentalTooth(
            tenant_id=test_tenant.id,
            chart_id=chart.id,
            fdi_number='11',
            state='caries',
            surfaces={'occlusal': 'caries'},
            notes='needs filling',
        )
        db.session.add(tooth)
        db.session.flush()

        tooth_data = tooth.to_dict()
        assert tooth_data['fdi_number'] == '11'
        assert tooth_data['state'] == 'caries'
        assert tooth_data['surfaces'] == {'occlusal': 'caries'}
        assert tooth_data['notes'] == 'needs filling'

        chart_data = chart.to_dict()
        assert chart_data['patient_id'] == patient.id
        assert chart_data['notes'] == 'check-up'
        assert len(chart_data['teeth']) == 1
        assert chart_data['teeth'][0]['fdi_number'] == '11'


class TestPatientVisitCounter:
    """models/patient_visit_counter.py"""

    def test_repr(self):
        from models.patient_visit_counter import PatientVisitCounter

        counter = PatientVisitCounter(patient_id=42, visit_count=7)
        assert repr(counter) == '<PatientVisitCounter patient=42 cnt=7>'


class TestAdvancedPermissions:
    """models/advanced_permissions.py"""

    def _role(self):
        from models.permissions import Role

        return Role(name='model-cov-role', name_ar='مدير')

    def test_module_permission_repr_and_to_dict(self, app, db, test_tenant):
        from models.advanced_permissions import ModulePermission

        perm = ModulePermission(
            tenant_id=test_tenant.id,
            role=self._role(),
            module_name='reception',
            can_view=True,
            can_create=True,
            can_edit=False,
            can_delete=False,
            can_approve=False,
            can_archive=False,
            can_force_payment=False,
            can_override_limits=False,
            can_access_reports=True,
            can_manage_users=False,
        )
        db.session.add(perm)
        db.session.flush()

        assert repr(perm) == '<ModulePermission مدير - reception>'

        data = perm.to_dict()
        assert data['module_name'] == 'reception'
        assert data['role_name'] == 'مدير'
        assert data['can_view'] is True
        assert data['can_create'] is True
        assert data['can_edit'] is False
        assert data['can_access_reports'] is True
        assert data['can_manage_users'] is False
        assert data['created_at'] is not None

    def test_department_permission_repr_and_to_dict(self, app, db, test_tenant):
        from models.advanced_permissions import DepartmentPermission

        perm = DepartmentPermission(
            tenant_id=test_tenant.id,
            role=self._role(),
            department=None,
            can_access=True,
            can_manage_patients=True,
            can_manage_visits=False,
            can_manage_appointments=False,
            can_manage_staff=False,
            can_override_department_limits=False,
            can_manage_department_settings=False,
        )
        db.session.add(perm)
        db.session.flush()

        assert repr(perm) == '<DepartmentPermission مدير - All>'

        data = perm.to_dict()
        assert data['role_name'] == 'مدير'
        assert data['department_name'] == 'جميع الأقسام'
        assert data['can_access'] is True
        assert data['can_manage_patients'] is True
        assert data['can_manage_visits'] is False


class TestRequestWorkflow:
    """models/request_workflow.py"""

    def test_reprs_and_to_dicts(self, app, db, test_tenant):
        from models.request_workflow import DepartmentWorkflow, RequestWorkflow

        workflow = RequestWorkflow(
            tenant_id=test_tenant.id,
            request_type='lab',
            request_id=11,
            department='cardiology',
            status='PENDING',
            action='requested',
        )
        db.session.add(workflow)
        db.session.flush()

        assert repr(workflow) == '<RequestWorkflow lab_11_cardiology>'
        data = workflow.to_dict()
        assert data['request_type'] == 'lab'
        assert data['request_id'] == 11
        assert data['department'] == 'cardiology'

        dept_workflow = DepartmentWorkflow(
            tenant_id=test_tenant.id,
            department_name='cardiology',
            department_name_ar='القلب',
        )
        db.session.add(dept_workflow)
        db.session.flush()

        assert repr(dept_workflow) == '<DepartmentWorkflow cardiology>'
        dept_data = dept_workflow.to_dict()
        assert dept_data['department_name'] == 'cardiology'


class TestRadiologyRequest:
    """models/radiology_request.py"""

    def test_repr_and_to_dict(self, app, db, test_tenant):
        from models.radiology_request import RadiologyRequest

        patient = _make_patient(db, test_tenant.id)

        request = RadiologyRequest(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            modality='CT',
            status='REQUESTED',
            body_part='Chest',
            request_number='RQ-001',
        )
        db.session.add(request)
        db.session.flush()

        assert repr(request) == '<RadiologyRequest #RQ-001>'

        data = request.to_dict()
        assert data['modality'] == 'CT'
        assert data['status'] == 'REQUESTED'
        assert data['body_part'] == 'Chest'
        assert data['request_number'] == 'RQ-001'


class TestLabTestCatalog:
    """models/lab_test_catalog.py"""

    def test_reprs(self):
        from models.lab_test_catalog import LabTestCatalog, LabTestPanel, LabTestPanelItem

        catalog = LabTestCatalog(code='CBC', name_ar='صورة دم كاملة')
        assert repr(catalog) == '<LabTestCatalog CBC: صورة دم كاملة>'

        panel = LabTestPanel(name_ar='لوحة أساسية')
        assert repr(panel) == '<LabTestPanel لوحة أساسية>'

        item = LabTestPanelItem(panel_id=3, test_id=9)
        assert repr(item) == '<LabTestPanelItem panel=3 test=9>'


class TestUserMfa:
    """models/user_mfa.py"""

    def test_reprs(self):
        from models.user_mfa import MFALoginAttempt, UserMFASettings

        settings = UserMFASettings(user_id=4, totp_enabled=True)
        assert repr(settings) == '<UserMFASettings user_id=4 enabled=True>'

        attempt = MFALoginAttempt(user_id=4, success=False)
        assert repr(attempt) == '<MFALoginAttempt user_id=4 success=False>'


class TestDataWarehouse:
    """models/data_warehouse.py"""

    def test_reprs(self):
        from models.data_warehouse import (
            DailyVisitSummary,
            DataWarehouseSync,
            MonthlyFinanceSummary,
        )

        sync = DataWarehouseSync(sync_name='nightly', status='SUCCESS')
        assert repr(sync) == '<DataWarehouseSync nightly SUCCESS>'

        daily = DailyVisitSummary(date=date(2026, 3, 4), total_visits=12)
        assert repr(daily) == '<DailyVisitSummary 2026-03-04 visits=12>'

        monthly = MonthlyFinanceSummary(year=2026, month=3)
        assert repr(monthly) == '<MonthlyFinanceSummary 2026-3>'


class TestBiometricAuth:
    """models/biometric_auth.py"""

    def test_reprs(self):
        from models.biometric_auth import BiometricAuthChallenge, BiometricCredential

        credential = BiometricCredential(user_id=5, device_type='fingerprint')
        assert repr(credential) == '<BiometricCredential user=5 type=fingerprint>'

        challenge = BiometricAuthChallenge(challenge_type='fingerprint')
        assert repr(challenge) == '<BiometricAuthChallenge type=fingerprint>'


class TestMedicalReport:
    """models/medical_report.py"""

    def test_repr(self):
        from models.medical_report import MedicalReport

        report = MedicalReport(title='Discharge summary')
        assert repr(report) == '<MedicalReport Discharge summary>'


class TestPatientEducation:
    """models/patient_education.py"""

    def test_reprs(self):
        from models.patient_education import (
            PatientEducationAssignment,
            PatientEducationMaterial,
        )

        material = PatientEducationMaterial(title='Diabetes guide')
        assert repr(material) == '<PatientEducationMaterial Diabetes guide>'

        assignment = PatientEducationAssignment(patient_id=2, material_id=6)
        assert repr(assignment) == '<PatientEducationAssignment patient=2 material=6>'


class TestIcdCoding:
    """models/icd_coding.py"""

    def test_reprs(self):
        from models.icd_coding import (
            CodedDiagnosis,
            CodedProcedure,
            CPTCode,
            DRGCode,
            ICD10Code,
            LOINCCode,
        )

        assert repr(ICD10Code(code='E11.9')) == '<ICD10Code E11.9>'
        assert repr(CPTCode(code='99213')) == '<CPTCode 99213>'
        assert repr(LOINCCode(code='2345-7')) == '<LOINCCode 2345-7>'
        assert repr(DRGCode(code='DGR-1')) == '<DRGCode DGR-1>'
        assert repr(CodedDiagnosis(diagnosis_type='PRIMARY')) == '<CodedDiagnosis PRIMARY>'
        assert repr(CodedProcedure(quantity=3)) == '<CodedProcedure 3x>'


class TestLabRequest:
    """models/lab_request.py"""

    def test_repr_and_to_dict(self, app, db, test_tenant):
        from models.lab_request import LabRequest

        patient = _make_patient(db, test_tenant.id)

        request = LabRequest(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            status='REQUESTED',
            request_number='LR-001',
            barcode='BC-001',
        )
        db.session.add(request)
        db.session.flush()

        assert repr(request) == '<LabRequest #LR-001>'

        data = request.to_dict()
        assert data['request_number'] == 'LR-001'
        assert data['patient_id'] == patient.id
        assert data['status'] == 'REQUESTED'
        assert data['barcode'] == 'BC-001'
        assert data['collection_time'] is None

    def test_result_repr(self):
        from models.lab_request import LabResult

        result = LabResult(test_code='WBC', value='7.2')
        assert repr(result) == '<LabResult WBC 7.2>'

        blank = LabResult(test_code='WBC')
        assert repr(blank) == '<LabResult WBC >'


class TestIotDevice:
    """models/iot_device.py"""

    def test_device_to_dict(self, app, db, test_tenant):
        from models.iot_device import IoTDevice

        device = IoTDevice(
            tenant_id=test_tenant.id,
            device_id='HR-1',
            device_type='heart_monitor',
            device_name='Monitor 1',
            manufacturer='Acme',
            model='M1',
            serial_number='SN-1',
            location='Ward A',
            status='online',
            last_seen=_stamp(),
            battery_level=88,
            is_active=True,
        )
        db.session.add(device)
        db.session.flush()

        data = device.to_dict()
        assert data['device_id'] == 'HR-1'
        assert data['device_type'] == 'heart_monitor'
        assert data['manufacturer'] == 'Acme'
        assert data['serial_number'] == 'SN-1'
        assert data['location'] == 'Ward A'
        assert data['status'] == 'online'
        assert data['last_seen'] == '2026-03-04T05:06:07'
        assert data['battery_level'] == 88
        assert data['is_active'] is True

    def test_reading_to_dict(self, app, db, test_tenant):
        from models.iot_device import IoTDevice, IoTReading

        device = IoTDevice(
            tenant_id=test_tenant.id,
            device_id='HR-2',
            device_type='heart_monitor',
            status='online',
        )
        db.session.add(device)
        db.session.flush()

        reading = IoTReading(
            tenant_id=test_tenant.id,
            device_id=device.id,
            reading_type='heart_rate',
            value=75.0,
            unit='bpm',
            recorded_at=_stamp(),
            is_critical=False,
        )
        db.session.add(reading)
        db.session.flush()

        data = reading.to_dict()
        assert data['reading_type'] == 'heart_rate'
        assert data['value'] == 75.0
        assert data['unit'] == 'bpm'
        assert data['recorded_at'] == '2026-03-04T05:06:07'
        assert data['is_critical'] is False


class TestPopulationHealth:
    """models/population_health.py"""

    def test_reprs(self):
        from models.population_health import (
            DiseaseRegistry,
            PopulationHealthIndicator,
            QualityMeasure,
        )

        assert repr(DiseaseRegistry(disease_name='Diabetes')) == '<DiseaseRegistry Diabetes>'
        assert (
            repr(PopulationHealthIndicator(indicator_name='BMI'))
            == '<PopulationHealthIndicator BMI>'
        )
        assert repr(QualityMeasure(measure_code='Q1')) == '<QualityMeasure Q1>'


class TestBackupRestore:
    """models/backup_restore.py"""

    def test_repr(self):
        from models.backup_restore import BackupRestoreLog

        log = BackupRestoreLog(operation='restore', status='SUCCESS')
        assert repr(log) == '<BackupRestoreLog restore SUCCESS>'


class TestDrugInteraction:
    """models/drug_interaction.py"""

    def test_to_dict(self, app, db, test_tenant):
        from models.drug_interaction import DrugInteraction

        medication_a = _make_medication(db, test_tenant.id, trade='DrugA')
        medication_b = _make_medication(db, test_tenant.id, trade='DrugB')

        interaction = DrugInteraction(
            tenant_id=test_tenant.id,
            medication_a_id=medication_a.id,
            medication_b_id=medication_b.id,
            severity='HIGH',
            description='increased bleeding risk',
            is_active=True,
        )
        db.session.add(interaction)
        db.session.flush()

        data = interaction.to_dict()
        assert data['medication_a_id'] == medication_a.id
        assert data['medication_b_id'] == medication_b.id
        assert data['severity'] == 'HIGH'
        assert data['description'] == 'increased bleeding risk'
        assert data['is_active'] is True


class TestEmar:
    """models/emar.py"""

    def test_status_validation_rejects_unknown_status(self):
        from models.emar import eMARAdministration

        with pytest.raises(ValueError, match='حالة إعطاء الدواء غير صالحة'):
            eMARAdministration(status='NOT_A_STATUS')

    def test_status_validation_normalises_case(self):
        from models.emar import eMARAdministration

        administration = eMARAdministration(status='given')
        assert administration.status == 'GIVEN'

    def test_is_terminal(self):
        from models.emar import eMARAdministration

        assert eMARAdministration(status='GIVEN').is_terminal is True
        assert eMARAdministration(status='NOT_GIVEN').is_terminal is True
        assert eMARAdministration(status='SCHEDULED').is_terminal is False
        assert eMARAdministration(status=None).is_terminal is False

    def test_repr(self):
        from models.emar import eMARAdministration

        assert repr(eMARAdministration(status='GIVEN')) == '<eMARAdministration GIVEN>'


class TestMedicalRecord:
    """models/medical_record.py"""

    def test_repr(self):
        from models.medical_record import MedicalRecord

        assert repr(MedicalRecord(title='Progress note')) == '<MedicalRecord Progress note>'


class TestExpense:
    """models/expense.py"""

    def test_repr(self, app, db, test_tenant):
        from models.expense import Expense

        expense = Expense(
            tenant_id=test_tenant.id,
            category='rent',
            amount=Decimal('125.50'),
        )
        db.session.add(expense)
        db.session.flush()

        assert repr(expense) == '<Expense rent 125.50>'


class TestApiKey:
    """models/api_key.py"""

    def test_to_dict_and_repr(self, app, db, test_tenant):
        from models.api_key import ApiKey

        key = ApiKey(
            tenant_id=test_tenant.id,
            name='Reporting key',
            key_prefix='abc123',
            key_hash='hashed-secret',
            scopes='read, write ,',
            is_active=True,
            rate_limit_max=100,
            rate_limit_window=60,
            expires_at=_stamp(),
            last_used_at=_stamp(),
        )
        db.session.add(key)
        db.session.flush()

        data = key.to_dict()
        assert data['name'] == 'Reporting key'
        assert data['key_prefix'] == 'abc123'
        assert data['scopes'] == ['read', 'write']
        assert data['is_active'] is True
        assert data['rate_limit'] == '100/60s'
        assert data['expires_at'] == '2026-03-04T05:06:07'
        assert data['last_used_at'] == '2026-03-04T05:06:07'
        assert data['revoked_at'] is None

        assert repr(key) == '<ApiKey abc123… (Reporting key)>'


class TestFollowUp:
    """models/follow_up.py"""

    def test_to_dict(self, app, db, test_tenant):
        from models.follow_up import FollowUpRequest

        patient = _make_patient(db, test_tenant.id)

        follow_up = FollowUpRequest(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            doctor_id=None,
            source_visit_id=None,
            appointment_id=None,
            suggested_date=date(2026, 4, 1),
            notes='review labs',
            status='PENDING',
        )
        db.session.add(follow_up)
        db.session.flush()

        data = follow_up.to_dict()
        assert data['patient_id'] == patient.id
        assert data['doctor_id'] is None
        assert data['source_visit_id'] is None
        assert data['appointment_id'] is None
        assert data['suggested_date'] == '2026-04-01'
        assert data['notes'] == 'review labs'
        assert data['status'] == 'PENDING'


class TestSsoConfig:
    """models/sso_config.py"""

    def test_reprs(self):
        from models.sso_config import SSOConfiguration, SSOUserMapping

        config = SSOConfiguration(name='Corporate LDAP', provider_type='ldap')
        assert repr(config) == '<SSOConfiguration Corporate LDAP type=ldap>'

        mapping = SSOUserMapping(user_id=7, external_id='ext-1')
        assert repr(mapping) == '<SSOUserMapping user=7 external=ext-1>'


class TestInvoice:
    """models/invoice.py"""

    def test_invoice_repr(self, app, db, test_tenant):
        from models.invoice import Invoice

        invoice = Invoice(
            tenant_id=test_tenant.id,
            invoice_number='INV-9',
            total_amount=Decimal('10.00'),
            currency='ILS',
            status='ISSUED',
        )
        db.session.add(invoice)
        db.session.flush()

        assert repr(invoice) == '<Invoice #INV-9>'

    def test_invoice_service_repr(self):
        from models.invoice import InvoiceService

        service = InvoiceService(service_code='CONS', quantity=2)
        assert repr(service) == '<InvoiceService CONS x2>'


class TestClinicalPathway:
    """models/clinical_pathway.py"""

    def test_reprs(self):
        from models.clinical_pathway import (
            ClinicalPathway,
            ClinicalPathwayStep,
            PatientCarePlan,
        )

        assert repr(ClinicalPathway(name='Diabetes')) == '<ClinicalPathway Diabetes>'
        assert repr(ClinicalPathwayStep(step_number=3)) == '<ClinicalPathwayStep 3>'
        assert repr(PatientCarePlan(status='ACTIVE')) == '<PatientCarePlan ACTIVE>'


class TestAppointmentWaitlist:
    """models/appointment_waitlist.py"""

    def test_repr(self):
        from models.appointment_waitlist import AppointmentWaitlist

        entry = AppointmentWaitlist(patient_id=8, status='WAITING')
        assert repr(entry) == '<AppointmentWaitlist patient=8 status=WAITING>'


class TestCdsAlert:
    """models/cds_alert.py"""

    def test_reprs(self):
        from models.cds_alert import CDSAlertRule, CDSFiredAlert

        assert repr(CDSAlertRule(rule_type='ALLERGY')) == '<CDSAlertRule ALLERGY>'
        assert repr(CDSFiredAlert(severity='HIGH')) == '<CDSFiredAlert HIGH>'


class TestAppointment:
    """models/appointment.py"""

    def test_repr(self):
        from models.appointment import Appointment

        appointment = Appointment(patient_id=3, starts_at=_stamp())
        assert repr(appointment) == '<Appointment patient=3 at=2026-03-04 05:06:07>'

    def test_validate_times_rejects_end_before_start(self):
        from models.appointment import Appointment

        appointment = Appointment(patient_id=3, starts_at=_stamp())
        with pytest.raises(ValueError, match='وقت النهاية يجب أن يكون بعد وقت البداية'):
            appointment.ends_at = _stamp().replace(minute=0)

    def test_validate_times_accepts_end_after_start(self):
        from models.appointment import Appointment

        appointment = Appointment(patient_id=3, starts_at=_stamp())
        appointment.ends_at = _stamp().replace(hour=6)
        assert appointment.ends_at.hour == 6


class TestMedicalDevice:
    """models/medical_device.py"""

    def test_to_dicts(self, app, db, test_tenant):
        from models.medical_device import DeviceAlarm, DeviceParameter, MedicalDevice

        device = MedicalDevice(
            tenant_id=test_tenant.id,
            device_id='VENT-1',
            device_type='ventilator',
            device_name='Ventilator 1',
            status='online',
        )
        db.session.add(device)
        db.session.flush()

        device_data = device.to_dict()
        assert device_data['device_id'] == 'VENT-1'
        assert device_data['device_type'] == 'ventilator'

        parameter = DeviceParameter(
            tenant_id=test_tenant.id,
            device_id=device.id,
            parameter_name='peak_pressure',
            value=22.5,
            unit='cmH2O',
            recorded_at=_stamp(),
        )
        db.session.add(parameter)
        db.session.flush()

        parameter_data = parameter.to_dict()
        assert parameter_data['parameter_name'] == 'peak_pressure'
        assert parameter_data['value'] == 22.5

    def test_alarm_to_dict(self, app, db, test_tenant):
        from models.medical_device import DeviceAlarm, MedicalDevice

        device = MedicalDevice(
            tenant_id=test_tenant.id,
            device_id='VENT-2',
            device_type='ventilator',
            status='online',
        )
        db.session.add(device)
        db.session.flush()

        alarm = DeviceAlarm(
            tenant_id=test_tenant.id,
            device_id=device.id,
            alarm_type='high_pressure',
            severity='critical',
            message='peak pressure above threshold',
            triggered_at=_stamp(),
            is_active=True,
        )
        db.session.add(alarm)
        db.session.flush()

        data = alarm.to_dict()
        assert data['device_id'] == device.id
        assert data['alarm_type'] == 'high_pressure'
        assert data['severity'] == 'critical'
        assert data['message'] == 'peak pressure above threshold'
        assert data['triggered_at'] == '2026-03-04T05:06:07'
        assert data['acknowledged_at'] is None
        assert data['is_active'] is True


class TestDigitalSignature:
    """models/digital_signature.py"""

    def test_reprs(self):
        from models.digital_signature import DigitalSignature, SessionLog

        signature = DigitalSignature(document_type='consent')
        assert repr(signature) == '<DigitalSignature consent>'

        log = SessionLog(session_id='abcdef1234567890')
        assert repr(log) == '<SessionLog abcdef12>'
