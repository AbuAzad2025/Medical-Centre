"""FHIR search and pagination utilities."""
from __future__ import annotations

from sqlalchemy import asc, desc


def parse_fhir_params(request):
    """Parse FHIR search parameters from request."""
    params = {}
    # Standard FHIR search params
    for key in ['_id', '_lastUpdated', '_count', '_offset', '_sort', '_include', '_revinclude']:
        val = request.args.get(key)
        if val is not None:
            params[key] = val
    # Resource-specific params
    for key in request.args:
        if not key.startswith('_'):
            params[key] = request.args.get(key)
    return params


def apply_fhir_pagination(query, request, default_count=20, max_count=100):
    """Apply FHIR pagination to a SQLAlchemy query."""
    count = min(int(request.args.get('_count', default_count)), max_count)
    offset = int(request.args.get('_offset', 0))
    return query.offset(offset).limit(count), count, offset


def apply_fhir_sort(query, model, sort_param):
    """Apply FHIR sorting to a query."""
    if not sort_param:
        return query
    # FHIR sort: -field for descending, field for ascending
    if sort_param.startswith('-'):
        field = sort_param[1:]
        if hasattr(model, field):
            return query.order_by(desc(getattr(model, field)))
    elif hasattr(model, sort_param):
        return query.order_by(asc(getattr(model, sort_param)))
    return query


def fhir_bundle(entries, total, resource_type='searchset'):
    """Create a FHIR Bundle response."""
    return {
        'resourceType': 'Bundle',
        'type': resource_type,
        'total': total,
        'entry': [{'resource': e} for e in entries],
        'link': [],
    }
