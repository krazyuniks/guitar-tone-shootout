<!-- domains: backend, database -->
# Query Pattern Rules
- ALWAYS `joinedload` for eager loading. NEVER `selectinload`, `subqueryload`, or `lazyload`.
- ALWAYS `.unique()` on results when `joinedload` with collections (1:N, M:N).
- `lazy="raise"` on ALL model relationships. NEVER `lazy="selectin"`, `lazy="select"`, or `lazy="subquery"`.
- One query per service method. Repositories return fully-hydrated aggregates.
- Paginated lists: use ID subquery for LIMIT/OFFSET, then hydrate with joinedload.
