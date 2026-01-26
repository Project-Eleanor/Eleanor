#!/bin/bash
# Eleanor Restore Script
# Restores from a backup created by backup.sh
# Usage: ./restore.sh --backup PATH [--verify-only]

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
BACKUP_PATH=""
VERIFY_ONLY=false
FORCE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --backup|-b)
            BACKUP_PATH="$2"
            shift 2
            ;;
        --verify|--verify-only)
            VERIFY_ONLY=true
            shift
            ;;
        --force|-f)
            FORCE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 --backup PATH [OPTIONS]"
            echo "Restore Eleanor from backup"
            echo ""
            echo "Options:"
            echo "  -b, --backup PATH     Backup file or directory (required)"
            echo "  --verify              Verify backup without restoring"
            echo "  -f, --force           Skip confirmation prompts"
            echo "  -h, --help            Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Validate backup path
if [[ -z "$BACKUP_PATH" ]]; then
    echo -e "${RED}Error: --backup PATH is required${NC}"
    exit 1
fi

if [[ ! -e "$BACKUP_PATH" ]]; then
    echo -e "${RED}Error: Backup not found: $BACKUP_PATH${NC}"
    exit 1
fi

echo -e "${BLUE}Eleanor Restore${NC}"
echo "==============="
echo ""

# Determine if backup is compressed
TEMP_DIR=""
if [[ -f "$BACKUP_PATH" ]] && [[ "$BACKUP_PATH" == *.tar.gz ]]; then
    echo -e "${YELLOW}Extracting compressed backup...${NC}"
    TEMP_DIR=$(mktemp -d)
    tar xzf "$BACKUP_PATH" -C "$TEMP_DIR"
    BACKUP_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "eleanor_backup_*" | head -1)
    if [[ -z "$BACKUP_DIR" ]]; then
        BACKUP_DIR="$TEMP_DIR"
    fi
elif [[ -d "$BACKUP_PATH" ]]; then
    BACKUP_DIR="$BACKUP_PATH"
else
    echo -e "${RED}Error: Backup must be a directory or .tar.gz file${NC}"
    exit 1
fi

echo "Backup directory: $BACKUP_DIR"
echo ""

# Cleanup function
cleanup() {
    if [[ -n "$TEMP_DIR" ]] && [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}
trap cleanup EXIT

# Verify backup contents
verify_backup() {
    echo -e "${YELLOW}Verifying backup contents...${NC}"

    local required_files=("manifest.json")
    local optional_files=("postgres_dump.sql" "redis_data.tar" "evidence_storage.tar" "config/.env")
    local missing=()
    local found=()

    # Check manifest
    if [[ -f "$BACKUP_DIR/manifest.json" ]]; then
        echo -e "${GREEN}  [OK] manifest.json${NC}"
        cat "$BACKUP_DIR/manifest.json"
        echo ""
    else
        echo -e "${RED}  [MISSING] manifest.json${NC}"
        missing+=("manifest.json")
    fi

    # Check other files
    for f in "${optional_files[@]}"; do
        if [[ -e "$BACKUP_DIR/$f" ]]; then
            local size=$(du -h "$BACKUP_DIR/$f" | cut -f1)
            echo -e "${GREEN}  [OK] $f ($size)${NC}"
            found+=("$f")
        else
            echo -e "${YELLOW}  [MISSING] $f${NC}"
        fi
    done

    echo ""

    if [[ ${#found[@]} -eq 0 ]]; then
        echo -e "${RED}Error: No restorable data found in backup${NC}"
        return 1
    fi

    echo -e "${GREEN}Backup verification passed${NC}"
    echo "Found ${#found[@]} restorable items"

    return 0
}

# Restore volume from tar
restore_volume() {
    local tar_file="$1"
    local volume_name="$2"

    if [[ ! -f "$BACKUP_DIR/$tar_file" ]]; then
        echo -e "${YELLOW}  Skipping $volume_name (no backup file)${NC}"
        return
    fi

    echo -e "${YELLOW}  Restoring $volume_name...${NC}"

    # Create volume if it doesn't exist
    docker volume create "$volume_name" >/dev/null 2>&1 || true

    # Restore using temporary container
    docker run --rm \
        -v "$volume_name:/target" \
        -v "$(realpath "$BACKUP_DIR"):/backup:ro" \
        alpine sh -c "rm -rf /target/* && tar xf /backup/$tar_file -C /target"

    echo -e "${GREEN}    Done${NC}"
}

# Restore PostgreSQL
restore_postgres() {
    echo -e "${YELLOW}Restoring PostgreSQL...${NC}"

    if [[ -f "$BACKUP_DIR/postgres_dump.sql" ]]; then
        # Restore from SQL dump
        echo "  Restoring from SQL dump..."

        # Start postgres container if not running
        cd "$PROJECT_ROOT"
        docker compose up -d postgres

        # Wait for postgres to be ready
        sleep 5

        # Restore
        docker exec -i eleanor-postgres psql -U eleanor eleanor < "$BACKUP_DIR/postgres_dump.sql"

        echo -e "${GREEN}    Done${NC}"
    elif [[ -f "$BACKUP_DIR/postgres_data.tar" ]]; then
        # Restore from volume backup
        restore_volume "postgres_data.tar" "eleanor_postgres_data"
    else
        echo -e "${YELLOW}  No PostgreSQL backup found${NC}"
    fi
}

# Restore Redis
restore_redis() {
    echo -e "${YELLOW}Restoring Redis...${NC}"
    restore_volume "redis_data.tar" "eleanor_redis_data"
}

# Restore Evidence
restore_evidence() {
    echo -e "${YELLOW}Restoring evidence storage...${NC}"
    restore_volume "evidence_storage.tar" "eleanor_evidence_storage"
}

# Restore Elasticsearch
restore_elasticsearch() {
    if [[ -f "$BACKUP_DIR/elasticsearch_data.tar" ]]; then
        echo -e "${YELLOW}Restoring Elasticsearch...${NC}"
        restore_volume "elasticsearch_data.tar" "eleanor_elasticsearch_data"
    else
        echo -e "${YELLOW}Skipping Elasticsearch (no backup)${NC}"
    fi
}

# Restore configuration
restore_config() {
    echo -e "${YELLOW}Restoring configuration...${NC}"

    if [[ -f "$BACKUP_DIR/config/.env" ]]; then
        if [[ -f "$PROJECT_ROOT/.env" ]] && ! $FORCE; then
            echo -e "${YELLOW}  .env already exists, creating .env.restored${NC}"
            cp "$BACKUP_DIR/config/.env" "$PROJECT_ROOT/.env.restored"
        else
            cp "$BACKUP_DIR/config/.env" "$PROJECT_ROOT/.env"
            chmod 600 "$PROJECT_ROOT/.env"
        fi
        echo -e "${GREEN}    Done${NC}"
    fi

    if [[ -d "$BACKUP_DIR/config/certificates" ]]; then
        if [[ -d "$PROJECT_ROOT/certificates" ]] && ! $FORCE; then
            echo -e "${YELLOW}  certificates/ already exists, creating certificates.restored/${NC}"
            cp -r "$BACKUP_DIR/config/certificates" "$PROJECT_ROOT/certificates.restored"
        else
            cp -r "$BACKUP_DIR/config/certificates" "$PROJECT_ROOT/"
        fi
        echo -e "${GREEN}    Done${NC}"
    fi
}

# Perform restore
do_restore() {
    echo -e "${YELLOW}Stopping Eleanor services...${NC}"
    cd "$PROJECT_ROOT"
    docker compose down 2>/dev/null || true

    echo ""
    restore_config
    restore_postgres
    restore_redis
    restore_evidence
    restore_elasticsearch

    echo ""
    echo -e "${YELLOW}Starting Eleanor services...${NC}"
    docker compose up -d

    echo ""
    echo -e "${GREEN}Restore Complete!${NC}"
    echo "================="
    echo ""
    echo "Services are starting. Run health check to verify:"
    echo "  ./scripts/health-check.sh"
}

# Main execution
main() {
    if ! verify_backup; then
        exit 1
    fi

    if $VERIFY_ONLY; then
        echo ""
        echo "Verification complete. Use without --verify to restore."
        exit 0
    fi

    echo ""
    if ! $FORCE; then
        echo -e "${RED}WARNING: This will replace all current data!${NC}"
        read -p "Are you sure you want to restore? [y/N]: " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Restore cancelled."
            exit 0
        fi
    fi

    do_restore
}

main
