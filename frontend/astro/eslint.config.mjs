import parser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import astroPlugin from 'eslint-plugin-astro';

const noExplicitAny = {
  plugins: { '@typescript-eslint': tsPlugin },
  rules: { '@typescript-eslint/no-explicit-any': 'error' },
};

export default [
  // .astro files: astro-eslint-parser handles templates; delegates frontmatter to @typescript-eslint/parser
  ...astroPlugin.configs.recommended,
  {
    files: ['src/**/*.astro'],
    ...noExplicitAny,
  },
  // .ts/.tsx files: plain @typescript-eslint/parser
  {
    files: ['src/**/*.ts', 'src/**/*.tsx'],
    ignores: ['node_modules/**', 'dist/**', '.astro/**'],
    languageOptions: { parser },
    ...noExplicitAny,
  },
];
