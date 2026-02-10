# Error Report: T99 — validation_failed

**Time:** 2026-02-10T18:16:08.367019+00:00
**Phase:** validation_failed
**Task:** T99

## Output

```
provider_generates_authorization_url - Pre-existing: T3K provider API changed
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
FAILED tests/integration/backend/frontend/test_shootout_detail_preprocessing_build.py::TestShootoutDetailPreProcessingBuild::test_detail_fragment_has_di_track_section
FAILED tests/integration/backend/frontend/test_shootout_detail_preprocessing_build.py::TestShootoutDetailPreProcessingBuild::test_di_track_section_has_audio_player
FAILED tests/integration/backend/frontend/test_shootout_detail_preprocessing_build.py::TestShootoutDetailPreProcessingBuild::test_di_track_section_shows_track_metadata
FAILED tests/integration/backend/frontend/test_shootout_detail_preprocessing_build.py::TestShootoutDetailPreProcessingBuild::test_audio_player_uses_stream_endpoint_pattern
FAILED tests/integration/backend/frontend/test_shootout_detail_preprocessing_build.py::TestShootoutDetailPreProcessingBuild::test_all_required_testids_present
= 5 failed, 1014 passed, 13 skipped, 16 deselected, 71 xfailed, 34 xpassed, 8 warnings in 43.02s =
error: Recipe `tdd-green` failed with exit code 1
error: Recipe `tdd-complete` failed with exit code 1

```
