#!/bin/bash
# Eleanor Health Check Script
# Validates all services are running and healthy
# Usage: ./health-check.sh [--json] [--verbose] [--wait SECONDS]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
JSON_OUTPUT=false
VERBOSE=false
WAIT_TIMEOUT=0
BACKEND_URL="${ELEANOR_BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${ELEANOR_FRONTEND_URL:-http://localhost:80}"
ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --json|-j)
            JSON_OUTPUT=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --wait|-w)
            WAIT_TIMEOUT="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Check health of all Eleanor services"
            echo ""
            echo "Options:"
            echo "  -j, --json           Output as JSON"
            echo "  -v, --verbose        Show detailed output"
            echo "  -w, --wait SECONDS   Wait for services (retry until timeout)"
            echo "  -h, --help           Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Health check results
declare -A HEALTH_STATUS
declare -A HEALTH_DETAILS

# Check function with retry support
check_service() {
    local name="$1"
    local check_cmd="$2"
    local start_time=$(date +%s)

    while true; do
        if eval "$check_cmd" >/dev/null 2>&1; then
            HEALTH_STATUS["$name"]="healthy"
            HEALTH_DETAILS["$name"]="Service responding"
            return 0
        else
            local current_time=$(date +%s)
            local elapsed=$((current_time - start_time))

            if [[ $WAIT_TIMEOUT -gt 0 ]] && [[ $elapsed -lt $WAIT_TIMEOUT ]]; then
                if $VERBOSE; then
                    echo -e "${YELLOW}Waiting for $name... ($elapsed/${WAIT_TIMEOUT}s)${NC}"
                fi
                sleep 2
            else
                HEALTH_STATUS["$name"]="unhealthy"
                HEALTH_DETAILS["$name"]="Service not responding"
                return 1
            fi
        fi
    done
}

# Check PostgreSQL
check_postgres() {
    local name="postgres"
    if command -v pg_isready >/dev/null 2>&1; then
        check_service "$name" "pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT -q"
    elif command -v nc >/dev/null 2>&1; then
        check_service "$name" "nc -z $POSTGRES_HOST $POSTGRES_PORT"
    else
        # Try via docker
        check_service "$name" "docker exec eleanor-postgres pg_isready -U eleanor -d eleanor -q"
    fi
}

# Check Elasticsearch
check_elasticsearch() {
    local name="elasticsearch"
    local cmd="curl -sf '$ELASTICSEARCH_URL/_cluster/health' | grep -qE '\"status\":\"(green|yellow)\"'"
    check_service "$name" "$cmd"

    if [[ "${HEALTH_STATUS[$name]}" == "healthy" ]]; then
        local status=$(curl -sf "$ELASTICSEARCH_URL/_cluster/health" 2>/dev/null | grep -oP '"status":"[^"]*"' | cut -d'"' -f4)
        HEALTH_DETAILS["$name"]="Cluster status: $status"
    fi
}

# Check Redis
check_redis() {
    local name="redis"
    local host=$(echo "$REDIS_URL" | sed -E 's|redis://([^:]+).*|\1|')
    local port=$(echo "$REDIS_URL" | sed -E 's|.*:([0-9]+).*|\1|')
    port=${port:-6379}

    if command -v redis-cli >/dev/null 2>&1; then
        check_service "$name" "redis-cli -h $host -p $port ping | grep -q PONG"
    elif command -v nc >/dev/null 2>&1; then
        check_service "$name" "echo PING | nc -w1 $host $port | grep -q PONG"
    else
        check_service "$name" "docker exec eleanor-redis redis-cli ping | grep -q PONG"
    fi
}

# Check Backend API
check_backend() {
    local name="backend"
    local cmd="curl -sf '$BACKEND_URL/api/v1/auth/me' 2>/dev/null | grep -qE '(401|username)'"
    # We expect 401 (unauthorized) which proves API is running
    check_service "$name" "curl -sf -o /dev/null -w '%{http_code}' '$BACKEND_URL/api/v1/auth/me' | grep -qE '(200|401|403)'"

    if [[ "${HEALTH_STATUS[$name]}" == "healthy" ]]; then
        HEALTH_DETAILS["$name"]="API responding"
    fi
}

# Check Frontend
check_frontend() {
    local name="frontend"
    check_service "$name" "curl -sf -o /dev/null '$FRONTEND_URL'"

    if [[ "${HEALTH_STATUS[$name]}" == "healthy" ]]; then
        HEALTH_DETAILS["$name"]="Frontend serving"
    fi
}

# Check Docker containers
check_docker_containers() {
    if ! command -v docker >/dev/null 2>&1; then
        if $VERBOSE; then
            echo -e "${YELLOW}Docker not available, skipping container checks${NC}"
        fi
        return
    fi

    local containers=("eleanor-postgres" "eleanor-elasticsearch" "eleanor-redis" "eleanor-backend" "eleanor-frontend")

    for container in "${containers[@]}"; do
        local status=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "not_found")
        local health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "none")

        if [[ "$status" == "running" ]]; then
            if [[ "$health" == "healthy" ]] || [[ "$health" == "none" ]]; then
                HEALTH_STATUS["container:$container"]="healthy"
                HEALTH_DETAILS["container:$container"]="Running (health: $health)"
            else
                HEALTH_STATUS["container:$container"]="degraded"
                HEALTH_DETAILS["container:$container"]="Running but unhealthy"
            fi
        elif [[ "$status" == "not_found" ]]; then
            HEALTH_STATUS["container:$container"]="not_found"
            HEALTH_DETAILS["container:$container"]="Container not found"
        else
            HEALTH_STATUS["container:$container"]="unhealthy"
            HEALTH_DETAILS["container:$container"]="Status: $status"
        fi
    done
}

# Print results in human-readable format
print_results() {
    echo -e "${BLUE}Eleanor Health Check Results${NC}"
    echo "=============================="
    echo ""

    local all_healthy=true

    # Core services
    echo -e "${CYAN}Core Services:${NC}"
    for service in postgres elasticsearch redis backend frontend; do
        local status="${HEALTH_STATUS[$service]:-unknown}"
        local details="${HEALTH_DETAILS[$service]:-No details}"

        case $status in
            healthy)
                echo -e "  ${GREEN}[OK]${NC} $service - $details"
                ;;
            degraded)
                echo -e "  ${YELLOW}[WARN]${NC} $service - $details"
                all_healthy=false
                ;;
            unhealthy)
                echo -e "  ${RED}[FAIL]${NC} $service - $details"
                all_healthy=false
                ;;
            *)
                echo -e "  ${YELLOW}[?]${NC} $service - $status"
                all_healthy=false
                ;;
        esac
    done

    # Docker containers (if checked)
    local has_container_checks=false
    for key in "${!HEALTH_STATUS[@]}"; do
        if [[ "$key" == container:* ]]; then
            has_container_checks=true
            break
        fi
    done

    if $has_container_checks; then
        echo ""
        echo -e "${CYAN}Docker Containers:${NC}"
        for key in "${!HEALTH_STATUS[@]}"; do
            if [[ "$key" == container:* ]]; then
                local container_name="${key#container:}"
                local status="${HEALTH_STATUS[$key]}"
                local details="${HEALTH_DETAILS[$key]}"

                case $status in
                    healthy)
                        echo -e "  ${GREEN}[OK]${NC} $container_name - $details"
                        ;;
                    degraded|not_found)
                        echo -e "  ${YELLOW}[WARN]${NC} $container_name - $details"
                        ;;
                    unhealthy)
                        echo -e "  ${RED}[FAIL]${NC} $container_name - $details"
                        all_healthy=false
                        ;;
                esac
            fi
        done
    fi

    echo ""
    if $all_healthy; then
        echo -e "${GREEN}Overall Status: HEALTHY${NC}"
        return 0
    else
        echo -e "${RED}Overall Status: UNHEALTHY${NC}"
        return 1
    fi
}

# Print results as JSON
print_json() {
    echo "{"
    echo "  \"timestamp\": \"$(date -Iseconds)\","
    echo "  \"services\": {"

    local first=true
    for service in postgres elasticsearch redis backend frontend; do
        local status="${HEALTH_STATUS[$service]:-unknown}"
        local details="${HEALTH_DETAILS[$service]:-No details}"

        if ! $first; then
            echo ","
        fi
        first=false

        printf "    \"%s\": {\"status\": \"%s\", \"details\": \"%s\"}" "$service" "$status" "$details"
    done

    echo ""
    echo "  },"
    echo "  \"containers\": {"

    first=true
    for key in "${!HEALTH_STATUS[@]}"; do
        if [[ "$key" == container:* ]]; then
            local container_name="${key#container:}"
            local status="${HEALTH_STATUS[$key]}"
            local details="${HEALTH_DETAILS[$key]}"

            if ! $first; then
                echo ","
            fi
            first=false

            printf "    \"%s\": {\"status\": \"%s\", \"details\": \"%s\"}" "$container_name" "$status" "$details"
        fi
    done

    echo ""
    echo "  },"

    # Determine overall status
    local overall="healthy"
    for key in "${!HEALTH_STATUS[@]}"; do
        if [[ "${HEALTH_STATUS[$key]}" == "unhealthy" ]]; then
            overall="unhealthy"
            break
        fi
    done

    echo "  \"overall\": \"$overall\""
    echo "}"
}

# Main execution
main() {
    if $VERBOSE; then
        echo -e "${BLUE}Starting health checks...${NC}"
        echo ""
    fi

    # Run all checks
    check_postgres
    check_elasticsearch
    check_redis
    check_backend
    check_frontend
    check_docker_containers

    # Output results
    if $JSON_OUTPUT; then
        print_json
    else
        print_results
    fi
}

main
