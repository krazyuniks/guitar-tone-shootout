# T3K OAuth Flow

## Passwordless Authentication

T3K uses passwordless OAuth. Users authenticate via email magic link on T3K's site -- no passwords exist.

GTS integrates via OAuth2:

1. User clicks "Login with T3K" -- redirected to T3K
2. T3K sends email link to user -- user clicks link
3. T3K redirects back with OAuth code -- GTS exchanges for tokens
4. Tokens stored in `.gts-auth.json` for worktree sharing

**No user credentials are stored or managed by GTS.** Only OAuth access/refresh tokens.
