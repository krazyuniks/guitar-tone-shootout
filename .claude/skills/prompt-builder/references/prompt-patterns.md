# Prompt Patterns and Templates

## XML Templates by Task Type

### Coding Tasks

```xml
<objective>
[Clear statement of what needs to be built/fixed/refactored]
Explain the end goal and why this matters.
</objective>

<context>
[Project type, tech stack, relevant constraints]
[Who will use this, what it's for]
@[relevant files to examine]
</context>

<requirements>
[Specific functional requirements]
[Performance or quality requirements]
Be explicit about what Claude should do.
</requirements>

<implementation>
[Any specific approaches or patterns to follow]
[What to avoid and WHY - explain the reasoning behind constraints]
</implementation>

<output>
Create/modify files with relative paths:
- `./path/to/file.ext` - [what this file should contain]
</output>

<verification>
Before declaring complete, verify your work:
- [Specific test or check to perform]
- [How to confirm the solution works]
</verification>

<success_criteria>
[Clear, measurable criteria for success]
</success_criteria>
```

### Analysis Tasks

```xml
<objective>
[What needs to be analyzed and why]
[What the analysis will be used for]
</objective>

<data_sources>
@[files or data to analyze]
![relevant commands to gather data]
</data_sources>

<analysis_requirements>
[Specific metrics or patterns to identify]
[Depth of analysis needed - use "thoroughly analyze" for complex tasks]
[Any comparisons or benchmarks]
</analysis_requirements>

<output_format>
[How results should be structured]
Save analysis to: `./analyses/[descriptive-name].md`
</output_format>

<verification>
[How to validate the analysis is complete and accurate]
</verification>
```

### Research Tasks

```xml
<research_objective>
[What information needs to be gathered]
[Intended use of the research]
For complex research, include: "Thoroughly explore multiple sources and consider various perspectives"
</research_objective>

<scope>
[Boundaries of the research]
[Sources to prioritize or avoid]
[Time period or version constraints]
</scope>

<deliverables>
[Format of research output]
[Level of detail needed]
Save findings to: `./research/[topic].md`
</deliverables>

<evaluation_criteria>
[How to assess quality/relevance of sources]
[Key questions that must be answered]
</evaluation_criteria>

<verification>
Before completing, verify:
- [All key questions are answered]
- [Sources are credible and relevant]
</verification>
```

---

## Question Templates for Intake Gate

Use these structured question patterns based on the gap identified during adaptive analysis.

### Ambiguous Scope

Example trigger: "build a dashboard"

- header: "Dashboard type"
- question: "What kind of dashboard is this?"
- options:
  - "Admin dashboard" -- Internal tools, user management, system metrics
  - "Analytics dashboard" -- Data visualisation, reports, business metrics
  - "User-facing dashboard" -- End-user features, personal data, settings

### Unclear Target

Example trigger: "fix the bug"

- header: "Bug location"
- question: "Where does this bug occur?"
- options:
  - "Frontend/UI" -- Visual issues, user interactions, rendering
  - "Backend/API" -- Server errors, data processing, endpoints
  - "Database" -- Queries, migrations, data integrity

### Auth/Security Tasks

- header: "Auth method"
- question: "What authentication approach?"
- options:
  - "JWT tokens" -- Stateless, API-friendly
  - "Session-based" -- Server-side sessions, traditional web
  - "OAuth/SSO" -- Third-party providers, enterprise

### Performance Tasks

- header: "Performance focus"
- question: "What's the main performance concern?"
- options:
  - "Load time" -- Initial render, bundle size, assets
  - "Runtime" -- Memory usage, CPU, rendering performance
  - "Database" -- Query optimisation, indexing, caching

### Output/Deliverable Clarity

- header: "Output purpose"
- question: "What will this be used for?"
- options:
  - "Production code" -- Ship to users, needs polish
  - "Prototype/POC" -- Quick validation, can be rough
  - "Internal tooling" -- Team use, moderate polish

### Question Rules

- Only ask about genuine gaps -- do not ask what is already stated
- Each option needs a description explaining implications
- Prefer options over free-text when choices are knowable
- User can always select "Other" for custom input
- 2-4 questions max per round

---

## Conditional Inclusions

### Extended Thinking Triggers

For complex reasoning tasks, include phrases like:
- "thoroughly analyze"
- "consider multiple approaches"
- "deeply consider"
- "explore multiple solutions"

Do not use for simple, straightforward tasks.

### "Go Beyond Basics" Language

For creative or ambitious tasks:

> "Include as many relevant features as possible. Go beyond the basics to create a fully-featured implementation."

### WHY Explanations for Constraints

In generated prompts, explain WHY constraints matter, not just what they are.

**Instead of:** "Never use ellipses"
**Write:** "Your response will be read aloud, so never use ellipses since text-to-speech can't pronounce them"

### Parallel Tool Calling

For agentic/multi-step workflows:

> "For maximum efficiency, whenever you need to perform multiple independent operations, invoke all relevant tools simultaneously rather than sequentially."

### Reflection After Tool Use

For complex agentic tasks:

> "After receiving tool results, carefully reflect on their quality and determine optimal next steps before proceeding."

### Additional Conditional Tags

| Tag | When to Include |
|-----|-----------------|
| `<research>` | Codebase exploration needed |
| `<validation>` | Task requires verification |
| `<examples>` | Complex or ambiguous requirements |

---

## File Naming Convention

```
.claude/prompts/[NNN]-[descriptive-name].md
```

- Number format: 001, 002, 003, etc.
- Check existing files in `.claude/prompts/` to determine next number
- Name format: lowercase, hyphen-separated, max 5 words
- Example: `.claude/prompts/001-implement-user-authentication.md`
- File should contain ONLY the prompt, no explanations or metadata

---

## Decision Tree After Saving

### Single Prompt

Present options:
1. Run prompt now (invoke `/run-prompt NNN`)
2. Review/edit prompt first
3. Save for later

### Multiple Parallel Prompts

Independent sub-tasks, no shared file modifications:
1. Run all in parallel (`/run-prompt NNN NNN+1 NNN+2 --parallel`)
2. Run sequentially instead
3. Review/edit first

### Multiple Sequential Prompts

Dependencies between prompts, must run in order:
1. Run all sequentially (`/run-prompt NNN NNN+1 NNN+2 --sequential`)
2. Run first only (`/run-prompt NNN`)
3. Review/edit first
