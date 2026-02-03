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

# Default command (can be overridden)
CMD ["pnpm", "dev"]
