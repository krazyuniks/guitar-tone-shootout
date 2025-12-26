import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import tailwind from '@astrojs/tailwind';

// https://astro.build/config
export default defineConfig({
  integrations: [react(), tailwind()],
  server: {
    host: true, // Listen on all interfaces for Docker
    port: 4321,
  },
  vite: {
    server: {
      watch: {
        usePolling: true, // Required for Docker volume mounts
      },
    },
  },
});
