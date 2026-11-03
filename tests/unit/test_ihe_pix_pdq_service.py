"""Tests for services.ihe_pix_pdq_service module - 100% coverage target."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.ihe_pix_pdq_service import IHEPixPdqService


class TestIHEPixPdqService:
    """Tests for IHEPixPdqService class."""

    def test_pix_query_not_found(self):
        """Test pix_query returns not found when patient doesn't exist."""
        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None
            mock_result.scalars.return_value.all.return_value = []
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pix_query('nonexistent', tenant_id=1)

            assert result['found'] is False
            assert result['identifiers'] == []

    def test_pix_query_with_domain_filter(self):
        """Test pix_query with domain filter."""
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.tenant_id = 1
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = mock_patient
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pix_query('1', domain='TENANT-1', tenant_id=1)

            assert result['found'] is True
            assert result['patient_id'] == 1

    def test_pix_query_without_tenant(self):
        """Test pix_query without tenant_id."""
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.tenant_id = 1
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = mock_patient
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pix_query('1')

            assert result['found'] is True

    def test_pix_query_national_id_lookup(self):
        """Test pix_query with national_id lookup."""
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.tenant_id = 1
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pix_query('1234567890', tenant_id=1)

            assert result['found'] is True

    def test_pix_query_exception_handling(self):
        """Test pix_query handles exceptions gracefully."""
        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.first.return_value = None
            mock_result.scalars.return_value.all.side_effect = Exception('DB error')
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pix_query('1234567890', tenant_id=1)

            assert result['found'] is False

    def test_pdq_query_basic(self):
        """Test pdq_query basic functionality."""
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.first_name = 'John'
        mock_patient.last_name = 'Doe'
        mock_patient.first_name_ar = None
        mock_patient.last_name_ar = None
        mock_patient.birth_date = None
        mock_patient.gender = 'male'
        mock_patient.phone = '1234567890'
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(tenant_id=1)

            assert result['total'] == 1
            assert len(result['patients']) == 1
            assert result['patients'][0]['id'] == 1

    def test_pdq_query_with_filters(self):
        """Test pdq_query with family_name and given_name filters."""
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.first_name = 'John'
        mock_patient.last_name = 'Doe'
        mock_patient.first_name_ar = None
        mock_patient.last_name_ar = None
        mock_patient.birth_date = None
        mock_patient.gender = 'male'
        mock_patient.phone = '1234567890'
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(
                family_name='Doe',
                given_name='John',
                tenant_id=1,
            )

            assert result['total'] == 1

    def test_pdq_query_no_match(self):
        """Test pdq_query with no matching patients."""
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.first_name = 'John'
        mock_patient.last_name = 'Doe'
        mock_patient.first_name_ar = None
        mock_patient.last_name_ar = None
        mock_patient.birth_date = None
        mock_patient.gender = 'male'
        mock_patient.phone = '1234567890'
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(
                family_name='Smith',
                tenant_id=1,
            )

            assert result['total'] == 0

    def test_pdq_query_with_phone_filter(self):
        """Test pdq_query with phone filter."""
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.first_name = 'John'
        mock_patient.last_name = 'Doe'
        mock_patient.first_name_ar = None
        mock_patient.last_name_ar = None
        mock_patient.birth_date = None
        mock_patient.gender = 'male'
        mock_patient.phone = '1234567890'
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(
                phone='1234567890',
                tenant_id=1,
            )

            assert result['total'] == 1

    def test_pdq_query_with_birth_date(self):
        """Test pdq_query with birth_date filter."""
        from datetime import date

        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.first_name = 'John'
        mock_patient.last_name = 'Doe'
        mock_patient.first_name_ar = None
        mock_patient.last_name_ar = None
        mock_patient.birth_date = date(1990, 1, 1)
        mock_patient.gender = 'male'
        mock_patient.phone = '1234567890'
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(
                birth_date='1990',
                tenant_id=1,
            )

            assert result['total'] == 1

    def test_atna_audit(self):
        """Test atna_audit function."""
        with patch('app.extensions.db.session.add') as mock_add:
            with patch('utils.db_safety.safe_commit') as mock_commit:
                IHEPixPdqService.atna_audit('PIX_QUERY', 1, 1, '0')

                mock_add.assert_called_once()
                mock_commit.assert_called_once()

    def test_atna_audit_exception(self):
        """Test atna_audit handles exceptions gracefully."""
        with patch('app.extensions.db.session.add') as mock_add:
            mock_add.side_effect = Exception('DB error')

            # Should not raise exception
            IHEPixPdqService.atna_audit('PIX_QUERY', 1, 1, '0')

    def test_pdq_query_given_name_arabic_fallback(self):
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.first_name = 'John'
        mock_patient.last_name = 'Doe'
        mock_patient.first_name_ar = 'جون'
        mock_patient.last_name_ar = None
        mock_patient.birth_date = None
        mock_patient.gender = 'male'
        mock_patient.phone = '1234567890'
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(
                given_name='غيرموجود',  # won't match first_name, but check arabic
                tenant_id=1,
            )
            # given_name 'غيرموجود' not in 'John' or 'جون', so no match
            assert result['total'] == 0

    def test_pdq_query_given_name_arabic_match(self):
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.first_name = 'John'
        mock_patient.last_name = 'Doe'
        mock_patient.first_name_ar = 'جون'
        mock_patient.last_name_ar = None
        mock_patient.birth_date = None
        mock_patient.gender = 'male'
        mock_patient.phone = '1234567890'
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(
                given_name='جون',
                tenant_id=1,
            )
            assert result['total'] == 1

    def test_pdq_query_birth_date_no_match(self):
        from datetime import date

        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.first_name = 'John'
        mock_patient.last_name = 'Doe'
        mock_patient.first_name_ar = None
        mock_patient.last_name_ar = None
        mock_patient.birth_date = date(1990, 1, 1)
        mock_patient.gender = 'male'
        mock_patient.phone = '1234567890'
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(
                birth_date='2000',
                tenant_id=1,
            )
            assert result['total'] == 0

    def test_pdq_query_phone_no_match(self):
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.first_name = 'John'
        mock_patient.last_name = 'Doe'
        mock_patient.first_name_ar = None
        mock_patient.last_name_ar = None
        mock_patient.birth_date = None
        mock_patient.gender = 'male'
        mock_patient.phone = '1234567890'
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(
                phone='9999999999',
                tenant_id=1,
            )
            assert result['total'] == 0

    def test_pdq_query_family_name_arabic_fallback(self):
        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.first_name = 'John'
        mock_patient.last_name = 'Doe'
        mock_patient.first_name_ar = None
        mock_patient.last_name_ar = 'دو'
        mock_patient.birth_date = None
        mock_patient.gender = 'male'
        mock_patient.phone = '1234567890'
        mock_patient.national_id = '1234567890'

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_patient]
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(
                family_name='دو',
                tenant_id=1,
            )
            assert result['total'] == 1

    def test_pdq_query_limit_break(self):
        patients = []
        for i in range(5):
            m = MagicMock()
            m.id = i + 1
            m.full_name = f'Patient {i}'
            m.first_name = 'Patient'
            m.last_name = str(i)
            m.first_name_ar = None
            m.last_name_ar = None
            m.birth_date = None
            m.gender = 'male'
            m.phone = '1234567890'
            m.national_id = '1234567890'
            patients.append(m)

        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = patients
            mock_execute.return_value = mock_result

            result = IHEPixPdqService.pdq_query(
                limit=2,
                tenant_id=1,
            )
            assert result['total'] == 2

    def test_ihe_service_instance(self):
        """Test ihe_service instance is created."""
        from services.ihe_pix_pdq_service import ihe_service

        assert ihe_service is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
