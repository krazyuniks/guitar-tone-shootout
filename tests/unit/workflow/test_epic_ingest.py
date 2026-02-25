"""Tests for epic ingest structural validation and sub-issues gate."""

from workflow.epic_ingest import check_sub_issues, validate_epic_structure

VALID_BODY = """\
## Summary
A feature that adds gear management.

## Observable Outcomes
- [ ] User can see gear list at /gear
- [ ] User can add new gear

## Decisions
- BC ownership: core
- Approach: standard CRUD

## Regression Boundaries
- Existing navigation must not break
"""


class TestEpicStructureValidation:
    """Test validate_epic_structure()."""

    def test_valid_epic_passes(self):
        errors = validate_epic_structure(VALID_BODY)
        assert errors == []

    def test_missing_section_detected(self):
        body = VALID_BODY.replace("## Decisions", "## Design Choices")
        errors = validate_epic_structure(body)
        assert any("Decisions" in e for e in errors)

    def test_empty_section_detected(self):
        body = """\
## Summary

## Observable Outcomes
- [ ] Something

## Decisions
- A decision

## Regression Boundaries
- Something
"""
        errors = validate_epic_structure(body)
        assert any("empty" in e.lower() for e in errors)

    def test_no_outcomes_checkbox_detected(self):
        body = VALID_BODY.replace("- [ ] ", "- ")
        errors = validate_epic_structure(body)
        assert any("checkbox" in e.lower() for e in errors)

    def test_checkbox_in_other_section_not_counted(self):
        """Checkbox in Decisions should not satisfy Observable Outcomes requirement."""
        body = """\
## Summary
A feature that adds gear management.

## Observable Outcomes
- User can see gear list at /gear

## Decisions
- [ ] BC ownership: core

## Regression Boundaries
- Existing navigation must not break
"""
        errors = validate_epic_structure(body)
        assert any("checkbox" in e.lower() for e in errors)

    def test_multiple_errors_reported(self):
        body = "Nothing here"
        errors = validate_epic_structure(body)
        # Should report missing sections + missing checkboxes
        assert len(errors) >= 4  # At least one per required section


class TestCheckSubIssues:
    """Test check_sub_issues() — uses children list from REST API."""

    def test_no_children_returns_no_errors(self):
        """Issue with no sub-issues passes the gate."""
        errors = check_sub_issues(999, [])
        assert errors == []

    def test_with_children_returns_error(self):
        """Issue with sub-issues is rejected with child details."""
        children = [
            {"number": 130, "title": "Child A", "state": "open"},
            {"number": 131, "title": "Child B", "state": "open"},
        ]
        errors = check_sub_issues(99, children)
        assert len(errors) == 1
        assert "parent with 2 sub-issue(s)" in errors[0]
        assert "#130" in errors[0]
        assert "#131" in errors[0]
        assert "leaf issues" in errors[0]
