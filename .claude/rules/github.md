# GitHub CLI Rules

## Repository Configuration

**Repository:** `krazyuniks/guitar-tone-shootout`

The git remote uses a custom SSH alias (`github_osx:`) which prevents `gh` CLI from auto-detecting the repository owner.

## Mandatory --repo Flag

**ALWAYS** include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands:

```bash
# Issues
gh issue list --repo krazyuniks/guitar-tone-shootout
gh issue view <number> --repo krazyuniks/guitar-tone-shootout
gh issue create --repo krazyuniks/guitar-tone-shootout --title "..."

# Pull Requests
gh pr list --repo krazyuniks/guitar-tone-shootout
gh pr view <number> --repo krazyuniks/guitar-tone-shootout
gh pr create --repo krazyuniks/guitar-tone-shootout --title "..."
gh pr checks <number> --repo krazyuniks/guitar-tone-shootout

# Other
gh api repos/krazyuniks/guitar-tone-shootout/...
```

## Why This Is Required

Without the `--repo` flag, `gh` will fail with:
```
GraphQL: Could not resolve to a Repository with the name 'ryanlauterbach/guitar-tone-shootout'
```

This happens because `gh` cannot parse the SSH alias format `git@github_osx:owner/repo.git`.
