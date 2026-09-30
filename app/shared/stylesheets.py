"""Render the stylesheet <link> tags from one declared order.

The list used to be hand-written into five shells. Order is load-bearing for
the cascade, so it is declared once in config.py and rendered from here, which
means adding a stylesheet is a one-line change instead of five.
"""

from __future__ import annotations

from markupsafe import Markup, escape


def stylesheets(shell: str = 'base') -> Markup:
    """Return the ordered <link> tags for *shell*.

    Every entry goes through url_for, so a stylesheet is fetched through the
    same hashed/static route as any other asset and a path typo is a 404 in
    development rather than a silently unstyled page in production.
    """
    from flask import url_for

    from config import STYLESHEET_SHARED, STYLESHEET_SHELL_EXTRAS, STYLESHEET_VENDOR

    extras = STYLESHEET_SHELL_EXTRAS.get(shell, ())
    unknown = shell not in STYLESHEET_SHELL_EXTRAS
    if unknown:
        raise KeyError(
            f'unknown shell {shell!r}; add it to STYLESHEET_SHELL_EXTRAS in config.py '
            f'rather than writing a <link> list by hand'
        )

    parts = [
        '    <link rel="stylesheet" href="{}">'.format(escape(url_for('static', filename=name)))
        for name in (*STYLESHEET_VENDOR, *STYLESHEET_SHARED, *extras)
    ]
    return Markup('\n'.join(parts))


def register(app) -> None:
    app.jinja_env.globals['stylesheets'] = stylesheets
