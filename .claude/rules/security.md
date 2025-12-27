# Security Rules

## Critical Rules

1. **Never commit secrets**
   - No API keys, passwords, or tokens in code
   - Use environment variables via `.env`
   - Check `.env.example` is sanitized

2. **SQL Injection Prevention**
   - Always use SQLAlchemy ORM or parameterized queries
   - Never interpolate user input into SQL strings
   ```python
   # WRONG
   db.execute(f"SELECT * FROM users WHERE id = {user_id}")

   # RIGHT
   db.execute(select(User).where(User.id == user_id))
   ```

3. **XSS Prevention**
   - Astro auto-escapes by default
   - React auto-escapes in JSX
   - Never use `dangerouslySetInnerHTML` or `set:html`

4. **Auth Checks**
   - All protected routes must check `current_user`
   - Verify ownership before returning/modifying resources
   ```python
   if shootout.user_id != current_user.id:
       raise HTTPException(status_code=404)
   ```

5. **CORS Configuration**
   - Restrict origins in production
   - Don't use `allow_origins=["*"]` in production

## Input Validation

- Validate all user input with Pydantic
- Set reasonable limits (string length, file size)
- Sanitize filenames before using in paths

## Dependency Security

- Keep dependencies updated
- Check for vulnerabilities: `pip-audit`, `npm audit`
- Pin versions in production
