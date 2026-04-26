---
target: story
target_id: S2
severity: blocker
timestamp: 2026-04-26T15:18:11Z
harness: codex-gpt-5
findings:
  - id: F1
    severity: blocker
    category: outcome_coverage
    summary: O2 cap contract is violated for multibyte UTF-8 output; committed .output can exceed max_bytes.
    evidence: 'Location: woof/lib/audit_filter.py:68. apply_size_cap slices bytes then decodes with errors="replace", which can expand the resulting UTF-8 byte length. Repro on this branch: apply_size_cap("€" * 1000, max_bytes=80, ...) returns 82 bytes.'
    suggestion: Reserve footer bytes and truncate on UTF-8 codepoint boundaries so len((truncated + footer).encode("utf-8")) is always <= max_bytes.
  - id: F2
    severity: blocker
    category: test_quality
    summary: O2 tests do not assert the configured cap, so they pass even when the cap contract is broken.
    evidence: 'Location: tests/unit/woof/test_audit_filter.py:84 and tests/unit/woof/test_dispatch.py:583. The first allows <= 100 + 200 bytes (for a 100-byte cap), and the second only checks < 2000 for a configured 200-byte cap.'
    suggestion: Assert committed output byte-length <= configured max_bytes and add at least one multibyte UTF-8 truncation case.
---
F1 (blocker) — `woof/lib/audit_filter.py:68`
1. What is wrong: `apply_size_cap()` truncates by bytes and then decodes with replacement; replacement characters can increase encoded byte-length relative to `keep`, so the committed payload can exceed `max_bytes`.
2. Why it matters: story `S2` satisfies `O2`, which requires output truncated to the configured cap. This implementation can violate that contract on valid UTF-8 input.
3. What resolves it: enforce the cap on the final encoded output by truncating at UTF-8 boundaries (or equivalent deterministic logic) before appending the footer.

F2 (blocker) — `tests/unit/woof/test_audit_filter.py:84`, `tests/unit/woof/test_dispatch.py:583`
1. What is wrong: the new O2 tests prove “some truncation happened” but do not verify “truncated to configured cap”.
2. Why it matters: this is exactly the class of missed assertion that allowed the F1 contract break to pass green.
3. What resolves it: tighten assertions to `<= max_bytes` in both unit and dispatch integration tests, and include a multibyte fixture to exercise byte-boundary truncation.
