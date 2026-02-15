<!-- domains: all -->
# Security Rules
- SQL injection: never f-string SQL. Use SQLAlchemy ORM or parameterised queries.
- XSS: never bypass auto-escaping. No `|safe` (Jinja2), `dangerouslySetInnerHTML` (React), `set:html` (Astro).
- Secrets: never commit secrets, API keys, or tokens to code. Use environment variables.
- CORS: never use `allow_origins=["*"]`. Restrict to known origins.
- Resource access: always verify `resource.user_id == current_user.id`. Return 404 not 403.
- Input validation: all API input/output via Pydantic schemas with reasonable limits.
