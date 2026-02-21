"""Tests for epic ingest structural validation."""

from workflow.epic_ingest import validate_epic_structure

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
