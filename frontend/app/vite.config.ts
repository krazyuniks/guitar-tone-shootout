import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  base: '/app/',
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Traefik preview hostnames (just preview) reach vite through nginx with
    // the public Host header; .tone-shootout.com covers every worktree subdomain.
    allowedHosts: ['.tone-shootout.com'],
    hmr: {
      // When nginx is the public entry point, HMR websocket must connect on
      // the nginx port (not the internal vite port). Set VITE_HMR_CLIENT_PORT
      // to the nginx port in the app service environment (matches NGINX_PORT).
      ...(process.env['VITE_HMR_CLIENT_PORT']
        ? { clientPort: parseInt(process.env['VITE_HMR_CLIENT_PORT'], 10) }
        : {}),
    },
    // Proxy API calls when accessing vite directly (without nginx).
    // When going through nginx, the /api and /auth location blocks already
    // route to webapp — these proxy entries are for standalone vite access.
    proxy: {
      '/api': { target: 'http://webapp:8000', changeOrigin: true },
      '/auth': { target: 'http://webapp:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
  },
})
