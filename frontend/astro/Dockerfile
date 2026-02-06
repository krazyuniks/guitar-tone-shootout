FROM node:20-alpine

# Install pnpm globally
RUN npm install -g pnpm@9

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json pnpm-lock.yaml* ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source code
COPY . .

# Healthcheck: verify base.html exists (build has run at least once)
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
  CMD test -f /app/dist/layouts/base.html

# Watch for source changes and auto-rebuild
CMD ["pnpm", "watch:build"]
