#!/bin/bash
# Eleanor Security Hardening Script
# Applies production security settings to OVA deployment
# Usage: ./security-hardening.sh [--check-only] [--verbose]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Flags
CHECK_ONLY=false
VERBOSE=false
FIXES_APPLIED=0
ISSUES_FOUND=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --check-only|-c)
            CHECK_ONLY=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Apply security hardening to Eleanor deployment"
            echo ""
            echo "Options:"
            echo "  -c, --check-only    Only check, don't apply fixes"
            echo "  -v, --verbose       Show detailed output"
            echo "  -h, --help          Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
    ((ISSUES_FOUND++)) || true
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    ((ISSUES_FOUND++)) || true
}

log_fix() {
    echo -e "${CYAN}[FIX]${NC} $1"
    ((FIXES_APPLIED++)) || true
}

# Banner
print_banner() {
    echo ""
    echo -e "${BLUE}${BOLD}Eleanor Security Hardening${NC}"
    echo "=========================="
    echo ""
    if $CHECK_ONLY; then
        echo -e "${YELLOW}Running in check-only mode${NC}"
    fi
    echo ""
}

# =============================================================================
# File Permission Checks
# =============================================================================

check_file_permissions() {
    log_info "Checking file permissions..."

    # .env file should be readable only by owner
    if [[ -f "$PROJECT_ROOT/.env" ]]; then
        local perms=$(stat -c %a "$PROJECT_ROOT/.env" 2>/dev/null || stat -f %OLp "$PROJECT_ROOT/.env" 2>/dev/null)
        if [[ "$perms" != "600" ]]; then
            log_warn ".env file permissions are $perms (should be 600)"
            if ! $CHECK_ONLY; then
                chmod 600 "$PROJECT_ROOT/.env"
                log_fix "Set .env permissions to 600"
            fi
        else
            log_ok ".env file permissions are correct (600)"
        fi
    fi

    # Certificates directory
    if [[ -d "$PROJECT_ROOT/certificates" ]]; then
        local cert_perms=$(stat -c %a "$PROJECT_ROOT/certificates" 2>/dev/null || stat -f %OLp "$PROJECT_ROOT/certificates" 2>/dev/null)
        if [[ "$cert_perms" != "700" ]]; then
            log_warn "certificates directory permissions are $cert_perms (should be 700)"
            if ! $CHECK_ONLY; then
                chmod 700 "$PROJECT_ROOT/certificates"
                log_fix "Set certificates directory permissions to 700"
            fi
        else
            log_ok "certificates directory permissions are correct"
        fi

        # Check individual key files
        for key in "$PROJECT_ROOT/certificates"/*.key "$PROJECT_ROOT/certificates"/*.pem; do
            if [[ -f "$key" ]]; then
                local key_perms=$(stat -c %a "$key" 2>/dev/null || stat -f %OLp "$key" 2>/dev/null)
                if [[ "$key_perms" != "600" ]]; then
                    log_warn "Key file $key has permissions $key_perms (should be 600)"
                    if ! $CHECK_ONLY; then
                        chmod 600 "$key"
                        log_fix "Set $key permissions to 600"
                    fi
                fi
            fi
        done
    fi

    # Scripts should be executable but not writable by group/others
    for script in "$SCRIPT_DIR"/*.sh; do
        if [[ -f "$script" ]]; then
            local script_perms=$(stat -c %a "$script" 2>/dev/null || stat -f %OLp "$script" 2>/dev/null)
            if [[ ! "$script_perms" =~ ^7[05][05]$ ]]; then
                if ! $CHECK_ONLY; then
                    chmod 755 "$script"
                    log_fix "Set $script permissions to 755"
                fi
            fi
        fi
    done

    echo ""
}

# =============================================================================
# Environment Configuration Checks
# =============================================================================

check_env_security() {
    log_info "Checking environment configuration..."

    if [[ ! -f "$PROJECT_ROOT/.env" ]]; then
        log_error ".env file not found"
        return
    fi

    # Source .env to check values
    set +u  # Allow unset variables
    source "$PROJECT_ROOT/.env"
    set -u

    # Check DEBUG is disabled
    if [[ "${DEBUG:-true}" == "true" ]]; then
        log_warn "DEBUG is enabled (should be false in production)"
        if ! $CHECK_ONLY; then
            sed -i.bak 's/^DEBUG=true/DEBUG=false/' "$PROJECT_ROOT/.env"
            log_fix "Disabled DEBUG mode"
        fi
    else
        log_ok "DEBUG is disabled"
    fi

    # Check registration is disabled
    if [[ "${SAM_ALLOW_REGISTRATION:-true}" == "true" ]]; then
        log_warn "User registration is enabled (consider disabling)"
    else
        log_ok "User registration is disabled"
    fi

    # Check SECRET_KEY is set and sufficient length
    if [[ -z "${SECRET_KEY:-}" ]]; then
        log_error "SECRET_KEY is not set"
    elif [[ ${#SECRET_KEY} -lt 32 ]]; then
        log_warn "SECRET_KEY is short (< 32 chars)"
    else
        log_ok "SECRET_KEY is set and has sufficient length"
    fi

    # Check database password
    if [[ -z "${POSTGRES_PASSWORD:-}" ]]; then
        log_error "POSTGRES_PASSWORD is not set"
    elif [[ "$POSTGRES_PASSWORD" == "eleanor" ]] || [[ "$POSTGRES_PASSWORD" == "password" ]]; then
        log_warn "POSTGRES_PASSWORD is a default/weak value"
    else
        log_ok "POSTGRES_PASSWORD is set"
    fi

    # Check CORS origins
    if [[ "${CORS_ORIGINS:-}" == "*" ]]; then
        log_warn "CORS_ORIGINS allows all origins (should be restricted)"
    else
        log_ok "CORS_ORIGINS is configured"
    fi

    # Check JWT expiration
    local jwt_expire="${JWT_EXPIRE_MINUTES:-60}"
    if [[ "$jwt_expire" -gt 480 ]]; then
        log_warn "JWT expiration is very long (${jwt_expire} minutes)"
    else
        log_ok "JWT expiration is reasonable (${jwt_expire} minutes)"
    fi

    echo ""
}

# =============================================================================
# SSL/TLS Checks
# =============================================================================

check_ssl_certificates() {
    log_info "Checking SSL certificates..."

    local cert_dir="$PROJECT_ROOT/certificates"

    if [[ ! -d "$cert_dir" ]]; then
        log_warn "Certificates directory not found"
        if ! $CHECK_ONLY; then
            mkdir -p "$cert_dir"
            chmod 700 "$cert_dir"
            log_fix "Created certificates directory"

            # Generate self-signed certificate
            if command -v openssl >/dev/null 2>&1; then
                local hostname="${ELEANOR_HOSTNAME:-localhost}"
                openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                    -keyout "$cert_dir/eleanor.key" \
                    -out "$cert_dir/eleanor.crt" \
                    -subj "/CN=$hostname" \
                    -addext "subjectAltName=DNS:$hostname,DNS:localhost,IP:127.0.0.1" \
                    2>/dev/null
                chmod 600 "$cert_dir/eleanor.key"
                log_fix "Generated self-signed certificate for $hostname"
            fi
        fi
        return
    fi

    # Check for certificate files
    local has_cert=false
    for cert in "$cert_dir"/*.crt "$cert_dir"/*.pem; do
        if [[ -f "$cert" ]] && [[ ! "$cert" == *".key"* ]]; then
            has_cert=true

            # Check expiration
            if command -v openssl >/dev/null 2>&1; then
                local expiry=$(openssl x509 -enddate -noout -in "$cert" 2>/dev/null | cut -d= -f2)
                local expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$expiry" +%s 2>/dev/null)
                local now_epoch=$(date +%s)
                local days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

                if [[ $days_left -lt 0 ]]; then
                    log_error "Certificate $cert has expired!"
                elif [[ $days_left -lt 30 ]]; then
                    log_warn "Certificate $cert expires in $days_left days"
                else
                    log_ok "Certificate $cert valid for $days_left days"
                fi
            fi
        fi
    done

    if ! $has_cert; then
        log_warn "No SSL certificates found"
    fi

    echo ""
}

# =============================================================================
# Docker Security Checks
# =============================================================================

check_docker_security() {
    log_info "Checking Docker security..."

    if ! command -v docker >/dev/null 2>&1; then
        log_warn "Docker not installed, skipping container checks"
        return
    fi

    # Check if containers are running as root
    for container in eleanor-backend eleanor-frontend eleanor-postgres eleanor-elasticsearch eleanor-redis; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            local user=$(docker exec "$container" whoami 2>/dev/null || echo "unknown")
            if [[ "$user" == "root" ]]; then
                log_warn "Container $container is running as root"
            else
                log_ok "Container $container running as $user"
            fi
        fi
    done

    # Check for exposed ports
    local exposed_ports=$(docker ps --format "{{.Ports}}" | grep -oE '0\.0\.0\.0:[0-9]+' | cut -d: -f2 | sort -u)
    if [[ -n "$exposed_ports" ]]; then
        $VERBOSE && log_info "Exposed ports: $exposed_ports"

        # Check for database ports exposed externally
        if echo "$exposed_ports" | grep -qE '^(5432|9200|6379)$'; then
            log_warn "Database/cache ports are exposed externally (5432, 9200, or 6379)"
        fi
    fi

    # Check resource limits
    for container in eleanor-backend eleanor-elasticsearch; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            local mem_limit=$(docker inspect --format '{{.HostConfig.Memory}}' "$container" 2>/dev/null)
            if [[ "$mem_limit" == "0" ]]; then
                log_warn "Container $container has no memory limit"
            fi
        fi
    done

    echo ""
}

# =============================================================================
# Network Security Checks
# =============================================================================

check_network_security() {
    log_info "Checking network security..."

    # Check for firewall
    local has_firewall=false

    if command -v ufw >/dev/null 2>&1; then
        if ufw status 2>/dev/null | grep -q "Status: active"; then
            has_firewall=true
            log_ok "UFW firewall is active"
        else
            log_warn "UFW is installed but not active"
        fi
    elif command -v firewall-cmd >/dev/null 2>&1; then
        if firewall-cmd --state 2>/dev/null | grep -q "running"; then
            has_firewall=true
            log_ok "firewalld is active"
        fi
    elif command -v iptables >/dev/null 2>&1; then
        local rules=$(iptables -L 2>/dev/null | wc -l)
        if [[ $rules -gt 8 ]]; then
            has_firewall=true
            log_ok "iptables has rules configured"
        fi
    fi

    if ! $has_firewall; then
        log_warn "No firewall detected or firewall is not active"
        if ! $CHECK_ONLY; then
            echo ""
            echo "Recommended firewall rules:"
            echo "  sudo ufw default deny incoming"
            echo "  sudo ufw default allow outgoing"
            echo "  sudo ufw allow ssh"
            echo "  sudo ufw allow 80/tcp"
            echo "  sudo ufw allow 443/tcp"
            echo "  sudo ufw enable"
        fi
    fi

    # Check for listening services
    if command -v ss >/dev/null 2>&1; then
        local listeners=$(ss -tlnp 2>/dev/null | grep LISTEN | wc -l)
        $VERBOSE && log_info "Found $listeners listening TCP services"
    fi

    echo ""
}

# =============================================================================
# Log Security Checks
# =============================================================================

check_logging() {
    log_info "Checking logging configuration..."

    # Check Docker logging driver
    if command -v docker >/dev/null 2>&1; then
        local log_driver=$(docker info 2>/dev/null | grep "Logging Driver" | awk '{print $3}')
        if [[ "$log_driver" == "json-file" ]]; then
            log_ok "Docker using json-file logging driver"

            # Check for log rotation
            local daemon_json="/etc/docker/daemon.json"
            if [[ -f "$daemon_json" ]]; then
                if grep -q "max-size" "$daemon_json"; then
                    log_ok "Docker log rotation is configured"
                else
                    log_warn "Docker log rotation not configured in daemon.json"
                fi
            else
                log_warn "Docker daemon.json not found, log rotation may not be configured"
            fi
        else
            log_ok "Docker using $log_driver logging driver"
        fi
    fi

    # Check log directory permissions
    if [[ -d "$PROJECT_ROOT/logs" ]]; then
        local log_perms=$(stat -c %a "$PROJECT_ROOT/logs" 2>/dev/null || stat -f %OLp "$PROJECT_ROOT/logs" 2>/dev/null)
        if [[ "$log_perms" != "750" ]] && [[ "$log_perms" != "700" ]]; then
            log_warn "logs directory has loose permissions ($log_perms)"
            if ! $CHECK_ONLY; then
                chmod 750 "$PROJECT_ROOT/logs"
                log_fix "Set logs directory permissions to 750"
            fi
        fi
    fi

    echo ""
}

# =============================================================================
# Backup Security Checks
# =============================================================================

check_backup_security() {
    log_info "Checking backup configuration..."

    local backup_dir="$PROJECT_ROOT/backups"

    if [[ -d "$backup_dir" ]]; then
        # Check permissions
        local backup_perms=$(stat -c %a "$backup_dir" 2>/dev/null || stat -f %OLp "$backup_dir" 2>/dev/null)
        if [[ "$backup_perms" != "700" ]] && [[ "$backup_perms" != "750" ]]; then
            log_warn "backups directory has loose permissions ($backup_perms)"
            if ! $CHECK_ONLY; then
                chmod 700 "$backup_dir"
                log_fix "Set backups directory permissions to 700"
            fi
        else
            log_ok "backups directory permissions are secure"
        fi

        # Check for recent backups
        local recent_backup=$(find "$backup_dir" -type f -mtime -7 2>/dev/null | head -1)
        if [[ -n "$recent_backup" ]]; then
            log_ok "Recent backup found within last 7 days"
        else
            log_warn "No recent backups found (older than 7 days)"
        fi
    else
        log_warn "Backup directory not found"
        if ! $CHECK_ONLY; then
            mkdir -p "$backup_dir"
            chmod 700 "$backup_dir"
            log_fix "Created secure backup directory"
        fi
    fi

    echo ""
}

# =============================================================================
# System Security Checks
# =============================================================================

check_system_security() {
    log_info "Checking system security..."

    # Check for security updates
    if command -v apt-get >/dev/null 2>&1; then
        local updates=$(apt-get -s upgrade 2>/dev/null | grep -c "^Inst" || echo "0")
        if [[ $updates -gt 0 ]]; then
            log_warn "$updates security updates available"
        else
            log_ok "System is up to date"
        fi
    fi

    # Check SSH configuration
    if [[ -f /etc/ssh/sshd_config ]]; then
        if grep -q "^PermitRootLogin yes" /etc/ssh/sshd_config; then
            log_warn "SSH allows root login"
        else
            log_ok "SSH root login is restricted"
        fi

        if grep -q "^PasswordAuthentication yes" /etc/ssh/sshd_config; then
            log_warn "SSH password authentication is enabled"
        fi
    fi

    # Check for fail2ban
    if command -v fail2ban-client >/dev/null 2>&1; then
        if systemctl is-active --quiet fail2ban 2>/dev/null; then
            log_ok "fail2ban is active"
        else
            log_warn "fail2ban is installed but not active"
        fi
    else
        log_warn "fail2ban is not installed (recommended for SSH protection)"
    fi

    echo ""
}

# =============================================================================
# Summary
# =============================================================================

print_summary() {
    echo ""
    echo -e "${BOLD}Security Hardening Summary${NC}"
    echo "=========================="
    echo ""

    if [[ $ISSUES_FOUND -eq 0 ]]; then
        echo -e "${GREEN}No security issues found!${NC}"
    else
        echo -e "${YELLOW}Issues found: $ISSUES_FOUND${NC}"
    fi

    if ! $CHECK_ONLY && [[ $FIXES_APPLIED -gt 0 ]]; then
        echo -e "${CYAN}Fixes applied: $FIXES_APPLIED${NC}"
    fi

    echo ""

    if [[ $ISSUES_FOUND -gt 0 ]]; then
        echo "Recommendations:"
        echo "  1. Review all warnings above"
        echo "  2. Run with sudo for system-level fixes"
        echo "  3. Review docs/PRODUCTION.md for detailed guidance"
        echo ""
        return 1
    fi

    return 0
}

# =============================================================================
# Main
# =============================================================================

main() {
    print_banner

    check_file_permissions
    check_env_security
    check_ssl_certificates
    check_docker_security
    check_network_security
    check_logging
    check_backup_security
    check_system_security

    print_summary
}

main
