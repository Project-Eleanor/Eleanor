#!/bin/bash
# Eleanor DFIR Platform - Base System Setup
# This script configures the base Ubuntu system for Eleanor

set -e

echo "=== Eleanor Base System Setup ==="

# Update system
echo "Updating system packages..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Install additional packages
echo "Installing base packages..."
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    nginx \
    certbot \
    python3-certbot-nginx \
    fail2ban \
    ufw \
    ntp \
    rsync \
    tree \
    ncdu \
    iotop \
    sysstat \
    acl

# Configure timezone
echo "Configuring timezone..."
timedatectl set-timezone UTC

# Configure NTP
echo "Configuring NTP..."
systemctl enable ntp
systemctl start ntp

# Configure fail2ban
echo "Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF

systemctl enable fail2ban
systemctl restart fail2ban

# Configure UFW firewall
echo "Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
ufw allow 8000/tcp  # Eleanor API
ufw allow 9443/tcp  # Setup wizard
echo "y" | ufw enable

# Configure sysctl for Elasticsearch
echo "Configuring system limits for Elasticsearch..."
cat >> /etc/sysctl.conf << 'EOF'

# Eleanor DFIR - Elasticsearch optimizations
vm.max_map_count = 262144
vm.swappiness = 1
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
EOF

sysctl -p

# Configure limits
cat >> /etc/security/limits.conf << 'EOF'

# Eleanor DFIR - Process limits
eleanor soft nofile 65535
eleanor hard nofile 65535
eleanor soft nproc 4096
eleanor hard nproc 4096
EOF

# Create Eleanor service account
echo "Setting up Eleanor user..."
usermod -aG docker eleanor 2>/dev/null || true

# Create directories
echo "Creating directories..."
mkdir -p /opt/eleanor/{backend,frontend,config,logs,data}
mkdir -p /opt/eleanor-setup
mkdir -p /var/lib/eleanor/{elasticsearch,postgres,redis,evidence,exports}
mkdir -p /var/log/eleanor

# Set permissions
chown -R eleanor:eleanor /opt/eleanor
chown -R eleanor:eleanor /opt/eleanor-setup
chown -R eleanor:eleanor /var/lib/eleanor
chown -R eleanor:eleanor /var/log/eleanor

# Store version
echo "${ELEANOR_VERSION:-1.0.0}" > /opt/eleanor/.version

# Create MOTD
cat > /etc/update-motd.d/99-eleanor << 'EOF'
#!/bin/bash
echo ""
echo "  _______ _                              "
echo " |  _____| |                             "
echo " | |__   | | ___  __ _ _ __   ___  _ __  "
echo " |  __|  | |/ _ \/ _\` | '_ \ / _ \| '__| "
echo " | |___  | |  __/ (_| | | | | (_) | |    "
echo " |______|_|\___|\__,_|_| |_|\___/|_|    "
echo ""
echo "  DFIR Platform - Digital Forensics & Incident Response"
echo ""
if [ -f /opt/eleanor/.version ]; then
    echo "  Version: $(cat /opt/eleanor/.version)"
fi
if [ -f /opt/eleanor/.configured ]; then
    echo "  Status: Configured"
    echo ""
    echo "  Access the platform at: https://$(hostname -I | awk '{print $1}')"
else
    echo "  Status: Setup Required"
    echo ""
    echo "  Complete setup at: https://$(hostname -I | awk '{print $1}'):9443"
fi
echo ""
EOF
chmod +x /etc/update-motd.d/99-eleanor

echo "=== Base System Setup Complete ==="
