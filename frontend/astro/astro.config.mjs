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
    build: {
      rollupOptions: {
        output: {
          assetFileNames: (assetInfo) => {
            if (assetInfo.names?.[0]?.endsWith('.css')) {
              return '_astro/styles[extname]';
            }
            return '_astro/[name].[hash][extname]';
          },
        },
      },
    },
  },
  build: {
    format: 'file',
  },
});
