"""Generate the scenario matrix and refuse to emit duplicates.

Duplication is the failure mode that matters here. A generator that varies every
axis against every template produces a large number and an unwatchable one: the
same journey reappears with a different colour code and reviewers stop reading.

So the generator is deliberately narrow. Each template declares only the axes its
assertions actually depend on, and the product is taken per template rather than
globally. Insurance coverage multiplies the number of scenarios that assert
anything about insurance and nothing else. Triage colour appears only on the
emergency template, because no other template reads triage.

Every emitted scenario carries a fingerprint of template plus axis values, and the
emitter asserts uniqueness before writing anything. A collision is an error, not a
warning.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# The dimensions read enums out of the application itself, so the repository root
# has to be importable before anything is generated. The test suite puts it there
# too; adding it here is what lets the generator run as a standalone command.
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dimensions import Fingerprint, build_dimensions  # noqa: E402

from templates import TEMPLATES, all_problems  # noqa: E402

OUT_DIR = os.path.join(ROOT, 'docs', 'scenarios', 'generated')


def _install_family_templates() -> None:
    """Register the family modules so their templates are in TEMPLATES.

    Imported lazily and by name, because the family modules import from this one
    and templates.py and a top-level import would be circular.

    The families are clinical-ops, identity, platform-admin and integration, and
    they are installed after the base set so a duplicate key is resolved in favour
    of the original template rather than silently replacing it.
    """
    import clinical_ops_templates
    import clinical_templates
    import identity_templates
    import integration_templates
    import platform_admin_templates
    import platform_templates

    clinical_templates.add_clinical_templates()
    platform_templates.add_platform_templates()
    clinical_ops_templates.add_clinical_ops_templates()
    identity_templates.add_identity_templates()
    platform_admin_templates.add_platform_admin_templates()
    integration_templates.add_integration_templates()
    _apply_axis_effects()


def _apply_axis_effects() -> None:
    """Attach each axis's stated mechanism to the template that declares it.

    Kept out of the template modules so the mechanism table can be read and
    reviewed in one place rather than scattered across six files, and so an axis
    with no mechanism fails loudly here instead of quietly multiplying the
    matrix.
    """
    from axis_effects import effects_for

    for tpl in TEMPLATES:
        mechanisms = effects_for(tpl)
        missing = [a for a in tpl.axes if a not in mechanisms]
        if missing:
            raise AssertionError(
                f'{tpl.key}: no stated mechanism for axis {missing[0]!r}. Either the '
                'axis changes nothing about the run and must be deleted from the '
                'template, or the mechanism belongs in axis_effects.py'
            )
        object.__setattr__(tpl, 'effect', mechanisms)
        tpl.__post_init__()


_install_family_templates()


def axes_for(template, dims):
    """Return [(name, values), ...] for the axes this template declares."""
    by_name = {d.name: d for d in dims}
    out = []
    for name in template.axes:
        if name not in by_name:
            raise KeyError(f'{template.key}: unknown axis {name!r}')
        out.append((name, by_name[name].values))
    return out


def generate(limit: int | None = None, group: int = 1, groups: int = 1):
    """Expand every template over its own axes.

    Returns (scenarios_for_this_shard, all_fingerprints). The fingerprint map is
    returned for the whole matrix, not just the shard, so the uniqueness check
    still covers scenarios that ended up in a different file.
    """
    dims = build_dimensions()
    by_name = {d.name: d for d in dims}
    scenarios = []
    fingerprints: dict[str, str] = {}

    for tpl in TEMPLATES:
        axis_values = axes_for(tpl, dims)
        names = [n for n, _ in axis_values]
        for combo in itertools.product(*(v for _, v in axis_values)):
            assignment = dict(zip(names, combo, strict=True))
            fp = Fingerprint(template=tpl.key, axes=tuple(sorted(assignment.items())))
            key = fp.key()
            if key in fingerprints:
                raise AssertionError(
                    f'duplicate fingerprint: {tpl.key} {assignment} '
                    f'already emitted as {fingerprints[key]}'
                )
            fingerprints[key] = tpl.key
            scenarios.append(
                {
                    'scenario_id': None,  # assigned after sharding
                    'template': tpl.key,
                    'family': tpl.family,
                    'axes': assignment,
                    'axes_note': {n: by_name[n].note for n in names},
                    'axes_effect': tpl.effects(assignment),
                    'rule': tpl.rule,
                    'expected_payment_status': tpl.expected_status,
                    'tags': list(tpl.tags),
                    'journey_steps': [
                        {
                            'step': i,
                            'department': s.department,
                            'api': s.api,
                            'assertion': s.assertion,
                        }
                        for i, s in enumerate(tpl.steps, 1)
                    ],
                }
            )

    total = len(scenarios)
    if not total:
        return [], {}

    # Deterministic sharding so a rerun with the same arguments produces the
    # same files, which is what makes a diff reviewable. group is 1-based, so
    # shift it before indexing or group 1 slices from per_group onward.
    if not 1 <= group <= groups:
        raise ValueError(f'group must be in 1..{groups}, got {group}')
    per_group, extra = divmod(total, groups)
    start = (group - 1) * per_group + min(group - 1, extra)
    end = start + per_group + (1 if group - 1 < extra else 0)
    shard = scenarios[start:end]

    # Scenario ids are numbered across the whole matrix, not the shard, so a
    # reader can tell which part of 5616 they are looking at.
    width = max(4, len(str(total)))
    for offset, sc in enumerate(shard):
        sc['scenario_id'] = f'GS-{start + offset + 1:0{width}d}'

    if limit:
        shard = shard[:limit]
    return shard, fingerprints


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--group', type=int, default=1, help='1-based shard index')
    ap.add_argument('--groups', type=int, default=1, help='total shards')
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--out', default=None)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    problems = all_problems()
    if problems:
        print('template routes do not exist:', file=sys.stderr)
        for p in problems:
            print(' ', p, file=sys.stderr)
        return 2

    scenarios, fingerprints = generate(limit=args.limit, group=args.group, groups=args.groups)

    suffix = '' if args.groups == 1 else f'.part{args.group}-of-{args.groups}'
    out = args.out or os.path.join(OUT_DIR, f'scenarios{suffix}.json')

    print(f'templates: {len(TEMPLATES)}')
    print(f'matrix total: {len(fingerprints)} unique scenarios')
    print(f'shard {args.group}/{args.groups}: {len(scenarios)} written')

    families: dict[str, int] = {}
    for s in scenarios:
        families[s['family']] = families.get(s['family'], 0) + 1
    for fam, n in sorted(families.items()):
        print(f'  {fam}: {n}')

    if args.dry_run:
        print('\ndry run, nothing written')
        return 0

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(scenarios, fh, ensure_ascii=False, indent=2)
        fh.write('\n')
    print(f'\nwrote {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
