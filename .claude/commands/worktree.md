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
/worktree auth-status
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
2. Run `/plan <issue>` to brainstorm implementation details
3. Or run `/ralph-plan` to create Ralph PRD artifacts
4. Then `ralph run` to execute
