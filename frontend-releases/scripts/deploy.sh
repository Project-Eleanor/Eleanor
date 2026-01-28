#!/usr/bin/env bash
#
# Eleanor Releases Website - Deployment Script
#
# Deploys the frontend to both Cloudflare Pages and the internal server (10.130.130.200).
#
# Prerequisites:
#   - 1Password CLI (op) installed and authenticated
#   - wrangler (Cloudflare CLI) installed
#   - sshpass installed
#   - Node.js and npm installed
#
# Usage:
#   ./scripts/deploy.sh [target]
#
# Targets:
#   all        - Deploy to both Cloudflare and internal server (default)
#   cloudflare - Deploy to Cloudflare Pages only
#   internal   - Deploy to internal server only
#   build      - Build only, no deployment
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$PROJECT_DIR/dist/eleanor-releases/browser"

# Configuration
CLOUDFLARE_PROJECT="eleanor-releases"
INTERNAL_SERVER="10.130.130.200"
INTERNAL_USER="template"
INTERNAL_WEB_ROOT="/var/www/eleanor-releases/frontend/dist"
OP_VAULT_CLOUDFLARE="Eleanor"
OP_ITEM_CLOUDFLARE="Cloudflare API Token"
OP_VAULT_SERVER="DFIR-Lab-Infra"
OP_ITEM_SERVER="Linux - vm-eleanor (template)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Build the frontend
build() {
    log_info "Building frontend..."
    cd "$PROJECT_DIR"
    npm run build
    log_success "Build complete: $DIST_DIR"
}

# Deploy to Cloudflare Pages
deploy_cloudflare() {
    log_info "Deploying to Cloudflare Pages..."

    # Get Cloudflare API token from 1Password
    local token
    token=$(op item get "$OP_ITEM_CLOUDFLARE" --vault="$OP_VAULT_CLOUDFLARE" --fields credential --reveal 2>/dev/null)

    if [[ -z "$token" ]]; then
        log_error "Failed to retrieve Cloudflare API token from 1Password"
        return 1
    fi

    # Deploy using wrangler
    CLOUDFLARE_API_TOKEN="$token" npx wrangler pages deploy "$DIST_DIR" \
        --project-name="$CLOUDFLARE_PROJECT" \
        --commit-dirty=true

    log_success "Deployed to Cloudflare Pages"
    log_info "  - https://www.project-eleanor.com"
    log_info "  - https://project-eleanor.com"
}

# Deploy to internal server
deploy_internal() {
    log_info "Deploying to internal server ($INTERNAL_SERVER)..."

    # Get server password from 1Password
    local password
    password=$(op item get "$OP_ITEM_SERVER" --vault="$OP_VAULT_SERVER" --fields password --reveal 2>/dev/null)

    if [[ -z "$password" ]]; then
        log_error "Failed to retrieve server password from 1Password"
        return 1
    fi

    # Find the main JS file (has hash in name)
    local main_js
    main_js=$(ls "$DIST_DIR"/main-*.js 2>/dev/null | head -1)

    if [[ -z "$main_js" ]]; then
        log_error "Could not find main JS file in $DIST_DIR"
        return 1
    fi

    local main_js_name
    main_js_name=$(basename "$main_js")

    log_info "Uploading files to server..."

    # Upload files to /tmp on server
    sshpass -p "$password" scp -o StrictHostKeyChecking=no \
        "$DIST_DIR/$main_js_name" \
        "$DIST_DIR/index.html" \
        "$DIST_DIR/polyfills-"*.js \
        "$DIST_DIR/styles-"*.css \
        "$DIST_DIR/assets/releases.json" \
        "$INTERNAL_USER@$INTERNAL_SERVER:/tmp/"

    log_info "Installing files on server..."

    # Copy files to web root using sudo
    # Note: Using secure-sudo-op wrapper for proper sudo handling
    local remote_cmd="cp /tmp/$main_js_name /tmp/index.html /tmp/polyfills-*.js /tmp/styles-*.css $INTERNAL_WEB_ROOT/ && \
        cat /tmp/releases.json > $INTERNAL_WEB_ROOT/assets/releases.json && \
        rm -f $INTERNAL_WEB_ROOT/main-*.js 2>/dev/null; \
        mv $INTERNAL_WEB_ROOT/$main_js_name $INTERNAL_WEB_ROOT/$(echo $main_js_name) && \
        rm -f /tmp/main-*.js /tmp/index.html /tmp/polyfills-*.js /tmp/styles-*.css /tmp/releases.json"

    # Use secure-sudo-op if available, otherwise fall back to direct SSH
    if command -v secure-sudo-op &>/dev/null; then
        secure-sudo-op "$OP_ITEM_SERVER" "$INTERNAL_USER" "$INTERNAL_SERVER" \
            "bash -c 'cp /tmp/$main_js_name /tmp/index.html /tmp/polyfills-*.js /tmp/styles-*.css $INTERNAL_WEB_ROOT/ && cat /tmp/releases.json > $INTERNAL_WEB_ROOT/assets/releases.json'"

        # Clean up old main.js files and tmp
        secure-sudo-op "$OP_ITEM_SERVER" "$INTERNAL_USER" "$INTERNAL_SERVER" \
            "bash -c 'cd $INTERNAL_WEB_ROOT && ls main-*.js 2>/dev/null | grep -v $main_js_name | xargs rm -f 2>/dev/null; rm -f /tmp/main-*.js /tmp/index.html /tmp/polyfills-*.js /tmp/styles-*.css /tmp/releases.json 2>/dev/null'"
    else
        log_warn "secure-sudo-op not found, using direct SSH (may require manual password entry)"
        sshpass -p "$password" ssh -o StrictHostKeyChecking=no "$INTERNAL_USER@$INTERNAL_SERVER" \
            "echo '$password' | sudo -S bash -c '$remote_cmd'"
    fi

    log_success "Deployed to internal server"
    log_info "  - http://$INTERNAL_SERVER"
}

# Show usage
usage() {
    echo "Usage: $0 [target]"
    echo ""
    echo "Targets:"
    echo "  all        - Deploy to both Cloudflare and internal server (default)"
    echo "  cloudflare - Deploy to Cloudflare Pages only"
    echo "  internal   - Deploy to internal server only"
    echo "  build      - Build only, no deployment"
    echo ""
}

# Main
main() {
    local target="${1:-all}"

    echo "=========================================="
    echo "Eleanor Releases - Deployment"
    echo "=========================================="
    echo ""

    case "$target" in
        all)
            build
            deploy_cloudflare
            deploy_internal
            ;;
        cloudflare)
            build
            deploy_cloudflare
            ;;
        internal)
            build
            deploy_internal
            ;;
        build)
            build
            ;;
        -h|--help|help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown target: $target"
            usage
            exit 1
            ;;
    esac

    echo ""
    log_success "Deployment complete!"
}

main "$@"
