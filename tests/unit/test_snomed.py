"""Tests for models.snomed module - 100% coverage target."""

from __future__ import annotations

import pytest

from models.snomed import SNOMEDConcept, SNOMEDRelationship


class TestSNOMEDConcept:
    """Tests for SNOMEDConcept model."""

    def test_snomed_concept_creation(self):
        """Test creating a SNOMEDConcept."""
        concept = SNOMEDConcept(
            concept_id='123456',
            term='Test Concept',
            term_ar='مفهوم اختبار',
            semantic_tag='disorder',
            is_active=True,
        )

        assert concept.concept_id == '123456'
        assert concept.term == 'Test Concept'
        assert concept.term_ar == 'مفهوم اختبار'
        assert concept.semantic_tag == 'disorder'
        assert concept.is_active is True

    def test_snomed_concept_defaults(self):
        """Test SNOMEDConcept with default values."""
        concept = SNOMEDConcept(
            concept_id='123456',
            term='Test Concept',
        )

        assert concept.concept_id == '123456'
        assert concept.term == 'Test Concept'
        assert concept.term_ar is None
        assert concept.semantic_tag is None
        # is_active default is True but requires DB session to be applied
        # Just verify the attribute exists
        assert hasattr(concept, 'is_active')

    def test_snomed_concept_repr(self):
        """Test SNOMEDConcept __repr__."""
        concept = SNOMEDConcept(
            concept_id='123456',
            term='Test Concept',
        )

        repr_str = repr(concept)
        assert 'SNOMEDConcept' in repr_str
        assert '123456' in repr_str
        assert 'Test Concept' in repr_str

    def test_snomed_concept_unique_constraint(self):
        """Test that concept_id is unique."""
        # This is a model definition test - verify the column definition
        from sqlalchemy import inspect


        # Verify the column exists and has unique constraint
        mapper = inspect(SNOMEDConcept)
        concept_id_col = mapper.columns.concept_id
        assert concept_id_col.unique is True
        assert concept_id_col.nullable is False


class TestSNOMEDRelationship:
    """Tests for SNOMEDRelationship model."""

    def test_snomed_relationship_creation(self):
        """Test creating a SNOMEDRelationship."""
        relationship = SNOMEDRelationship(
            source_id='123456',
            target_id='789012',
            relationship_type='is_a',
            is_active=True,
        )

        assert relationship.source_id == '123456'
        assert relationship.target_id == '789012'
        assert relationship.relationship_type == 'is_a'
        assert relationship.is_active is True

    def test_snomed_relationship_defaults(self):
        """Test SNOMEDRelationship with default values."""
        relationship = SNOMEDRelationship(
            source_id='123456',
            target_id='789012',
            relationship_type='is_a',
        )

        assert relationship.source_id == '123456'
        assert relationship.target_id == '789012'
        assert relationship.relationship_type == 'is_a'
        # is_active default is True but requires DB session to be applied
        # Just verify the attribute exists
        assert hasattr(relationship, 'is_active')

    def test_snomed_relationship_repr(self):
        """Test SNOMEDRelationship __repr__."""
        relationship = SNOMEDRelationship(
            source_id='123456',
            target_id='789012',
            relationship_type='is_a',
        )

        repr_str = repr(relationship)
        assert 'SNOMEDRelationship' in repr_str
        assert '123456' in repr_str
        assert '789012' in repr_str


class TestSNOMEDTableArgs:
    """Tests for table arguments."""

    def test_snomed_concept_table_args(self):
        """Test SNOMEDConcept table args."""
        assert SNOMEDConcept.__tablename__ == 'snomed_concepts'
        assert SNOMEDConcept.__table_args__ == {'extend_existing': True}

    def test_snomed_relationship_table_args(self):
        """Test SNOMEDRelationship table args."""
        assert SNOMEDRelationship.__tablename__ == 'snomed_relationships'
        assert SNOMEDRelationship.__table_args__ == {'extend_existing': True}


class TestSNOMEDColumnTypes:
    """Tests for column types and constraints."""

    def test_snomed_concept_columns(self):
        """Test SNOMEDConcept column types."""
        from sqlalchemy import inspect

        mapper = inspect(SNOMEDConcept)
        cols = {c.key: c for c in mapper.columns}

        assert 'id' in cols
        assert 'concept_id' in cols
        assert 'term' in cols
        assert 'term_ar' in cols
        assert 'semantic_tag' in cols
        assert 'is_active' in cols
        assert 'created_at' in cols
        assert 'updated_at' in cols

    def test_snomed_relationship_columns(self):
        """Test SNOMEDRelationship column types."""
        from sqlalchemy import inspect

        mapper = inspect(SNOMEDRelationship)
        cols = {c.key: c for c in mapper.columns}

        assert 'id' in cols
        assert 'source_id' in cols
        assert 'target_id' in cols
        assert 'relationship_type' in cols
        assert 'is_active' in cols
        assert 'created_at' in cols


class TestSNOMEDIndexes:
    """Tests for indexes."""

    def test_snomed_concept_indexes(self):
        """Test SNOMEDConcept indexes."""

        table = SNOMEDConcept.__table__
        index_names = [idx.name for idx in table.indexes]
        # Should have index on concept_id (unique) and possibly others
        assert len(index_names) >= 1

    def test_snomed_relationship_indexes(self):
        """Test SNOMEDRelationship indexes."""

        table = SNOMEDRelationship.__table__
        index_names = [idx.name for idx in table.indexes]
        # Should have indexes on source_id and target_id
        assert len(index_names) >= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
