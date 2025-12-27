---
name: ui-design-system
description: Design tokens, visual patterns, and component styling for Guitar Tone Shootout. Use for UI decisions, colors, typography, and component design.
---

# UI Design System

**Activation:** design, colors, theme, styling, tokens, UI, visual, dark mode, component style

## Design Direction

**Aesthetic:** Professional audio tool (Quad Cortex / DAW inspired)
- Dark theme primary
- Clean, functional, aesthetically pleasing
- Not generic AI-designed

**Target Users:** Musicians, audio engineers, content creators

## Color Tokens

### Background Layers

```css
--bg-base: #0a0a0a;        /* Page background */
--bg-surface: #141414;      /* Card background */
--bg-elevated: #1f1f1f;     /* Hover, modals */
--bg-muted: #262626;        /* Subtle backgrounds */
```

### Text

```css
--text-primary: #ffffff;
--text-secondary: #a1a1a1;
--text-muted: #666666;
```

### Borders

```css
--border-default: #333333;
--border-subtle: #262626;
--border-focus: #3b82f6;
```

### Accents

```css
--accent-primary: #3b82f6;   /* Blue - CTAs, links */
--accent-success: #22c55e;   /* Green - signal flow, success */
--accent-warning: #f59e0b;   /* Amber - highlights, badges */
--accent-error: #ef4444;     /* Red - errors, destructive */
```

### Block Type Colors

```css
--block-di: #3b82f6;         /* Blue - DI tracks */
--block-amp: #f59e0b;        /* Amber - Amp models */
--block-cab: #22c55e;        /* Green - Cabinets/IRs */
--block-effect: #a855f7;     /* Purple - Effects */
```

## Typography

### Font Families

```css
--font-sans: 'Inter', system-ui, sans-serif;
--font-mono: 'JetBrains Mono', monospace;
```

### Font Sizes (Tailwind)

| Class | Size | Use |
|-------|------|-----|
| `text-xs` | 12px | Badges, captions |
| `text-sm` | 14px | Metadata, secondary |
| `text-base` | 16px | Body text |
| `text-lg` | 18px | Subheadings |
| `text-xl` | 20px | Card titles |
| `text-2xl` | 24px | Page headings |
| `text-3xl` | 30px | Hero text |

### Font Weights

- `font-normal` (400) - Body text
- `font-medium` (500) - Labels, buttons
- `font-semibold` (600) - Headings
- `font-bold` (700) - Hero, emphasis

## Spacing Scale

Use Tailwind defaults consistently:

| Token | Value | Use |
|-------|-------|-----|
| `1` | 4px | Tight spacing |
| `2` | 8px | Icon gaps |
| `3` | 12px | Small padding |
| `4` | 16px | Standard padding |
| `6` | 24px | Card padding |
| `8` | 32px | Section gaps |
| `12` | 48px | Large sections |

## Border Radius

```css
--radius-sm: 4px;    /* Buttons, inputs */
--radius-md: 8px;    /* Cards */
--radius-lg: 12px;   /* Modals */
--radius-full: 9999px; /* Pills, avatars */
```

## Shadows

```css
/* Card default */
shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);

/* Card hover / elevated */
shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);

/* Modal */
shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5);
```

## Component Patterns

### Card

```tsx
<div className="bg-[#141414] border border-[#333333] rounded-lg p-4
                hover:bg-[#1f1f1f] transition-colors">
  {children}
</div>
```

### Button (Primary)

```tsx
<button className="px-4 py-2 bg-blue-600 text-white rounded-md font-medium
                   hover:bg-blue-700 disabled:opacity-50 transition-colors">
  {label}
</button>
```

### Input

```tsx
<input className="w-full px-3 py-2 bg-[#1f1f1f] border border-[#333333] rounded-md
                  text-white placeholder-gray-500
                  focus:border-blue-500 focus:ring-1 focus:ring-blue-500" />
```

### Badge

```tsx
<span className="px-2 py-0.5 text-xs font-medium rounded-full
                 bg-amber-500/20 text-amber-400">
  Metal
</span>
```

## Block Card Pattern

```tsx
const blockStyles = {
  di: {
    border: 'border-blue-500/50',
    bg: 'bg-blue-500/10',
    icon: 'text-blue-400',
  },
  amp: {
    border: 'border-amber-500/50',
    bg: 'bg-amber-500/10',
    icon: 'text-amber-400',
  },
  cab: {
    border: 'border-green-500/50',
    bg: 'bg-green-500/10',
    icon: 'text-green-400',
  },
  effect: {
    border: 'border-purple-500/50',
    bg: 'bg-purple-500/10',
    icon: 'text-purple-400',
  },
};
```

## Hover States

- Cards: `hover:bg-[#1f1f1f]` (elevate)
- Buttons: `hover:bg-blue-700` (darken primary)
- Links: `hover:text-blue-400` (highlight)
- Scale: `hover:scale-[1.02]` (subtle grow)

## Transitions

```css
/* Default for colors */
transition-colors duration-150

/* For transforms */
transition-transform duration-200

/* For all properties */
transition-all duration-200
```

## WCAG 2.1 AA Compliance

- Text contrast: 4.5:1 minimum
- UI elements: 3:1 minimum
- Focus indicators: `ring-2 ring-blue-500`
- Keyboard navigation: All interactive elements focusable

## Responsive Breakpoints

| Breakpoint | Width | Use |
|------------|-------|-----|
| `sm` | 640px | Mobile landscape |
| `md` | 768px | Tablet |
| `lg` | 1024px | Desktop |
| `xl` | 1280px | Large desktop |

## Resources

See `resources/` for:
- `component-examples.md` - Full component code
- `block-designs.md` - Signal chain block patterns
