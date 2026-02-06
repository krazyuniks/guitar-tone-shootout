# Error Report: T29 — green_failed_after_bounce

**Time:** 2026-02-06T03:50:22.600066+00:00
**Phase:** green_failed_after_bounce
**Task:** T29

## Output

```
t are present as
        attributes of the instance's class are allowed. These could be,
        for example, any mapped columns or relationships.
        """
        cls_ = type(self)
        for k in kwargs:
            if not hasattr(cls_, k):
>               raise TypeError(
                    "%r is an invalid keyword argument for %s" % (k, cls_.__name__)
                )
E               TypeError: 'name' is an invalid keyword argument for Shootout

.venv/lib/python3.12/site-packages/sqlalchemy/orm/decl_base.py:2179: TypeError
---------------------------- Captured stdout setup -----------------------------
[FIXTURE] Setting session override: <tests.integration.webapp.conftest._TestAsyncSession object at 0x7f2ffbe5b7d0>
[FIXTURE] pages._session_override is now: <tests.integration.webapp.conftest._TestAsyncSession object at 0x7f2ffbe5b7d0>
----------------------------- Captured stdout call -----------------------------
[HOOK] Setting current user: testuser
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

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/webapp/test_htmx_fragment_endpoints_t29.py::TestLibraryMyGearFragments::test_library_my_gear_list_fragment_shows_only_user_gear
FAILED tests/integration/webapp/test_htmx_fragment_endpoints_t29.py::TestLibraryChainsFragments::test_library_chains_list_fragment_shows_only_user_chains
FAILED tests/integration/webapp/test_htmx_fragment_endpoints_t29.py::TestLibraryShootoutsFragments::test_library_shootouts_list_fragment_returns_html
FAILED tests/integration/webapp/test_htmx_fragment_endpoints_t29.py::TestLibraryShootoutsFragments::test_library_shootouts_list_fragment_shows_only_user_shootouts
FAILED tests/integration/webapp/test_htmx_fragment_endpoints_t29.py::TestLibraryShootoutsFragments::test_library_shootouts_list_fragment_accepts_status_filter
FAILED tests/integration/webapp/test_htmx_fragment_endpoints_t29.py::TestLibraryShootoutsFragments::test_library_shootouts_list_fragment_accepts_pagination
================== 6 failed, 645 passed, 8 warnings in 25.10s ==================
error: Recipe `tdd-green` failed with exit code 1

```
