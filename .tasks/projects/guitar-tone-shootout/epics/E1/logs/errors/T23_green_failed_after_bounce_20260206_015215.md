# Error Report: T23 — green_failed_after_bounce

**Time:** 2026-02-06T01:52:15.788397+00:00
**Phase:** green_failed_after_bounce
**Task:** T23

## Output

```
o.session.AsyncSession object at 0x7fece533d0d0>
=============================== warnings summary ===============================
tests/unit/webapp/test_gear_templates_t23.py:10
  /app/tests/unit/webapp/test_gear_templates_t23.py:10: PytestUnknownMarkWarning: Unknown pytest.mark.unit - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.unit

tests/unit/webapp/test_gear_templates_t23.py:72
  /app/tests/unit/webapp/test_gear_templates_t23.py:72: PytestUnknownMarkWarning: Unknown pytest.mark.unit - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.unit

tests/unit/webapp/test_gear_templates_t23.py:133
  /app/tests/unit/webapp/test_gear_templates_t23.py:133: PytestUnknownMarkWarning: Unknown pytest.mark.unit - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.unit

tests/unit/webapp/test_orm_base.py::TestUUIDMixin::test_uuid_mixin_generates_uuidv7
  /app/tests/unit/webapp/test_orm_base.py:51: SAWarning: This declarative base already contains a class with the same class name and module name as test_orm_base.TestModel, and will be replaced in the string-lookup table.
    class TestModel(UUIDMixin, Base):

tests/unit/webapp/test_orm_base.py::TestTimestampMixin::test_timestamp_mixin_adds_columns
  /app/tests/unit/webapp/test_orm_base.py:77: SAWarning: This declarative base already contains a class with the same class name and module name as test_orm_base.TestModel, and will be replaced in the string-lookup table.
    class TestModel(TimestampMixin, Base):

tests/unit/webapp/test_orm_base.py::TestTimestampMixin::test_timestamp_mixin_sets_created_at
  /app/tests/unit/webapp/test_orm_base.py:87: SAWarning: This declarative base already contains a class with the same class name and module name as test_orm_base.TestModel, and will be replaced in the string-lookup table.
    class TestModel(TimestampMixin, Base):

tests/unit/webapp/test_orm_base.py::TestTimestampMixin::test_timestamp_mixin_sets_updated_at
  /app/tests/unit/webapp/test_orm_base.py:110: SAWarning: This declarative base already contains a class with the same class name and module name as test_orm_base.TestModel, and will be replaced in the string-lookup table.
    class TestModel(TimestampMixin, Base):

tests/unit/webapp/test_orm_base.py::TestEnumByValue::test_enum_by_value_stores_value_not_name
  /app/tests/unit/webapp/test_orm_base.py:140: SAWarning: This declarative base already contains a class with the same class name and module name as test_orm_base.TestModel, and will be replaced in the string-lookup table.
    class TestModel(Base):

tests/integration/audio/test_processor.py::TestProcessDITrack::test_process_di_track_basic
  /app/.venv/lib/python3.12/site-packages/pyloudnorm/normalize.py:62: UserWarning: Possible clipped samples in output.
    warnings.warn("Possible clipped samples in output.")

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearBrowsePageRoute::test_gear_browse_route_returns_html
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearBrowsePageRoute::test_gear_browse_renders_base_layout
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearBrowsePageRoute::test_gear_browse_includes_filter_controls
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearBrowsePageRoute::test_gear_browse_has_htmx_attributes
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_route_returns_html
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_renders_all_fields
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_returns_404_for_nonexistent_slug
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_returns_404_for_non_public_gear
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_renders_base_layout
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearDetailPageRoute::test_gear_detail_includes_back_link
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearHTMXFragments::test_gear_list_fragment_endpoint_exists
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearHTMXFragments::test_gear_list_fragment_accepts_filters
FAILED tests/integration/webapp/test_gear_page_routes.py::TestGearHTMXFragments::test_gear_list_fragment_accepts_search_query
================= 13 failed, 474 passed, 9 warnings in 18.88s ==================
error: Recipe `tdd-green` failed with exit code 1

```
