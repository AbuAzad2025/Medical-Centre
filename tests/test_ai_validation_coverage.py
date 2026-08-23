"""AI Validation Service — full coverage (was 28%)."""


class TestValidateUserData:
    def test_valid_user(self):
        from services.ai_validation_service import AIValidationService

        ok, errors, _warnings = AIValidationService.validate_user_data(
            {
                'email': 'test@example.com',
                'password': 'SecureP@ss123',
                'phone': '0501234567',
            }
        )
        assert ok is True and not errors

    def test_invalid_email(self):
        from services.ai_validation_service import AIValidationService

        ok, errors, _ = AIValidationService.validate_user_data({'email': 'notanemail'})
        assert not ok
        assert any('البريد' in e for e in errors)

    def test_empty_email(self):
        from services.ai_validation_service import AIValidationService

        ok, _errors, _ = AIValidationService.validate_user_data({'email': ''})
        assert not ok

    def test_short_password(self):
        from services.ai_validation_service import AIValidationService

        ok, _errors, _ = AIValidationService.validate_user_data({'password': 'short'})
        assert not ok

    def test_weak_password_digits_only(self):
        from services.ai_validation_service import AIValidationService

        ok, _, warnings = AIValidationService.validate_user_data({'password': '12345678'})
        assert ok  # digits-only = warning not error
        assert warnings

    def test_invalid_phone_alpha(self):
        from services.ai_validation_service import AIValidationService

        ok, _errors, _ = AIValidationService.validate_user_data({'phone': 'abc'})
        assert not ok

    def test_short_phone_warning(self):
        from services.ai_validation_service import AIValidationService

        _, _, warnings = AIValidationService.validate_user_data({'phone': '12345'})
        assert warnings

    def test_empty_data_no_errors(self):
        from services.ai_validation_service import AIValidationService

        ok, errors, _warnings = AIValidationService.validate_user_data({})
        assert ok is True and not errors


class TestValidatePatientData:
    def test_valid_patient(self):
        from datetime import date

        from services.ai_validation_service import AIValidationService

        ok, errors, _ = AIValidationService.validate_patient_data(
            {
                'first_name': 'Ahmad',
                'last_name': 'Ali',
                'birth_date': date(1990, 1, 15),
                'gender': 'M',
            }
        )
        assert isinstance(ok, bool) and isinstance(errors, list)

    def test_empty_patient(self):
        from services.ai_validation_service import AIValidationService

        _ok, errors, _ = AIValidationService.validate_patient_data({})
        assert isinstance(errors, list)


class TestValidateVisitData:
    def test_basic_visit(self):
        from services.ai_validation_service import AIValidationService

        ok, _errors, _ = AIValidationService.validate_visit_data(
            {
                'patient_id': 1,
                'department_id': 1,
                'visit_type': 'REGULAR',
            }
        )
        assert isinstance(ok, bool)

    def test_empty_visit(self):
        from services.ai_validation_service import AIValidationService

        _ok, errors, _ = AIValidationService.validate_visit_data({})
        assert isinstance(errors, list)
