"""
Frontend-Backend Field Contract Tests — covers:
1. maxlength attributes match DB column lengths
2. HTML input types match model column types
3. <select> options match model enum values
"""

import re
import json
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import declarative_base

from app.extensions import db
from app_factory import create_app


# ─── Helpers ────────────────────────────────────────────────────────────────


def get_model_columns():
    """Extract column metadata from all SQLAlchemy models."""
    app = create_app('testing')
    with app.app_context():
        # Get all model classes from db.Model registry
        from models import __all__ as model_names
        import models

        columns_info = {}  # model_name -> {col_name: {type, length, nullable, enum_values}}

        for name in model_names:
            model = getattr(models, name, None)
            if not model or not hasattr(model, '__table__'):
                continue

            mapper = inspect(model)
            cols = {}
            for col in mapper.columns:
                col_info = {
                    'type': str(col.type),
                    'length': getattr(col.type, 'length', None),
                    'nullable': col.nullable,
                    'enum_values': None,
                }
                # Check for enum
                if hasattr(col.type, 'enums'):
                    col_info['enum_values'] = list(col.type.enums)
                elif hasattr(col.type, '_enum_class'):
                    col_info['enum_values'] = [e.value for e in col.type._enum_class]
                cols[col.name] = col_info
            if cols:
                columns_info[name] = cols
        return columns_info


def parse_template_forms(template_path: Path) -> List[Dict]:
    """Parse a template file and extract form fields with their attributes."""
    content = template_path.read_text(encoding='utf-8', errors='ignore')
    forms = []

    # Find all form blocks
    form_pattern = re.compile(r'<form[^>]*>.*?</form>', re.DOTALL | re.IGNORECASE)
    for form_match in form_pattern.finditer(content):
        form_html = form_match.group(0)

        # Extract form method
        method_match = re.search(r'method=[\'"](GET|POST)[\'"]', form_html, re.IGNORECASE)
        method = method_match.group(1).upper() if method_match else 'GET'

        # Extract inputs, selects, textareas
        fields = []

        # <input> fields
        for inp in re.finditer(r'<input[^>]*>', form_html, re.IGNORECASE):
            tag = inp.group(0)
            attrs = extract_attrs(tag)
            if 'name' in attrs:
                fields.append(
                    {
                        'type': 'input',
                        'name': attrs['name'],
                        'input_type': attrs.get('type', 'text'),
                        'maxlength': attrs.get('maxlength'),
                        'required': 'required' in attrs,
                        'pattern': attrs.get('pattern'),
                    }
                )

        # <select> fields
        for sel in re.finditer(r'<select[^>]*>.*?</select>', form_html, re.DOTALL | re.IGNORECASE):
            tag = sel.group(0)
            attrs = extract_attrs(tag[: tag.find('>') + 1])
            if 'name' in attrs:
                # Extract options
                options = re.findall(r'<option[^>]*value=[\'"]([^\'"]*)[\'"]', tag, re.IGNORECASE)
                fields.append(
                    {
                        'type': 'select',
                        'name': attrs['name'],
                        'options': options,
                        'required': 'required' in attrs,
                    }
                )

        # <textarea> fields
        for ta in re.finditer(
            r'<textarea[^>]*>.*?</textarea>', form_html, re.DOTALL | re.IGNORECASE
        ):
            tag = ta.group(0)
            attrs = extract_attrs(tag[: tag.find('>') + 1])
            if 'name' in attrs:
                fields.append(
                    {
                        'type': 'textarea',
                        'name': attrs['name'],
                        'maxlength': attrs.get('maxlength'),
                        'required': 'required' in attrs,
                    }
                )

        if fields:
            forms.append({'fields': fields, 'method': method})

    return forms


def extract_attrs(tag: str) -> Dict[str, str]:
    """Extract attributes from an HTML tag."""
    attrs = {}
    # Match attr="value" or attr='value' or attr=value
    for match in re.finditer(r'(\w+)=([\'"](.*?)[\'"]|(\S+))', tag):
        key = match.group(1)
        value = match.group(3) if match.group(3) is not None else match.group(4)
        attrs[key] = value
    return attrs


def map_sql_type_to_html_input(sql_type: str) -> str:
    """Map SQLAlchemy column type to expected HTML input type."""
    sql_type = sql_type.lower()
    if 'string' in sql_type or 'text' in sql_type or 'varchar' in sql_type or 'char' in sql_type:
        return 'text'
    if 'integer' in sql_type or 'int' in sql_type or 'bigint' in sql_type or 'smallint' in sql_type:
        return 'number'
    if 'float' in sql_type or 'numeric' in sql_type or 'decimal' in sql_type:
        return 'number'
    if 'boolean' in sql_type or 'bool' in sql_type:
        return 'checkbox'
    if 'date' in sql_type and 'time' not in sql_type:
        return 'date'
    if 'datetime' in sql_type or 'timestamp' in sql_type:
        return 'datetime-local'
    if 'time' in sql_type:
        return 'time'
    if 'email' in sql_type:
        return 'email'
    return 'text'


SEMANTIC_HTML_TYPES = {
    'tel',
    'email',
    'url',
    'number',
    'date',
    'datetime-local',
    'month',
    'week',
    'time',
    'color',
    'range',
    'search',
    'tel',
    'password',
    'hidden',
    'checkbox',
    'radio',
    'file',
    'submit',
    'button',
    'reset',
    'image',
    'submit',
}


# ─── Test Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope='session')
def model_columns():
    """Get all model column metadata."""
    return get_model_columns()


@pytest.fixture(scope='session')
def template_forms():
    """Parse all template forms."""
    app = create_app('testing')
    with app.app_context():
        template_dir = Path(app.root_path) / 'templates'
        all_forms = {}
        for tmpl in template_dir.rglob('*.html'):
            forms = parse_template_forms(tmpl)
            if forms:
                all_forms[str(tmpl.relative_to(template_dir))] = forms
        return all_forms


# ─── Tests ──────────────────────────────────────────────────────────────────


class TestMaxLengthContract:
    """Test that maxlength attributes match DB column lengths."""

    def test_input_maxlength_matches_db(self, model_columns, template_forms):
        """All text/varchar inputs should have maxlength <= DB column length."""
        errors = []

        for template_name, forms in template_forms.items():
            for form in forms:
                for field in form['fields']:
                    if field['type'] != 'input':
                        continue
                    if field['input_type'] not in (
                        'text',
                        'email',
                        'password',
                        'tel',
                        'url',
                        'search',
                    ):
                        continue
                    if not field.get('maxlength'):
                        continue

                    maxlength = int(field['maxlength'])
                    field_name = field['name']

                    # Try to find matching model column
                    for model_name, cols in model_columns.items():
                        if field_name in cols:
                            col_info = cols[field_name]
                            db_length = col_info['length']
                            if db_length and maxlength > db_length:
                                errors.append(
                                    f"{template_name}: field '{field_name}' maxlength={maxlength} "
                                    f'exceeds DB length={db_length} (model={model_name})'
                                )
                            break

        assert not errors, '\n'.join(errors[:20])  # Show first 20


class TestInputTypeContract:
    """Test that HTML input types match model column types."""

    def test_input_type_matches_model(self, model_columns, template_forms):
        """HTML input type should be compatible with model column type."""
        errors = []

        for template_name, forms in template_forms.items():
            for form in forms:
                # Skip strict type checking for GET forms (filters/search)
                if form.get('method') == 'GET':
                    continue

                for field in form['fields']:
                    if field['type'] != 'input':
                        continue

                    field_name = field['name']
                    html_type = field['input_type']

                    # Find matching model column
                    for model_name, cols in model_columns.items():
                        if field_name in cols:
                            col_info = cols[field_name]
                            expected_type = map_sql_type_to_html_input(col_info['type'])

                            # Check compatibility
                            compatible = False
                            if html_type == expected_type:
                                compatible = True
                            elif html_type == 'text' and expected_type in (
                                'number',
                                'date',
                                'datetime-local',
                                'email',
                            ):
                                # text is permissive fallback
                                compatible = True
                            elif html_type == 'number' and expected_type == 'text':
                                # number is stricter but acceptable for numeric text
                                compatible = True
                            elif html_type == 'email' and expected_type == 'text':
                                # email is stricter
                                compatible = True
                            elif html_type == 'checkbox' and expected_type == 'text':
                                # boolean as checkbox
                                compatible = True
                            elif html_type in SEMANTIC_HTML_TYPES:
                                # Semantic HTML5 types are acceptable enhancements over base types
                                base_map = {
                                    'tel': 'text',
                                    'email': 'text',
                                    'url': 'text',
                                    'number': 'number',
                                    'date': 'date',
                                    'datetime-local': 'datetime-local',
                                    'month': 'date',
                                    'week': 'date',
                                    'time': 'time',
                                    'color': 'text',
                                    'range': 'number',
                                    'password': 'text',
                                    'hidden': 'number',
                                    'radio': 'number',
                                }
                                if base_map.get(html_type) == expected_type:
                                    compatible = True
                                elif expected_type == 'text' and html_type in (
                                    'tel',
                                    'email',
                                    'url',
                                    'color',
                                    'password',
                                    'hidden',
                                ):
                                    compatible = True
                                elif expected_type == 'number' and html_type == 'range':
                                    compatible = True
                                elif expected_type == 'date' and html_type in (
                                    'datetime-local',
                                    'month',
                                    'week',
                                ):
                                    compatible = True

                            if not compatible:
                                errors.append(
                                    f"{template_name}: field '{field_name}' HTML type='{html_type}' "
                                    f"incompatible with model type '{col_info['type']}' "
                                    f"(expected input type ~ '{expected_type}', model={model_name})"
                                )
                            break

        assert not errors, '\n'.join(errors[:20])


class TestEnumSelectContract:
    """Test that <select> options match model enum values."""

    def test_select_options_match_enum(self, model_columns, template_forms):
        """Select options should match model enum column values."""
        errors = []

        for template_name, forms in template_forms.items():
            for form in forms:
                for field in form['fields']:
                    if field['type'] != 'select':
                        continue

                    field_name = field['name']
                    options = set(field['options'])
                    if not options:
                        continue

                    # Find matching model column with enum
                    for model_name, cols in model_columns.items():
                        if field_name in cols:
                            col_info = cols[field_name]
                            enum_values = col_info['enum_values']
                            if enum_values:
                                enum_set = set(str(v) for v in enum_values)
                                # Check if template options are subset of enum (allow subset)
                                extra = options - enum_set
                                if extra:
                                    errors.append(
                                        f"{template_name}: select '{field_name}' has extra options {extra} "
                                        f'not in model enum {enum_values} (model={model_name})'
                                    )
                                # Check if required enum values are missing (for required fields)
                                if field.get('required'):
                                    missing = enum_set - options
                                    if missing and len(enum_set) <= 10:  # Only flag for small enums
                                        errors.append(
                                            f"{template_name}: required select '{field_name}' missing enum values {missing} "
                                            f'(model={model_name})'
                                        )
                            break

        assert not errors, '\n'.join(errors[:20])


class TestRequiredFieldsPresent:
    """Test that non-nullable model columns have required fields in forms."""

    def test_non_nullable_fields_have_required(self, model_columns, template_forms):
        """Non-nullable model columns should have required attribute in forms (where applicable)."""
        warnings = []  # Use warnings, not errors - not all nullable=False need required in HTML

        for template_name, forms in template_forms.items():
            for form in forms:
                for field in form['fields']:
                    field_name = field['name']

                    for model_name, cols in model_columns.items():
                        if field_name in cols:
                            col_info = cols[field_name]
                            if not col_info['nullable'] and not col_info.get('enum_values'):
                                # Non-nullable, non-enum field
                                if field.get('required') is not True:
                                    warnings.append(
                                        f"{template_name}: field '{field_name}' is non-nullable in DB "
                                        f'(model={model_name}) but not marked required in form'
                                    )
                            break

        # Just warn, don't fail - some fields are set server-side
        if warnings:
            print('\n⚠️  REQUIRED FIELD WARNINGS (review manually):')
            for w in warnings[:20]:
                print(f'  - {w}')


# ─── Main ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
