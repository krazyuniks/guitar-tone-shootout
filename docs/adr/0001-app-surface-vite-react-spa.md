# ADR-0001: App surface is a Vite + React SPA under /app/*

- Status: accepted
- Date: 2026-06-26
- Supersedes: the blanket "No SPA navigation" rule in AGENTS.md, rescoped to the public Astro surface
- Related: design-system ADR 003, "Default app stack is Vite + React; Next.js is parked"

## Context

GTS has two frontend surfaces with different requirements:

- A public surface for reach and revenue: landing pages, SEO/AdSense content, and browse-and-play pages for all public shootouts. It is mostly static content with a small number of interactive embeds. Astro SSG is the right tool for this surface.
- A logged-in app surface: the signal-chain builder, the Gear Browser, and the user's own shootouts stack. It sits behind auth, has no SEO requirement, shares substantial client state, and needs a full-viewport work area.

The app surface is a simplified web-based DAW, not a content page. It has one cohesive state boundary: the chain, selected slot, open browser, search and filter state, draft changes, and job state all change together. Implementing that as Astro islands would mean hoisting the app into one large island: a SPA inside an Astro shell, with the SPA tradeoffs and without the cleaner app routing boundary.

The January 2026 design exploration showed the strain in practice by combining HTMX, Alpine, React islands, Radix, react-query, and dnd-kit to cover one app workflow. The useful concepts from that work carry forward; the mixed app-hosting model does not.

## Decision

The logged-in app surface is a Vite + React single-page application served under `/app/*`, with client-side routing.

- App routes (`/app`, `/app/build`, `/app/shootouts`, `/app/library`) are owned by the SPA and use client-side navigation.
- Public routes (`/`, `/shootouts`, `/shootouts/:id`, `/gear/*`) remain Astro SSG/SSR output served by nginx, with standard link navigation.
- The former blanket "No SPA navigation" rule is rescoped to the public Astro surface only.
- The SPA is built on the design-system Dense family and the vendored `gts` theme tokens. The design system is consumed by vendored/copied source, not by `file:` dependencies.
- The two surfaces share one comparison-player React component: an Astro island on public pages and a route component in the app.

## Consequences

- The public Astro surface is unchanged and remains the SEO/AdSense surface.
- The logged-in builder, Gear Browser, and app shootouts area move away from the Astro-island/Jinja/HTMX/Alpine composition model.
- Next.js remains parked; the app stack is Vite + React unless a future ADR reverses that.
- Slice A3 of the frontend-reshape epic scaffolds the SPA under `/app/*`; slice A4 adds build/typecheck and spacing enforcement.
- `docs/adr/` is now the in-repo home for GTS architecture decision records. Deferred decisions, including the dependency-injection composition-root decision, use later ADR numbers.
