#!/bin/bash
# Eleanor First-Run Setup Wizard
# Interactive configuration for OVA deployment
# Usage: ./first-run-setup.sh [--dry-run] [--non-interactive]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Flags
DRY_RUN=false
NON_INTERACTIVE=false

# Configuration values (to be collected)
ELEANOR_HOSTNAME=""
ADMIN_USERNAME=""
ADMIN_PASSWORD=""
ADMIN_EMAIL=""
ES_HEAP_SIZE="1g"
ENABLE_VELOCIRAPTOR=false
ENABLE_IRIS=false
ENABLE_OPENCTI=false
ENABLE_SHUFFLE=false
ENABLE_TIMESKETCH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --non-interactive|-y)
            NON_INTERACTIVE=true
            shift
            ;;
        --hostname)
            ELEANOR_HOSTNAME="$2"
            shift 2
            ;;
        --admin-user)
            ADMIN_USERNAME="$2"
            shift 2
            ;;
        --admin-password)
            ADMIN_PASSWORD="$2"
            shift 2
            ;;
        --admin-email)
            ADMIN_EMAIL="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Eleanor first-run configuration wizard"
            echo ""
            echo "Options:"
            echo "  --dry-run             Show what would be done without making changes"
            echo "  -y, --non-interactive Run with defaults, no prompts"
            echo "  --hostname NAME       Set hostname (required for non-interactive)"
            echo "  --admin-user USER     Admin username (required for non-interactive)"
            echo "  --admin-password PASS Admin password (required for non-interactive)"
            echo "  --admin-email EMAIL   Admin email (required for non-interactive)"
            echo "  -h, --help            Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Banner
print_banner() {
    echo ""
    echo -e "${BLUE}${BOLD}"
    echo "  ███████╗██╗     ███████╗ █████╗ ███╗   ██╗ ██████╗ ██████╗ "
    echo "  ██╔════╝██║     ██╔════╝██╔══██╗████╗  ██║██╔═══██╗██╔══██╗"
    echo "  █████╗  ██║     █████╗  ███████║██╔██╗ ██║██║   ██║██████╔╝"
    echo "  ██╔══╝  ██║     ██╔══╝  ██╔══██║██║╚██╗██║██║   ██║██╔══██╗"
    echo "  ███████╗███████╗███████╗██║  ██║██║ ╚████║╚██████╔╝██║  ██║"
    echo "  ╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝"
    echo -e "${NC}"
    echo -e "${CYAN}  Digital Forensics & Incident Response Platform${NC}"
    echo ""
    echo "  First-Run Setup Wizard"
    echo "  ======================"
    echo ""
}

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"

    local missing=()

    # Check for required tools
    for cmd in docker openssl curl; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done

    # Check Docker Compose
    if ! docker compose version >/dev/null 2>&1 && ! docker-compose version >/dev/null 2>&1; then
        missing+=("docker-compose")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo -e "${RED}Missing required tools: ${missing[*]}${NC}"
        echo "Please install them and try again."
        exit 1
    fi

    # Check if Docker daemon is running
    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}Docker daemon is not running.${NC}"
        echo "Please start Docker and try again."
        exit 1
    fi

    echo -e "${GREEN}All prerequisites met.${NC}"
    echo ""
}

# Detect system resources
detect_resources() {
    echo -e "${YELLOW}Detecting system resources...${NC}"

    # Memory
    local total_mem_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    local total_mem_gb=$((total_mem_kb / 1024 / 1024))

    echo "  Total RAM: ${total_mem_gb}GB"

    # Set Elasticsearch heap based on available memory
    if [[ $total_mem_gb -ge 32 ]]; then
        ES_HEAP_SIZE="8g"
    elif [[ $total_mem_gb -ge 16 ]]; then
        ES_HEAP_SIZE="4g"
    elif [[ $total_mem_gb -ge 8 ]]; then
        ES_HEAP_SIZE="2g"
    else
        ES_HEAP_SIZE="1g"
    fi

    echo "  Recommended ES heap: ${ES_HEAP_SIZE}"

    # CPU
    local cpu_cores=$(nproc 2>/dev/null || echo "unknown")
    echo "  CPU cores: ${cpu_cores}"

    # Disk
    local disk_free=$(df -h "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    echo "  Free disk space: ${disk_free}"

    echo ""
}

# Check if this is a first run
is_first_run() {
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        return 1
    fi
    return 0
}

# Validate password strength
validate_password() {
    local password="$1"
    local min_length=12

    if [[ ${#password} -lt $min_length ]]; then
        echo "Password must be at least $min_length characters"
        return 1
    fi

    if ! echo "$password" | grep -qE '[A-Z]'; then
        echo "Password must contain at least one uppercase letter"
        return 1
    fi

    if ! echo "$password" | grep -qE '[a-z]'; then
        echo "Password must contain at least one lowercase letter"
        return 1
    fi

    if ! echo "$password" | grep -qE '[0-9]'; then
        echo "Password must contain at least one digit"
        return 1
    fi

    return 0
}

# Prompt for configuration
collect_configuration() {
    echo -e "${CYAN}Configuration${NC}"
    echo "============="
    echo ""

    # Hostname
    if [[ -z "$ELEANOR_HOSTNAME" ]]; then
        local default_hostname=$(hostname -f 2>/dev/null || hostname)
        read -p "Hostname/IP for Eleanor [$default_hostname]: " input
        ELEANOR_HOSTNAME="${input:-$default_hostname}"
    fi
    echo -e "  Hostname: ${GREEN}$ELEANOR_HOSTNAME${NC}"

    # Admin credentials
    echo ""
    echo -e "${CYAN}Admin Account${NC}"

    if [[ -z "$ADMIN_USERNAME" ]]; then
        read -p "Admin username [admin]: " input
        ADMIN_USERNAME="${input:-admin}"
    fi
    echo -e "  Username: ${GREEN}$ADMIN_USERNAME${NC}"

    if [[ -z "$ADMIN_PASSWORD" ]]; then
        while true; do
            read -sp "Admin password (min 12 chars, mixed case, digit): " ADMIN_PASSWORD
            echo ""

            local validation_msg
            if validation_msg=$(validate_password "$ADMIN_PASSWORD"); then
                read -sp "Confirm password: " confirm_password
                echo ""

                if [[ "$ADMIN_PASSWORD" == "$confirm_password" ]]; then
                    break
                else
                    echo -e "${RED}Passwords do not match. Try again.${NC}"
                fi
            else
                echo -e "${RED}$validation_msg${NC}"
            fi
        done
    fi
    echo -e "  Password: ${GREEN}[set]${NC}"

    if [[ -z "$ADMIN_EMAIL" ]]; then
        read -p "Admin email [admin@$ELEANOR_HOSTNAME]: " input
        ADMIN_EMAIL="${input:-admin@$ELEANOR_HOSTNAME}"
    fi
    echo -e "  Email: ${GREEN}$ADMIN_EMAIL${NC}"

    # Integrations
    echo ""
    echo -e "${CYAN}Integrations${NC}"
    echo "Which integrations do you want to enable?"
    echo "(You can enable these later by editing .env)"
    echo ""

    if ! $NON_INTERACTIVE; then
        read -p "Enable Velociraptor (endpoint collection)? [y/N]: " -n 1 -r
        echo ""
        [[ $REPLY =~ ^[Yy]$ ]] && ENABLE_VELOCIRAPTOR=true

        read -p "Enable IRIS (case management)? [y/N]: " -n 1 -r
        echo ""
        [[ $REPLY =~ ^[Yy]$ ]] && ENABLE_IRIS=true

        read -p "Enable OpenCTI (threat intelligence)? [y/N]: " -n 1 -r
        echo ""
        [[ $REPLY =~ ^[Yy]$ ]] && ENABLE_OPENCTI=true

        read -p "Enable Shuffle (SOAR workflows)? [y/N]: " -n 1 -r
        echo ""
        [[ $REPLY =~ ^[Yy]$ ]] && ENABLE_SHUFFLE=true

        read -p "Enable Timesketch (timeline analysis)? [y/N]: " -n 1 -r
        echo ""
        [[ $REPLY =~ ^[Yy]$ ]] && ENABLE_TIMESKETCH=true
    fi

    echo ""
    echo "Selected integrations:"
    $ENABLE_VELOCIRAPTOR && echo -e "  ${GREEN}[x]${NC} Velociraptor" || echo -e "  [ ] Velociraptor"
    $ENABLE_IRIS && echo -e "  ${GREEN}[x]${NC} IRIS" || echo -e "  [ ] IRIS"
    $ENABLE_OPENCTI && echo -e "  ${GREEN}[x]${NC} OpenCTI" || echo -e "  [ ] OpenCTI"
    $ENABLE_SHUFFLE && echo -e "  ${GREEN}[x]${NC} Shuffle" || echo -e "  [ ] Shuffle"
    $ENABLE_TIMESKETCH && echo -e "  ${GREEN}[x]${NC} Timesketch" || echo -e "  [ ] Timesketch"

    echo ""
}

# Generate secrets and write .env
generate_env() {
    echo -e "${YELLOW}Generating configuration...${NC}"

    if $DRY_RUN; then
        echo -e "${CYAN}[DRY RUN] Would generate secrets and create .env${NC}"
        return
    fi

    # Generate secrets
    local secrets_file=$(mktemp)
    bash "$SCRIPT_DIR/generate-secrets.sh" --output "$secrets_file"

    # Source the secrets
    source "$secrets_file"

    # Create .env file
    cat > "$PROJECT_ROOT/.env" << EOF
# =============================================================================
# Eleanor Configuration
# Generated by first-run-setup.sh on $(date -Iseconds)
# =============================================================================

# =============================================================================
# Core Settings
# =============================================================================
ELEANOR_HOSTNAME=$ELEANOR_HOSTNAME
SECRET_KEY=$SECRET_KEY

# =============================================================================
# Database
# =============================================================================
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
DATABASE_URL=postgresql://eleanor:\${POSTGRES_PASSWORD}@postgres:5432/eleanor

# =============================================================================
# Elasticsearch
# =============================================================================
ELASTICSEARCH_URL=http://elasticsearch:9200
ES_JAVA_OPTS=-Xms${ES_HEAP_SIZE} -Xmx${ES_HEAP_SIZE}

# =============================================================================
# Redis
# =============================================================================
REDIS_URL=redis://redis:6379

# =============================================================================
# Security
# =============================================================================
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
CORS_ORIGINS=https://$ELEANOR_HOSTNAME,http://localhost:4200

# =============================================================================
# Application
# =============================================================================
DEBUG=false
LOG_LEVEL=INFO
EVIDENCE_PATH=/app/evidence

# =============================================================================
# Authentication
# =============================================================================
SAM_ENABLED=true
SAM_ALLOW_REGISTRATION=false

# Initial admin (created on first run)
ADMIN_USERNAME=$ADMIN_USERNAME
ADMIN_PASSWORD=$ADMIN_PASSWORD
ADMIN_EMAIL=$ADMIN_EMAIL

# =============================================================================
# Integrations
# =============================================================================

# Velociraptor
VELOCIRAPTOR_ENABLED=$ENABLE_VELOCIRAPTOR
VELOCIRAPTOR_URL=https://velociraptor:8003
VELOCIRAPTOR_API_KEY=
VELOCIRAPTOR_VERIFY_SSL=false

# IRIS
IRIS_ENABLED=$ENABLE_IRIS
IRIS_URL=https://iris:8443
IRIS_API_KEY=
IRIS_VERIFY_SSL=false
IRIS_DB_PASSWORD=$IRIS_DB_PASSWORD
IRIS_SECRET_KEY=$IRIS_SECRET_KEY
IRIS_PASSWORD_SALT=$IRIS_PASSWORD_SALT
IRIS_ADMIN_PASSWORD=$IRIS_ADMIN_PASSWORD

# OpenCTI
OPENCTI_ENABLED=$ENABLE_OPENCTI
OPENCTI_URL=http://opencti:8080
OPENCTI_API_KEY=$OPENCTI_ADMIN_TOKEN
OPENCTI_VERIFY_SSL=false
OPENCTI_ADMIN_EMAIL=$ADMIN_EMAIL
OPENCTI_ADMIN_PASSWORD=$OPENCTI_ADMIN_PASSWORD
OPENCTI_ADMIN_TOKEN=$OPENCTI_ADMIN_TOKEN

# Shuffle
SHUFFLE_ENABLED=$ENABLE_SHUFFLE
SHUFFLE_URL=http://shuffle:3001
SHUFFLE_API_KEY=$SHUFFLE_API_KEY
SHUFFLE_VERIFY_SSL=false
SHUFFLE_ADMIN_USER=$ADMIN_USERNAME
SHUFFLE_ADMIN_PASSWORD=$SHUFFLE_ADMIN_PASSWORD

# Timesketch
TIMESKETCH_ENABLED=$ENABLE_TIMESKETCH
TIMESKETCH_URL=http://timesketch:5000
TIMESKETCH_USERNAME=$ADMIN_USERNAME
TIMESKETCH_PASSWORD=$TIMESKETCH_PASSWORD
TIMESKETCH_VERIFY_SSL=false
TIMESKETCH_DB_PASSWORD=$TIMESKETCH_DB_PASSWORD
TIMESKETCH_SECRET_KEY=$TIMESKETCH_SECRET_KEY
EOF

    chmod 600 "$PROJECT_ROOT/.env"
    rm -f "$secrets_file"

    echo -e "${GREEN}.env file created${NC}"
}

# Generate SSL certificates
generate_certificates() {
    echo -e "${YELLOW}Generating SSL certificates...${NC}"

    if $DRY_RUN; then
        echo -e "${CYAN}[DRY RUN] Would generate SSL certificates${NC}"
        return
    fi

    bash "$SCRIPT_DIR/generate-certs.sh" \
        --hostname "$ELEANOR_HOSTNAME" \
        --output "$PROJECT_ROOT/certificates"

    echo -e "${GREEN}Certificates generated${NC}"
}

# Start services
start_services() {
    echo -e "${YELLOW}Starting Eleanor services...${NC}"

    if $DRY_RUN; then
        echo -e "${CYAN}[DRY RUN] Would run: docker compose --profile prod up -d${NC}"
        return
    fi

    cd "$PROJECT_ROOT"

    # Pull latest images
    echo "Pulling images..."
    docker compose pull

    # Start services
    echo "Starting containers..."
    docker compose --profile prod up -d

    echo -e "${GREEN}Services started${NC}"
}

# Wait for services to be healthy
wait_for_services() {
    echo -e "${YELLOW}Waiting for services to be healthy...${NC}"

    if $DRY_RUN; then
        echo -e "${CYAN}[DRY RUN] Would wait for health checks${NC}"
        return
    fi

    local max_wait=120
    local waited=0

    while [[ $waited -lt $max_wait ]]; do
        if bash "$SCRIPT_DIR/health-check.sh" --wait 5 >/dev/null 2>&1; then
            echo -e "${GREEN}All services healthy${NC}"
            return 0
        fi

        echo -n "."
        sleep 5
        waited=$((waited + 5))
    done

    echo ""
    echo -e "${RED}Timeout waiting for services. Running health check:${NC}"
    bash "$SCRIPT_DIR/health-check.sh" || true
    return 1
}

# Create admin user via API
create_admin_user() {
    echo -e "${YELLOW}Creating admin user...${NC}"

    if $DRY_RUN; then
        echo -e "${CYAN}[DRY RUN] Would create admin user via API${NC}"
        return
    fi

    # Wait a bit more for the API to be fully ready
    sleep 5

    # Try to create the admin user
    local response
    response=$(curl -sf -X POST "http://localhost:8000/api/v1/auth/setup" \
        -H "Content-Type: application/json" \
        -d "{
            \"username\": \"$ADMIN_USERNAME\",
            \"password\": \"$ADMIN_PASSWORD\",
            \"email\": \"$ADMIN_EMAIL\"
        }" 2>&1) || true

    if echo "$response" | grep -q "username"; then
        echo -e "${GREEN}Admin user created${NC}"
    elif echo "$response" | grep -qi "already"; then
        echo -e "${YELLOW}Admin user already exists${NC}"
    else
        echo -e "${YELLOW}Note: Admin user may need to be created manually${NC}"
        echo "You can create it by running:"
        echo "  docker exec eleanor-backend python -c \"from app.cli import create_admin; create_admin('$ADMIN_USERNAME', '$ADMIN_PASSWORD', '$ADMIN_EMAIL')\""
    fi
}

# Print final summary
print_summary() {
    echo ""
    echo -e "${GREEN}${BOLD}Setup Complete!${NC}"
    echo "==============="
    echo ""
    echo -e "${CYAN}Access Eleanor:${NC}"
    echo "  URL: https://$ELEANOR_HOSTNAME"
    echo "  Username: $ADMIN_USERNAME"
    echo "  Password: [as configured]"
    echo ""
    echo -e "${CYAN}Service URLs:${NC}"
    echo "  Frontend:      https://$ELEANOR_HOSTNAME"
    echo "  Backend API:   https://$ELEANOR_HOSTNAME/api"
    echo "  Elasticsearch: http://localhost:9200"

    if $ENABLE_IRIS; then
        echo "  IRIS:          https://$ELEANOR_HOSTNAME:8443"
    fi

    echo ""
    echo -e "${CYAN}Next Steps:${NC}"
    echo "  1. Access Eleanor at https://$ELEANOR_HOSTNAME"
    echo "  2. Accept the self-signed certificate warning"
    echo "  3. Log in with your admin credentials"
    echo "  4. Configure integrations in Settings"
    echo ""
    echo -e "${CYAN}Useful Commands:${NC}"
    echo "  View logs:      docker compose logs -f"
    echo "  Health check:   ./scripts/health-check.sh"
    echo "  Stop services:  docker compose down"
    echo "  Backup:         ./scripts/backup.sh"
    echo ""
    echo -e "${YELLOW}Note: Self-signed certificates are used.${NC}"
    echo "For production, configure proper SSL certificates."
    echo ""
}

# Main execution
main() {
    print_banner

    # Check if already configured
    if ! is_first_run; then
        echo -e "${YELLOW}Eleanor appears to be already configured (.env exists).${NC}"
        echo ""
        read -p "Do you want to reconfigure? This will overwrite existing settings. [y/N]: " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Exiting. Use --help for options."
            exit 0
        fi
    fi

    check_prerequisites
    detect_resources
    collect_configuration

    echo ""
    echo -e "${CYAN}Configuration Summary${NC}"
    echo "====================="
    echo "  Hostname: $ELEANOR_HOSTNAME"
    echo "  Admin: $ADMIN_USERNAME ($ADMIN_EMAIL)"
    echo "  ES Heap: $ES_HEAP_SIZE"
    echo ""

    if ! $NON_INTERACTIVE && ! $DRY_RUN; then
        read -p "Proceed with setup? [Y/n]: " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "Setup cancelled."
            exit 0
        fi
    fi

    generate_env
    generate_certificates
    start_services
    wait_for_services
    create_admin_user
    print_summary
}

main
