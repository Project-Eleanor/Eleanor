# Velociraptor Server Docker Image
# Downloads pre-built binary from GitHub releases

FROM debian:bookworm-slim

ARG VELOCIRAPTOR_VERSION=0.75.6

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download Velociraptor binary
RUN curl -L -o /usr/local/bin/velociraptor \
    "https://github.com/Velocidex/velociraptor/releases/download/v0.75/velociraptor-v${VELOCIRAPTOR_VERSION}-linux-amd64" \
    && chmod +x /usr/local/bin/velociraptor

# Create directories
RUN mkdir -p /velociraptor/config /velociraptor/data /velociraptor/logs

WORKDIR /velociraptor

# Expose ports
# 8000 - Frontend (client connections)
# 8001 - GUI
# 8003 - API
EXPOSE 8000 8001 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f -k https://localhost:8001/ || exit 1

# Default command - run frontend server
ENTRYPOINT ["/usr/local/bin/velociraptor"]
CMD ["--config", "/velociraptor/config/server.config.yaml", "frontend", "-v"]
