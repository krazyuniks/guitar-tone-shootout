# Navigation

## Standard Page Navigation

All links use standard `<a href>` tags. No SPA transitions, no client-side routing.

```html
<a href="/gear">Gear</a>
<a href="/shootouts">Shootouts</a>
<a href="/library/my-gear">My Gear</a>
<a href="/about">About</a>
```

## HTMX Is Not For Navigation

HTMX is used for small in-page interactions only (checkboxes, modals, inline updates). Page navigation is always a full browser request.

## Debugging Navigation Issues

If a link click does nothing or hangs:
1. Check browser console for JS errors
2. Check Network tab — a full navigation request should appear
3. Verify there's no JavaScript intercepting the click (no ClientRouter, no custom click handlers)
