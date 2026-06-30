import parser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';

// Astro templates (.astro) require eslint-plugin-astro + astro-eslint-parser.
// TypeScript enforcement for .astro files is handled by `astro check` (pnpm check).
// This config covers the .ts/.tsx helper files in the Astro project.
export default [
  {
    files: ['src/**/*.ts', 'src/**/*.tsx'],
    ignores: ['node_modules/**', 'dist/**', '.astro/**'],
    languageOptions: { parser },
    plugins: { '@typescript-eslint': tsPlugin },
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
    },
  },
];
