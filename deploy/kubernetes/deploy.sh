#!/bin/bash
set -e

# Eleanor Kubernetes Deployment Script
# Usage: ./deploy.sh [environment] [action]
# Environments: development, production
# Actions: deploy, delete, status, logs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENVIRONMENT="${1:-development}"
ACTION="${2:-deploy}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi

    if ! command -v kustomize &> /dev/null; then
        log_warn "kustomize not found. Using kubectl's built-in kustomize."
        KUSTOMIZE="kubectl kustomize"
    else
        KUSTOMIZE="kustomize build"
    fi

    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
        exit 1
    fi

    log_info "Prerequisites OK"
}

# Get namespace based on environment
get_namespace() {
    if [ "$ENVIRONMENT" == "production" ]; then
        echo "eleanor"
    else
        echo "eleanor-dev"
    fi
}

# Deploy Eleanor
deploy() {
    local overlay_path="$SCRIPT_DIR/overlays/$ENVIRONMENT"
    local namespace=$(get_namespace)

    if [ ! -d "$overlay_path" ]; then
        log_error "Environment '$ENVIRONMENT' not found at $overlay_path"
        exit 1
    fi

    log_info "Deploying Eleanor to $ENVIRONMENT environment (namespace: $namespace)"

    # Build and apply manifests
    log_info "Building manifests..."
    $KUSTOMIZE "$overlay_path" > /tmp/eleanor-manifests.yaml

    log_info "Applying manifests..."
    kubectl apply -f /tmp/eleanor-manifests.yaml

    log_info "Waiting for deployments to be ready..."
    kubectl -n "$namespace" wait --for=condition=available deployment --all --timeout=300s || true

    log_info "Deployment complete!"

    # Show status
    status
}

# Delete Eleanor deployment
delete() {
    local overlay_path="$SCRIPT_DIR/overlays/$ENVIRONMENT"
    local namespace=$(get_namespace)

    log_warn "This will delete Eleanor from $ENVIRONMENT environment"
    read -p "Are you sure? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log_info "Aborted"
        exit 0
    fi

    log_info "Deleting Eleanor from $namespace..."

    $KUSTOMIZE "$overlay_path" | kubectl delete -f - --ignore-not-found

    # Optionally delete PVCs
    read -p "Delete persistent volumes? (yes/no): " delete_pvcs
    if [ "$delete_pvcs" == "yes" ]; then
        kubectl -n "$namespace" delete pvc --all
    fi

    log_info "Deletion complete"
}

# Show status
status() {
    local namespace=$(get_namespace)

    log_info "Eleanor status in namespace: $namespace"
    echo ""

    echo "=== Pods ==="
    kubectl -n "$namespace" get pods -o wide
    echo ""

    echo "=== Services ==="
    kubectl -n "$namespace" get svc
    echo ""

    echo "=== HPA ==="
    kubectl -n "$namespace" get hpa
    echo ""

    echo "=== PVCs ==="
    kubectl -n "$namespace" get pvc
    echo ""

    echo "=== Ingress ==="
    kubectl -n "$namespace" get ingress
}

# Show logs
logs() {
    local namespace=$(get_namespace)
    local component="${3:-backend}"

    log_info "Showing logs for $component in $namespace"
    kubectl -n "$namespace" logs -l "app.kubernetes.io/name=$component" --tail=100 -f
}

# Port forward for local access
port_forward() {
    local namespace=$(get_namespace)

    log_info "Starting port forwards..."
    log_info "Frontend: http://localhost:8080"
    log_info "Backend API: http://localhost:8000"
    log_info "Press Ctrl+C to stop"

    kubectl -n "$namespace" port-forward svc/frontend 8080:80 &
    kubectl -n "$namespace" port-forward svc/backend 8000:8000 &
    wait
}

# Scale deployment
scale() {
    local namespace=$(get_namespace)
    local component="${3:-backend}"
    local replicas="${4:-3}"

    log_info "Scaling $component to $replicas replicas"
    kubectl -n "$namespace" scale deployment "$component" --replicas="$replicas"
}

# Main
check_prerequisites

case "$ACTION" in
    deploy)
        deploy
        ;;
    delete)
        delete
        ;;
    status)
        status
        ;;
    logs)
        logs "$@"
        ;;
    port-forward)
        port_forward
        ;;
    scale)
        scale "$@"
        ;;
    *)
        echo "Usage: $0 [environment] [action]"
        echo ""
        echo "Environments: development, production"
        echo ""
        echo "Actions:"
        echo "  deploy       Deploy Eleanor to cluster"
        echo "  delete       Delete Eleanor deployment"
        echo "  status       Show deployment status"
        echo "  logs         Show logs (logs [component])"
        echo "  port-forward Start port forwarding for local access"
        echo "  scale        Scale deployment (scale [component] [replicas])"
        exit 1
        ;;
esac
