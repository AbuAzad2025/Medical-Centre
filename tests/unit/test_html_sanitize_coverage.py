"""Security tests for utils.html_sanitize (XSS prevention)."""

from utils.html_sanitize import sanitize_rich_html


class TestRichHtmlSanitizer:
    def test_preserves_safe_formatting(self):
        html = '<p>Hello <b>World</b> <i>and</i> <a href="/x">link</a></p>'
        assert sanitize_rich_html(html) == html

    def test_strips_script_tag(self):
        html = '<script>alert(1)</script><p>Safe</p>'
        result = sanitize_rich_html(html)
        assert '<script' not in result.lower()
        assert 'alert(1)' not in result
        assert '<p>Safe</p>' in result

    def test_strips_event_handlers(self):
        html = '<img src="x" onerror="alert(1)" onload="hack()">'
        result = sanitize_rich_html(html)
        assert 'onerror' not in result.lower()
        assert 'onload' not in result.lower()
        assert '<img src="x">' in result

    def test_strips_javascript_urls(self):
        html = '<a href="javascript:alert(1)">click</a>'
        result = sanitize_rich_html(html)
        assert 'javascript:' not in result.lower()

    def test_strips_embedded_content(self):
        html = '<iframe src="evil"></iframe><object data="x"></object>ok'
        result = sanitize_rich_html(html)
        assert '<iframe' not in result.lower()
        assert '<object' not in result.lower()
        assert 'ok' in result

    def test_preserves_inline_style(self):
        html = '<div style="color:red">styled</div>'
        assert sanitize_rich_html(html) == html

    def test_empty_input(self):
        assert sanitize_rich_html('') == ''
        assert sanitize_rich_html(None) == ''

    def test_length_limit(self):
        result = sanitize_rich_html('x' * 100, max_length=10)
        assert len(result) == 10
