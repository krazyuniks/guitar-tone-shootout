"""V2 prompt assembly system.

Builds agent prompts from plan context, skills, and failure feedback
using a 7-section deterministic template architecture. No AI tokens
spent on prompt construction -- the complexity lives in plan.json
(written by Opus), not in the template system.

Reference: Research doc Section 8.5 Decisions 1-7.
No dependency on run_epic.py or any V1 code.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.dispatch import estimate_tokens

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

logger = logging.getLogger(__name__)

# Prompt size budget: under 2,000 tokens (Section 8.5 Decision 4).
# Skill content is injected via system prompt and does not count.
PROMPT_TOKEN_LIMIT = 2000


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RetryContext:
    """Failure feedback for a retry attempt."""

    attempt: int
    error: str
    files_modified: list[str]
    jsonl_excerpt: str


@dataclass
class PromptContext:
    """All context needed to build an agent prompt."""

    plan: dict
    checkpoint: dict | None = None
    retry: RetryContext | None = None


@dataclass
class StorySpec:
    """Story specification extracted from plan.json."""

    story_id: str
    name: str
    purpose: str
    agent: dict = field(default_factory=dict)
    scope: dict = field(default_factory=dict)
    implementation_notes: list[str] = field(default_factory=list)
    truths_addressed: list[int] = field(default_factory=list)
    state_assumption: str = "cumulative"

    @property
    def model(self) -> str:
        return self.agent.get("model", "sonnet")

    @property
    def skills(self) -> list[str]:
        return self.agent.get("skills", [])

    @property
    def tools(self) -> list[str]:
        return self.agent.get("tools", [])

    @property
    def mcp(self) -> list[str]:
        return self.agent.get("mcp", [])

    @property
    def max_turns(self) -> int:
        return self.agent.get("max_turns", 30)

    @property
    def max_budget_usd(self) -> float:
        return self.agent.get("max_budget_usd", 3.0)

    @classmethod
    def from_dict(cls, data: dict) -> "StorySpec":
        """Create a StorySpec from a plan.json story dict."""
        return cls(
            story_id=data["story_id"],
            name=data["name"],
            purpose=data["purpose"],
            agent=data.get("agent", {}),
            scope=data.get("scope", {}),
            implementation_notes=data.get("implementation_notes", []),
            truths_addressed=data.get("truths_addressed", []),
            state_assumption=data.get("state_assumption", "cumulative"),
        )


# ---------------------------------------------------------------------------
# Role templates (Section 8.5 Decision 2, Section 1)
# Short, focused -- ~50-100 words each.
# Domain knowledge comes from skills, not from the role section.
# ---------------------------------------------------------------------------

ROLE_IMPLEMENTATION = """\
# Role: Implementation Agent

You are implementing a story in the GTS codebase. You receive a clear \
scope (files to create/modify), implementation notes, and verification \
criteria. Your job is to write working code that satisfies the criteria.

You do NOT explore the codebase beyond reading exemplar files listed in \
scope. You do NOT plan. You do NOT write tests. You implement the scope, \
verify your work, and commit."""

ROLE_VALIDATION = """\
# Role: Validation Agent

You are checking whether a set of criteria pass or fail. For each \
criterion, perform the check and report the result with concrete evidence.

You do NOT fix anything. You do NOT modify any files. You only observe \
and report. Your output must be structured JSON matching the provided schema."""

ROLE_REGRESSION_TEST = """\
# Role: Regression Test Agent

You are writing regression tests that capture the current working behaviour \
of the system. The product already works -- your tests lock in that behaviour \
as a safety net against future regressions.

Read the existing test patterns, follow the conventions, and write tests \
that verify observable behaviour. Do NOT modify production code."""

ROLE_TEMPLATES: dict[str, str] = {
    "implementation": ROLE_IMPLEMENTATION,
    "validation": ROLE_VALIDATION,
    "regression": ROLE_REGRESSION_TEST,
}


# ---------------------------------------------------------------------------
# Constraint templates (Section 8.5 Decision 2, Section 7)
# ---------------------------------------------------------------------------

CONSTRAINTS_IMPLEMENTATION = """\
# Constraints

- Do NOT create test files. Tests are a separate story.
- Do NOT modify files outside your scope unless fixing an import.
- Do NOT run `just check` or `just test` -- the orchestrator handles validation.
- Do NOT explore the codebase beyond reading exemplar files listed in scope.
- Commit your work when done. The pre-commit hooks handle formatting."""

CONSTRAINTS_VALIDATION = """\
# Constraints

- Do NOT modify any files. You are read-only.
- Do NOT attempt to fix problems you discover.
- Report every criterion as pass or fail with concrete evidence.
- Empty or generic evidence (e.g. "looks good") is not acceptable."""

CONSTRAINTS_REGRESSION_TEST = """\
# Constraints

- Do NOT modify production code. Only create/modify test files.
- Do NOT mock internal services. Test against real services.
- Follow existing test patterns and fixtures in the codebase.
- Commit your work when done. The pre-commit hooks handle formatting."""

CONSTRAINT_TEMPLATES: dict[str, str] = {
    "implementation": CONSTRAINTS_IMPLEMENTATION,
    "validation": CONSTRAINTS_VALIDATION,
    "regression": CONSTRAINTS_REGRESSION_TEST,
}


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _get_agent_role(story: StorySpec) -> str:
    """Determine the agent role from the story specification.

    The role is inferred from the story_id prefix or model:
    - Stories with 'validation' or 'check' in their ID -> validation
    - Stories with 'test' or 'regression' in their ID -> regression
    - Everything else -> implementation
    """
    sid = story.story_id.lower()
    if "validation" in sid or "check" in sid:
        return "validation"
    if "test" in sid or "regression" in sid:
        return "regression"
    return "implementation"


def build_role_section(story: StorySpec) -> str:
    """Section 1: Role template based on agent type."""
    role = _get_agent_role(story)
    return ROLE_TEMPLATES.get(role, ROLE_IMPLEMENTATION)


def build_plan_context_section(story: StorySpec, plan: dict) -> str:
    """Section 2: Epic goal, story purpose, and observable truths.

    Provides the agent with enough context to understand what "done"
    looks like, even for truths it is not directly implementing.
    """
    goal = plan.get("goal", "")
    truths = plan.get("observable_truths", [])

    # Build the addressed truths list
    addressed = []
    for t in truths:
        if t["id"] in story.truths_addressed:
            addressed.append(f"- Truth {t['id']}: {t['statement']}")

    # Build the full truths reference list
    all_truths = []
    for t in truths:
        all_truths.append(f"{t['id']}. {t['statement']}")

    lines = [
        "# Context",
        "",
        "## Goal",
        goal,
        "",
        f"## Story: {story.name}",
        f"**Purpose:** {story.purpose}",
    ]

    if addressed:
        lines.append("")
        lines.append("**Truths Addressed:**")
        lines.extend(addressed)

    if all_truths:
        lines.append("")
        lines.append("## Observable Truths (for reference)")
        lines.extend(all_truths)

    return "\n".join(lines)


def build_scope_section(story: StorySpec) -> str:
    """Section 3: Files to create and modify with instructions.

    This is the most important section -- it tells the agent exactly
    which files to touch. "Follow pattern in X" references are the
    primary mechanism for consistency.
    """
    scope = story.scope
    create = scope.get("create", [])
    modify = scope.get("modify", [])

    if not create and not modify:
        return ""

    lines = ["# Scope"]

    if create:
        lines.append("")
        lines.append("## Create")
        for path in create:
            lines.append(f"- `{path}`")

    if modify:
        lines.append("")
        lines.append("## Modify")
        for path in modify:
            lines.append(f"- `{path}`")

    return "\n".join(lines)


def build_implementation_notes_section(story: StorySpec) -> str:
    """Section 4: Domain-specific hints from the planner.

    Prevents common mistakes without bloating the prompt with entire
    skill files. These are the planner's targeted guidance.
    """
    notes = story.implementation_notes
    if not notes:
        return ""

    lines = ["# Implementation Notes", ""]
    for note in notes:
        lines.append(f"- {note}")

    return "\n".join(lines)


def build_verification_section(story: StorySpec, checkpoint: dict | None) -> str:
    """Section 5: Criteria the agent should check before committing.

    From Anthropic's guidance: "Give Claude a way to verify its work.
    This is the single highest-leverage thing you can do."

    The criteria come from the validation checkpoint that follows this
    story in the plan.
    """
    if not checkpoint:
        return ""

    checks = checkpoint.get("checks", [])
    if not checks:
        return ""

    lines = ["# Verification", "", "After completing your work, verify:"]
    for check in checks:
        criterion = check.get("criterion", "")
        if criterion:
            lines.append(f"- {criterion}")

    return "\n".join(lines)


def build_failure_feedback_section(retry: RetryContext | None) -> str:
    """Section 6: Failure feedback for retry attempts.

    Replaces V1's raw pytest output dump with structured information:
    key error, files modified, and JSONL excerpt. The agent receives
    clear guidance on what to fix.
    """
    if not retry:
        return ""

    lines = [
        "# Previous Attempt Failed",
        "",
        "## Error",
        retry.error,
        "",
        "## Files Modified",
    ]

    for path in retry.files_modified:
        lines.append(f"- `{path}`")

    if retry.jsonl_excerpt:
        lines.append("")
        lines.append("## JSONL Entry")
        lines.append(retry.jsonl_excerpt)

    lines.extend(
        [
            "",
            "## What to Do",
            "Fix the error. The files listed above already exist from the "
            "previous attempt. Read them, understand the error, and correct it.",
        ]
    )

    return "\n".join(lines)


def build_constraints_section(story: StorySpec) -> str:
    """Section 7: What NOT to do."""
    role = _get_agent_role(story)
    return CONSTRAINT_TEMPLATES.get(role, CONSTRAINTS_IMPLEMENTATION)


# ---------------------------------------------------------------------------
# Core prompt builder
# ---------------------------------------------------------------------------


def build_agent_prompt(story: StorySpec, context: PromptContext) -> str:
    """Assemble the complete prompt for an agent invocation.

    Concatenates 7 sections separated by horizontal rules. Empty
    sections are omitted. The total prompt body targets under 2,000
    tokens (skill content is injected via system prompt and does not
    count against this budget).

    Args:
        story: Story specification from plan.json.
        context: Plan context, checkpoint, and optional retry info.

    Returns:
        The assembled prompt string.
    """
    sections = [
        build_role_section(story),
        build_plan_context_section(story, context.plan),
        build_scope_section(story),
        build_implementation_notes_section(story),
        build_verification_section(story, context.checkpoint),
        build_failure_feedback_section(context.retry),
        build_constraints_section(story),
    ]

    prompt = "\n\n---\n\n".join(s for s in sections if s)

    token_count = estimate_tokens(prompt)
    if token_count > PROMPT_TOKEN_LIMIT:
        logger.warning(
            "Prompt exceeds %d token budget: %d tokens for story %s. "
            "Consider reducing implementation notes or scope descriptions.",
            PROMPT_TOKEN_LIMIT,
            token_count,
            story.story_id,
        )

    return prompt


# ---------------------------------------------------------------------------
# Validation agent prompt (Section 8.5 Decision 5)
# Minimal ~100-200 tokens. No skills, no implementation notes.
# ---------------------------------------------------------------------------


def build_validation_prompt(
    checkpoint: dict,
    check_type: str,
) -> str:
    """Build a minimal validation agent prompt.

    Validation agents are fundamentally different from implementation
    agents. They check, they do not build. The prompt is ~100-200 tokens
    combined with --json-schema for structured pass/fail output.

    Args:
        checkpoint: Validation checkpoint dict from plan.json.
        check_type: The check type (http, http+dom, browser+db, etc.).

    Returns:
        Minimal validation prompt string.
    """
    checks = checkpoint.get("checks", [])

    criteria_lines = []
    for i, check in enumerate(checks, 1):
        criterion = check.get("criterion", "")
        criteria_lines.append(f"{i}. {criterion}")

    check_instructions = _check_type_instructions(check_type)

    lines = [
        ROLE_VALIDATION,
        "",
        "---",
        "",
        "# Criteria",
        "",
        *criteria_lines,
        "",
        f"# Check Type: {check_type}",
        "",
        check_instructions,
        "",
        "Report each criterion as pass or fail with evidence.",
        "",
        "---",
        "",
        CONSTRAINTS_VALIDATION,
    ]

    return "\n".join(lines)


def _check_type_instructions(check_type: str) -> str:
    """Return check-type-specific instructions for validation agents."""
    instructions: dict[str, str] = {
        "http": (
            "Make HTTP requests and report status codes, URLs, and "
            "response excerpts as evidence."
        ),
        "http+dom": (
            "Use Chrome DevTools MCP to load the page and inspect the DOM. "
            "Report status codes, URLs, CSS selectors, and element text."
        ),
        "browser+db": (
            "Use Chrome DevTools MCP to perform browser actions, then "
            "query the database to verify state changes. Report actions, "
            "SQL queries, row counts, and sample rows."
        ),
        "api+response": (
            "Make API requests and report status codes, URLs, HTTP methods, "
            "and response body excerpts."
        ),
        "process": (
            "Check that the specified process is running. Report process "
            "name, PID or status, and relevant log excerpts."
        ),
        "screenshot": (
            "Use Chrome DevTools MCP to capture screenshots. Report "
            "screenshot paths and visual observations."
        ),
        "regression": (
            "Run the regression test suite (`just test-golden-path`). "
            "Report the test command, exit code, test count, and failure "
            "count."
        ),
        "quality": (
            "Run quality checks (`just check`). Report the commands run, "
            "exit code, and error count."
        ),
    }
    return instructions.get(check_type, "Perform the checks and report evidence.")


# ---------------------------------------------------------------------------
# Prompt logging (Section 8.5 Decision 6)
# ---------------------------------------------------------------------------


def log_prompt(
    epic_dir: Path,
    story_id: str,
    attempt: int,
    prompt: str,
) -> Path:
    """Save full prompt text to prompt-attempt-N.md for debugging.

    The prompt is the primary debugging artefact when agents fail.
    Stored alongside the story JSONL log.

    Args:
        epic_dir: Path to the epic directory (e.g. .planning/epics/E95).
        story_id: The story identifier.
        attempt: The attempt number (1-based).
        prompt: The full prompt text.

    Returns:
        Path to the saved prompt file.
    """
    story_dir = epic_dir / "stories" / story_id
    story_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = story_dir / f"prompt-attempt-{attempt}.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    logger.info(
        "Prompt logged: %s (%d tokens)",
        prompt_path,
        estimate_tokens(prompt),
    )

    return prompt_path


# ---------------------------------------------------------------------------
# Skill file assembly (Section 8.5 Decision 3)
# ---------------------------------------------------------------------------


def _strip_yaml_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from a markdown document.

    Frontmatter is a block delimited by --- at the start of the file.
    It contains metadata (name, description, context) that is not
    needed at runtime by the agent.

    Args:
        content: Raw markdown content, possibly with frontmatter.

    Returns:
        Content with frontmatter stripped.
    """
    if not content.startswith("---"):
        return content

    # Find the closing --- delimiter
    match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
    if match:
        return content[match.end() :].strip()

    # Malformed frontmatter -- return as-is
    return content


def write_skill_file(story: StorySpec, tmp_dir: Path) -> Path:
    """Assemble skill content into a temp file for system prompt injection.

    Reads SKILL.md files for each skill in the story's skills list,
    strips YAML frontmatter (not needed at runtime), and concatenates
    with separators.

    This is the fallback path when --agents JSON skills field is
    unavailable. The --agents JSON dispatch uses skill names directly.

    Args:
        story: Story specification with a skills list.
        tmp_dir: Temporary directory to write the assembled file.

    Returns:
        Path to the assembled skill file.
    """
    skills_content: list[str] = []

    for skill_name in story.skills:
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        if skill_path.exists():
            raw = skill_path.read_text(encoding="utf-8")
            content = _strip_yaml_frontmatter(raw)
            if content:
                skills_content.append(content)
        else:
            logger.warning(
                "Skill '%s' not found at %s -- skipping",
                skill_name,
                skill_path,
            )

    assembled = "\n\n---\n\n".join(skills_content)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Use a sanitised story name for the filename
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", story.story_id)
    path = tmp_dir / f"skills-{safe_name}.md"
    path.write_text(assembled, encoding="utf-8")

    logger.info(
        "Skill file assembled: %s (%d tokens from %d skills)",
        path,
        estimate_tokens(assembled),
        len(skills_content),
    )

    return path


# ---------------------------------------------------------------------------
# Convenience: find checkpoint for a story
# ---------------------------------------------------------------------------


def find_checkpoint_for_story(plan: dict, story_id: str) -> dict | None:
    """Find the validation checkpoint that follows a given story.

    Args:
        plan: The full plan.json dict.
        story_id: The story to find a checkpoint for.

    Returns:
        Checkpoint dict if one exists after this story, else None.
    """
    for cp in plan.get("validation_checkpoints", []):
        if cp.get("after_story") == story_id:
            return cp
    return None
