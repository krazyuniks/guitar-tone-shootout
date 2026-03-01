<!-- domains: backend, security -->
# Authentication Rules
- T3K webapp login = passwordless OAuth. No user credentials stored by GTS.
- T3K source sync = API key → JWT exchange via T3KTokenManager. No DB token storage.
- Token-based auth (stateless). JWT validated per request. No server-side sessions.
- Resource ownership: always verify `resource.user_id == current_user.id`. Return 404 (not 403).
- Admin API (Webapp, port 8000, `/api/admin/*`): NO authentication. Network-level access control only.
- User API (Webapp, port 8000): all `/api/*` routes require `CurrentUser` token authentication.
- CORS: never use `allow_origins=["*"]`.
