#!/bin/bash
# Eleanor Admin Password Reset Script
# Emergency password reset for locked-out admins
# Usage: ./reset-admin-password.sh [--user USERNAME] [--password PASSWORD]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Defaults
USERNAME=""
NEW_PASSWORD=""
GENERATE_PASSWORD=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --user|-u)
            USERNAME="$2"
            shift 2
            ;;
        --password|-p)
            NEW_PASSWORD="$2"
            shift 2
            ;;
        --generate|-g)
            GENERATE_PASSWORD=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Reset password for an Eleanor admin user"
            echo ""
            echo "Options:"
            echo "  -u, --user USERNAME     User to reset (default: admin)"
            echo "  -p, --password PASS     New password (prompted if not provided)"
            echo "  -g, --generate          Generate a random password"
            echo "  -h, --help              Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}Eleanor Admin Password Reset${NC}"
echo "============================="
echo ""

# Default username
if [[ -z "$USERNAME" ]]; then
    USERNAME="admin"
fi
echo "User: $USERNAME"

# Generate or prompt for password
if $GENERATE_PASSWORD; then
    NEW_PASSWORD=$(openssl rand -base64 16 | tr -d '=' | head -c 20)
    echo -e "Generated password: ${GREEN}$NEW_PASSWORD${NC}"
elif [[ -z "$NEW_PASSWORD" ]]; then
    while true; do
        read -sp "New password (min 12 chars): " NEW_PASSWORD
        echo ""

        if [[ ${#NEW_PASSWORD} -lt 12 ]]; then
            echo -e "${RED}Password must be at least 12 characters${NC}"
            continue
        fi

        read -sp "Confirm password: " confirm
        echo ""

        if [[ "$NEW_PASSWORD" == "$confirm" ]]; then
            break
        else
            echo -e "${RED}Passwords do not match${NC}"
        fi
    done
fi

echo ""

# Check if backend container is running
if ! docker exec eleanor-backend echo "ok" >/dev/null 2>&1; then
    echo -e "${RED}Error: Backend container is not running${NC}"
    echo "Start services with: docker compose up -d"
    exit 1
fi

# Generate password hash using Python in the container
echo -e "${YELLOW}Resetting password...${NC}"

HASH=$(docker exec eleanor-backend python -c "
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
print(pwd_context.hash('$NEW_PASSWORD'))
")

# Update password in database
docker exec eleanor-postgres psql -U eleanor -d eleanor -c "
UPDATE users SET hashed_password = '$HASH', updated_at = NOW()
WHERE username = '$USERNAME';
" >/dev/null 2>&1

# Check if update was successful
RESULT=$(docker exec eleanor-postgres psql -U eleanor -d eleanor -t -c "
SELECT COUNT(*) FROM users WHERE username = '$USERNAME';
" 2>/dev/null | tr -d ' ')

if [[ "$RESULT" == "1" ]]; then
    echo -e "${GREEN}Password reset successfully!${NC}"
    echo ""
    echo "Username: $USERNAME"
    if $GENERATE_PASSWORD; then
        echo -e "Password: ${GREEN}$NEW_PASSWORD${NC}"
        echo ""
        echo -e "${YELLOW}Save this password - it won't be shown again${NC}"
    fi
else
    echo -e "${RED}Error: User '$USERNAME' not found${NC}"
    echo ""
    echo "Available users:"
    docker exec eleanor-postgres psql -U eleanor -d eleanor -t -c "
    SELECT username, email FROM users WHERE is_active = true;
    " 2>/dev/null
    exit 1
fi
