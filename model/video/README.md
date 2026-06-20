# gts-video

Video rendering library for Guitar Tone Shootout using Remotion.

## Overview

This package provides video composition and rendering capabilities for GTS using:
- **Remotion** for declarative React-based video composition
- **Node.js 20** runtime environment
- **Chromium** for server-side rendering
- **Python/uv** integration for hybrid Python/Node.js workflows

## Architecture

Video rendering runs as a standalone Bounded Context (BC) service:
- Exposed via HTTP API on port 8002
- Called by the worker service for video generation jobs
- No direct database dependencies
- Processes audio output and metadata into final video compositions

## Dependencies

- `gts-domain` - Core domain models

## Development

See `infrastructure/docker/Dockerfile.video` for container configuration.
