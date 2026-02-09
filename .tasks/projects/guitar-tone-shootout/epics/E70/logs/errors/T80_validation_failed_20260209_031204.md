# Error Report: T80 — validation_failed

**Time:** 2026-02-09T03:12:04.188461+00:00
**Phase:** validation_failed
**Task:** T80

## Output

```
-existing: component not yet implemented
XPASS tests/unit/frontend/test_signal_chain_builder_component.py::TestBuildConfiguration::test_tsconfig_exists - Pre-existing: component not yet implemented
XPASS tests/unit/webapp/test_app_skeleton.py::TestCORSMiddleware::test_cors_headers_present_on_response - Pre-existing: CORS configuration changed
XPASS tests/unit/webapp/test_app_skeleton.py::TestCORSMiddleware::test_options_preflight_works - Pre-existing: CORS configuration changed
XPASS tests/unit/webapp/test_gear_templates_t23.py::TestGearFragmentTemplates::test_gear_fragments_directory_exists - Pre-existing: template structure changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_module_exists - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_has_authorization_url - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_has_token_url - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_has_user_info_url - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_generates_authorization_url - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_generates_authorization_url_with_scope - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_exchanges_code_for_token - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_retrieves_user_info - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_handles_token_exchange_error - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_handles_user_info_error - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_uses_environment_config - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_has_default_api_url - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_token_exchange_includes_all_parameters - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_user_info_includes_authorization_header - Pre-existing: T3K provider API changed
XPASS tests/integration/webapp/test_chain_list_page_route.py::TestLibraryChainsPageRoute::test_library_chains_requires_authentication - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_gear_page_routes.py::TestGearBrowsePageRoute::test_gear_browse_route_returns_html - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_gear_page_routes.py::TestGearBrowsePageRoute::test_gear_browse_renders_base_layout - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_route_returns_html - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_renders_all_fields - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_returns_404_for_nonexistent_slug - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_returns_404_for_non_public_gear - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_renders_base_layout - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_library_page_route.py::TestLibraryMyGearPageRoute::test_library_my_gear_renders_base_layout - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_library_page_route.py::TestLibraryMyGearPageRoute::test_library_my_gear_has_htmx_attributes - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_library_page_route.py::TestLibraryMyGearPageRoute::test_library_my_gear_shows_gear_type_filter - Pre-existing: template assertions need update
=========== 837 passed, 63 xfailed, 31 xpassed, 8 warnings in 39.65s ===========
Tests passing
2. Verifying test files unchanged...
✗ 1 violation(s) detected:
  MODIFIED: tests/unit/worktree/test_video_service_integration_t80.py
    Locked test file modified during implementation
error: Recipe `tdd-complete` failed with exit code 1

```
