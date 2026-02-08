# Error Report: T44 — test_fix_green_failed

**Time:** 2026-02-08T07:28:46.254999+00:00
**Phase:** test_fix_green_failed
**Task:** T44

## Output

```
Verifying tests pass for T44...
WARNING: No test files found in lock commit 0ee5875ad9d58762960d22d6d0810a443331690c, falling back to full test suite
============================= test session starts ==============================
platform linux -- Python 3.14.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /app
configfile: pyproject.toml
plugins: cov-7.0.0, anyio-4.12.1, asyncio-1.3.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collected 724 items / 3 errors

==================================== ERRORS ====================================
__ ERROR collecting tests/integration/webapp/test_chain_builder_page_route.py __
ImportError while importing test module '/app/tests/integration/webapp/test_chain_builder_page_route.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/local/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/webapp/test_chain_builder_page_route.py:21: in <module>
    from webapp.api.pages import (
E   ImportError: cannot import name 'set_session_override' from 'webapp.api.pages' (/app/apps/webapp/src/webapp/api/pages.py)
______ ERROR collecting tests/integration/webapp/test_shootouts_pages.py _______
ImportError while importing test module '/app/tests/integration/webapp/test_shootouts_pages.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/local/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/webapp/test_shootouts_pages.py:13: in <module>
    from webapp.api.pages import router, set_session_override, set_user_override
E   ImportError: cannot import name 'set_session_override' from 'webapp.api.pages' (/app/apps/webapp/src/webapp/api/pages.py)
_ ERROR collecting tests/integration/webapp/test_signal_chain_builder_api_integration.py _
ImportError while importing test module '/app/tests/integration/webapp/test_signal_chain_builder_api_integration.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/local/lib/python3.14/importlib/__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/integration/webapp/test_signal_chain_builder_api_integration.py:25: in <module>
    from webapp.api.v1.library import set_session_override as set_library_session, set_user_override as set_library_user
E   ImportError: cannot import name 'set_session_override' from 'webapp.api.v1.library' (/app/apps/webapp/src/webapp/api/v1/library.py)
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

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/integration/webapp/test_chain_builder_page_route.py
ERROR tests/integration/webapp/test_shootouts_pages.py
ERROR tests/integration/webapp/test_signal_chain_builder_api_integration.py
!!!!!!!!!!!!!!!!!!! Interrupted: 3 errors during collection !!!!!!!!!!!!!!!!!!!!
======================== 3 warnings, 3 errors in 5.33s =========================
error: Recipe `tdd-green` failed with exit code 2

```
