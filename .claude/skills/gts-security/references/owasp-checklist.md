# OWASP Top 10 Checklist

Before any PR, verify:

| Category | Verification |
|----------|--------------|
| **Injection** | SQLAlchemy ORM or parameterised queries. Never f-strings with SQL. |
| **Broken Authentication** | Session cookies with `httponly`, `secure`, `samesite=lax`. |
| **Sensitive Data Exposure** | No secrets in code. HTTPS in production. |
| **Broken Access Control** | Check `current_user` ownership on all resources. |
| **Security Misconfiguration** | CSP headers, CORS restricted, admin routes blocked. |
| **XSS** | Auto-escaping enabled (Astro/React/Jinja2). No raw HTML injection. |
| **Insecure Deserialization** | Pydantic validation on all inputs. |
| **Vulnerable Components** | `pip-audit` and `npm audit` clean. |
| **Logging & Monitoring** | Auth failures logged. No secrets in logs. |

## SQL Injection Prevention

Always use SQLAlchemy ORM or parameterised queries. Never interpolate user input.

```python
# WRONG - vulnerable to SQL injection
db.execute(f"SELECT * FROM users WHERE id = {user_id}")
db.execute(text(f"SELECT * FROM users WHERE name = '{name}'"))

# RIGHT - parameterised
db.execute(select(User).where(User.id == user_id))
db.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
```

## XSS Prevention

Template engines auto-escape by default. Never bypass this protection.

| Engine | Auto-escapes | Dangerous (NEVER use) |
|--------|--------------|----------------------|
| Astro | Yes | `set:html` |
| React | Yes | `dangerouslySetInnerHTML` |
| Jinja2 | Yes | `| safe` filter |

## Auth Checks (Broken Access Control)

All protected routes must verify authentication and authorisation.

```python
# Verify user owns the resource (prevents IDOR)
if shootout.user_id != current_user.id:
    raise HTTPException(status_code=404)  # 404 not 403 (don't leak existence)
```

## CORS Configuration

```python
# WRONG - allows any origin
allow_origins=["*"]

# RIGHT - restrict to known origins
allow_origins=["https://yourdomain.com"]
```

## Input Validation

All user input validated via Pydantic schemas:

```python
class CreateShootout(BaseModel):
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()
```

**Key rules:**
- Set reasonable limits (string length, file size)
- Sanitise filenames before using in paths
- Validate file types for uploads
- Never trust Content-Type headers for file validation

## Secret Hygiene

- No API keys, passwords, or tokens in code
- Use environment variables via `.env`
- Check `.env.example` is sanitised (no real values)
- Use `gitleaks` to detect accidentally committed secrets

```bash
# Verify no secrets committed
gitleaks detect --source . --config .gitleaks.toml --verbose
```
