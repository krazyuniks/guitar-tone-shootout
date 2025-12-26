# Multi-stage production build for Guitar Tone Shootout Frontend

# Stage 1: Build static assets
FROM node:24-alpine AS builder

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy dependency files
COPY package.json pnpm-lock.yaml* ./

# Install dependencies
RUN pnpm install --frozen-lockfile || pnpm install

# Copy application code
COPY . .

# Build static assets
RUN pnpm build

# Stage 2: Production image (nginx serves static files)
# This stage creates a minimal image with just the built assets
# In docker-compose.prod.yml, nginx copies from this build stage
FROM alpine:3.21 AS production

WORKDIR /app

# Copy built assets
COPY --from=builder /app/dist /app/dist

# No CMD - this image is used as a source for nginx volume
# The nginx container will copy from /app/dist
