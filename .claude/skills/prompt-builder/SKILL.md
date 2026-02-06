---
name: prompt-builder
description: Create optimised prompts that another Claude instance can execute. Guides through requirements gathering, generates XML-structured prompts, and saves to .claude/prompts/.
---

# Prompt Builder Skill

**Activation:** Prompt creation, task delegation, sub-agent prompts

## Workflow

### Step 0: Intake Gate

1. **If no task description provided:** Ask what kind of prompt (Coding, Analysis, Research)
2. **Analyse description:** Extract task type, complexity, prompt structure (single vs multiple), execution strategy (parallel vs sequential), depth needed
3. **Ask 2-4 clarifying questions** based on genuine gaps (scope, target, auth method, performance focus, output purpose)
4. **Decision gate:** "Ready to proceed?" -- loop until user confirms

### Step 1: Generate and Save

**Pre-generation analysis:**
1. Single vs multiple prompts
2. Execution strategy (parallel/sequential)
3. Reasoning depth (standard vs extended thinking)
4. Required tools
5. Quality needs ("go beyond basics"?)

**Prompt construction rules -- always include:**
- XML tag structure (`<objective>`, `<context>`, `<requirements>`, `<output>`, `<verification>`)
- Contextual information (why, who, what)
- Explicit, specific instructions
- File output paths (relative)
- Reference to CLAUDE.md
- Success criteria

**Conditionally include:**
- Extended thinking triggers for complex reasoning
- "Go beyond basics" for creative tasks
- WHY explanations for constraints
- Parallel tool calling guidance
- Reflection after tool use
- Examples for ambiguous requirements

**Save to:** `.claude/prompts/[NNN]-[descriptive-name].md`

Check existing prompts with Glob to determine next sequence number.

### Step 2: Decision Tree

After saving, present options based on scenario:

**Single prompt:** Run now, Review first, Save for later

**Multiple parallel prompts:** Run all in parallel, Run sequentially, Review first

**Multiple sequential prompts:** Run all sequentially, Run first only, Review first

Use `/run-prompt` to execute when user chooses to run.

## Prompt Patterns

See `references/prompt-patterns.md` for XML templates for coding, analysis, and research tasks.

## Intelligence Rules

1. **Clarity First:** If unclear, ask before proceeding
2. **Context is Critical:** Include WHY, WHO, WHAT
3. **Be Explicit:** Specific instructions, exact formats
4. **Scope Assessment:** Simple -> concise, Complex -> comprehensive
5. **Precision vs Brevity:** Default to precision
6. **Output Clarity:** Specify exactly where to save outputs
7. **Verification Always:** Include success criteria and verification steps
