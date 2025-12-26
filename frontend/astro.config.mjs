import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  integrations: [react()],
  server: {
    host: true, // Listen on all interfaces for Docker
    port: 4321,
  },
  vite: {
    plugins: [tailwindcss()],
    server: {
      watch: {
        usePolling: true, // Required for Docker volume mounts
      },
      proxy: {
        '/api': {
          target: 'http://backend:8000',
          changeOrigin: true,
        },
      },
    },
  },
});
