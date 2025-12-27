#!/bin/bash
# Skill Auto-Activation Hook (UserPromptSubmit)
#
# Analyzes user prompts and suggests relevant skills to Claude.
# Based on claude-rio pattern for deterministic skill matching.

set -e

# Read the prompt from stdin (JSON format from Claude Code)
INPUT=$(cat)

# Extract the prompt text
PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty')

# Early exit if no prompt
if [ -z "$PROMPT" ]; then
    exit 0
fi

# Path to skill rules
SKILL_RULES=".claude/skill-rules.json"

if [ ! -f "$SKILL_RULES" ]; then
    exit 0
fi

# Convert prompt to lowercase for matching
PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

# Function to count keyword matches
count_matches() {
    local keywords="$1"
    local text="$2"
    local count=0

    for keyword in $keywords; do
        if echo "$text" | grep -qi "\b${keyword}\b" 2>/dev/null; then
            count=$((count + 1))
        fi
    done

    echo "$count"
}

# Read skills from rules file and find matches
SUGGESTIONS=""

# Backend skill
BACKEND_KEYWORDS="backend api endpoint route fastapi sqlalchemy database model schema pydantic alembic migration async await crud repository service auth oauth jwt tone3000 taskiq worker job queue"
BACKEND_MATCHES=$(count_matches "$BACKEND_KEYWORDS" "$PROMPT_LOWER")
if [ "$BACKEND_MATCHES" -gt 0 ]; then
    SUGGESTIONS="${SUGGESTIONS}backend-dev (score: ${BACKEND_MATCHES}), "
fi

# Frontend skill
FRONTEND_KEYWORDS="frontend astro react component island page tailwind css styling layout ui ux typescript tsx jsx hook state props"
FRONTEND_MATCHES=$(count_matches "$FRONTEND_KEYWORDS" "$PROMPT_LOWER")
if [ "$FRONTEND_MATCHES" -gt 0 ]; then
    SUGGESTIONS="${SUGGESTIONS}frontend-dev (score: ${FRONTEND_MATCHES}), "
fi

# Playwright skill
PLAYWRIGHT_KEYWORDS="playwright browser e2e end-to-end automation screenshot selector locator click fill navigate assertion chromium debug trace"
PLAYWRIGHT_MATCHES=$(count_matches "$PLAYWRIGHT_KEYWORDS" "$PROMPT_LOWER")
if [ "$PLAYWRIGHT_MATCHES" -gt 0 ]; then
    SUGGESTIONS="${SUGGESTIONS}playwright (score: ${PLAYWRIGHT_MATCHES}), "
fi

# Pipeline skill
PIPELINE_KEYWORDS="pipeline audio video nam neural amp pedalboard ffmpeg ir impulse response wav flac mp4 processing render di track signal chain tone amp model"
PIPELINE_MATCHES=$(count_matches "$PIPELINE_KEYWORDS" "$PROMPT_LOWER")
if [ "$PIPELINE_MATCHES" -gt 0 ]; then
    SUGGESTIONS="${SUGGESTIONS}pipeline-dev (score: ${PIPELINE_MATCHES}), "
fi

# Testing skill
TESTING_KEYWORDS="test pytest testing unit test integration test fixture mock patch coverage assert parametrize conftest"
TESTING_MATCHES=$(count_matches "$TESTING_KEYWORDS" "$PROMPT_LOWER")
if [ "$TESTING_MATCHES" -gt 0 ]; then
    SUGGESTIONS="${SUGGESTIONS}testing (score: ${TESTING_MATCHES}), "
fi

# Docker skill
DOCKER_KEYWORDS="docker container compose dockerfile service volume network build image postgres redis nginx worker"
DOCKER_MATCHES=$(count_matches "$DOCKER_KEYWORDS" "$PROMPT_LOWER")
if [ "$DOCKER_MATCHES" -gt 0 ]; then
    SUGGESTIONS="${SUGGESTIONS}docker-infra (score: ${DOCKER_MATCHES}), "
fi

# Output suggestions if any matches found
if [ -n "$SUGGESTIONS" ]; then
    # Remove trailing comma and space
    SUGGESTIONS="${SUGGESTIONS%, }"
    echo "SUGGESTED SKILLS: ${SUGGESTIONS}"
    echo ""
    echo "Skills provide domain-specific patterns and best practices."
    echo "Read the relevant SKILL.md files in .claude/skills/ for guidance."
fi
