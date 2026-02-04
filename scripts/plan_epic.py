#!/usr/bin/env python3
"""
Plan an epic by breaking it into well-structured GitHub issues.

Usage:
    python scripts/plan_epic.py 42

Or via just:
    just plan 42
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# GTS repository - required for gh commands due to SSH alias
REPO = "krazyuniks/guitar-tone-shootout"


def get_epic(epic_number: int) -> dict:
    """Fetch epic from GitHub."""
    result = subprocess.run(
        ["gh", "issue", "view", str(epic_number),
         "--repo", REPO,
         "--json", "title,body,labels,state"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"Error fetching epic #{epic_number}: {result.stderr}")
        sys.exit(1)

    return json.loads(result.stdout)


def build_planner_prompt(epic: dict, epic_number: int) -> str:
    """Build prompt for planner agent."""

    return f"""You are the PLANNER agent. Your job is to break this epic into well-structured GitHub issues.

## Epic #{epic_number}: {epic['title']}

{epic['body']}

---

## Your Task

1. Analyse this epic and identify 3-7 discrete tasks
2. For each task, create a GitHub issue using `gh issue create`
3. Ensure each issue has: Objective, Acceptance Criteria, Scope, Dependencies
4. Update the epic with links to created tasks

## Issue Creation Command

IMPORTANT: Always include `--repo {REPO}` with all gh commands.

```bash
gh issue create \\
  --repo {REPO} \\
  --title "[Task]: <title>" \\
  --label "task" \\
  --body "<body with all sections>"
```

## Requirements

- Each task should be 2-4 hours of work
- Acceptance criteria must be testable (will become pytest tests)
- Scope must specify exact file paths
- Dependencies reference other task numbers

## Begin

Read the epic above and create the tasks now. Use bash to run gh commands.
After creating all tasks, update epic #{epic_number} with the task list.
"""


def run_planner(epic_number: int):
    """Run the planner agent on an epic."""

    epic = get_epic(epic_number)

    # Check if epic label
    labels = [l['name'] for l in epic.get('labels', [])]
    if 'epic' not in labels:
        print(f"Warning: Issue #{epic_number} doesn't have 'epic' label")

    prompt = build_planner_prompt(epic, epic_number)

    # Write prompt to temp file for claude
    prompt_file = Path(f"/tmp/plan-epic-{epic_number}.md")
    prompt_file.write_text(prompt)

    print(f"Planning epic #{epic_number}: {epic['title']}")
    print("=" * 60)
    print()

    # Invoke Claude with planner agent via wrapper script
    script_dir = Path(__file__).parent
    wrapper = script_dir / "claude-agent.sh"

    result = subprocess.run(
        [str(wrapper), "planner", "--print", "-f", str(prompt_file)],
        text=True
    )

    if result.returncode != 0:
        print("\nPlanner finished with errors")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Planning complete!")
    print(f"\nNext steps:")
    print(f"  just epic-sync {epic_number}   # Sync to .tasks/")
    print(f"  just epic-start {epic_number}  # Begin execution")


def main():
    parser = argparse.ArgumentParser(description="Plan an epic into tasks")
    parser.add_argument("epic", type=int, help="Epic issue number")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Show prompt without running")
    
    args = parser.parse_args()
    
    if args.dry_run:
        epic = get_epic(args.epic)
        print(build_planner_prompt(epic, args.epic))
    else:
        run_planner(args.epic)


if __name__ == "__main__":
    main()
