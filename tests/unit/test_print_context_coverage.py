"""Coverage tests for app/shared/print_context.py"""


class TestPrintContext:
    def test_resolve_print_slots(self):
        from app.shared.print_context import resolve_print_slots

        result = resolve_print_slots('invoice', None)
        assert isinstance(result, tuple)

    def test_get_active_modules(self):
        from app.shared.print_context import _get_active_modules

        result = _get_active_modules()
        assert isinstance(result, set)

    def test_is_doc_type_allowed(self):
        from app.shared.print_context import _is_doc_type_allowed

        result = _is_doc_type_allowed('invoice', set())
        assert isinstance(result, bool)

    def test_get_doc_type_category(self):
        from app.shared.print_context import _get_doc_type_category

        result = _get_doc_type_category('invoice')
        assert isinstance(result, str)

    def test_generate_qr_data_uri(self):
        from app.shared.print_context import generate_qr_data_uri

        result = generate_qr_data_uri('test payload')
        assert isinstance(result, str)

    def test_generate_barcode_code128(self):
        from app.shared.print_context import generate_barcode_code128

        result = generate_barcode_code128('12345')
        assert isinstance(result, str)

    def test_resolve_print_context(self):
        from app.shared.print_context import resolve_print_context

        result = resolve_print_context('invoice')
        assert isinstance(result, dict)
