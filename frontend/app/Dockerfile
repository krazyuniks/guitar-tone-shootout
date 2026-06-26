FROM node:24.13.1-alpine

ARG USER_UID=1000
ARG USER_GID=1000

RUN npm install -g pnpm@10

RUN deluser --remove-home node \
    && addgroup -g $USER_GID appgroup \
    && adduser -u $USER_UID -G appgroup -D -s /bin/sh appuser

WORKDIR /app
RUN chown appuser:appgroup /app

USER appuser

COPY --chown=$USER_UID:$USER_GID package.json pnpm-lock.yaml* ./
RUN pnpm install

COPY --chown=$USER_UID:$USER_GID . .

HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=5 \
  CMD wget -qO /dev/null http://localhost:5173/app/ || exit 1

CMD ["pnpm", "dev"]
