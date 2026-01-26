#!/bin/bash
# Eleanor DFIR Platform - Cleanup for OVA Distribution
# This script prepares the VM for distribution

set -e

echo "=== Cleanup for Distribution ==="

# Stop services
echo "Stopping services..."
systemctl stop eleanor 2>/dev/null || true
systemctl stop eleanor-setup 2>/dev/null || true

# Clean apt cache
echo "Cleaning apt cache..."
apt-get clean
apt-get autoremove -y

# Remove temporary files
echo "Removing temporary files..."
rm -rf /tmp/*
rm -rf /var/tmp/*
rm -rf /var/cache/apt/archives/*.deb

# Clean log files
echo "Cleaning log files..."
find /var/log -type f -name "*.log" -delete
find /var/log -type f -name "*.gz" -delete
journalctl --vacuum-size=50M

# Remove SSH host keys (will be regenerated on first boot)
echo "Removing SSH host keys..."
rm -f /etc/ssh/ssh_host_*

# Create script to regenerate SSH keys on first boot
cat > /etc/rc.local << 'EOF'
#!/bin/bash
# Regenerate SSH host keys if missing
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    dpkg-reconfigure openssh-server
fi

# Remove this script after first run
rm -f /etc/rc.local
exit 0
EOF
chmod +x /etc/rc.local

# Clear machine ID
echo "Clearing machine ID..."
truncate -s 0 /etc/machine-id
rm -f /var/lib/dbus/machine-id

# Clear bash history
echo "Clearing bash history..."
cat /dev/null > ~/.bash_history
history -c

# Clear cloud-init state for re-run
echo "Clearing cloud-init state..."
cloud-init clean --logs 2>/dev/null || true

# Reset hostname
echo "Resetting hostname..."
echo "eleanor" > /etc/hostname
hostnamectl set-hostname eleanor

# Remove provisioning artifacts
echo "Removing provisioning artifacts..."
rm -rf /tmp/eleanor-scripts
rm -rf /tmp/eleanor-wizard

# Zero free space (optional, makes OVA smaller)
echo "Zeroing free space (this may take a while)..."
dd if=/dev/zero of=/EMPTY bs=1M 2>/dev/null || true
rm -f /EMPTY

# Sync filesystem
sync

echo "=== Cleanup Complete ==="
echo "VM is ready for OVA export."
