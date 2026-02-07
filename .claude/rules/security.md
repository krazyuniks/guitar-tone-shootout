# Security Rules

## Hard Constraints

- **SQL injection:** Never f-string SQL. Use SQLAlchemy ORM or parameterised queries.
- **XSS:** Never bypass auto-escaping. No `|safe` (Jinja2), `dangerouslySetInnerHTML` (React), `set:html` (Astro).
- **Secrets:** Never commit secrets, API keys, or tokens to code. Use environment variables.
- **CORS:** Never use `allow_origins=["*"]`. Restrict to known origins.
- **Resource access:** Always verify `resource.user_id == current_user.id`. Return 404 not 403.
- **Input validation:** All API input/output via Pydantic schemas with reasonable limits.

## Security Review SLA

| Severity | Response Time | Examples |
|----------|---------------|---------|
| **Critical** | Same day | Auth bypass, RCE, SQLi, exposed secrets |
| **High** | 48 hours | XSS, CSRF, privilege escalation |
| **Medium** | 1 week | Information disclosure, weak crypto |
| **Low** | Next sprint | Missing headers, verbose errors |

For detailed reference (OWASP checklist, headers, scanning, dependencies), see the `gts-security` skill.
