# Error Report: T137 — green_failed_after_bounce

**Time:** 2026-02-12T05:06:44.426257+00:00
**Phase:** green_failed_after_bounce
**Task:** T137

## Output

```
t_app_skeleton.py::TestCORSMiddleware::test_options_preflight_works - Pre-existing: CORS configuration changed
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
FAILED tests/unit/webapp/test_shootout_comment_model.py::TestShootoutCommentCascadeDelete::test_deleting_shootout_cascades_to_comments
= 1 failed, 1957 passed, 19 skipped, 124 deselected, 74 xfailed, 33 xpassed, 44 warnings in 89.02s (0:01:29) =
error: Recipe `tdd-green` failed with exit code 1

```
