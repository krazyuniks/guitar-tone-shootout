# Error Report: T90 — test_fix_green_failed

**Time:** 2026-02-10T15:48:30.907171+00:00
**Phase:** test_fix_green_failed
**Task:** T90

## Output

```
(router)
    
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/di-tracks/{wav_track.id}/stream")
    
>       assert response.status_code == 200
E       assert 404 == 200
E        +  where 404 = <Response [404 Not Found]>.status_code

tests/integration/webapp/test_di_track_stream.py:289: AssertionError
---------------------------- Captured stdout setup -----------------------------
[FIXTURE] Setting session override: <tests.integration.webapp.conftest._TestAsyncSession object at 0x7fa4cdfee3f0>
----------------------------- Captured stdout call -----------------------------
[HOOK] Setting current user: testuser
________ TestDITrackStreamEndpoint.test_stream_requires_authentication _________

self = <tests.integration.webapp.test_di_track_stream.TestDITrackStreamEndpoint object at 0x7fa4cedc6c50>
db_session = <tests.integration.webapp.conftest._TestAsyncSession object at 0x7fa4ce06e140>
wav_track = <webapp.adapters.persistence.models.shootout.DITrack object at 0x7fa4ce06e690>

    async def test_stream_requires_authentication(
        self,
        db_session: AsyncSession,
        wav_track: DITrack,
    ) -> None:
        """Test stream endpoint requires authentication."""
        from fastapi import FastAPI
        from webapp.auth.dependencies import set_user_override
    
        # Clear user override to simulate unauthenticated request
        set_user_override(None)
    
        app = FastAPI()
        app.include_router(router)
    
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/di-tracks/{wav_track.id}/stream")
    
        # Should return 401 Unauthorized
>       assert response.status_code == 401
E       assert 404 == 401
E        +  where 404 = <Response [404 Not Found]>.status_code

tests/integration/webapp/test_di_track_stream.py:360: AssertionError
---------------------------- Captured stdout setup -----------------------------
[FIXTURE] Setting session override: <tests.integration.webapp.conftest._TestAsyncSession object at 0x7fa4ce06e140>
----------------------------- Captured stdout call -----------------------------
[HOOK] Setting current user: testuser
___ TestDITrackStreamEndpoint.test_stream_returns_file_response_with_headers ___

self = <tests.integration.webapp.test_di_track_stream.TestDITrackStreamEndpoint object at 0x7fa4cedc6e50>
db_session = <tests.integration.webapp.conftest._TestAsyncSession object at 0x7fa4cde9e950>
test_user = <webapp.adapters.persistence.models.user.User object at 0x7fa4cde9e550>
wav_track = <webapp.adapters.persistence.models.shootout.DITrack object at 0x7fa4ce06e250>

    async def test_stream_returns_file_response_with_headers(
        self,
        db_session: AsyncSession,
        test_user: User,
        wav_track: DITrack,
    ) -> None:
        """Test stream returns FileResponse with correct headers for audio streaming."""
        from fastapi import FastAPI
    
        app = FastAPI()
        app.include_router(router)
    
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/di-tracks/{wav_track.id}/stream")
    
>       assert response.status_code == 200
E       assert 404 == 200
E        +  where 404 = <Response [404 Not Found]>.status_code

tests/integration/webapp/test_di_track_stream.py:380: AssertionError
---------------------------- Captured stdout setup -----------------------------
[FIXTURE] Setting session override: <tests.integration.webapp.conftest._TestAsyncSession object at 0x7fa4cde9e950>
----------------------------- Captured stdout call -----------------------------
[HOOK] Setting current user: testuser
=========================== short test summary info ============================
FAILED tests/integration/webapp/test_di_track_stream.py::TestDITrackStreamEndpoint::test_stream_wav_returns_correct_content_type
FAILED tests/integration/webapp/test_di_track_stream.py::TestDITrackStreamEndpoint::test_stream_flac_returns_correct_content_type
FAILED tests/integration/webapp/test_di_track_stream.py::TestDITrackStreamEndpoint::test_stream_ogg_returns_correct_content_type
FAILED tests/integration/webapp/test_di_track_stream.py::TestDITrackStreamEndpoint::test_stream_mp3_returns_correct_content_type
FAILED tests/integration/webapp/test_di_track_stream.py::TestDITrackStreamEndpoint::test_stream_owner_can_access_track
FAILED tests/integration/webapp/test_di_track_stream.py::TestDITrackStreamEndpoint::test_stream_requires_authentication
FAILED tests/integration/webapp/test_di_track_stream.py::TestDITrackStreamEndpoint::test_stream_returns_file_response_with_headers
========================= 7 failed, 2 passed in 0.47s ==========================

```
