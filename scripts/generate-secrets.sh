#!/bin/bash
# Generate secure random secrets for Eleanor deployment
# Usage: ./generate-secrets.sh [--output FILE]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default output
OUTPUT_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output|-o)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--output FILE]"
            echo "Generate secure random secrets for Eleanor deployment"
            echo ""
            echo "Options:"
            echo "  -o, --output FILE   Write secrets to file instead of stdout"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Check for required tools
command -v openssl >/dev/null 2>&1 || {
    echo -e "${RED}Error: openssl is required but not installed.${NC}"
    exit 1
}

# Generate a secure random string
# Args: length (default: 32)
generate_secret() {
    local length=${1:-32}
    openssl rand -base64 "$length" | tr -d '\n=' | head -c "$length"
}

# Generate a secure random hex string
# Args: length (default: 32)
generate_hex_secret() {
    local length=${1:-32}
    openssl rand -hex "$((length / 2))"
}

# Generate URL-safe base64 secret (like Python's secrets.token_urlsafe)
generate_urlsafe_secret() {
    local length=${1:-32}
    openssl rand -base64 "$length" | tr '+/' '-_' | tr -d '=' | head -c "$length"
}

# Generate password (alphanumeric with special chars)
generate_password() {
    local length=${1:-24}
    # Use /dev/urandom for maximum entropy
    LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*()_+-=' < /dev/urandom | head -c "$length"
}

# Generate simple password (alphanumeric only, for compatibility)
generate_simple_password() {
    local length=${1:-24}
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$length"
}

# Build the secrets output
generate_all_secrets() {
    cat << EOF
# =============================================================================
# Eleanor Generated Secrets
# Generated: $(date -Iseconds)
# =============================================================================

# Core Eleanor Secrets
SECRET_KEY=$(generate_urlsafe_secret 48)
POSTGRES_PASSWORD=$(generate_simple_password 32)
REDIS_PASSWORD=$(generate_simple_password 24)

# JWT Settings
JWT_SECRET=$(generate_urlsafe_secret 64)

# IRIS Secrets
IRIS_DB_PASSWORD=$(generate_simple_password 32)
IRIS_SECRET_KEY=$(generate_urlsafe_secret 48)
IRIS_PASSWORD_SALT=$(generate_hex_secret 32)
IRIS_ADMIN_PASSWORD=$(generate_password 20)

# OpenCTI Secrets
OPENCTI_ADMIN_PASSWORD=$(generate_password 20)
OPENCTI_ADMIN_TOKEN=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || generate_hex_secret 32 | sed 's/\(........\)\(....\)\(....\)\(....\)\(............\)/\1-\2-\3-\4-\5/')
OPENCTI_MINIO_USER=opencti_minio_$(generate_simple_password 8)
OPENCTI_MINIO_PASSWORD=$(generate_simple_password 32)
OPENCTI_RABBITMQ_USER=opencti_rmq
OPENCTI_RABBITMQ_PASSWORD=$(generate_simple_password 32)
OPENCTI_ELASTICSEARCH_PASSWORD=$(generate_simple_password 32)

# Shuffle Secrets
SHUFFLE_ADMIN_PASSWORD=$(generate_password 20)
SHUFFLE_API_KEY=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || generate_hex_secret 32 | sed 's/\(........\)\(....\)\(....\)\(....\)\(............\)/\1-\2-\3-\4-\5/')

# Timesketch Secrets
TIMESKETCH_PASSWORD=$(generate_password 20)
TIMESKETCH_DB_PASSWORD=$(generate_simple_password 32)
TIMESKETCH_SECRET_KEY=$(generate_urlsafe_secret 48)

# Encryption Keys (for evidence at rest)
EVIDENCE_ENCRYPTION_KEY=$(generate_hex_secret 64)
EOF
}

# Main execution
main() {
    echo -e "${BLUE}Eleanor Secret Generator${NC}"
    echo "========================="
    echo ""

    if [[ -n "$OUTPUT_FILE" ]]; then
        # Write to file
        if [[ -f "$OUTPUT_FILE" ]]; then
            echo -e "${YELLOW}Warning: $OUTPUT_FILE already exists.${NC}"
            read -p "Overwrite? [y/N] " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo -e "${RED}Aborted.${NC}"
                exit 1
            fi
        fi

        generate_all_secrets > "$OUTPUT_FILE"
        chmod 600 "$OUTPUT_FILE"
        echo -e "${GREEN}Secrets written to: $OUTPUT_FILE${NC}"
        echo -e "${YELLOW}File permissions set to 600 (owner read/write only)${NC}"
    else
        # Output to stdout
        echo -e "${YELLOW}Generating secrets (output to stdout)...${NC}"
        echo ""
        generate_all_secrets
    fi

    echo ""
    echo -e "${GREEN}Done!${NC}"
}

main
