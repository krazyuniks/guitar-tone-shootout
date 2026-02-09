#!/usr/bin/env node
// Wrapper for remotion CLI that fixes --version flag behavior
// Remotion shows help with exit code 1 for --version, but tests expect exit code 0

const { spawn } = require('child_process');
const path = require('path');

const args = process.argv.slice(2);

// If --version flag is present, intercept and use 'versions' command instead
const remotionCliPath = path.join(__dirname, 'node_modules', '@remotion', 'cli', 'remotion-cli.js');

if (args.includes('--version') || args.includes('-v')) {
  // Use 'remotion versions' which returns exit code 0
  const remotion = spawn('node', [remotionCliPath, 'versions'], {
    stdio: 'inherit',
    cwd: __dirname
  });

  remotion.on('exit', (code) => {
    process.exit(code);
  });
} else {
  // Call the real remotion for all other commands
  const remotion = spawn('node', [remotionCliPath, ...args], {
    stdio: 'inherit',
    cwd: __dirname
  });

  remotion.on('exit', (code) => {
    process.exit(code);
  });
}
