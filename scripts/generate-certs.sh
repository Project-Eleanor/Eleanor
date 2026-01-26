#!/bin/bash
# Generate SSL certificates for Eleanor services
# Usage: ./generate-certs.sh [--hostname HOSTNAME] [--output DIR]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
HOSTNAME="${ELEANOR_HOSTNAME:-eleanor.local}"
OUTPUT_DIR="./certificates"
DAYS_VALID=365
KEY_SIZE=2048

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --hostname|-h)
            HOSTNAME="$2"
            shift 2
            ;;
        --output|-o)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --days|-d)
            DAYS_VALID="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo "Generate SSL certificates for Eleanor services"
            echo ""
            echo "Options:"
            echo "  -h, --hostname NAME   Hostname for certificates (default: eleanor.local)"
            echo "  -o, --output DIR      Output directory (default: ./certificates)"
            echo "  -d, --days DAYS       Certificate validity in days (default: 365)"
            echo "      --help            Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Check for openssl
command -v openssl >/dev/null 2>&1 || {
    echo -e "${RED}Error: openssl is required but not installed.${NC}"
    exit 1
}

echo -e "${BLUE}Eleanor SSL Certificate Generator${NC}"
echo "==================================="
echo ""
echo "Hostname: $HOSTNAME"
echo "Output directory: $OUTPUT_DIR"
echo "Validity: $DAYS_VALID days"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate CA certificate
echo -e "${YELLOW}Generating Certificate Authority...${NC}"

# CA private key
openssl genrsa -out "$OUTPUT_DIR/ca.key" 4096 2>/dev/null

# CA certificate
openssl req -new -x509 -key "$OUTPUT_DIR/ca.key" \
    -out "$OUTPUT_DIR/ca.crt" \
    -days "$DAYS_VALID" \
    -subj "/C=US/ST=State/L=City/O=Eleanor DFIR/OU=Security/CN=Eleanor CA" \
    2>/dev/null

echo -e "${GREEN}CA certificate generated${NC}"

# Function to generate service certificate
generate_service_cert() {
    local service_name="$1"
    local cn="$2"
    local alt_names="$3"

    echo -e "${YELLOW}Generating certificate for $service_name...${NC}"

    # Create config file for SAN
    local config_file=$(mktemp)
    cat > "$config_file" << EOF
[req]
default_bits = $KEY_SIZE
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
C = US
ST = State
L = City
O = Eleanor DFIR
OU = $service_name
CN = $cn

[req_ext]
subjectAltName = @alt_names

[alt_names]
$alt_names
EOF

    # Generate private key
    openssl genrsa -out "$OUTPUT_DIR/${service_name}.key" $KEY_SIZE 2>/dev/null

    # Generate CSR
    openssl req -new -key "$OUTPUT_DIR/${service_name}.key" \
        -out "$OUTPUT_DIR/${service_name}.csr" \
        -config "$config_file" \
        2>/dev/null

    # Sign with CA
    openssl x509 -req -in "$OUTPUT_DIR/${service_name}.csr" \
        -CA "$OUTPUT_DIR/ca.crt" \
        -CAkey "$OUTPUT_DIR/ca.key" \
        -CAcreateserial \
        -out "$OUTPUT_DIR/${service_name}.crt" \
        -days "$DAYS_VALID" \
        -extensions req_ext \
        -extfile "$config_file" \
        2>/dev/null

    # Remove CSR and temp config
    rm -f "$OUTPUT_DIR/${service_name}.csr" "$config_file"

    # Create combined PEM (cert + key)
    cat "$OUTPUT_DIR/${service_name}.crt" "$OUTPUT_DIR/${service_name}.key" \
        > "$OUTPUT_DIR/${service_name}.pem"

    echo -e "${GREEN}$service_name certificate generated${NC}"
}

# Generate certificates for each service
generate_service_cert "nginx" "$HOSTNAME" "DNS.1 = $HOSTNAME
DNS.2 = localhost
DNS.3 = eleanor
DNS.4 = frontend
IP.1 = 127.0.0.1"

generate_service_cert "backend" "backend.$HOSTNAME" "DNS.1 = backend.$HOSTNAME
DNS.2 = backend
DNS.3 = localhost
DNS.4 = api.$HOSTNAME
IP.1 = 127.0.0.1"

generate_service_cert "elasticsearch" "elasticsearch.$HOSTNAME" "DNS.1 = elasticsearch.$HOSTNAME
DNS.2 = elasticsearch
DNS.3 = localhost
IP.1 = 127.0.0.1"

generate_service_cert "postgres" "postgres.$HOSTNAME" "DNS.1 = postgres.$HOSTNAME
DNS.2 = postgres
DNS.3 = localhost
IP.1 = 127.0.0.1"

generate_service_cert "redis" "redis.$HOSTNAME" "DNS.1 = redis.$HOSTNAME
DNS.2 = redis
DNS.3 = localhost
IP.1 = 127.0.0.1"

generate_service_cert "iris" "iris.$HOSTNAME" "DNS.1 = iris.$HOSTNAME
DNS.2 = iris
DNS.3 = localhost
IP.1 = 127.0.0.1"

# Set permissions
echo -e "${YELLOW}Setting permissions...${NC}"
chmod 644 "$OUTPUT_DIR"/*.crt
chmod 600 "$OUTPUT_DIR"/*.key
chmod 600 "$OUTPUT_DIR"/*.pem

# Generate DH parameters for forward secrecy
echo -e "${YELLOW}Generating DH parameters (this may take a moment)...${NC}"
openssl dhparam -out "$OUTPUT_DIR/dhparam.pem" 2048 2>/dev/null
echo -e "${GREEN}DH parameters generated${NC}"

# Summary
echo ""
echo -e "${GREEN}Certificate generation complete!${NC}"
echo ""
echo "Generated files:"
ls -la "$OUTPUT_DIR"
echo ""
echo -e "${YELLOW}Note: These are self-signed certificates.${NC}"
echo "For production, consider using Let's Encrypt or a proper CA."
echo ""
echo "To trust the CA in your browser, import: $OUTPUT_DIR/ca.crt"
