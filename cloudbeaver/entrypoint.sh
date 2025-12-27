#!/bin/bash
# CloudBeaver entrypoint script
# Injects environment variables into config files before starting CloudBeaver

set -e

CONFIG_DIR="/opt/cloudbeaver/conf"
WORKSPACE_DIR="/opt/cloudbeaver/workspace"
DATASOURCES_TEMPLATE="${CONFIG_DIR}/initial-data-sources.conf"
DATASOURCES_TARGET="${WORKSPACE_DIR}/GlobalConfiguration/.dbeaver/data-sources.json"

# Ensure workspace directory structure exists
mkdir -p "$(dirname "${DATASOURCES_TARGET}")"

# If data-sources.json doesn't exist yet, create it from template with env var substitution
if [ ! -f "${DATASOURCES_TARGET}" ] && [ -f "${DATASOURCES_TEMPLATE}" ]; then
    echo "Initializing data sources with environment variables..."

    # Use sed to replace ${DB_PASSWORD} placeholder with actual value
    sed "s/\${DB_PASSWORD}/${DB_PASSWORD}/g" "${DATASOURCES_TEMPLATE}" > "${DATASOURCES_TARGET}"

    echo "Data sources initialized."
fi

# Execute the original CloudBeaver entrypoint
exec ./launch-product.sh
