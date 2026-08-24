"""Core queries service (was 44%)."""


class TestCoreQueries:
    def test_module_import(self):
        from services.core_queries import CoreQueryService

        assert CoreQueryService is not None
