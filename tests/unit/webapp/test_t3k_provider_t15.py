"""Unit tests for T3K OAuth provider implementation (T15)."""


class TestT3KProviderInit:
    """Test T3K provider __init__.py exports."""

    def test_providers_module_exists(self) -> None:
        """Test providers package can be imported."""
        import webapp.auth.providers

        assert webapp.auth.providers is not None

    def test_t3k_provider_exported_from_providers_init(self) -> None:
        """Test T3KProvider is exported from providers package."""
        from webapp.auth.providers import T3KProvider

        assert T3KProvider is not None
