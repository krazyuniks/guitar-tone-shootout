# /worktree-teardown - Remove Worktree

Tear down a worktree and clean up all resources.

## Usage

```
/worktree-teardown <worktree-name|branch>
```

## Examples

```bash
/worktree-teardown 42-feature-audio
/worktree-teardown 42/feature-audio
```

## What Gets Cleaned Up

1. **Docker resources**:
   - Stop and remove containers
   - Remove isolated volumes (postgres, redis, uploads)
   - Keep shared model cache
2. **Git worktree**:
   - Remove from git worktree list
   - Delete worktree directory
3. **Registry**:
   - Remove entry from SQLite database
   - Free port allocation
4. **Branches** (if merged):
   - Delete local branch
   - Delete remote branch

## Commands Executed

```bash
./worktree.py teardown <input>
```

## Safety

- Will **NOT** delete unmerged branches without `--force`
- Will **NOT** touch model cache volume
- Cannot teardown `main` worktree
- Can be run from any worktree (operates on specified target)
