# Error Report: T89 — full_suite_green_failed

**Time:** 2026-02-10T15:38:40.129002+00:00
**Phase:** full_suite_green_failed
**Task:** T89

## Output

```
t_t3k_provider_retrieves_user_info - Pre-existing: T3K provider API changed
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
XPASS tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_returns_404_for_nonexistent_slug - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_returns_404_for_non_public_gear - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_library_page_route.py::TestLibraryMyGearPageRoute::test_library_my_gear_renders_base_layout - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_library_page_route.py::TestLibraryMyGearPageRoute::test_library_my_gear_has_htmx_attributes - Pre-existing: template assertions need update
XPASS tests/integration/webapp/test_library_page_route.py::TestLibraryMyGearPageRoute::test_library_my_gear_shows_gear_type_filter - Pre-existing: template assertions need update
FAILED tests/integration/webapp/test_htmx_fragment_endpoints_t29.py::TestLibraryShootoutsFragments::test_library_shootouts_list_fragment_returns_html
FAILED tests/integration/webapp/test_htmx_fragment_endpoints_t29.py::TestLibraryShootoutsFragments::test_library_shootouts_list_fragment_shows_only_user_shootouts
FAILED tests/integration/webapp/test_htmx_fragment_endpoints_t29.py::TestLibraryShootoutsFragments::test_library_shootouts_list_fragment_accepts_status_filter
FAILED tests/integration/webapp/test_signal_chain_builder_api_integration.py::TestLibraryAPIForBuilder::test_list_user_gear_returns_items
FAILED tests/integration/webapp/test_signal_chain_builder_api_integration.py::TestLibraryAPIForBuilder::test_library_includes_all_gear_types
FAILED tests/integration/webapp/test_signal_chain_builder_api_integration.py::TestSignalChainAPIForBuilder::test_create_chain_with_blocks
FAILED tests/integration/webapp/test_signal_chain_builder_api_integration.py::TestSignalChainAPIForBuilder::test_update_chain_replaces_blocks
FAILED tests/integration/webapp/test_signal_chain_builder_api_integration.py::TestSignalChainAPIForBuilder::test_list_user_chains
FAILED tests/integration/webapp/test_signal_chain_builder_api_integration.py::TestSignalChainAPIForBuilder::test_delete_chain
FAILED tests/integration/webapp/test_signal_chain_builder_api_integration.py::TestBuilderPermutationMode::test_create_chain_with_multiple_gear_at_same_position
FAILED tests/integration/webapp/test_signal_chain_builder_api_integration.py::TestBuilderValidation::test_chain_requires_name
FAILED tests/integration/webapp/test_signal_chain_builder_api_integration.py::TestBuilderValidation::test_chain_requires_valid_platform
FAILED tests/integration/webapp/test_signal_chain_builder_api_integration.py::TestBuilderValidation::test_block_requires_valid_gear_type
= 13 failed, 898 passed, 13 skipped, 16 deselected, 74 xfailed, 31 xpassed, 9 warnings in 39.41s =
error: Recipe `tdd-green` failed with exit code 1

```
