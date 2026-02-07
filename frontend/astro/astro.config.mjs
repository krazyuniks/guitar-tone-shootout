import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import react from '@astrojs/react';

// https://astro.build/config
export default defineConfig({
  output: 'static',
  outDir: './dist',
  integrations: [react()],
  vite: {
    plugins: [tailwindcss()],
  },
  build: {
    format: 'file',
  },
});
