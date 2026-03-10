<!-- domains: all -->
# GitHub CLI Rules
- Repository: `krazyuniks/guitar-tone-shootout`
- ALWAYS include `--repo krazyuniks/guitar-tone-shootout` with ALL `gh` commands.
- On OSX (DWP Mac): the git remote uses a custom SSH alias (`github_osx:`) which prevents `gh` from auto-detecting the repository. Without `--repo`, commands will fail.
- On Linux: `gh` works directly without proxy configuration. The `--repo` flag is still required for consistency.
