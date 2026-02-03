/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        // Background colors
        'bg-base': 'var(--color-bg-base)',
        'bg-surface': 'var(--color-bg-surface)',
        'bg-elevated': 'var(--color-bg-elevated)',

        // Text colors
        'text-primary': 'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-muted': 'var(--color-text-muted)',

        // Accent colors
        'accent-primary': 'var(--color-accent-primary)',
        'accent-secondary': 'var(--color-accent-secondary)',
        'accent-success': 'var(--color-accent-success)',
        'accent-warning': 'var(--color-accent-warning)',
        'accent-error': 'var(--color-accent-error)',
        'accent-info': 'var(--color-accent-info)',

        // Block type colors
        'block-amp': 'var(--color-block-amp)',
        'block-pedal': 'var(--color-block-pedal)',
        'block-loop': 'var(--color-block-loop)',
        'block-ir': 'var(--color-block-ir)',
        'block-pre': 'var(--color-block-pre)',
        'block-post': 'var(--color-block-post)',

        // Gear type colors
        'gear-amp': 'var(--color-gear-amp)',
        'gear-cab': 'var(--color-gear-cab)',
        'gear-pedal': 'var(--color-gear-pedal)',
        'gear-full-rig': 'var(--color-gear-full-rig)',
      },
    },
  },
  plugins: [],
};
