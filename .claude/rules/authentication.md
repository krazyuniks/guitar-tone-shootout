# Authentication Rules

## Hard Constraints

- **T3K = passwordless OAuth.** No user credentials stored or managed by GTS. Only OAuth access/refresh tokens.
- **Session cookies:** `httponly=True`, `samesite=lax`, `secure=True` in production.
- **Resource ownership:** Always verify `resource.user_id == current_user.id`. Return 404 (not 403) to avoid leaking existence.
- **Admin API (Worker, port 8001):** NO authentication. Access controlled at network level — port not exposed publicly.
- **User API (Webapp, port 8000):** All `/api/v1/*` routes require `CurrentUser` session authentication.
- **CORS:** Never use `allow_origins=["*"]`.

For detailed reference (OAuth flow, session config, auth file, API endpoints), see the `gts-auth` skill.
