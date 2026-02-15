<!-- domains: all -->
# No Defensive Parsing
- If the upstream is deterministic (e.g. `--json-schema` constrained decoding, CLI envelope format), trust it. Read the one field where the data lives. Do not write fallback paths for impossible cases.
- If something fails, fail with a clear error. Do not silently try another extraction path — that hides the real problem and creates new bugs.
- Three lines, not twenty. `json.loads(text)` then `Model.model_validate(data)`. If either fails, raise with the actual error.
- Never write "defensive" code that handles cases you invented. If you don't know the format, read the docs — don't guess and add try/except around each guess.
