# Error Report: T138 — validation_failed_after_restore

**Time:** 2026-02-12T05:49:19.983967+00:00
**Phase:** validation_failed_after_restore
**Task:** T138

## Output

```
ed
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
ERROR tests/integration/webapp/test_shootout_comments_api.py::TestCreateComment::test_create_comment_returns_201
ERROR tests/integration/webapp/test_shootout_comments_api.py::TestCreateComment::test_create_comment_includes_author_info
ERROR tests/integration/webapp/test_shootout_comments_api.py::TestCreateComment::test_create_comment_persists_to_database
ERROR tests/integration/webapp/test_shootout_comments_api.py::TestCreateComment::test_create_comment_returns_422_for_empty_content
ERROR tests/integration/webapp/test_shootout_comments_api.py::TestCreateComment::test_create_comment_returns_422_for_too_long_content
ERROR tests/integration/webapp/test_shootout_comments_api.py::TestCreateComment::test_create_comment_requires_authentication
ERROR tests/integration/webapp/test_shootout_comments_api.py::TestListComments::test_list_comments_returns_200
ERROR tests/integration/webapp/test_shootout_comments_api.py::TestListComments::test_list_comments_requires_authentication
ERROR tests/integration/webapp/test_shootout_comments_api.py::TestDeleteComment::test_delete_comment_returns_404_for_missing_comment
ERROR tests/integration/webapp/test_shootout_comments_api.py::TestDeleteComment::test_delete_comment_requires_authentication
= 1992 passed, 19 skipped, 130 deselected, 74 xfailed, 33 xpassed, 45 warnings, 10 errors in 91.84s (0:01:31) =
error: Recipe `tdd-green` failed with exit code 1
error: Recipe `tdd-complete` failed with exit code 1

```
