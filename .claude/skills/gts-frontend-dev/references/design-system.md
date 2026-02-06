# Design System

Professional audio tool aesthetic (Quad Cortex / DAW inspired). Dark primary theme.

**Full Reference:** [Wiki: Design/Style-Guide](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Design-Style-Guide)

## Design Tokens

All tokens defined in `astro/src/styles/global.css` (single source of truth).

### Background Layers

| Token | Value | Use |
|-------|-------|-----|
| `--color-bg-base` | `#0a0a0a` | Page background |
| `--color-bg-surface` | `#141414` | Cards, panels |
| `--color-bg-elevated` | `#1f1f1f` | Modals, dropdowns, hover states |

**Tailwind:** `bg-bg-base`, `bg-bg-surface`, `bg-bg-elevated`

### Text Colors

| Token | Value | Use |
|-------|-------|-----|
| `--color-text-primary` | `#ffffff` | Primary text, headings |
| `--color-text-secondary` | `#a1a1a1` | Secondary text, labels |
| `--color-text-muted` | `#666666` | Disabled, placeholder text |

**Tailwind:** `text-text-primary`, `text-text-secondary`, `text-text-muted`

### Accent Colors

| Token | Value | Use |
|-------|-------|-----|
| `--color-accent-primary` | `#3b82f6` | Blue - CTAs, links |
| `--color-accent-success` | `#22c55e` | Green - success states |
| `--color-accent-warning` | `#f59e0b` | Amber - warnings |
| `--color-accent-error` | `#ef4444` | Red - errors, destructive |

**Tailwind:** `text-accent-primary`, `bg-accent-success`, `border-accent-warning`, etc.

### Block Type Colors

Signal chain component identification:

| Token | Value | Use |
|-------|-------|-----|
| `--color-block-di` | `#3b82f6` | Blue - DI/Input blocks |
| `--color-block-amp` | `#f59e0b` | Amber - Amp/NAM blocks |
| `--color-block-cab` | `#22c55e` | Green - Cabinet/IR blocks |
| `--color-block-effect` | `#a855f7` | Purple - Pre-amp pedals |
| `--color-block-post-effect` | `#06b6d4` | Cyan - Post-amp effects |

**Tailwind:** `bg-block-di`, `border-block-amp`, `text-block-effect`, etc.

### Typography

| Use | Class | Spec |
|-----|-------|------|
| Body | `text-base font-normal` | 16px, 400 |
| Heading | `text-2xl font-semibold` | 24px, 600 |
| Caption | `text-xs font-medium` | 12px, 500 |
| Mono | `font-mono` | JetBrains Mono |

**Fonts:** `--font-sans`: Inter, `--font-mono`: JetBrains Mono

## Component Patterns

**Card:**
```html
<div class="bg-bg-surface border border-[#333333] rounded-lg p-4
            hover:bg-bg-elevated transition-colors">
```

**Button:**
```html
<button class="px-4 py-2 bg-accent-primary text-white rounded-md font-medium
               hover:bg-blue-700 disabled:opacity-50">
```

**Block Card (signal chain blocks):**
```tsx
const blockStyles = {
  di:          { border: 'border-block-di/50',          bg: 'bg-block-di/10' },
  amp:         { border: 'border-block-amp/50',         bg: 'bg-block-amp/10' },
  cab:         { border: 'border-block-cab/50',         bg: 'bg-block-cab/10' },
  effect:      { border: 'border-block-effect/50',      bg: 'bg-block-effect/10' },
  postEffect:  { border: 'border-block-post-effect/50', bg: 'bg-block-post-effect/10' },
};
```

## Aesthetic Principles

### Do

- **Intentional choices** - Bold maximalism and refined minimalism both work
- **Dominant colors with sharp accents** - Not timid, evenly-distributed palettes
- **Atmosphere and depth** - Gradients, textures, layered transparencies
- **Purposeful motion** - High-impact moments over scattered micro-interactions

### Avoid ("AI Slop")

- Overused fonts without character
- Cliched colour schemes (purple gradients on white)
- Predictable layouts and component patterns
- Cookie-cutter design lacking context-specific character

## Updating Design Tokens

1. Edit `astro/src/styles/global.css`
2. Run `just build-astro` (or let the Astro service auto-rebuild via chokidar)
3. Changes apply to both static (Astro) and dynamic (Jinja2) pages
4. No backend restart needed

## Full Documentation

- [Style Guide](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Design-Style-Guide)
- [Tools & Workflow](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Design-Tools-and-Workflow)
- [Inspiration](https://github.com/krazyuniks/guitar-tone-shootout/wiki/Design-Inspiration)
