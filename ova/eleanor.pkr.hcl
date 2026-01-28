/*
 * Eleanor DFIR Platform - Packer Build Configuration
 *
 * Builds OVA appliance for VMware and VirtualBox deployment.
 * Target: Ubuntu 22.04 Server with Eleanor pre-installed
 */

packer {
  required_plugins {
    vmware = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/vmware"
    }
    virtualbox = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/virtualbox"
    }
    vsphere = {
      version = ">= 1.2.0"
      source  = "github.com/hashicorp/vsphere"
    }
  }
}

# Variables
variable "iso_url" {
  type        = string
  default     = "https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso"
  description = "Ubuntu 22.04 Server ISO URL"
}

variable "iso_checksum" {
  type        = string
  default     = "sha256:9bc6028870aef3f74f4e16b900008179e78b130e6b0b9a140635434a46aa98b0"
  description = "ISO checksum"
}

variable "vm_name" {
  type        = string
  default     = "eleanor-dfir"
  description = "VM name"
}

variable "cpus" {
  type        = number
  default     = 4
  description = "Number of CPUs"
}

variable "memory" {
  type        = number
  default     = 16384
  description = "Memory in MB"
}

variable "disk_size" {
  type        = number
  default     = 102400
  description = "Disk size in MB (100GB)"
}

variable "ssh_username" {
  type        = string
  default     = "eleanor"
  description = "SSH username for provisioning"
}

variable "ssh_password" {
  type        = string
  default     = "eleanor-setup"
  description = "Temporary SSH password (changed during setup)"
  sensitive   = true
}

variable "version" {
  type        = string
  default     = "1.0.0"
  description = "Eleanor version"
}

variable "headless" {
  type        = bool
  default     = true
  description = "Run build in headless mode (no GUI)"
}

# vSphere variables (set via environment or .pkrvars.hcl file)
variable "vsphere_server" {
  type        = string
  default     = ""
  description = "vCenter server address"
}

variable "vsphere_username" {
  type        = string
  default     = ""
  description = "vCenter username"
}

variable "vsphere_password" {
  type        = string
  default     = ""
  sensitive   = true
  description = "vCenter password"
}

variable "vsphere_datacenter" {
  type        = string
  default     = ""
  description = "vSphere datacenter name"
}

variable "vsphere_host" {
  type        = string
  default     = ""
  description = "ESXi host"
}

variable "vsphere_datastore" {
  type        = string
  default     = ""
  description = "Datastore name"
}

variable "vsphere_network" {
  type        = string
  default     = "VM Network"
  description = "Network name"
}

variable "vsphere_folder" {
  type        = string
  default     = ""
  description = "VM folder for build VMs"
}

variable "http_bind_address" {
  type        = string
  default     = ""
  description = "IP address to bind HTTP server (for cloud-init). Leave empty for auto-detect."
}

# Local variables
locals {
  build_timestamp = formatdate("YYYYMMDD-hhmm", timestamp())
  output_name     = "${var.vm_name}-${var.version}-${local.build_timestamp}"
}

# VMware vSphere source
source "vmware-iso" "eleanor" {
  vm_name              = var.vm_name
  guest_os_type        = "ubuntu-64"
  cpus                 = var.cpus
  memory               = var.memory
  disk_size            = var.disk_size
  disk_type_id         = "0"  # Growable virtual disk
  disk_adapter_type    = "pvscsi"
  network_adapter_type = "vmxnet3"

  iso_url      = var.iso_url
  iso_checksum = var.iso_checksum

  http_directory = "cloud-init"

  boot_wait = "5s"
  boot_command = [
    "c<wait>",
    "linux /casper/vmlinuz --- autoinstall ds='nocloud-net;s=http://{{ .HTTPIP }}:{{ .HTTPPort }}/'<enter><wait>",
    "initrd /casper/initrd<enter><wait>",
    "boot<enter>"
  ]

  ssh_username         = var.ssh_username
  ssh_password         = var.ssh_password
  ssh_timeout          = "30m"
  ssh_handshake_attempts = 100

  shutdown_command = "echo '${var.ssh_password}' | sudo -S shutdown -P now"

  output_directory = "output-vmware"
  format           = "ova"
  ovftool_options  = [
    "--compress=9",
    "--allowExtraConfig"
  ]
}

# vSphere ISO source (builds directly on ESXi)
source "vsphere-iso" "eleanor" {
  vcenter_server      = var.vsphere_server
  username            = var.vsphere_username
  password            = var.vsphere_password
  insecure_connection = true

  datacenter = var.vsphere_datacenter
  host       = var.vsphere_host
  datastore  = var.vsphere_datastore
  folder     = var.vsphere_folder

  vm_name       = "${var.vm_name}-${local.build_timestamp}"
  guest_os_type = "ubuntu64Guest"
  CPUs          = var.cpus
  RAM           = var.memory
  RAM_reserve_all = true

  disk_controller_type = ["pvscsi"]
  storage {
    disk_size             = var.disk_size
    disk_thin_provisioned = true
  }

  network_adapters {
    network      = var.vsphere_network
    network_card = "vmxnet3"
  }

  iso_url      = var.iso_url
  iso_checksum = var.iso_checksum

  # Mount cloud-init data as secondary CD-ROM
  cd_files = [
    "./cloud-init/meta-data",
    "./cloud-init/user-data"
  ]
  cd_label = "CIDATA"

  ip_wait_timeout   = "45m"
  ip_settle_timeout = "30s"

  boot_wait = "3s"
  boot_command = [
    "e<wait3s>",
    "<down><down><down><end>",
    " autoinstall",
    "<f10>"
  ]

  ssh_username         = var.ssh_username
  ssh_password         = var.ssh_password
  ssh_private_key_file = pathexpand("~/.ssh/id_ed25519")
  ssh_timeout          = "30m"

  shutdown_command = "echo '${var.ssh_password}' | sudo -S shutdown -P now"

  # Export as OVA
  export {
    force            = true
    output_directory = "output-vsphere"
  }
}

# VirtualBox source
source "virtualbox-iso" "eleanor" {
  vm_name              = var.vm_name
  guest_os_type        = "Ubuntu_64"
  cpus                 = var.cpus
  memory               = var.memory
  disk_size            = var.disk_size
  hard_drive_interface = "sata"
  headless             = var.headless

  # Skip guest additions (we use open-vm-tools instead)
  guest_additions_mode   = "disable"
  virtualbox_version_file = ""

  iso_url      = var.iso_url
  iso_checksum = var.iso_checksum

  http_directory = "cloud-init"

  boot_wait = "5s"
  boot_command = [
    "e<wait3s>",
    "<down><down><down><end>",
    " autoinstall ds='nocloud-net;s=http://{{ .HTTPIP }}:{{ .HTTPPort }}/'",
    "<f10>"
  ]

  ssh_username         = var.ssh_username
  ssh_password         = var.ssh_password
  ssh_timeout          = "45m"

  shutdown_command = "echo '${var.ssh_password}' | sudo -S shutdown -P now"

  output_directory = "output-virtualbox"
  format           = "ova"

  vboxmanage = [
    ["modifyvm", "{{.Name}}", "--nat-localhostreachable1", "on"],
    ["modifyvm", "{{.Name}}", "--audio", "none"],
    ["modifyvm", "{{.Name}}", "--usb", "off"],
    ["modifyvm", "{{.Name}}", "--vrde", "off"]
  ]

  export_opts = [
    "--manifest",
    "--vsys", "0",
    "--description", "Eleanor DFIR Platform v${var.version}",
    "--version", "${var.version}"
  ]
}

# Build configuration
build {
  name = "eleanor"

  sources = [
    "source.vmware-iso.eleanor",
    "source.virtualbox-iso.eleanor",
    "source.vsphere-iso.eleanor"
  ]

  # Wait for cloud-init to finish
  provisioner "shell" {
    inline = [
      "while [ ! -f /var/lib/cloud/instance/boot-finished ]; do echo 'Waiting for cloud-init...'; sleep 5; done",
      "echo '${var.ssh_password}' | sudo -S cloud-init status --wait"
    ]
  }

  # Copy setup scripts
  provisioner "file" {
    source      = "scripts"
    destination = "/tmp/eleanor-scripts"
  }

  # Copy setup wizard
  provisioner "file" {
    source      = "setup-wizard"
    destination = "/tmp/eleanor-wizard"
  }

  # Run base system setup
  provisioner "shell" {
    script = "scripts/01-base-system.sh"
    execute_command = "echo '${var.ssh_password}' | sudo -S bash '{{.Path}}'"
    environment_vars = [
      "ELEANOR_VERSION=${var.version}"
    ]
  }

  # Install Docker
  provisioner "shell" {
    script = "scripts/02-docker-install.sh"
    execute_command = "echo '${var.ssh_password}' | sudo -S bash '{{.Path}}'"
  }

  # Setup Eleanor
  provisioner "shell" {
    script = "scripts/03-eleanor-setup.sh"
    execute_command = "echo '${var.ssh_password}' | sudo -S bash '{{.Path}}'"
    environment_vars = [
      "ELEANOR_VERSION=${var.version}"
    ]
  }

  # Install setup wizard
  provisioner "shell" {
    script = "scripts/04-setup-wizard.sh"
    execute_command = "echo '${var.ssh_password}' | sudo -S bash '{{.Path}}'"
  }

  # Cleanup
  provisioner "shell" {
    script = "scripts/05-cleanup.sh"
    execute_command = "echo '${var.ssh_password}' | sudo -S bash '{{.Path}}'"
  }

  # Create OVA manifest
  post-processor "manifest" {
    output     = "manifest-${local.output_name}.json"
    strip_path = true
    custom_data = {
      version    = var.version
      build_time = local.build_timestamp
    }
  }

  # Compress output
  post-processor "compress" {
    output = "eleanor-${var.version}.tar.gz"
  }
}
