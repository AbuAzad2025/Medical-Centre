"""Sanitize rich-text HTML from privileged WYSIWYG fields.

The application intentionally renders some admin/manager-controlled HTML
(print headers/footers, patient-education material) with Jinja's ``|safe``.
That is only acceptable if dangerous constructs are stripped on the way in.
This module provides a small, dependency-free sanitiser based on the standard
library ``HTMLParser``. It keeps normal formatting tags and inline styles but
removes executable content (scripts, event handlers, javascript: URLs, and
active-embedded elements).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

# Tags that can execute script / embed active content and must be removed
# entirely (including their child text where it makes sense).
_DROP_TAGS = frozenset(
    {
        'script',
        'style',
        'iframe',
        'object',
        'embed',
        'applet',
        'meta',
        'link',
        'base',
        'form',
        'svg',
        'math',
        'template',
        'noscript',
        'frame',
        'frameset',
    }
)

# Event-handler attributes (onclick, onload, ...) and dangerous URL attrs.
_EVENT_ATTR = re.compile(r'^on[a-z]', re.IGNORECASE)


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self._drop_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in _DROP_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth:
            return

        safe_attrs: list[str] = []
        for name, value in attrs:
            if not name:
                continue
            lname = name.lower()
            if _EVENT_ATTR.match(lname):
                continue
            if lname in {'src', 'href', 'action', 'xlink:href', 'formaction'}:
                if value and re.match(r'^\s*(javascript|vbscript|data):', value, re.IGNORECASE):
                    continue
            # Block srcdoc and style expressions that can execute
            if lname in {'srcdoc'}:
                continue
            if value is None:
                safe_attrs.append(lname)
            else:
                escaped = value.replace('&', '&amp;').replace('"', '&quot;')
                safe_attrs.append(f'{lname}="{escaped}"')
        self.parts.append(f'<{tag}{" " + " ".join(safe_attrs) if safe_attrs else ""}>')

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _DROP_TAGS:
            self._drop_depth = max(0, self._drop_depth - 1)
            return
        if self._drop_depth:
            return
        self.parts.append(f'</{tag}>')

    def handle_data(self, data: str) -> None:
        if not self._drop_depth:
            self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self._drop_depth:
            self.parts.append(f'&{name};')

    def handle_charref(self, name: str) -> None:
        if not self._drop_depth:
            self.parts.append(f'&#{name};')

    def handle_comment(self, data: str) -> None:
        # Drop comments entirely
        return


def sanitize_rich_html(raw: str | None, max_length: int = 20000) -> str:
    """Return *raw* with executable HTML removed.

    Keeps ordinary formatting (headings, paragraphs, lists, tables, links,
    images, inline styles) while dropping scripts, event handlers, and
    javascript:/data: URLs. Safe to store and later render with ``|safe``.
    """
    if not raw:
        return ''
    raw = raw[:max_length]
    parser = _Sanitizer()
    try:
        parser.feed(raw)
        parser.close()
    except Exception:
        # On any parse anomaly fail closed: return an escaped copy.
        from markupsafe import escape

        return str(escape(raw))
    return ''.join(parser.parts)
