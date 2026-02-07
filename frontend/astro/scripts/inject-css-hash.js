#!/usr/bin/env node
/**
 * Post-build script: injects the actual CSS filename (with content hash)
 * into dist/layouts/base.html, replacing the CSS_PLACEHOLDER token.
 *
 * Astro generates hashed CSS filenames for cache busting. This script
 * ensures the Jinja2 base layout always references the correct file.
 */

import { readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const distDir = join(__dirname, '..', 'dist');
const astroDir = join(distDir, '_astro');
const baseHtml = join(distDir, 'layouts', 'base.html');

if (!existsSync(astroDir)) {
  console.error('Error: dist/_astro/ not found. Run astro build first.');
  process.exit(1);
}

if (!existsSync(baseHtml)) {
  console.error('Error: dist/layouts/base.html not found.');
  process.exit(1);
}

// Find the CSS file (there should be exactly one main CSS file)
const cssFiles = readdirSync(astroDir).filter(f => f.endsWith('.css'));

if (cssFiles.length === 0) {
  console.error('Error: No CSS files found in dist/_astro/');
  process.exit(1);
}

// Use the first CSS file (Astro produces one bundled CSS)
const cssFilename = cssFiles[0];

let content = readFileSync(baseHtml, 'utf-8');
const replaced = content.replace(/CSS_PLACEHOLDER/g, cssFilename);

if (replaced === content) {
  // No placeholder found — check if it already has a valid CSS reference
  if (content.includes('/_astro/') && content.includes('.css')) {
    // Already has a CSS reference — update it to the current hash
    const updated = content.replace(
      /\/_astro\/[^"']+\.css/g,
      `/_astro/${cssFilename}`
    );
    writeFileSync(baseHtml, updated);
    console.log(`Updated CSS reference to: /_astro/${cssFilename}`);
  } else {
    console.log('Warning: No CSS_PLACEHOLDER or existing CSS reference found in base.html');
  }
} else {
  writeFileSync(baseHtml, replaced);
  console.log(`Injected CSS hash: /_astro/${cssFilename}`);
}
