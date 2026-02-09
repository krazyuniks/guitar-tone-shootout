#!/usr/bin/env node
// Wrapper for tsc that adds necessary flags when compiling single files
// This ensures tsconfig.json settings are respected even with explicit file arguments

const { spawn } = require('child_process');
const path = require('path');

const args = process.argv.slice(2);

// If compiling a specific .ts file, add required flags from tsconfig.json
const hasFileArg = args.some(arg => arg.endsWith('.ts') && !arg.startsWith('-'));

if (hasFileArg && !args.includes('--jsx')) {
  args.push('--jsx', 'react-jsx');
}
if (hasFileArg && !args.includes('--esModuleInterop')) {
  args.push('--esModuleInterop');
}
if (hasFileArg && !args.includes('--moduleResolution')) {
  args.push('--moduleResolution', 'node');
}
if (hasFileArg && !args.includes('--skipLibCheck')) {
  args.push('--skipLibCheck');
}

// Call the real tsc
const tscPath = path.join(__dirname, 'node_modules', 'typescript', 'bin', 'tsc');
const tsc = spawn('node', [tscPath, ...args], {
  stdio: 'inherit',
  cwd: __dirname
});

tsc.on('exit', (code) => {
  process.exit(code);
});
