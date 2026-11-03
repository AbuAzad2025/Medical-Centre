"""Tests for services.ai_validator module - 100% coverage target."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.ai_validator import AIValidator


def _make_scalar_side_effect(values):
    """Create a side_effect for db.session.execute that returns scalars in sequence."""
    mock_results = []
    for v in values:
        m = MagicMock()
        m.scalar.return_value = v
        mock_results.append(m)
    return mock_results


class TestAIValidatorValidateSystemData:
    """Tests for AIValidator.validate_system_data."""

    def test_empty_system(self):
        """Test validate_system_data with no users."""
        # 13 queries: total_users=0, active_users=0, total_doctors=0,
        # doctors_without_dept=0, total_departments=0, active_departments=0,
        # total_patients=0, total_visits=0, old_active_visits=0,
        # visits_without_doctor=0, visits_without_patient=0,
        # patients_with_future_birth=0, patients_too_old=0
        values = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert result['valid'] is False
        assert len(result['errors']) >= 1
        assert 'لا يوجد مستخدمين' in result['errors'][0]

    def test_all_inactive_users(self):
        """Test all users inactive warning."""
        values = [5, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('غير نشطين' in w for w in result['warnings'])

    def test_high_inactive_rate(self):
        """Test high inactive rate warning."""
        values = [10, 2, 1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('نسبة المستخدمين' in w for w in result['warnings'])

    def test_no_doctors(self):
        """Test no doctors warning."""
        values = [5, 5, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('لا يوجد أطباء' in w for w in result['warnings'])

    def test_doctors_without_dept(self):
        """Test doctors without department warning."""
        values = [5, 5, 2, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('طبيب بدون قسم' in w for w in result['warnings'])

    def test_no_departments(self):
        """Test no departments warning."""
        values = [5, 5, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('لا يوجد أقسام' in w for w in result['warnings'])

    def test_all_departments_inactive(self):
        """Test all departments inactive error."""
        values = [5, 5, 1, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('جميع الأقسام غير نشطة' in e for e in result['errors'])

    def test_patients_no_visits(self):
        """Test patients but no visits warning."""
        values = [5, 5, 1, 0, 1, 1, 5, 0, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('مرضى ولكن لا توجد زيارات' in w for w in result['warnings'])

    def test_old_active_visits(self):
        """Test old active visits warning."""
        values = [5, 5, 1, 0, 1, 1, 0, 0, 3, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('زيارة نشطة منذ' in w for w in result['warnings'])

    def test_visits_without_doctor(self):
        """Test visits without doctor error."""
        values = [5, 5, 1, 0, 1, 1, 0, 0, 0, 2, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('زيارة بدون طبيب' in e for e in result['errors'])

    def test_visits_without_patient(self):
        """Test visits without patient error."""
        values = [5, 5, 1, 0, 1, 1, 0, 0, 0, 0, 1, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('زيارة بدون مريض' in e for e in result['errors'])

    def test_future_birth_dates(self):
        """Test future birth dates error."""
        values = [5, 5, 1, 0, 1, 1, 0, 0, 0, 0, 0, 2, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('تاريخ ميلاد في المستقبل' in e for e in result['errors'])

    def test_very_old_patients(self):
        """Test very old patients warning."""
        values = [5, 5, 1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 2]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert any('عمر أكثر من 150' in w for w in result['warnings'])

    def test_healthy_system(self):
        """Test healthy system returns valid."""
        values = [5, 5, 1, 0, 1, 1, 5, 5, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.validate_system_data()
        assert result['valid'] is True
        assert result['errors'] == []
        assert result['warnings'] == []

    def test_exception_handling(self):
        """Test exception handling."""
        with patch('services.ai_validator.db.session.execute', side_effect=Exception('DB error')):
            result = AIValidator.validate_system_data()
        assert result['valid'] is False
        assert any('خطأ في التحقق' in e for e in result['errors'])


class TestAIValidatorValidateBeforeAction:
    """Tests for AIValidator.validate_before_action."""

    def test_create_user_missing_username(self):
        result = AIValidator.validate_before_action(
            'create_user', {'email': 'a@b.com', 'password': '123456'}
        )
        assert result['valid'] is False
        assert any('اسم المستخدم' in i for i in result['issues'])

    def test_create_user_missing_email(self):
        result = AIValidator.validate_before_action(
            'create_user', {'username': 'user', 'password': '123456'}
        )
        assert result['valid'] is False
        assert any('البريد الإلكتروني' in i for i in result['issues'])

    def test_create_user_short_password(self):
        result = AIValidator.validate_before_action(
            'create_user', {'username': 'user', 'email': 'a@b.com', 'password': '123'}
        )
        assert result['valid'] is False
        assert any('كلمة المرور' in i for i in result['issues'])

    def test_create_user_valid(self):
        result = AIValidator.validate_before_action(
            'create_user', {'username': 'user', 'email': 'a@b.com', 'password': '123456'}
        )
        assert result['valid'] is True

    def test_create_user_no_data(self):
        result = AIValidator.validate_before_action('create_user')
        assert result['valid'] is True

    def test_create_patient_missing_name(self):
        result = AIValidator.validate_before_action('create_patient', {'birth_date': '2020-01-01'})
        assert result['valid'] is False
        assert any('اسم المريض' in i for i in result['issues'])

    def test_create_patient_future_birth(self):
        future = (date.today() + timedelta(days=1)).isoformat()
        result = AIValidator.validate_before_action(
            'create_patient', {'first_name': 'John', 'birth_date': future}
        )
        assert result['valid'] is False
        assert any('تاريخ الميلاد' in i for i in result['issues'])

    def test_create_patient_invalid_birth(self):
        result = AIValidator.validate_before_action(
            'create_patient', {'first_name': 'John', 'birth_date': 'not-a-date'}
        )
        assert result['valid'] is False
        assert any('تاريخ ميلاد غير صحيح' in i for i in result['issues'])

    def test_create_patient_valid(self):
        result = AIValidator.validate_before_action('create_patient', {'first_name': 'John'})
        assert result['valid'] is True

    def test_create_patient_with_full_name(self):
        result = AIValidator.validate_before_action('create_patient', {'full_name': 'John Doe'})
        assert result['valid'] is True

    def test_create_visit_missing_patient(self):
        result = AIValidator.validate_before_action('create_visit', {'doctor_id': 1})
        assert result['valid'] is False
        assert any('المريض' in i for i in result['issues'])

    def test_create_visit_missing_doctor(self):
        result = AIValidator.validate_before_action('create_visit', {'patient_id': 1})
        assert result['valid'] is False
        assert any('الطبيب' in i for i in result['issues'])

    def test_create_visit_valid(self):
        result = AIValidator.validate_before_action(
            'create_visit', {'patient_id': 1, 'doctor_id': 2}
        )
        assert result['valid'] is True

    def test_create_visit_no_data(self):
        result = AIValidator.validate_before_action('create_visit')
        assert result['valid'] is True

    def test_unknown_action(self):
        result = AIValidator.validate_before_action('unknown_action', {})
        assert result['valid'] is True


class TestAIValidatorGetSystemHealthReport:
    """Tests for AIValidator.get_system_health_report."""

    def test_healthy_report(self):
        values = [5, 5, 1, 0, 1, 1, 5, 5, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.get_system_health_report()
        assert 'report' in result
        assert result['status'] == '✅ ممتاز'
        assert result['color'] == 'success'

    def test_critical_report(self):
        values = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        mocks = _make_scalar_side_effect(values)
        with patch('services.ai_validator.db.session.execute', side_effect=mocks):
            result = AIValidator.get_system_health_report()
        assert result['status'] == '⛔ حرج'
        assert result['color'] == 'danger'

    def test_warning_report(self):
        with patch.object(
            AIValidator,
            'validate_system_data',
            return_value={'valid': False, 'errors': [], 'warnings': ['w']},
        ):
            result = AIValidator.get_system_health_report()
        assert result['status'] == '⚠️ يحتاج انتباه'
        assert result['color'] == 'warning'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
