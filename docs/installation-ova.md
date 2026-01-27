# Eleanor DFIR Platform - OVA Appliance Installation

This guide covers deploying Eleanor using the pre-built OVA virtual appliance.

## Overview

The Eleanor OVA provides a complete, pre-configured DFIR platform ready to deploy on VMware or VirtualBox. It includes:

- Eleanor DFIR Platform
- PostgreSQL Database
- Elasticsearch
- Redis
- Setup Wizard for easy configuration

## System Requirements

### Minimum

| Resource | Requirement |
|----------|-------------|
| vCPU | 4 cores |
| RAM | 16 GB |
| Storage | 100 GB |
| Network | 1 NIC with DHCP or static IP |

### Recommended (Production)

| Resource | Requirement |
|----------|-------------|
| vCPU | 8 cores |
| RAM | 32 GB |
| Storage | 500 GB SSD |
| Network | 2 NICs (management + collection) |

## Download

Download the OVA from the [GitHub Releases](https://github.com/project-eleanor/Eleanor/releases) page:

- `eleanor-dfir-vX.X.X-vmware.ova` - VMware Workstation/ESXi/Fusion
- `eleanor-dfir-vX.X.X-virtualbox.ova` - VirtualBox

Verify the download:
```bash
sha256sum -c SHA256SUMS-vX.X.X.txt
```

## VMware Installation

### VMware Workstation / Fusion

1. Open VMware Workstation/Fusion
2. File → Open → Select the OVA file
3. Choose storage location
4. Review VM settings:
   - Adjust CPU/RAM if needed
   - Configure network adapter
5. Click "Import"
6. Power on the VM

### VMware ESXi / vSphere

1. Open vSphere Client
2. Right-click datacenter/folder → Deploy OVF Template
3. Select the OVA file (local or URL)
4. Follow the wizard:
   - Name and folder
   - Compute resource
   - Storage (thick/thin provisioning)
   - Network mapping
5. Review and complete
6. Power on the VM

### ESXi CLI Deployment

```bash
# Upload OVA to datastore
ovftool --noSSLVerify --datastore=datastore1 \
  --network="VM Network" \
  eleanor-dfir-v1.0.0-vmware.ova \
  vi://root@esxi-host

# Or deploy directly
ovftool --noSSLVerify --datastore=datastore1 \
  --network="VM Network" \
  --name="Eleanor-DFIR" \
  --powerOn \
  eleanor-dfir-v1.0.0-vmware.ova \
  vi://root@esxi-host
```

## VirtualBox Installation

1. Open VirtualBox Manager
2. File → Import Appliance
3. Select the OVA file
4. Review settings:
   - Adjust CPU/RAM if needed
   - Change MAC address policy if cloning
5. Click "Import"
6. Configure network adapter:
   - Settings → Network → Attached to: Bridged Adapter
7. Start the VM

## First Boot

### Console Access

After booting, the console displays:
```
Eleanor DFIR Platform
Version: 1.0.0

Network:
  IP Address: 192.168.1.100
  Setup URL:  https://192.168.1.100:9443

Default credentials:
  Console: eleanor / eleanor

Press Enter to login...
```

### Network Configuration

If DHCP is unavailable, configure a static IP:

```bash
# Login with default credentials
# Username: eleanor
# Password: eleanor

# Configure network
sudo nmtui

# Or manually
sudo nano /etc/netplan/00-installer-config.yaml
```

Example static configuration:
```yaml
network:
  version: 2
  ethernets:
    ens160:
      addresses:
        - 192.168.1.100/24
      gateway4: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
```

Apply changes:
```bash
sudo netplan apply
```

## Setup Wizard

### Access the Wizard

1. Open browser to `https://<VM-IP>:9443`
2. Accept self-signed certificate warning
3. Click "Begin Setup"

### Step 1: Admin Account

Configure the initial administrator:

- **Email**: admin@yourcompany.com
- **Username**: admin
- **Password**: (strong password)
- **Organization**: Your Company Name

### Step 2: Network Settings

Configure Eleanor's network settings:

- **Hostname**: eleanor.internal (or FQDN)
- **SSL Certificate**: Generate self-signed or upload custom
- **Timezone**: Select your timezone

### Step 3: Storage

Configure evidence storage:

- **Local Storage**: /data/evidence (default)
- **NFS Mount**: Configure external storage (optional)
- **S3 Compatible**: MinIO or AWS S3 (optional)

### Step 4: Integrations

Configure optional integrations:

#### Velociraptor
```
URL: https://velociraptor.internal:8001
CA Certificate: [Upload or paste]
Client Certificate: [Upload or paste]
Client Key: [Upload or paste]
```

#### IRIS Case Management
```
URL: http://iris.internal:8000
API Key: [Generate in IRIS admin]
```

#### OpenCTI
```
URL: http://opencti.internal:8080
API Key: [From OpenCTI profile]
```

#### Timesketch
```
URL: http://timesketch.internal:5000
API Key: [Generate in Timesketch]
```

### Step 5: Review & Complete

Review all settings and click "Complete Setup".

Eleanor will:
1. Initialize the database
2. Create Elasticsearch indices
3. Configure services
4. Restart with production settings

This takes 2-5 minutes.

## Post-Installation

### Access Eleanor

After setup completes:

- **Web UI**: `https://<VM-IP>` (ports 80/443)
- **API**: `https://<VM-IP>/api/v1`

Login with the admin credentials created during setup.

### Change Default Passwords

```bash
# SSH into the appliance
ssh eleanor@<VM-IP>

# Change system password
passwd

# Change root password (if needed)
sudo passwd root
```

### SSL Certificate

Replace the self-signed certificate:

```bash
# Copy your certificates
sudo cp your-cert.crt /etc/eleanor/ssl/eleanor.crt
sudo cp your-cert.key /etc/eleanor/ssl/eleanor.key

# Restart nginx
sudo systemctl restart nginx
```

### Updates

Check for updates:
```bash
ssh eleanor@<VM-IP>
sudo eleanor-update
```

Or update containers manually:
```bash
cd /opt/eleanor
docker-compose pull
docker-compose up -d
```

## Service Management

### View Service Status

```bash
# All services
sudo systemctl status eleanor

# Individual components
sudo systemctl status eleanor-backend
sudo systemctl status eleanor-frontend
sudo systemctl status eleanor-worker
```

### View Logs

```bash
# All logs
sudo journalctl -u eleanor -f

# Backend logs
docker logs eleanor-backend -f

# Worker logs
docker logs eleanor-celery-worker -f
```

### Restart Services

```bash
# All Eleanor services
sudo systemctl restart eleanor

# Individual service
docker restart eleanor-backend
```

## Backup & Recovery

### Create Backup

```bash
# Full backup
sudo /opt/eleanor/scripts/backup.sh /backup/eleanor-$(date +%Y%m%d).tar.gz

# Database only
docker exec eleanor-postgres pg_dump -U eleanor eleanor | gzip > eleanor-db.sql.gz
```

### Restore Backup

```bash
# Full restore
sudo /opt/eleanor/scripts/restore.sh /backup/eleanor-20240115.tar.gz

# Database only
zcat eleanor-db.sql.gz | docker exec -i eleanor-postgres psql -U eleanor eleanor
```

## Troubleshooting

### Services Not Starting

```bash
# Check Docker status
sudo systemctl status docker

# Check container status
docker ps -a

# View container logs
docker logs eleanor-backend --tail 100
```

### Network Issues

```bash
# Check network configuration
ip addr show

# Test DNS resolution
nslookup google.com

# Check firewall
sudo ufw status
```

### Reset to Factory

```bash
# WARNING: This erases all data
sudo /opt/eleanor/scripts/factory-reset.sh
```

### Support

- GitHub Issues: https://github.com/project-eleanor/Eleanor/issues
- Documentation: https://docs.project-eleanor.com
- Community: https://discord.gg/project-eleanor

## Next Steps

1. [Configure Integrations](integrations.md)
2. [Set Up Users & RBAC](administration.md)
3. [Quick Start Investigation](quickstart.md)
