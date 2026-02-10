# Error Report: T94 — test_fix_green_failed

**Time:** 2026-02-10T16:52:41.539361+00:00
**Phase:** test_fix_green_failed
**Task:** T94

## Output

```
ration/webapp/test_signal_chain_group_permutations.py:438: AttributeError
---------------------------- Captured stdout setup -----------------------------
[FIXTURE] Setting session override: <tests.integration.webapp.conftest._TestAsyncSession object at 0x7f37d62af6f0>
----------------------------- Captured stdout call -----------------------------
[HOOK] Setting current user: testuser
_ TestGeneratePermutationsAPI.test_generate_returns_error_for_too_many_permutations _

self = <tests.integration.webapp.test_signal_chain_group_permutations.TestGeneratePermutationsAPI object at 0x7f37d7117410>
authenticated_client = <httpx.AsyncClient object at 0x7f37d6cea5d0>
db_session = <tests.integration.webapp.conftest._TestAsyncSession object at 0x7f37d61686e0>
test_user = <webapp.adapters.persistence.models.user.User object at 0x7f37d61a0750>
base_chain = <webapp.adapters.persistence.models.signal_chain.SignalChain object at 0x7f37d5fb4550>

    async def test_generate_returns_error_for_too_many_permutations(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        base_chain: SignalChain,
    ) -> None:
        """Test that API returns error when exceeding max_permutations."""
        # Create group that exceeds limit
        group = SignalChainGroup(
            id=uuid4(),
            user_id=test_user.id,
            name="Too Many",
            base_chain_id=base_chain.id,
            slot_positions=[0, 1, 2],
            gear_options={
                0: [uuid4() for _ in range(4)],
                1: [uuid4() for _ in range(4)],
                2: [uuid4() for _ in range(4)],
            },
            include_null=False,
            max_permutations=27,
        )
    
        from webapp.adapters.persistence.models.signal_chain import (
            SignalChainGroup as SignalChainGroupModel,
        )
    
        # Convert gear_options dict[int, list[UUID]] to dict[int, list[str]] for ORM
        gear_options_str: dict[int, list[str]] = {}
        for pos, gear_ids in group.gear_options.items():
            gear_options_str[pos] = [str(gear_id) for gear_id in gear_ids]
    
        model = SignalChainGroupModel(
            id=group.id,
            user_id=group.user_id,
            name=group.name,
            description=group.description,
            base_chain_id=group.base_chain_id,
            slot_positions=group.slot_positions,
            gear_options=gear_options_str,
            include_null=group.include_null,
            created_at=group.created_at,
            updated_at=group.updated_at,
        )
        db_session.add(model)
        await db_session.flush()
    
        response = await authenticated_client.post(
            f"/api/v1/signal-chain-groups/{group.id}/generate",
        )
    
        # Should return error status (400 or 422)
>       assert response.status_code in (400, 422)
E       assert 404 in (400, 422)
E        +  where 404 = <Response [404 Not Found]>.status_code

tests/integration/webapp/test_signal_chain_group_permutations.py:607: AssertionError
---------------------------- Captured stdout setup -----------------------------
[FIXTURE] Setting session override: <tests.integration.webapp.conftest._TestAsyncSession object at 0x7f37d61686e0>
----------------------------- Captured stdout call -----------------------------
[HOOK] Setting current user: testuser
=========================== short test summary info ============================
ERROR tests/integration/webapp/test_signal_chain_group_permutations.py::TestSignalChainGroupPermutations::test_generates_2x2_permutations
ERROR tests/integration/webapp/test_signal_chain_group_permutations.py::TestSignalChainGroupPermutations::test_chain_naming_includes_group_name
ERROR tests/integration/webapp/test_signal_chain_group_permutations.py::TestSignalChainGroupPermutations::test_chains_created_via_signal_chain_service
ERROR tests/integration/webapp/test_signal_chain_group_permutations.py::TestGeneratePermutationsAPI::test_generate_endpoint_exists
ERROR tests/integration/webapp/test_signal_chain_group_permutations.py::TestGeneratePermutationsAPI::test_generate_returns_chain_ids
ERROR tests/integration/webapp/test_signal_chain_group_permutations.py::TestGeneratePermutationsAPI::test_generate_requires_authentication
ERROR tests/integration/webapp/test_signal_chain_group_permutations.py::TestGeneratePermutationsAPI::test_generate_enforces_ownership
FAILED tests/integration/webapp/test_signal_chain_group_permutations.py::TestSignalChainGroupPermutations::test_generate_permutations_method_exists
FAILED tests/integration/webapp/test_signal_chain_group_permutations.py::TestSignalChainGroupPermutations::test_includes_null_option_when_enabled
FAILED tests/integration/webapp/test_signal_chain_group_permutations.py::TestGeneratePermutationsAPI::test_generate_returns_error_for_too_many_permutations
==================== 3 failed, 1 passed, 7 errors in 0.87s =====================

```
