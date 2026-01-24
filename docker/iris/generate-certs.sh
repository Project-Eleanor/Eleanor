#!/bin/bash
# Generate self-signed certificates for IRIS

CERT_DIR="$(dirname "$0")/certificates"
mkdir -p "$CERT_DIR"

# Generate private key
openssl genrsa -out "$CERT_DIR/server.key" 2048

# Generate self-signed certificate
openssl req -new -x509 -key "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.crt" \
    -days 365 \
    -subj "/C=US/ST=State/L=City/O=Eleanor/OU=DFIR/CN=iris.eleanor.local"

# Set permissions
chmod 644 "$CERT_DIR/server.crt"
chmod 600 "$CERT_DIR/server.key"

echo "Certificates generated in $CERT_DIR"
ls -la "$CERT_DIR"
