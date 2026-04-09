# /worktree - Git Worktree Management

Alias to `./worktree.py` for managing git worktrees.

## Usage

```
/worktree <command> [arguments]
```

## Commands

Pass any arguments directly to `worktree.py`:

```bash
./worktree.py $ARGUMENTS
```

## Common Examples

### Setup a new worktree from GitHub issue
```
/worktree setup 441
/worktree setup https://github.com/krazyuniks/guitar-tone-shootout/issues/441
```

### List all worktrees
```
/worktree list
```

### Teardown a worktree
```
/worktree teardown 441
```

### Check auth status
```
just t3k-auth-status
```

### Start services in current worktree
```
/worktree start
```

## Help

For full command reference:
```
/worktree --help
```

Or see the global `/worktree` skill for detailed documentation.

## After Setup

Once your worktree is created:
1. `cd` into the new worktree directory
2. If the discovery workflow is available, run `/epic discover <N>` before unfamiliar work
3. Otherwise, implement directly from the GitHub issue — the worktree is your isolated workspace
