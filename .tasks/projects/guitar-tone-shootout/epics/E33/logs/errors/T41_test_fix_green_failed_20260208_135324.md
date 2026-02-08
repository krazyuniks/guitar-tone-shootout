# Error Report: T41 — test_fix_green_failed

**Time:** 2026-02-08T13:53:24.891859+00:00
**Phase:** test_fix_green_failed
**Task:** T41

## Output

```
e:
        """Verify get_public() uses ID-subquery pattern for pagination.
    
        Citation: .claude/rules/query-patterns.md:73-98
        Acceptance Criteria: T41 - query count = 2, correct entity count
    
        Tests that get_public() uses two-step ID-subquery pattern:
        1. ID query: SELECT Shootout.id ... WHERE is_processed = true LIMIT X OFFSET Y
        2. Hydration query: SELECT Shootout.* ... WHERE Shootout.id IN (...) with joinedload
    
        Expected: 2 SQL queries total (ID subquery + hydration query).
        This avoids pagination issues where LIMIT/OFFSET on joined rows
        limits rows instead of entities.
        """
        # Create test data: 10 processed shootouts with di_track and chains
        from datetime import UTC, datetime
    
        # First, create users for the shootouts
        from webapp.adapters.persistence.models.user import User
        test_user = User(
            id=uuid4(),
            username="test_user",
            email="test@example.com",
        )
        db_session.add(test_user)
    
        # Create DI tracks
        from webapp.adapters.persistence.models.shootout import DITrack
        di_tracks = []
        for i in range(10):
            di_track = DITrack(
                id=uuid4(),
                user_id=test_user.id,
                name=f"DI Track {i:02d}",
                file_path=f"/audio/di-track-{i}.wav",
                original_filename=f"di-track-{i}.wav",
                duration_seconds=30.0,
                sample_rate=44100,
            )
            db_session.add(di_track)
            di_tracks.append(di_track)
    
        # Create signal chains for shootout chains
        from core.domain.value_objects.signal_chain_enums import Platform
        from webapp.adapters.persistence.models.signal_chain import SignalChain
        signal_chains = []
        for i in range(20):  # 20 chains total (2 per shootout)
            chain = SignalChain(
                id=uuid4(),
                user_id=test_user.id,
                name=f"Signal Chain {i:02d}",
                platform=Platform.NAM,
            )
            db_session.add(chain)
            signal_chains.append(chain)
    
        # Create 10 processed shootouts
        from webapp.adapters.persistence.models.shootout import Shootout, ShootoutStatus
        for i in range(10):
            shootout_entity = ShootoutEntity(
                id=uuid4(),
                user_id=test_user.id,
                name=f"Test Shootout {i:02d}",
                di_track_id=di_tracks[i].id,
                description=f"Test shootout {i}",
            )
            # Mark as processed (required for get_public)
            shootout_entity.mark_processed(output_path=f"/videos/shootout-{i}.mp4")
    
            # Add 2 chains to each shootout (creates 1:N relationship for joins)
            chain1 = ShootoutChainVO(
                id=uuid4(),
                shootout_id=shootout_entity.id,
                signal_chain_id=signal_chains[i * 2].id,
                position=0,
                label=f"Chain A-{i}",
            )
            chain2 = ShootoutChainVO(
                id=uuid4(),
                shootout_id=shootout_entity.id,
                signal_chain_id=signal_chains[i * 2 + 1].id,
                position=1,
                label=f"Chain B-{i}",
            )
            shootout_entity.add_chain(chain1)
            shootout_entity.add_chain(chain2)
    
            await shootout_repository.save(shootout_entity)
    
        await db_session.commit()
    
        # Expire all objects to force fresh queries
        db_session.expire_all()
    
        # Execute get_public with pagination
        with QueryCounter(db_engine) as counter:
            results = await shootout_repository.get_public(
                limit=5,
                offset=0,
            )
    
        # Acceptance Criteria: query count = 2 (ID subquery + hydration query)
>       assert counter.count == 2, f"Expected 2 queries (ID + hydration), got {counter.count}"
E       AssertionError: Expected 2 queries (ID + hydration), got 1
E       assert 1 == 2
E        +  where 1 = <test_shootout_repository.QueryCounter object at 0x7f345660b380>.count

tests/integration/webapp/repositories/test_shootout_repository.py:181: AssertionError
---------------------------- Captured stdout setup -----------------------------
[FIXTURE] Setting session override: <sqlalchemy.ext.asyncio.session.AsyncSession object at 0x7f3456645550>
----------------------------- Captured stdout call -----------------------------
[QUERY 1] SELECT anon_1.user_id, anon_1.di_track_id, anon_1.name, anon_1.description, anon_1.status, anon_1.vi...
=========================== short test summary info ============================
FAILED tests/integration/webapp/repositories/test_shootout_repository.py::test_shootout_get_public_single_query_with_pagination
============================== 1 failed in 0.20s ===============================

```
