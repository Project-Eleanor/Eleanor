#!/bin/bash
# Eleanor DFIR Platform - Enhanced Setup Wizard Installation
# This script installs the web-based setup wizard with enterprise features:
# - Storage: Local, S3, Azure Blob, GCS
# - Authentication: Local + OIDC
# - Database: Embedded PostgreSQL or external managed DB

set -e

echo "=== Installing Enhanced Setup Wizard ==="

WIZARD_DIR="/opt/eleanor-setup"
ELEANOR_DIR="/opt/eleanor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_WIZARD_DIR="${SCRIPT_DIR}/../setup-wizard"

# Create directories
mkdir -p ${WIZARD_DIR}/static
mkdir -p ${ELEANOR_DIR}

# Copy wizard files from source
echo "Copying wizard files..."
if [ -d "${SOURCE_WIZARD_DIR}" ]; then
    # Copy from repository during build
    cp -f "${SOURCE_WIZARD_DIR}/wizard-server.py" "${WIZARD_DIR}/" 2>/dev/null || true
    cp -rf "${SOURCE_WIZARD_DIR}/static/"* "${WIZARD_DIR}/static/" 2>/dev/null || true
fi

# Also check /tmp for staged files (used during packer builds)
if [ -d "/tmp/eleanor-wizard" ]; then
    cp -f "/tmp/eleanor-wizard/wizard-server.py" "${WIZARD_DIR}/" 2>/dev/null || true
    cp -rf "/tmp/eleanor-wizard/static/"* "${WIZARD_DIR}/static/" 2>/dev/null || true
fi

# Create Python virtual environment
echo "Creating virtual environment..."
python3 -m venv ${WIZARD_DIR}/venv
source ${WIZARD_DIR}/venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip

# Core dependencies
pip install \
    flask>=3.0.0 \
    gunicorn>=21.0.0 \
    pyyaml>=6.0 \
    python-dotenv>=1.0.0 \
    psutil>=5.9.0 \
    requests>=2.31.0

# Database driver (for connection testing)
pip install \
    psycopg2-binary>=2.9.0

# Cloud storage dependencies (for credential testing)
echo "Installing cloud storage libraries..."
pip install \
    boto3>=1.34.0 \
    azure-storage-blob>=12.19.0 \
    google-cloud-storage>=2.14.0

deactivate

# Set permissions
echo "Setting permissions..."
chown -R eleanor:eleanor ${WIZARD_DIR} 2>/dev/null || true
chmod +x ${WIZARD_DIR}/wizard-server.py

# Create systemd service for setup wizard
echo "Creating setup wizard service..."
cat > /etc/systemd/system/eleanor-setup.service << 'EOF'
[Unit]
Description=Eleanor DFIR Setup Wizard
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/eleanor-setup
Environment="PATH=/opt/eleanor-setup/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/opt/eleanor-setup/venv/bin/python /opt/eleanor-setup/wizard-server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create a service to generate SSL certs on first boot (if not present)
cat > /etc/systemd/system/eleanor-ssl-init.service << 'EOF'
[Unit]
Description=Eleanor SSL Certificate Initialization
Before=eleanor-setup.service
ConditionPathExists=!/etc/nginx/ssl/eleanor.crt

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'mkdir -p /etc/nginx/ssl && openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/nginx/ssl/eleanor.key -out /etc/nginx/ssl/eleanor.crt -subj "/CN=eleanor/O=DFIR/C=US"'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Enable services
systemctl daemon-reload
systemctl enable eleanor-ssl-init
systemctl enable eleanor-setup

# Start SSL init if certs don't exist
if [ ! -f /etc/nginx/ssl/eleanor.crt ]; then
    systemctl start eleanor-ssl-init
fi

# Start setup wizard (for testing/development)
# In production OVA, this will start on boot
systemctl start eleanor-setup || echo "Note: Wizard will start on next boot"

echo "=== Setup Wizard Installation Complete ==="
echo "Setup wizard available at: https://[IP]:9443"
echo ""
echo "Enterprise features enabled:"
echo "  - Storage backends: Local, S3, Azure Blob, GCS"
echo "  - Authentication: Local accounts, OIDC/SSO"
echo "  - Database: Embedded or external PostgreSQL"
