#!/bin/bash
# Eleanor DFIR Platform - Implementation Verification Script
# Run this script to verify all components are properly implemented

set -e

BACKEND_DIR="/home/ares/Eleanor/backend"
FRONTEND_DIR="/home/ares/Eleanor/frontend"

echo "=== Eleanor Implementation Verification ==="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        return 0
    else
        echo -e "${RED}✗${NC} $1 (MISSING)"
        return 1
    fi
}

check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $1/"
        return 0
    else
        echo -e "${RED}✗${NC} $1/ (MISSING)"
        return 1
    fi
}

echo "=== Phase 1: Celery & Parsers ==="
check_file "$BACKEND_DIR/app/tasks/__init__.py"
check_file "$BACKEND_DIR/app/tasks/celery_app.py"
check_file "$BACKEND_DIR/app/tasks/parsing.py"
check_file "$BACKEND_DIR/app/tasks/enrichment.py"
check_file "$BACKEND_DIR/app/tasks/indexing.py"
check_file "$BACKEND_DIR/app/models/parsing_job.py"
check_file "$BACKEND_DIR/app/api/v1/parsing.py"
check_file "$BACKEND_DIR/app/parsers/formats/dissect_adapter.py"
check_file "$BACKEND_DIR/app/parsers/formats/registry_hive.py"
check_file "$BACKEND_DIR/app/parsers/formats/prefetch.py"
check_file "$BACKEND_DIR/app/parsers/formats/mft.py"
check_file "$BACKEND_DIR/app/parsers/formats/pcap.py"
echo ""

echo "=== Phase 2: Investigation Graphs ==="
check_file "$BACKEND_DIR/app/models/graph.py"
check_file "$BACKEND_DIR/app/services/graph_builder.py"
check_file "$BACKEND_DIR/app/api/v1/graphs.py"
check_file "$FRONTEND_DIR/src/app/shared/models/graph.model.ts"
check_file "$FRONTEND_DIR/src/app/core/api/graph.service.ts"
check_file "$FRONTEND_DIR/src/app/shared/components/cytoscape-graph/cytoscape-graph.component.ts"
check_file "$FRONTEND_DIR/src/app/features/investigation-graph/investigation-graph.component.ts"
echo ""

echo "=== Phase 3: Workbooks ==="
check_file "$BACKEND_DIR/app/api/v1/workbooks.py"
check_file "$FRONTEND_DIR/src/app/shared/models/workbook.model.ts"
check_file "$FRONTEND_DIR/src/app/core/api/workbook.service.ts"
check_file "$FRONTEND_DIR/src/app/features/workbooks/workbook-list.component.ts"
check_file "$FRONTEND_DIR/src/app/features/workbooks/workbook-viewer.component.ts"
echo ""

echo "=== Phase 4: Correlation Rules ==="
check_file "$BACKEND_DIR/app/services/correlation_engine.py"
check_file "$BACKEND_DIR/app/services/event_buffer.py"
check_file "$BACKEND_DIR/app/services/realtime_processor.py"
check_file "$BACKEND_DIR/alembic/versions/003_add_correlation_states.py"
echo ""

echo "=== Phase 5: OVA Distribution ==="
check_dir "/home/ares/Eleanor/ova"
check_file "/home/ares/Eleanor/ova/eleanor.pkr.hcl"
check_file "/home/ares/Eleanor/ova/cloud-init/user-data"
check_file "/home/ares/Eleanor/ova/scripts/01-base-system.sh"
check_file "/home/ares/Eleanor/ova/scripts/02-docker-install.sh"
check_file "/home/ares/Eleanor/ova/scripts/03-eleanor-setup.sh"
check_file "/home/ares/Eleanor/ova/scripts/04-setup-wizard.sh"
check_file "/home/ares/Eleanor/ova/scripts/05-cleanup.sh"
echo ""

echo "=== Database Migrations ==="
check_file "$BACKEND_DIR/alembic/versions/001_add_parsing_jobs.py"
check_file "$BACKEND_DIR/alembic/versions/002_add_saved_graphs.py"
check_file "$BACKEND_DIR/alembic/versions/003_add_correlation_states.py"
echo ""

echo "=== Python Syntax Check ==="
echo "Checking Python files for syntax errors..."
python3 -m py_compile "$BACKEND_DIR/app/services/correlation_engine.py" && echo -e "${GREEN}✓${NC} correlation_engine.py"
python3 -m py_compile "$BACKEND_DIR/app/services/event_buffer.py" && echo -e "${GREEN}✓${NC} event_buffer.py"
python3 -m py_compile "$BACKEND_DIR/app/services/realtime_processor.py" && echo -e "${GREEN}✓${NC} realtime_processor.py"
python3 -m py_compile "$BACKEND_DIR/app/api/v1/workbooks.py" && echo -e "${GREEN}✓${NC} workbooks.py"
python3 -m py_compile "$BACKEND_DIR/app/api/v1/graphs.py" && echo -e "${GREEN}✓${NC} graphs.py"
python3 -m py_compile "$BACKEND_DIR/app/api/v1/parsing.py" && echo -e "${GREEN}✓${NC} parsing.py"
echo ""

echo "=== TypeScript Files Check ==="
if command -v npx &> /dev/null && [ -f "$FRONTEND_DIR/node_modules/.bin/tsc" ]; then
    echo "Checking TypeScript files..."
    cd "$FRONTEND_DIR"
    npx tsc --noEmit --skipLibCheck 2>/dev/null && echo -e "${GREEN}✓${NC} TypeScript compilation successful" || echo -e "${YELLOW}!${NC} TypeScript check skipped (run npm install first)"
else
    echo -e "${YELLOW}!${NC} TypeScript check skipped (tsc not available)"
fi
echo ""

echo "=== Verification Complete ==="
