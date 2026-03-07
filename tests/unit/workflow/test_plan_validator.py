"""Tests for plan_validator — scope coherence, story enrichment, and test spec validation."""

from workflow.models import (
    AgentConfig,
    CheckCriterion,
    CriticalTransition,
    ObservableTruth,
    Plan,
    Scope,
    Story,
    TestAssertion,
    TestSpec,
    UserJourney,
    ValidationCheckpoint,
)
from workflow.plan_validator import (
    _check_acceptance_criteria,
    _check_scope_coherence,
    _check_story_enrichment,
    _check_test_specs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_AGENT = AgentConfig(model="sonnet")

_DEFAULT_TRUTH = ObservableTruth(id=1, statement="placeholder truth")

_DEFAULT_JOURNEY = UserJourney(
    journey_id="J1",
    persona="tester",
    narrative="placeholder journey",
    truths_covered=[1],
    entry_point="/",
    critical_transitions=[
        CriticalTransition(source="/", to="/page", mechanism="click"),
    ],
)

_DEFAULT_CHECKPOINT = ValidationCheckpoint(
    after_story="s1",
    check_type="process",
    checks=[CheckCriterion(criterion="placeholder")],
)


def _make_story(
    story_id: str,
    create: list[str] | None = None,
    modify: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    architectural_context: list[str] | None = None,
    navigation_hints: list[str] | None = None,
    test_spec: TestSpec | None = None,
) -> Story:
    """Build a minimal Story with the given scope and enrichment fields."""
    return Story(
        story_id=story_id,
        name=f"Story {story_id}",
        purpose="test",
        agent=_DEFAULT_AGENT,
        scope=Scope(create=create or [], modify=modify or []),
        acceptance_criteria=acceptance_criteria
        if acceptance_criteria is not None
        else ["placeholder acceptance criterion"],
        architectural_context=architectural_context
        if architectural_context is not None
        else ["placeholder architectural context"],
        navigation_hints=navigation_hints
        if navigation_hints is not None
        else ["placeholder navigation hint"],
        truths_addressed=[1],
        test_spec=test_spec,
    )


def _make_plan(stories: list[Story]) -> Plan:
    """Build a minimal valid Plan containing the given stories."""
    return Plan(
        epic_number=999,
        goal="test goal",
        observable_truths=[_DEFAULT_TRUTH],
        user_journeys=[_DEFAULT_JOURNEY],
        stories=stories,
        validation_checkpoints=[_DEFAULT_CHECKPOINT],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScopeCoherence:
    """Tests for _check_scope_coherence projected filesystem state tracking."""

    def test_modify_existing_file_passes(self) -> None:
        """scope.modify with a file that exists on disk produces no errors."""
        # workflow/plan_validator.py definitely exists relative to PROJECT_ROOT
        plan = _make_plan(
            [
                _make_story("s1", modify=["workflow/plan_validator.py"]),
            ]
        )
        errors = _check_scope_coherence(plan)
        assert errors == []

    def test_modify_nonexistent_file_fails(self) -> None:
        """scope.modify with a path that doesn't exist on disk produces an error."""
        plan = _make_plan(
            [
                _make_story("s1", modify=["nonexistent/path/foo.py"]),
            ]
        )
        errors = _check_scope_coherence(plan)
        assert len(errors) == 1
        assert errors[0].check == "scope_coherence"
        assert "nonexistent/path/foo.py" in errors[0].message
        assert "not created by a prior story" in errors[0].message

    def test_modify_file_created_by_prior_story(self) -> None:
        """Story 2 modifying a file created by Story 1 produces no error."""
        plan = _make_plan(
            [
                _make_story("s1", create=["zzz_new_pkg/foo.py"]),
                _make_story("s2", modify=["zzz_new_pkg/foo.py"]),
            ]
        )
        errors = _check_scope_coherence(plan)
        # Filter to only modify-related errors (ignore create parent dir errors)
        modify_errors = [e for e in errors if "scope.modify" in e.message]
        assert modify_errors == []

    def test_modify_file_created_by_same_story_fails(self) -> None:
        """A story creating AND modifying the same file should fail the modify check.

        The projected state only includes files from PRIOR stories, not the
        current one.
        """
        plan = _make_plan(
            [
                _make_story(
                    "s1",
                    create=["zzz_new_pkg/foo.py"],
                    modify=["zzz_new_pkg/foo.py"],
                ),
            ]
        )
        errors = _check_scope_coherence(plan)
        modify_errors = [e for e in errors if "scope.modify" in e.message]
        assert len(modify_errors) == 1
        assert "zzz_new_pkg/foo.py" in modify_errors[0].message

    def test_create_with_projected_parent_dir(self) -> None:
        """Story 2 creating a file whose parent dir is projected from Story 1."""
        plan = _make_plan(
            [
                _make_story("s1", create=["zzz_new_pkg/__init__.py"]),
                _make_story("s2", create=["zzz_new_pkg/module.py"]),
            ]
        )
        errors = _check_scope_coherence(plan)
        # Story 1 may error on parent (zzz_new_pkg doesn't exist on disk),
        # but Story 2 must NOT error because Story 1 projected zzz_new_pkg/
        s2_errors = [e for e in errors if "s2" in e.message]
        assert s2_errors == []

    def test_create_with_nonexistent_parent_fails(self) -> None:
        """Creating a file whose parent doesn't exist on disk or in projected state fails."""
        plan = _make_plan(
            [
                _make_story("s1", create=["zzz_nonexistent/deep/path/foo.py"]),
            ]
        )
        errors = _check_scope_coherence(plan)
        parent_errors = [e for e in errors if "scope.create" in e.message]
        assert len(parent_errors) == 1
        assert "zzz_nonexistent/deep/path" in parent_errors[0].message
        assert "not created by a prior story" in parent_errors[0].message

    def test_create_projects_ancestor_dirs(self) -> None:
        """Story 1 creating a/b/c/d.py projects ancestor dirs a/, a/b/, a/b/c/.

        Story 2 creating a/b/e.py should pass because a/b/ was projected.
        """
        plan = _make_plan(
            [
                _make_story("s1", create=["zzz_a/b/c/d.py"]),
                _make_story("s2", create=["zzz_a/b/e.py"]),
            ]
        )
        errors = _check_scope_coherence(plan)
        s2_errors = [e for e in errors if "s2" in e.message]
        assert s2_errors == []


class TestAcceptanceCriteria:
    """Tests for _check_acceptance_criteria validation."""

    def test_story_with_acceptance_criteria_passes(self) -> None:
        plan = _make_plan([_make_story("s1")])
        errors = _check_acceptance_criteria(plan)
        assert errors == []

    def test_empty_acceptance_criteria_fails(self) -> None:
        plan = _make_plan([_make_story("s1", acceptance_criteria=[])])
        errors = _check_acceptance_criteria(plan)
        assert len(errors) == 1
        assert errors[0].check == "acceptance_criteria"
        assert "s1" in errors[0].message


class TestStoryEnrichment:
    """Tests for _check_story_enrichment validation."""

    def test_fully_enriched_stories_pass(self) -> None:
        plan = _make_plan(
            [
                _make_story("s1"),
                _make_story("s2"),
            ]
        )
        errors = _check_story_enrichment(plan)
        assert errors == []

    def test_empty_architectural_context_fails(self) -> None:
        plan = _make_plan([_make_story("s1", architectural_context=[])])
        errors = _check_story_enrichment(plan)
        assert len(errors) == 1
        assert errors[0].check == "story_enrichment"
        assert "architectural_context" in errors[0].message
        assert "s1" in errors[0].message

    def test_empty_navigation_hints_fails(self) -> None:
        plan = _make_plan([_make_story("s1", navigation_hints=[])])
        errors = _check_story_enrichment(plan)
        assert len(errors) == 1
        assert errors[0].check == "story_enrichment"
        assert "navigation_hints" in errors[0].message

    def test_multiple_enrichment_errors_reported(self) -> None:
        """All enrichment failures are reported, not just the first."""
        plan = _make_plan(
            [
                _make_story(
                    "s1",
                    architectural_context=[],
                    navigation_hints=[],
                ),
            ]
        )
        errors = _check_story_enrichment(plan)
        assert len(errors) == 2
        checks = {e.message.split("empty ")[1].split(".")[0] for e in errors}
        assert "architectural_context" in checks
        assert "navigation_hints" in checks


class TestTestSpecs:
    """Tests for _check_test_specs validation."""

    def test_missing_test_spec_produces_no_errors(self) -> None:
        """Missing test_spec is a warning (logged), not an error."""
        plan = _make_plan([_make_story("s1")])
        errors = _check_test_specs(plan)
        assert errors == []

    def test_valid_test_spec_passes(self) -> None:
        """A fully valid test_spec produces no errors."""
        spec = TestSpec(
            test_type="integration",
            fixtures=["make_user", "make_shootout(chains=2)"],
            assertions=[
                TestAssertion(
                    type="http_status", details={"route": "/foo", "expected_status": 200}
                ),
                TestAssertion(type="dom_element", details={"selector": "[data-testid='x']"}),
            ],
        )
        plan = _make_plan([_make_story("s1", test_spec=spec)])
        errors = _check_test_specs(plan)
        assert errors == []

    def test_invalid_test_type_fails(self) -> None:
        """test_type must be 'integration' or 'e2e'."""
        spec = TestSpec(test_type="unit", fixtures=[], assertions=[])
        plan = _make_plan([_make_story("s1", test_spec=spec)])
        errors = _check_test_specs(plan)
        assert len(errors) == 1
        assert errors[0].check == "test_spec"
        assert "'unit'" in errors[0].message

    def test_unknown_fixture_fails(self) -> None:
        """Fixture names not in the known catalogue produce errors."""
        spec = TestSpec(
            test_type="integration",
            fixtures=["make_user", "make_nonexistent"],
            assertions=[],
        )
        plan = _make_plan([_make_story("s1", test_spec=spec)])
        errors = _check_test_specs(plan)
        assert len(errors) == 1
        assert "make_nonexistent" in errors[0].message

    def test_fixture_with_args_validated_by_base_name(self) -> None:
        """Fixture args like 'make_shootout(chains=2)' are stripped before lookup."""
        spec = TestSpec(
            test_type="integration",
            fixtures=["make_shootout(chains=2)"],
            assertions=[],
        )
        plan = _make_plan([_make_story("s1", test_spec=spec)])
        errors = _check_test_specs(plan)
        assert errors == []

    def test_invalid_assertion_type_fails(self) -> None:
        """Assertion type must be one of the known types."""
        spec = TestSpec(
            test_type="e2e",
            fixtures=[],
            assertions=[
                TestAssertion(type="screenshot", details={}),
            ],
        )
        plan = _make_plan([_make_story("s1", test_spec=spec)])
        errors = _check_test_specs(plan)
        assert len(errors) == 1
        assert "'screenshot'" in errors[0].message

    def test_multiple_errors_reported(self) -> None:
        """All test_spec errors across stories are reported."""
        spec = TestSpec(
            test_type="bad_type",
            fixtures=["unknown_fixture"],
            assertions=[TestAssertion(type="invalid_type", details={})],
        )
        plan = _make_plan([_make_story("s1", test_spec=spec)])
        errors = _check_test_specs(plan)
        assert len(errors) == 3  # bad test_type + unknown fixture + invalid assertion type


class TestTestAssertionFlatFormat:
    """Tests for TestAssertion flat-format parsing."""

    def test_flat_format_collected_into_details(self) -> None:
        """Extra keys at top level are moved into details."""
        assertion = TestAssertion.model_validate(
            {"type": "http_status", "route": "/foo", "expected_status": 200}
        )
        assert assertion.type == "http_status"
        assert assertion.details == {"route": "/foo", "expected_status": 200}

    def test_nested_format_preserved(self) -> None:
        """Explicit details dict is preserved as-is."""
        assertion = TestAssertion.model_validate(
            {"type": "db_state", "details": {"query": "SELECT 1", "expected": 1}}
        )
        assert assertion.type == "db_state"
        assert assertion.details == {"query": "SELECT 1", "expected": 1}

    def test_flat_format_merges_with_details(self) -> None:
        """Flat keys merge into existing details."""
        assertion = TestAssertion.model_validate(
            {"type": "http_status", "details": {"route": "/foo"}, "auth": "test_user"}
        )
        assert assertion.details == {"route": "/foo", "auth": "test_user"}
