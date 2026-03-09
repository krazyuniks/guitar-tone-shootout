---
github_issue: 146
title: "Phase 4 — Security fixes, group detail page, comment editing"
state: OPEN
labels: []
fetched: 2026-03-06T23:54:30Z
---

## Summary

Address the high-priority security gap (shootout chain ownership validation), wire the missing group detail page endpoint, add comment editing, and clean up dead `is_system_track` references. These are small, well-scoped fixes spanning 4B, 4C, and cleanup.

## Observable Outcomes

- [ ] `GET /library/chains/group?id=<uuid>` returns the group detail page showing group name, description, and list of chains in the group
- [ ] Clicking a group item link on the group list page navigates to the group detail page (no 404)
- [ ] Creating a shootout with a signal chain not owned by the current user returns 404 (not 403, not success)
- [ ] Creating a shootout with a chain owned by the current user succeeds as before
- [ ] `PATCH /api/v1/comments/<id>` with `{"body": "updated text"}` updates the comment body; returns updated comment
- [ ] `PATCH /api/v1/comments/<id>` by a non-author returns 404
- [ ] Comment on shootout detail page shows an edit button for the author only
- [ ] Clicking edit shows an inline form; submitting updates the comment text in place via HTMX
- [ ] Hardcoded `is_system_track: False` removed from `pages/context.py`
- [ ] Frontend `is_system_track` badge and delete-button suppression references removed

## Decisions

- **BC ownership:** Group detail page is webapp (pages BC). Comment editing is webapp API + frontend. Shootout ownership is webapp API validation.
- **Auth:** Shootout creation validates `chain.user_id == current_user.id` for all selected chains. Comment edit validates `comment.user_id == current_user.id`. Both return 404 on mismatch.
- **Frontend pattern:** Group detail page is SSR (Jinja2 template, already built as `fragments/library/group_detail.html.ts`). Comment editing uses HTMX inline swap.
- **API contract:** `PATCH /api/v1/comments/<id>` accepts `{"body": str}`, returns full comment schema. No new endpoints for group detail (SSR page route only).
- **Cleanup:** `is_system_track` references are dead code — remove without replacement.

## Regression Boundaries

- Existing shootout creation with valid owned chains must continue to work
- Existing comment display (create, delete) must not change
- Group list page must continue to work
- DI track pages must render correctly after `is_system_track` removal
