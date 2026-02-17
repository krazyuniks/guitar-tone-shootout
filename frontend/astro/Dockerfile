FROM node:24.13.1-alpine

# Build args for user mapping (avoids root-owned files on bind mounts)
ARG UID=1000
ARG GID=1000

# Install pnpm globally
RUN npm install -g pnpm@10

# Replace default node user (UID 1000) with host UID/GID
RUN deluser --remove-home node \
    && addgroup -g $GID appgroup \
    && adduser -u $UID -G appgroup -D -s /bin/sh appuser

# Set working directory with correct ownership
WORKDIR /app
RUN chown appuser:appgroup /app

# Switch to non-root user before installing deps (avoids chown on node_modules)
USER appuser

# Copy package files
COPY --chown=$UID:$GID package.json pnpm-lock.yaml* ./

# Install dependencies (as non-root, so node_modules is owned correctly)
RUN pnpm install

# Copy source code
COPY --chown=$UID:$GID . .

# Healthcheck: verify base.html exists (build has run at least once)
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
  CMD test -f /app/dist/layouts/base.html

# Watch for source changes and auto-rebuild
CMD ["pnpm", "watch:build"]
