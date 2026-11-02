"""Tests for utils.hl7 and related HL7 utility modules - 100% coverage target."""

from __future__ import annotations

import pytest

# Test the alias modules
import utils.hl7
import utils.hl7_generator
import utils.hl7_message_generator
import utils.hl7_utils


class TestHL7AliasModules:
    """Tests for HL7 alias modules."""

    def test_hl7_imports_from_services(self):
        """Test utils.hl7 imports from services.hl7_message_generator."""
        # These should be available through the import
        assert hasattr(utils.hl7, 'build_adt')
        assert hasattr(utils.hl7, 'build_orm')
        assert hasattr(utils.hl7, 'build_oru')
        assert hasattr(utils.hl7, 'build_siu')
        assert hasattr(utils.hl7, 'build_rde')
        assert hasattr(utils.hl7, 'build_rds')
        assert hasattr(utils.hl7, 'build_mdm')
        assert hasattr(utils.hl7, 'build_ack')
        assert hasattr(utils.hl7, 'generate_message')
        assert hasattr(utils.hl7, 'send_mllp')

    def test_hl7_generator_alias(self):
        """Test utils.hl7_generator imports from services."""
        assert hasattr(utils.hl7_generator, 'build_adt')
        assert hasattr(utils.hl7_generator, 'generate_message')

    def test_hl7_message_generator_alias(self):
        """Test utils.hl7_message_generator imports from services."""
        assert hasattr(utils.hl7_message_generator, 'build_adt')
        assert hasattr(utils.hl7_message_generator, 'generate_message')

    def test_hl7_utils_alias(self):
        """Test utils.hl7_utils imports from services."""
        assert hasattr(utils.hl7_utils, 'build_adt')
        assert hasattr(utils.hl7_utils, 'generate_message')

    def test_all_aliases_point_to_same_functions(self):
        """Test all aliases point to the same functions."""
        assert utils.hl7.build_adt is utils.hl7_generator.build_adt
        assert utils.hl7_generator.build_adt is utils.hl7_message_generator.build_adt
        assert utils.hl7_message_generator.build_adt is utils.hl7_utils.build_adt


class TestHL7GeneratorExports:
    """Tests for HL7 generator exports."""

    def test_all_exports_available(self):
        """Test all exported functions are available."""
        from utils import hl7

        # Check that the module has expected functions
        expected_exports = [
            'build_adt', 'build_orm', 'build_oru', 'build_siu', 'build_rde',
            'build_rds', 'build_mdm', 'build_ack', 'generate_message',
            'send_mllp', 'build_msh', 'build_pid', 'build_pv1',
        ]
        for item in expected_exports:
            assert hasattr(hl7, item), f"Missing export: {item}"

    def test_key_classes_available(self):
        """Test key classes are available."""
        from utils import hl7

        assert hasattr(hl7, 'HL7Generator')
        assert hasattr(hl7, 'HL7MessageBuilder')
        assert hasattr(hl7, 'HL7MessageGenerator')
        assert hasattr(hl7, 'MessageGenerator')

    def test_aliases_available(self):
        """Test convenience aliases are available."""
        from utils import hl7

        # Class aliases
        assert hasattr(hl7, 'HL7Generator')
        assert hasattr(hl7, 'HL7MessageBuilder')
        assert hasattr(hl7, 'HL7MessageGenerator')
        assert hasattr(hl7, 'MessageGenerator')

        # Function aliases
        assert hasattr(hl7, 'send_message')
        assert hasattr(hl7, 'send_hl7_message')
        assert hasattr(hl7, 'send_to_external')
        assert hasattr(hl7, 'transmit_message')
        assert hasattr(hl7, 'transmit_hl7')
        assert hasattr(hl7, 'send_hl7')

    def test_validation_functions_available(self):
        """Test validation functions are available."""
        from utils import hl7

        assert hasattr(hl7, 'validate_hl7_message')
        assert hasattr(hl7, 'validate_message')

    def test_message_creation_functions(self):
        """Test message creation functions."""
        from utils import hl7

        assert hasattr(hl7, 'create_message')
        assert hasattr(hl7, 'build_message')
        assert hasattr(hl7, 'generate_message')
        assert hasattr(hl7, 'make_message')
        assert hasattr(hl7, 'render_message')

    def test_segment_builders_available(self):
        """Test segment builder functions."""
        from utils import hl7

        assert hasattr(hl7, 'build_msh')
        assert hasattr(hl7, 'build_pid')
        assert hasattr(hl7, 'build_pv1')

    def test_message_type_builders_available(self):
        """Test message type builders."""
        from utils import hl7

        assert hasattr(hl7, 'build_adt')
        assert hasattr(hl7, 'build_orm')
        assert hasattr(hl7, 'build_oru')
        assert hasattr(hl7, 'build_siu')
        assert hasattr(hl7, 'build_rde')
        assert hasattr(hl7, 'build_rds')
        assert hasattr(hl7, 'build_mdm')
        assert hasattr(hl7, 'build_ack')

    def test_convenience_builders_available(self):
        """Test convenience builders."""
        from utils import hl7

        assert hasattr(hl7, 'build_adt_a01')
        assert hasattr(hl7, 'build_adt_a04')
        assert hasattr(hl7, 'build_adt_a08')
        assert hasattr(hl7, 'build_orm_o01')
        assert hasattr(hl7, 'build_oru_r01')
        assert hasattr(hl7, 'build_siu_s12')
        assert hasattr(hl7, 'build_rde_o11')
        assert hasattr(hl7, 'build_rds_o13')
        assert hasattr(hl7, 'build_mdm_t02')

    def test_mllp_functions_available(self):
        """Test MLLP functions."""
        from utils import hl7

        assert hasattr(hl7, 'frame_mllp')
        assert hasattr(hl7, 'send_mllp')

    def test_constants_available(self):
        """Test HL7 constants."""
        import services.hl7_message_generator as hl7_service

        # Constants are in the service module
        assert hasattr(hl7_service, 'MLLP_START')
        assert hasattr(hl7_service, 'MLLP_END')
        assert hasattr(hl7_service, 'DEFAULT_SEPARATOR')
        assert hasattr(hl7_service, 'ENCODING_CHARS')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
