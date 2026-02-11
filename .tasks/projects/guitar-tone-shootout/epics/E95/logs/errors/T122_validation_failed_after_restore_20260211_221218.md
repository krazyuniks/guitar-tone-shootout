# Error Report: T122 — validation_failed_after_restore

**Time:** 2026-02-11T22:12:18.847446+00:00
**Phase:** validation_failed_after_restore
**Task:** T122

## Output

```
15.py::TestT3KProvider::test_t3k_provider_handles_token_exchange_error - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_handles_user_info_error - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_uses_environment_config - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_has_default_api_url - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_token_exchange_includes_all_parameters - Pre-existing: T3K provider API changed
XPASS tests/unit/webapp/test_t3k_provider_t15.py::TestT3KProvider::test_t3k_provider_user_info_includes_authorization_header - Pre-existing: T3K provider API changed
XPASS tests/integration/video/test_remotion_typescript_compilation.py::TestTypeScriptCompilation::test_no_typescript_syntax_errors - Pre-existing: video node_modules not installed in webapp container
XPASS tests/integration/video/test_remotion_typescript_compilation.py::TestTypeScriptCompilation::test_no_typescript_type_errors - Pre-existing: video node_modules not installed in webapp container
XPASS tests/integration/video/test_remotion_typescript_compilation.py::TestRemotionStudioLaunch::test_remotion_config_exists - Pre-existing: video node_modules not installed in webapp container
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
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsDevelopmentMode::test_404_endpoint_raises_not_found_error
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsDevelopmentMode::test_400_endpoint_raises_bad_request_error
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsDevelopmentMode::test_409_endpoint_raises_conflict_error
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsDevelopmentMode::test_422_endpoint_raises_validation_error
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsDevelopmentMode::test_500_endpoint_raises_unhandled_exception
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsDevelopmentMode::test_endpoints_do_not_require_authentication
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsProductionMode::test_404_endpoint_returns_404_in_production
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsProductionMode::test_400_endpoint_returns_404_in_production
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsProductionMode::test_409_endpoint_returns_404_in_production
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsProductionMode::test_422_endpoint_returns_404_in_production
ERROR tests/integration/webapp/test_error_test_endpoints_t122.py::TestErrorEndpointsProductionMode::test_500_endpoint_returns_404_in_production
= 1627 passed, 20 skipped, 113 deselected, 72 xfailed, 33 xpassed, 43 warnings, 11 errors in 64.36s (0:01:04) =
error: Recipe `tdd-green` failed with exit code 1
error: Recipe `tdd-complete` failed with exit code 1

```
