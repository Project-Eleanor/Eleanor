#!/bin/bash
# Eleanor Backup Script
# Creates full backup of all data volumes and configuration
# Usage: ./backup.sh [--output DIR] [--compress] [--include-es]

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
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="eleanor_backup_${TIMESTAMP}"

# Defaults
OUTPUT_DIR="${PROJECT_ROOT}/backups"
COMPRESS=false
INCLUDE_ELASTICSEARCH=false
STOP_SERVICES=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output|-o)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --compress|-c)
            COMPRESS=true
            shift
            ;;
        --include-es|--include-elasticsearch)
            INCLUDE_ELASTICSEARCH=true
            shift
            ;;
        --stop-services)
            STOP_SERVICES=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Create backup of Eleanor data"
            echo ""
            echo "Options:"
            echo "  -o, --output DIR      Output directory (default: ./backups)"
            echo "  -c, --compress        Compress backup with gzip"
            echo "  --include-es          Include Elasticsearch data (large)"
            echo "  --stop-services       Stop services during backup (consistent)"
            echo "  -h, --help            Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}Eleanor Backup${NC}"
echo "=============="
echo ""
echo "Timestamp: $TIMESTAMP"
echo "Output: $OUTPUT_DIR/$BACKUP_NAME"
echo ""

# Create backup directory
BACKUP_PATH="$OUTPUT_DIR/$BACKUP_NAME"
mkdir -p "$BACKUP_PATH"

# Function to run docker command
docker_cmd() {
    if command -v docker >/dev/null 2>&1; then
        docker "$@"
    else
        echo -e "${RED}Docker not found${NC}"
        exit 1
    fi
}

# Stop services if requested
if $STOP_SERVICES; then
    echo -e "${YELLOW}Stopping services for consistent backup...${NC}"
    cd "$PROJECT_ROOT"
    docker compose stop || true
fi

# Backup function
backup_volume() {
    local volume_name="$1"
    local backup_file="$2"

    echo -e "${YELLOW}Backing up $volume_name...${NC}"

    # Check if volume exists
    if ! docker volume inspect "$volume_name" >/dev/null 2>&1; then
        echo -e "${YELLOW}  Volume $volume_name not found, skipping${NC}"
        return
    fi

    # Create backup using a temporary container
    docker run --rm \
        -v "$volume_name:/source:ro" \
        -v "$BACKUP_PATH:/backup" \
        alpine tar cf "/backup/$backup_file" -C /source .

    echo -e "${GREEN}  Done: $backup_file${NC}"
}

# Backup PostgreSQL
backup_postgres() {
    echo -e "${YELLOW}Backing up PostgreSQL database...${NC}"

    # Try to use pg_dump from running container
    if docker exec eleanor-postgres pg_dump -U eleanor eleanor > "$BACKUP_PATH/postgres_dump.sql" 2>/dev/null; then
        echo -e "${GREEN}  Done: postgres_dump.sql${NC}"
    else
        echo -e "${YELLOW}  Container not running, backing up volume directly${NC}"
        backup_volume "eleanor_postgres_data" "postgres_data.tar"
    fi
}

# Backup Elasticsearch (optional, can be large)
backup_elasticsearch() {
    if ! $INCLUDE_ELASTICSEARCH; then
        echo -e "${YELLOW}Skipping Elasticsearch (use --include-es to include)${NC}"
        return
    fi

    echo -e "${YELLOW}Backing up Elasticsearch data (this may take a while)...${NC}"

    # Try to create a snapshot via API first
    local es_url="${ELASTICSEARCH_URL:-http://localhost:9200}"

    if curl -sf "$es_url/_cluster/health" >/dev/null 2>&1; then
        # Elasticsearch is running, try snapshot API
        # Note: This requires a snapshot repository to be configured
        echo -e "${YELLOW}  Elasticsearch is running, backing up volume...${NC}"
    fi

    backup_volume "eleanor_elasticsearch_data" "elasticsearch_data.tar"
}

# Backup Redis
backup_redis() {
    echo -e "${YELLOW}Backing up Redis data...${NC}"

    # Try to trigger BGSAVE first
    if docker exec eleanor-redis redis-cli BGSAVE >/dev/null 2>&1; then
        sleep 2  # Wait for save to complete
    fi

    backup_volume "eleanor_redis_data" "redis_data.tar"
}

# Backup evidence storage
backup_evidence() {
    echo -e "${YELLOW}Backing up evidence storage...${NC}"
    backup_volume "eleanor_evidence_storage" "evidence_storage.tar"
}

# Backup configuration files
backup_config() {
    echo -e "${YELLOW}Backing up configuration...${NC}"

    mkdir -p "$BACKUP_PATH/config"

    # Copy .env file
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        cp "$PROJECT_ROOT/.env" "$BACKUP_PATH/config/.env"
        echo -e "${GREEN}  Done: .env${NC}"
    fi

    # Copy certificates
    if [[ -d "$PROJECT_ROOT/certificates" ]]; then
        cp -r "$PROJECT_ROOT/certificates" "$BACKUP_PATH/config/"
        echo -e "${GREEN}  Done: certificates/${NC}"
    fi

    # Copy docker-compose files
    for f in docker-compose*.yml; do
        if [[ -f "$PROJECT_ROOT/$f" ]]; then
            cp "$PROJECT_ROOT/$f" "$BACKUP_PATH/config/"
        fi
    done

    echo -e "${GREEN}  Configuration backed up${NC}"
}

# Create manifest
create_manifest() {
    echo -e "${YELLOW}Creating backup manifest...${NC}"

    cat > "$BACKUP_PATH/manifest.json" << EOF
{
    "backup_name": "$BACKUP_NAME",
    "timestamp": "$(date -Iseconds)",
    "hostname": "$(hostname)",
    "eleanor_version": "$(cat "$PROJECT_ROOT/VERSION" 2>/dev/null || echo "unknown")",
    "includes": {
        "postgres": true,
        "redis": true,
        "evidence": true,
        "elasticsearch": $INCLUDE_ELASTICSEARCH,
        "config": true
    },
    "files": [
$(ls -1 "$BACKUP_PATH" | sed 's/^/        "/;s/$/",/' | head -c -2)
    ]
}
EOF

    echo -e "${GREEN}  Done: manifest.json${NC}"
}

# Compress backup
compress_backup() {
    if ! $COMPRESS; then
        return
    fi

    echo -e "${YELLOW}Compressing backup...${NC}"

    cd "$OUTPUT_DIR"
    tar czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
    rm -rf "$BACKUP_NAME"

    BACKUP_PATH="${OUTPUT_DIR}/${BACKUP_NAME}.tar.gz"
    echo -e "${GREEN}  Compressed to: ${BACKUP_NAME}.tar.gz${NC}"
}

# Restart services if they were stopped
restart_services() {
    if $STOP_SERVICES; then
        echo -e "${YELLOW}Restarting services...${NC}"
        cd "$PROJECT_ROOT"
        docker compose start || true
    fi
}

# Print summary
print_summary() {
    echo ""
    echo -e "${GREEN}Backup Complete!${NC}"
    echo "================"
    echo ""
    echo "Location: $BACKUP_PATH"

    if $COMPRESS; then
        local size=$(du -h "${BACKUP_PATH}" | cut -f1)
        echo "Size: $size"
    else
        local size=$(du -sh "$BACKUP_PATH" | cut -f1)
        echo "Size: $size"
        echo ""
        echo "Contents:"
        ls -lh "$BACKUP_PATH"
    fi

    echo ""
    echo "To restore, run:"
    echo "  ./scripts/restore.sh --backup $BACKUP_PATH"
}

# Main execution
main() {
    # Run backups
    backup_config
    backup_postgres
    backup_redis
    backup_evidence
    backup_elasticsearch
    create_manifest
    compress_backup
    restart_services
    print_summary
}

# Trap to ensure services are restarted on error
trap restart_services EXIT

main
