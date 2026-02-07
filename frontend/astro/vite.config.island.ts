/**
 * Vite configuration for building React islands as standalone bundles.
 *
 * STORY-010: SignalChainBuilder React Island
 *
 * This builds React components as standalone JavaScript bundles that can be
 * loaded in Jinja2/SSR pages without requiring Astro's client hydration.
 *
 * Usage:
 *   pnpm build:islands
 *
 * Output:
 *   dist/islands/signal-chain-builder.js  - The bundled React component (alongside Astro output)
 */
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  define: {
    // Replace process.env.NODE_ENV with "production" for browser compatibility
    'process.env.NODE_ENV': JSON.stringify('production'),
    'process.env': JSON.stringify({}),
  },
  build: {
    // Output to dist/islands alongside Astro output
    // Both share the same frontend_dist volume, avoiding the EBUSY error from
    // having a separate volume mounted at dist/islands that Astro couldn't clean
    outDir: 'dist/islands',
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, 'src/islands/signal-chain-builder.tsx'),
      name: 'SignalChainBuilder',
      formats: ['iife'],
      fileName: () => 'signal-chain-builder.js',
    },
    rollupOptions: {
      // React and ReactDOM are bundled (not externalized) for simplicity
      // This ensures the island is self-contained
      output: {
        // Expose the mount function globally
        extend: true,
      },
    },
    minify: 'esbuild',
    sourcemap: false,
  },
});
