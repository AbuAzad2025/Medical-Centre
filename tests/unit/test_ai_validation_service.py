"""Behavioural tests for services.ai_validation_service (validators + system logic)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from services.ai_validation_service import AIValidationService

V = AIValidationService


class TestValidateUserDataBranches:
    def test_valid_all_fields(self):
        ok, errors, warnings = V.validate_user_data(
            {'email': 'a@example.com', 'password': 'S3cure!pass', 'phone': '0501234567'}
        )
        assert (ok, errors, warnings) == (True, [], [])

    def test_email_unusual_tld_warns(self):
        ok, errors, warnings = V.validate_user_data({'email': 'a@example.co.uk'})
        assert ok and not errors
        assert warnings

    def test_password_all_alpha_warns(self):
        ok, _errors, warnings = V.validate_user_data({'password': 'abcdefgh'})
        assert ok
        assert warnings

    def test_phone_too_long_warns(self):
        ok, _errors, warnings = V.validate_user_data({'phone': '1' * 20})
        assert ok
        assert warnings


class TestValidatePatientDataBranches:
    def test_age_negative(self):
        ok, errors, _ = V.validate_patient_data({'age': -1})
        assert not ok and errors

    def test_age_over_150(self):
        ok, errors, _ = V.validate_patient_data({'age': 151})
        assert not ok and errors

    def test_age_over_120_warns(self):
        ok, errors, warnings = V.validate_patient_data({'age': 130})
        assert ok and not errors
        assert warnings

    def test_age_under_1_warns(self):
        ok, _errors, warnings = V.validate_patient_data({'age': 0.5})
        assert ok
        assert warnings

    def test_future_birth_date(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        ok, errors, _ = V.validate_patient_data({'birth_date': future})
        assert not ok and errors

    def test_birth_date_age_over_150(self):
        ok, errors, _ = V.validate_patient_data({'birth_date': '1800-01-01'})
        assert not ok and errors

    def test_birth_date_invalid_format(self):
        ok, errors, _ = V.validate_patient_data({'birth_date': 'yesterday'})
        assert not ok and errors

    def test_gender_invalid(self):
        ok, errors, _ = V.validate_patient_data({'gender': 'alien'})
        assert not ok and errors

    def test_gender_valid_variants(self):
        for g in ('male', 'Female', 'ذكر', 'أنثى', 'm', 'F'):
            ok, _errors, _ = V.validate_patient_data({'gender': g})
            assert ok, g

    def test_national_id_non_digits(self):
        ok, errors, _ = V.validate_patient_data({'national_id': 'ABC123456'})
        assert not ok and errors

    def test_national_id_wrong_length_warns(self):
        ok, _errors, warnings = V.validate_patient_data({'national_id': '12345'})
        assert ok
        assert warnings


class TestValidateVisitDataBranches:
    def test_visit_far_future(self):
        future = (date.today() + timedelta(days=400)).isoformat()
        ok, errors, _ = V.validate_visit_data({'visit_date': future})
        assert not ok and errors

    def test_visit_old_warns(self):
        old = (date.today() - timedelta(days=400)).isoformat()
        ok, _errors, warnings = V.validate_visit_data({'visit_date': old})
        assert ok
        assert warnings

    def test_visit_date_invalid(self):
        ok, errors, _ = V.validate_visit_data({'visit_date': 'soon'})
        assert not ok and errors

    def test_symptoms_short_and_long(self):
        ok, _errors, warnings = V.validate_visit_data({'symptoms': 'hi'})
        assert ok and warnings
        _ok, _errors, warnings = V.validate_visit_data({'symptoms': 'x' * 5001})
        assert warnings

    def test_diagnosis_short_warns(self):
        ok, _errors, warnings = V.validate_visit_data({'diagnosis': 'ab'})
        assert ok and warnings

    def test_blood_pressure_normal(self):
        ok, errors, warnings = V.validate_visit_data({'blood_pressure': '120/80'})
        assert ok and not errors and not warnings

    def test_blood_pressure_systolic_high(self):
        ok, errors, _ = V.validate_visit_data({'blood_pressure': '300/80'})
        assert not ok and errors

    def test_blood_pressure_systolic_out_of_comfort(self):
        ok, errors, warnings = V.validate_visit_data({'blood_pressure': '200/80'})
        assert ok and not errors
        assert warnings

    def test_blood_pressure_diastolic_high(self):
        ok, errors, _ = V.validate_visit_data({'blood_pressure': '120/160'})
        assert not ok and errors

    def test_blood_pressure_diastolic_out_of_comfort(self):
        ok, errors, warnings = V.validate_visit_data({'blood_pressure': '150/120'})
        assert ok and not errors
        assert warnings

    def test_blood_pressure_systolic_not_greater(self):
        ok, errors, _ = V.validate_visit_data({'blood_pressure': '80/100'})
        assert not ok and any('غير منطقي' in e for e in errors)

    def test_blood_pressure_garbage(self):
        ok, errors, _ = V.validate_visit_data({'blood_pressure': 'high/low'})
        assert not ok and errors

    def test_temperature_normal_and_ranges(self):
        ok, errors, warnings = V.validate_visit_data({'temperature': 37.0})
        assert ok and not errors and not warnings
        # 43 C is beyond the comfort range -> warning (not an error)
        ok, errors, warnings = V.validate_visit_data({'temperature': 43.0})
        assert ok and not errors
        assert warnings
        # 50 C is incompatible with life -> error
        ok, errors, _ = V.validate_visit_data({'temperature': 50.0})
        assert not ok and errors

    def test_temperature_invalid(self):
        ok, errors, _ = V.validate_visit_data({'temperature': 'hot'})
        assert not ok and errors

    def test_heart_rate_ranges(self):
        ok, errors, _ = V.validate_visit_data({'heart_rate': 260})
        assert not ok and errors
        _ok, errors, warnings = V.validate_visit_data({'heart_rate': 45})
        assert not errors and warnings
        _ok, errors, _ = V.validate_visit_data({'heart_rate': 160})
        assert not errors

    def test_heart_rate_invalid(self):
        ok, errors, _ = V.validate_visit_data({'heart_rate': 'fast'})
        assert not ok and errors

    def test_weight_ranges(self):
        ok, errors, _ = V.validate_visit_data({'weight': 0.2})
        assert not ok and errors
        _ok, errors, warnings = V.validate_visit_data({'weight': 1.5})
        assert not errors and warnings
        ok, _errors, warnings = V.validate_visit_data({'weight': 400})
        assert not ok or warnings

    def test_weight_invalid(self):
        ok, errors, _ = V.validate_visit_data({'weight': 'heavy'})
        assert not ok and errors


class TestValidateMedicationDataBranches:
    def test_dosage_short_warns(self):
        ok, _errors, warnings = V.validate_medication_data({'dosage': 'x'})
        assert ok
        assert warnings

    def test_frequency_invalid(self):
        ok, errors, _ = V.validate_medication_data({'frequency': 0})
        assert not ok and errors

    def test_frequency_high_warns(self):
        ok, _errors, warnings = V.validate_medication_data({'frequency': 11})
        assert ok
        assert warnings

    def test_frequency_non_numeric_passes_silently(self):
        ok, errors, _warnings = V.validate_medication_data({'frequency': '3 times daily'})
        assert ok and not errors

    def test_duration_invalid(self):
        ok, errors, _ = V.validate_medication_data({'duration': 0})
        assert not ok and errors

    def test_duration_long_warns(self):
        ok, _errors, warnings = V.validate_medication_data({'duration': 400})
        assert ok
        assert warnings

    def test_duration_non_numeric_passes(self):
        ok, errors, _warnings = V.validate_medication_data({'duration': 'a week'})
        assert ok and not errors

    def test_price_negative(self):
        ok, errors, _ = V.validate_medication_data({'price': -1})
        assert not ok and errors

    def test_price_high_warns(self):
        ok, _errors, warnings = V.validate_medication_data({'price': 99999})
        assert ok
        assert warnings

    def test_price_non_numeric(self):
        ok, errors, _ = V.validate_medication_data({'price': 'free'})
        assert not ok and errors


class TestValidateFinancialDataBranches:
    def test_amount_negative(self):
        ok, errors, _ = V.validate_financial_data({'amount': -5})
        assert not ok and errors

    def test_amount_large_warns(self):
        ok, _errors, warnings = V.validate_financial_data({'amount': 500000})
        assert ok
        assert warnings

    def test_amount_zero_warns(self):
        ok, _errors, warnings = V.validate_financial_data({'amount': 0})
        assert ok
        assert warnings

    def test_amount_non_numeric(self):
        ok, errors, _ = V.validate_financial_data({'amount': 'lots'})
        assert not ok and errors

    def test_discount_negative(self):
        ok, errors, _ = V.validate_financial_data({'discount': -1})
        assert not ok and errors

    def test_discount_over_100(self):
        ok, errors, _ = V.validate_financial_data({'discount': 101})
        assert not ok and errors

    def test_discount_large_warns(self):
        ok, _errors, warnings = V.validate_financial_data({'discount': 75})
        assert ok
        assert warnings

    def test_discount_non_numeric(self):
        ok, errors, _ = V.validate_financial_data({'discount': 'half'})
        assert not ok and errors

    def test_paid_far_exceeds_total_warns(self):
        ok, errors, warnings = V.validate_financial_data({'paid_amount': 200, 'total_amount': 100})
        assert ok and not errors
        assert warnings

    def test_paid_non_numeric_ignored(self):
        ok, errors, _warnings = V.validate_financial_data(
            {'paid_amount': 'foo', 'total_amount': 'bar'}
        )
        assert ok and not errors


class TestValidateSystemLogic:
    def test_create_appointment_missing_doctor(self, app, test_tenant, rollback_db):
        ok, errors, _ = V.validate_system_logic(
            'create_appointment',
            {'doctor_id': 999999, 'appointment_time': '2030-01-01T10:00:00'},
            None,
        )
        assert not ok and any('الطبيب' in e for e in errors)

    def test_create_appointment_valid(self, app, test_tenant, rollback_db, db):
        from models.user import User

        doctor = User(
            username=f'vall_doc_{datetime.now(UTC).strftime("%H%M%S%f")}',
            email=f'vall_doc_{datetime.now(UTC).strftime("%H%M%S%f")}@test.local',
            full_name='Val Doc',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        doctor.set_password('test123')
        db.session.add(doctor)
        db.session.commit()
        ok, errors, _ = V.validate_system_logic(
            'create_appointment',
            {'doctor_id': doctor.id, 'appointment_time': '2030-01-01T10:00:00'},
            None,
        )
        assert ok, errors

    def test_create_appointment_detects_conflict(self, app, test_tenant, rollback_db, db):
        from models.patient import Patient
        from models.user import User
        from models.visit import Visit

        suffix = datetime.now(UTC).strftime('%H%M%S%f')
        doctor = User(
            username=f'vall_cdoc_{suffix}',
            email=f'vall_cdoc_{suffix}@test.local',
            full_name='Conflict Doc',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        doctor.set_password('test123')
        patient = Patient(
            tenant_id=test_tenant.id,
            first_name='ConflictPatient',
            last_name='Test',
            phone='0500000099',
        )
        db.session.add_all([doctor, patient])
        db.session.flush()
        starts = datetime(2030, 1, 1, 10, 0)
        db.session.add(
            Visit(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                doctor_id=doctor.id,
                visit_time=starts,
                status='WAITING',
            )
        )
        db.session.commit()

        ok, errors, _ = V.validate_system_logic(
            'create_appointment',
            {'doctor_id': doctor.id, 'appointment_time': starts.isoformat()},
            None,
        )
        assert not ok and any('تعارض' in e or 'موعد آخر' in e for e in errors)

    def test_create_appointment_tolerates_bad_timestamp(self, app, test_tenant, rollback_db, db):
        from models.user import User

        suffix = datetime.now(UTC).strftime('%H%M%S%f')
        doctor = User(
            username=f'vall_bad_{suffix}',
            email=f'vall_bad_{suffix}@test.local',
            full_name='Bad Time Doc',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        doctor.set_password('test123')
        db.session.add(doctor)
        db.session.commit()
        # A garbage timestamp must not crash the validator
        ok, errors, _ = V.validate_system_logic(
            'create_appointment',
            {'doctor_id': doctor.id, 'appointment_time': 'whenever'},
            None,
        )
        assert ok and not errors

    def test_create_visit_missing_patient(self, app, test_tenant, rollback_db):
        ok, errors, _ = V.validate_system_logic('create_visit', {'patient_id': 99999999}, None)
        assert not ok and any('المريض' in e for e in errors)

    def test_delete_user_self(self, app, test_tenant, rollback_db):
        ok, errors, _ = V.validate_system_logic(
            'delete_user', {'user_id': 7, 'current_user_id': 7}, None
        )
        assert not ok and errors

    def test_delete_patient_with_visits_warns(self, app, test_tenant, rollback_db, db):
        from models.patient import Patient
        from models.visit import Visit

        patient = Patient(
            tenant_id=test_tenant.id,
            first_name='LogicPatient',
            last_name='Test',
            phone='0500000071',
        )
        db.session.add(patient)
        db.session.flush()
        db.session.add(
            Visit(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                status='COMPLETED',
                visit_time=datetime(2030, 5, 1, 9, 0),
            )
        )
        db.session.commit()
        ok, _errors, warnings = V.validate_system_logic(
            'delete_patient', {'patient_id': patient.id}, None
        )
        assert ok
        assert any('زيارة' in w or 'سابقة' in w for w in warnings)


class TestFormatValidationMessage:
    def test_errors_block(self):
        msg = V.format_validation_message(['e1', 'e2'], [])
        assert 'e1' in msg and 'e2' in msg
        assert '❌' in msg or 'خطأ' in msg

    def test_warnings_block(self):
        msg = V.format_validation_message([], ['w1'])
        assert 'w1' in msg

    def test_both_blocks_and_save_message(self):
        msg = V.format_validation_message(['boom'], ['careful'])
        assert 'boom' in msg and 'careful' in msg

    def test_clean_message(self):
        msg = V.format_validation_message([], [])
        assert msg

    def test_only_errors_means_cannot_save(self):
        msg = V.format_validation_message(['x'], [])
        assert 'لا يمكن' in msg or 'أخطاء' in msg

    def test_only_warnings_means_review_message(self):
        msg = V.format_validation_message([], ['x'])
        assert 'التحذيرات' in msg or 'تراجع' in msg
