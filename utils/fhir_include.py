"""FHIR _include and _revinclude support utilities."""
from __future__ import annotations


def parse_include_params(request):
    """Parse _include and _revinclude from request."""
    includes = request.args.getlist('_include')
    revincludes = request.args.getlist('_revinclude')
    return includes, revincludes


def resolve_include(entries, include_params, model_lookup):
    """Resolve _include references in FHIR bundle entries.

    include_params: list of strings like 'Patient:general-practitioner'
    model_lookup: dict mapping resource type to (model, id_field) for lookup
    """
    if not include_params:
        return entries

    included_ids = set()
    included_resources = []

    for inc in include_params:
        parts = inc.split(':')
        if len(parts) < 2:
            continue
        source_type = parts[0]
        field = parts[1]

        for entry in entries:
            resource = entry.get('resource', {})
            if resource.get('resourceType') != source_type:
                continue
            ref = resource.get(field)
            if isinstance(ref, dict) and 'reference' in ref:
                ref_str = ref['reference']
                if '/' in ref_str:
                    ref_type, ref_id = ref_str.split('/', 1)
                    key = (ref_type, ref_id)
                    if key not in included_ids:
                        included_ids.add(key)
                        # Look up the referenced resource
                        if ref_type in model_lookup:
                            model, _ = model_lookup[ref_type]
                            try:
                                obj = model.query.get(int(ref_id))
                                if obj:
                                    included_resources.append({
                                        'resourceType': ref_type,
                                        'id': str(ref_id),
                                        'included': True,
                                    })
                            except (ValueError, Exception):
                                pass
            elif isinstance(ref, list):
                for r in ref:
                    if isinstance(r, dict) and 'reference' in r:
                        ref_str = r['reference']
                        if '/' in ref_str:
                            ref_type, ref_id = ref_str.split('/', 1)
                            key = (ref_type, ref_id)
                            if key not in included_ids:
                                included_ids.add(key)

    # Add included resources to entries
    for res in included_resources:
        entries.append({'resource': res})

    return entries


def apply_include_to_bundle(bundle, include_params):
    """Apply _include to a FHIR bundle."""
    if not include_params:
        return bundle
    # Mark entries as included
    for entry in bundle.get('entry', []):
        entry['search'] = {'mode': 'match'}
    return bundle
