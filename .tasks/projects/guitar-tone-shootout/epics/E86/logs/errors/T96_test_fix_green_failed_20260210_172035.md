# Error Report: T96 — test_fix_green_failed

**Time:** 2026-02-10T17:20:35.409816+00:00
**Phase:** test_fix_green_failed
**Task:** T96

## Output

```
item["gear_model_id"] == str(test_gear_model.id)
        assert item["gear_name"] is not None
        assert item["gear_type"] is not None
    
        # NEW: platform and size fields must be present
>       assert "platform" in item
E       AssertionError: assert 'platform' in {'gear_model_id': 'ffa12699-75e5-4dc1-b112-b40a59c9aaf4', 'gear_name': 'Test Amp', 'gear_type': 'amp', 'id': '1a2b32e2-3f2f-439d-8d30-f39491f689d3', ...}

tests/integration/webapp/test_library_model_level.py:169: AssertionError
---------------------------- Captured stdout setup -----------------------------
[FIXTURE] Setting session override: <tests.integration.webapp.conftest._TestAsyncSession object at 0x7f1926cf3890>
----------------------------- Captured stdout call -----------------------------
[HOOK] Setting current user: testuser
_________ TestLibraryModelLevelAPI.test_toggle_adds_if_not_in_library __________

self = <tests.integration.webapp.test_library_model_level.TestLibraryModelLevelAPI object at 0x7f19278fc510>
authenticated_client = <httpx.AsyncClient object at 0x7f1926b59ba0>
db_session = <tests.integration.webapp.conftest._TestAsyncSession object at 0x7f1926b588a0>
test_user = <webapp.adapters.persistence.models.user.User object at 0x7f1926b59a70>
test_gear_model = <webapp.adapters.persistence.models.gear_model.GearModel object at 0x7f1926b5ab10>

    async def test_toggle_adds_if_not_in_library(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_gear_model: GearModel,
    ) -> None:
        """POST /api/v1/library/gear/{gear_model_id}/toggle adds if not present."""
        # Verify not in library yet
        result = await db_session.execute(
            select(UserGear).where(
                UserGear.user_id == test_user.id,
                UserGear.gear_model_id == test_gear_model.id,
            )
        )
        assert result.scalar_one_or_none() is None
    
        # Toggle (should add)
        response = await authenticated_client.post(
            f"/api/v1/library/gear/{test_gear_model.id}/toggle",
        )
    
>       assert response.status_code == 200
E       assert 404 == 200
E        +  where 404 = <Response [404 Not Found]>.status_code

tests/integration/webapp/test_library_model_level.py:227: AssertionError
---------------------------- Captured stdout setup -----------------------------
[FIXTURE] Setting session override: <tests.integration.webapp.conftest._TestAsyncSession object at 0x7f1926b588a0>
----------------------------- Captured stdout call -----------------------------
[HOOK] Setting current user: testuser
______ TestLibraryModelLevelAPI.test_toggle_removes_if_already_in_library ______

self = <tests.integration.webapp.test_library_model_level.TestLibraryModelLevelAPI object at 0x7f1927afed50>
authenticated_client = <httpx.AsyncClient object at 0x7f1926bfc180>
db_session = <tests.integration.webapp.conftest._TestAsyncSession object at 0x7f1926b5bbb0>
test_user = <webapp.adapters.persistence.models.user.User object at 0x7f1926bfc510>
test_gear_model = <webapp.adapters.persistence.models.gear_model.GearModel object at 0x7f1926bfcfc0>

    async def test_toggle_removes_if_already_in_library(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_gear_model: GearModel,
    ) -> None:
        """POST /api/v1/library/gear/{gear_model_id}/toggle removes if present."""
        # Add to library first
        user_gear = UserGear(
            id=uuid4(),
            user_id=test_user.id,
            gear_model_id=test_gear_model.id,
        )
        db_session.add(user_gear)
        await db_session.commit()
        user_gear_id = user_gear.id
    
        # Toggle (should remove)
        response = await authenticated_client.post(
            f"/api/v1/library/gear/{test_gear_model.id}/toggle",
        )
    
>       assert response.status_code == 200
E       assert 404 == 200
E        +  where 404 = <Response [404 Not Found]>.status_code

tests/integration/webapp/test_library_model_level.py:266: AssertionError
---------------------------- Captured stdout setup -----------------------------
[FIXTURE] Setting session override: <tests.integration.webapp.conftest._TestAsyncSession object at 0x7f1926b5bbb0>
----------------------------- Captured stdout call -----------------------------
[HOOK] Setting current user: testuser
=========================== short test summary info ============================
FAILED tests/integration/webapp/test_library_model_level.py::TestLibraryModelLevelAPI::test_list_returns_platform_and_size
FAILED tests/integration/webapp/test_library_model_level.py::TestLibraryModelLevelAPI::test_toggle_adds_if_not_in_library
FAILED tests/integration/webapp/test_library_model_level.py::TestLibraryModelLevelAPI::test_toggle_removes_if_already_in_library
========================= 3 failed, 6 passed in 0.46s ==========================

```
