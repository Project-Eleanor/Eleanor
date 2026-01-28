#!/usr/bin/env python3
"""Eleanor DFIR Platform - Enhanced Setup Wizard Server.

This wizard supports enterprise deployment configuration:
- Storage: Local, S3, Azure Blob, GCS
- Authentication: Local + OIDC (Azure AD, Okta, Keycloak)
- Database: Embedded PostgreSQL or external managed DB
"""

import json
import os
import secrets
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psutil
import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

ELEANOR_DIR = Path("/opt/eleanor")
SETUP_DIR = Path("/opt/eleanor-setup")
CONFIGURED_FLAG = ELEANOR_DIR / ".configured"
STATUS_FILE = SETUP_DIR / "setup-status.json"


# =============================================================================
# Deployment Profiles
# =============================================================================

DEPLOYMENT_PROFILES = {
    "small": {
        "name": "Small",
        "description": "Single analyst, light workload",
        "min_ram_gb": 8,
        "min_cpu": 2,
        "min_disk_gb": 50,
        "elasticsearch_heap": "512m",
        "postgres_memory": "256MB",
        "worker_count": 1,
    },
    "medium": {
        "name": "Medium",
        "description": "Small team (2-5 analysts), moderate workload",
        "min_ram_gb": 16,
        "min_cpu": 4,
        "min_disk_gb": 200,
        "elasticsearch_heap": "2g",
        "postgres_memory": "1GB",
        "worker_count": 2,
    },
    "large": {
        "name": "Large",
        "description": "Enterprise team (5+ analysts), heavy workload",
        "min_ram_gb": 32,
        "min_cpu": 8,
        "min_disk_gb": 500,
        "elasticsearch_heap": "4g",
        "postgres_memory": "4GB",
        "worker_count": 4,
    },
}


# =============================================================================
# Status Management
# =============================================================================


def update_status(step: str, progress: int, message: str, error: str | None = None):
    """Update setup status file."""
    with open(STATUS_FILE, "w") as f:
        json.dump(
            {
                "step": step,
                "progress": progress,
                "message": message,
                "error": error,
                "timestamp": time.time(),
            },
            f,
        )


# =============================================================================
# Static Routes
# =============================================================================


@app.route("/")
def index():
    """Serve setup wizard UI."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/configured")
def is_configured():
    """Check if Eleanor is already configured."""
    return jsonify({"configured": CONFIGURED_FLAG.exists()})


# =============================================================================
# System Info & Profiles
# =============================================================================


@app.route("/api/system-info")
def system_info():
    """Get system information and requirements check."""
    mem = psutil.virtual_memory()
    cpu_count = psutil.cpu_count()

    # Check disk for /var/lib/eleanor or /opt/eleanor
    disk_path = "/var/lib/eleanor"
    if not Path(disk_path).exists():
        disk_path = "/opt/eleanor" if Path("/opt/eleanor").exists() else "/"
    disk = psutil.disk_usage(disk_path)

    checks = {
        "memory_gb": round(mem.total / (1024**3), 1),
        "memory_available_gb": round(mem.available / (1024**3), 1),
        "memory_ok": mem.total >= 8 * (1024**3),  # 8GB minimum
        "disk_gb": round(disk.total / (1024**3), 1),
        "disk_free_gb": round(disk.free / (1024**3), 1),
        "disk_ok": disk.free >= 50 * (1024**3),  # 50GB free minimum
        "cpu_count": cpu_count,
        "cpu_ok": cpu_count >= 2,  # 2 cores minimum
        "docker_ok": check_docker(),
        "hostname": get_hostname(),
        "ip_address": get_ip_address(),
    }

    checks["all_ok"] = all(
        [
            checks["memory_ok"],
            checks["disk_ok"],
            checks["cpu_ok"],
            checks["docker_ok"],
        ]
    )

    # Suggest deployment profile based on resources
    if mem.total >= 32 * (1024**3) and cpu_count >= 8:
        checks["suggested_profile"] = "large"
    elif mem.total >= 16 * (1024**3) and cpu_count >= 4:
        checks["suggested_profile"] = "medium"
    else:
        checks["suggested_profile"] = "small"

    return jsonify(checks)


@app.route("/api/profiles")
def get_profiles():
    """Get deployment size profiles."""
    return jsonify(DEPLOYMENT_PROFILES)


def check_docker():
    """Check if Docker is running."""
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def get_hostname():
    """Get system hostname."""
    try:
        result = subprocess.run(["hostname", "-f"], capture_output=True, text=True)
        return result.stdout.strip() or "eleanor"
    except Exception:
        return "eleanor"


def get_ip_address():
    """Get primary IP address."""
    try:
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# =============================================================================
# Database Testing
# =============================================================================


@app.route("/api/db/test", methods=["POST"])
def test_database():
    """Test database connection."""
    config = request.json or {}

    db_type = config.get("db_type", "embedded")
    if db_type == "embedded":
        return jsonify(
            {"success": True, "message": "Embedded PostgreSQL will be configured"}
        )

    # External database test
    host = config.get("host", "")
    port = config.get("port", 5432)
    user = config.get("user", "")
    password = config.get("password", "")
    database = config.get("database", "eleanor")

    if not all([host, user, password]):
        return jsonify({"success": False, "message": "Missing required fields"})

    try:
        import psycopg2

        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            connect_timeout=10,
        )
        conn.close()
        return jsonify(
            {"success": True, "message": f"Successfully connected to {host}:{port}"}
        )
    except ImportError:
        # psycopg2 not installed, try basic socket test
        import socket

        try:
            sock = socket.create_connection((host, int(port)), timeout=10)
            sock.close()
            return jsonify(
                {
                    "success": True,
                    "message": f"Port {port} is reachable on {host} (full test requires psycopg2)",
                }
            )
        except Exception as e:
            return jsonify({"success": False, "message": f"Connection failed: {e}"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Connection failed: {e}"})


# =============================================================================
# Storage Testing
# =============================================================================


@app.route("/api/storage/test", methods=["POST"])
def test_storage():
    """Test storage credentials and access."""
    config = request.json or {}
    backend = config.get("backend", "local")

    if backend == "local":
        path = config.get("path", "/var/lib/eleanor/evidence")
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            test_file = Path(path) / ".test"
            test_file.write_text("test")
            test_file.unlink()
            return jsonify({"success": True, "message": f"Local storage OK at {path}"})
        except Exception as e:
            return jsonify({"success": False, "message": f"Storage test failed: {e}"})

    elif backend == "s3":
        return test_s3_storage(config)

    elif backend == "azure":
        return test_azure_storage(config)

    elif backend == "gcs":
        return test_gcs_storage(config)

    return jsonify({"success": False, "message": f"Unknown storage backend: {backend}"})


def test_s3_storage(config: dict) -> dict:
    """Test S3 storage connection."""
    bucket = config.get("bucket", "")
    region = config.get("region", "us-east-1")
    access_key = config.get("access_key", "")
    secret_key = config.get("secret_key", "")
    endpoint_url = config.get("endpoint_url", "")

    if not all([bucket, access_key, secret_key]):
        return jsonify(
            {"success": False, "message": "Missing required S3 credentials"}
        )

    try:
        import boto3
        from botocore.exceptions import ClientError

        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

        s3_args = {}
        if endpoint_url:
            s3_args["endpoint_url"] = endpoint_url

        s3 = session.client("s3", **s3_args)

        # Try to list objects (head_bucket requires special permissions)
        s3.list_objects_v2(Bucket=bucket, MaxKeys=1)

        return jsonify({"success": True, "message": f"S3 bucket '{bucket}' is accessible"})

    except ImportError:
        return jsonify(
            {"success": False, "message": "boto3 not installed. Install during setup."}
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        return jsonify(
            {"success": False, "message": f"S3 error ({error_code}): {e}"}
        )
    except Exception as e:
        return jsonify({"success": False, "message": f"S3 connection failed: {e}"})


def test_azure_storage(config: dict) -> dict:
    """Test Azure Blob storage connection."""
    connection_string = config.get("connection_string", "")
    container = config.get("container", "evidence")

    if not connection_string:
        return jsonify(
            {"success": False, "message": "Azure connection string is required"}
        )

    try:
        from azure.storage.blob import BlobServiceClient

        blob_service = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service.get_container_client(container)

        # Check if container exists, create if not
        if not container_client.exists():
            return jsonify(
                {
                    "success": True,
                    "message": f"Azure storage accessible. Container '{container}' will be created.",
                }
            )

        return jsonify(
            {"success": True, "message": f"Azure container '{container}' is accessible"}
        )

    except ImportError:
        return jsonify(
            {
                "success": False,
                "message": "azure-storage-blob not installed. Install during setup.",
            }
        )
    except Exception as e:
        return jsonify({"success": False, "message": f"Azure connection failed: {e}"})


def test_gcs_storage(config: dict) -> dict:
    """Test Google Cloud Storage connection."""
    bucket = config.get("bucket", "")
    credentials_json = config.get("credentials_json", "")

    if not bucket:
        return jsonify({"success": False, "message": "GCS bucket name is required"})

    try:
        from google.cloud import storage
        from google.oauth2 import service_account

        if credentials_json:
            # Parse JSON credentials
            creds_dict = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict
            )
            client = storage.Client(credentials=credentials)
        else:
            # Use default credentials (if running in GCP)
            client = storage.Client()

        bucket_obj = client.bucket(bucket)
        if not bucket_obj.exists():
            return jsonify(
                {
                    "success": True,
                    "message": f"GCS accessible. Bucket '{bucket}' will be created.",
                }
            )

        return jsonify(
            {"success": True, "message": f"GCS bucket '{bucket}' is accessible"}
        )

    except ImportError:
        return jsonify(
            {
                "success": False,
                "message": "google-cloud-storage not installed. Install during setup.",
            }
        )
    except json.JSONDecodeError:
        return jsonify(
            {"success": False, "message": "Invalid JSON in service account credentials"}
        )
    except Exception as e:
        return jsonify({"success": False, "message": f"GCS connection failed: {e}"})


# =============================================================================
# OIDC Discovery
# =============================================================================


@app.route("/api/oidc/discover", methods=["POST"])
def discover_oidc():
    """Fetch and parse OIDC discovery document."""
    config = request.json or {}
    issuer = config.get("issuer", "").rstrip("/")

    if not issuer:
        return jsonify({"success": False, "message": "OIDC issuer URL is required"})

    discovery_url = f"{issuer}/.well-known/openid-configuration"

    try:
        response = requests.get(discovery_url, timeout=10, verify=True)
        response.raise_for_status()

        discovery = response.json()

        # Extract key endpoints
        result = {
            "success": True,
            "message": f"OIDC provider discovered: {discovery.get('issuer', issuer)}",
            "discovery": {
                "issuer": discovery.get("issuer"),
                "authorization_endpoint": discovery.get("authorization_endpoint"),
                "token_endpoint": discovery.get("token_endpoint"),
                "userinfo_endpoint": discovery.get("userinfo_endpoint"),
                "jwks_uri": discovery.get("jwks_uri"),
                "scopes_supported": discovery.get("scopes_supported", []),
                "claims_supported": discovery.get("claims_supported", []),
            },
        }

        return jsonify(result)

    except requests.exceptions.SSLError as e:
        return jsonify(
            {"success": False, "message": f"SSL verification failed: {e}. Check certificate."}
        )
    except requests.exceptions.ConnectionError as e:
        return jsonify(
            {"success": False, "message": f"Cannot connect to {issuer}: {e}"}
        )
    except requests.exceptions.HTTPError as e:
        return jsonify(
            {"success": False, "message": f"HTTP error from {discovery_url}: {e}"}
        )
    except Exception as e:
        return jsonify({"success": False, "message": f"OIDC discovery failed: {e}"})


# =============================================================================
# Configuration Validation
# =============================================================================


@app.route("/api/validate", methods=["POST"])
def validate_config():
    """Validate full setup configuration."""
    config = request.json or {}
    errors = []
    warnings = []

    # Validate deployment profile
    profile = config.get("profile", "small")
    if profile not in DEPLOYMENT_PROFILES:
        errors.append(f"Invalid deployment profile: {profile}")

    # Validate database config
    db_type = config.get("db_type", "embedded")
    if db_type == "external":
        if not config.get("db_host"):
            errors.append("External database: host is required")
        if not config.get("db_user"):
            errors.append("External database: username is required")
        if not config.get("db_password"):
            errors.append("External database: password is required")

    # Validate storage config
    storage = config.get("storage_backend", "local")
    if storage == "s3":
        if not config.get("storage_bucket"):
            errors.append("S3: bucket name is required")
        if not config.get("storage_access_key"):
            errors.append("S3: access key is required")
        if not config.get("storage_secret_key"):
            errors.append("S3: secret key is required")
    elif storage == "azure":
        if not config.get("storage_connection_string"):
            errors.append("Azure: connection string is required")
    elif storage == "gcs":
        if not config.get("storage_bucket"):
            errors.append("GCS: bucket name is required")

    # Validate authentication config
    auth_local = config.get("auth_local_enabled", True)
    auth_oidc = config.get("auth_oidc_enabled", False)

    if not auth_local and not auth_oidc:
        errors.append("At least one authentication method must be enabled")

    if auth_oidc:
        if not config.get("oidc_issuer"):
            errors.append("OIDC: issuer URL is required")
        if not config.get("oidc_client_id"):
            errors.append("OIDC: client ID is required")
        if not config.get("oidc_client_secret"):
            errors.append("OIDC: client secret is required")

    # Validate admin account (required if local auth enabled)
    if auth_local:
        if not config.get("admin_username"):
            errors.append("Admin username is required")
        admin_password = config.get("admin_password", "")
        if not admin_password:
            errors.append("Admin password is required")
        elif len(admin_password) < 12:
            errors.append("Admin password must be at least 12 characters")
        else:
            # Check password complexity
            has_upper = any(c.isupper() for c in admin_password)
            has_lower = any(c.islower() for c in admin_password)
            has_digit = any(c.isdigit() for c in admin_password)
            if not (has_upper and has_lower and has_digit):
                warnings.append(
                    "Password should contain uppercase, lowercase, and digits"
                )

    # Validate hostname
    hostname = config.get("hostname", "")
    if not hostname:
        warnings.append("Hostname not set, will use system default")

    return jsonify(
        {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
    )


# =============================================================================
# Setup Process
# =============================================================================


@app.route("/api/setup", methods=["POST"])
def start_setup():
    """Start the setup process."""
    config = request.json or {}

    # Validate first
    validation = validate_config_internal(config)
    if not validation["valid"]:
        return jsonify({"status": "error", "errors": validation["errors"]}), 400

    # Start setup in background
    thread = threading.Thread(target=run_setup, args=(config,))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started"})


def validate_config_internal(config: dict) -> dict:
    """Internal config validation."""
    errors = []

    auth_local = config.get("auth_local_enabled", True)
    if auth_local:
        if not config.get("admin_username"):
            errors.append("Admin username required")
        if not config.get("admin_password"):
            errors.append("Admin password required")
        elif len(config.get("admin_password", "")) < 12:
            errors.append("Admin password must be at least 12 characters")

    return {"valid": len(errors) == 0, "errors": errors}


def run_setup(config: dict):
    """Run the complete setup process."""
    try:
        # Step 1: Generate secrets
        update_status("secrets", 5, "Generating security keys...")
        secret_key = secrets.token_hex(32)
        jwt_secret = secrets.token_hex(32)
        db_password = config.get("db_password") or secrets.token_urlsafe(24)

        # Step 2: Create environment file
        update_status("config", 15, "Creating configuration...")
        create_env_file(config, secret_key, jwt_secret, db_password)

        # Step 3: Set hostname
        hostname = config.get("hostname", "eleanor")
        if hostname:
            update_status("hostname", 20, f"Setting hostname to {hostname}...")
            try:
                subprocess.run(
                    ["hostnamectl", "set-hostname", hostname],
                    check=True,
                    capture_output=True,
                )
            except Exception as e:
                # Non-fatal, continue
                pass

        # Step 4: Save GCS credentials if provided
        if config.get("storage_backend") == "gcs" and config.get("gcs_credentials_json"):
            update_status("storage", 25, "Saving GCS credentials...")
            creds_path = ELEANOR_DIR / "gcs-key.json"
            creds_path.write_text(config["gcs_credentials_json"])
            os.chmod(creds_path, 0o600)

        # Step 5: Generate Docker Compose based on profile
        update_status("docker", 30, "Configuring Docker services...")
        profile = config.get("profile", "small")
        configure_docker_compose(profile, config)

        # Step 6: Start Docker services
        update_status("services", 40, "Starting Docker services...")
        os.chdir(ELEANOR_DIR)
        result = subprocess.run(
            ["docker", "compose", "up", "-d"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise Exception(f"Docker Compose failed: {result.stderr}")

        # Step 7: Wait for services
        update_status("health", 50, "Waiting for services to start...")
        wait_for_services()

        # Step 8: Run database migrations
        update_status("migrations", 70, "Running database migrations...")
        run_migrations()

        # Step 9: Create admin user (if local auth enabled)
        if config.get("auth_local_enabled", True):
            update_status("admin", 85, "Creating admin user...")
            create_admin_user(config)

        # Step 10: Configure nginx
        update_status("nginx", 92, "Configuring nginx...")
        subprocess.run(["systemctl", "enable", "nginx"], check=False)
        subprocess.run(["systemctl", "restart", "nginx"], check=False)

        # Step 11: Enable Eleanor service
        update_status("enable", 95, "Enabling Eleanor service...")
        subprocess.run(["systemctl", "enable", "eleanor"], check=False)

        # Step 12: Mark as complete
        update_status("complete", 100, "Setup complete!")
        CONFIGURED_FLAG.touch()

        # Disable setup wizard
        subprocess.run(["systemctl", "disable", "eleanor-setup"], check=False)

    except Exception as e:
        update_status("error", -1, "Setup failed", str(e))
        raise


def create_env_file(
    config: dict, secret_key: str, jwt_secret: str, db_password: str
):
    """Create the .env configuration file."""
    env_file = ELEANOR_DIR / ".env"

    # Database configuration
    db_type = config.get("db_type", "embedded")
    if db_type == "embedded":
        db_host = "postgres"
        db_port = 5432
        db_user = "eleanor"
        db_name = "eleanor"
    else:
        db_host = config.get("db_host", "localhost")
        db_port = config.get("db_port", 5432)
        db_user = config.get("db_user", "eleanor")
        db_password = config.get("db_password", db_password)
        db_name = config.get("db_name", "eleanor")

    # Build environment content
    lines = [
        "# Eleanor DFIR Platform Configuration",
        "# Generated by Enhanced Setup Wizard",
        f"# Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "# =========================================",
        "# Database Configuration",
        "# =========================================",
        f"DB_TYPE={db_type}",
        f"POSTGRES_HOST={db_host}",
        f"POSTGRES_PORT={db_port}",
        f"POSTGRES_USER={db_user}",
        f"POSTGRES_PASSWORD={db_password}",
        f"POSTGRES_DB={db_name}",
        f"DATABASE_URL=postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}",
        "",
        "# =========================================",
        "# Storage Configuration",
        "# =========================================",
        f"STORAGE_BACKEND={config.get('storage_backend', 'local')}",
        f"STORAGE_PATH={config.get('storage_path', '/var/lib/eleanor/evidence')}",
    ]

    # S3 storage config
    if config.get("storage_backend") == "s3":
        lines.extend(
            [
                f"STORAGE_BUCKET={config.get('storage_bucket', '')}",
                f"STORAGE_REGION={config.get('storage_region', 'us-east-1')}",
                f"STORAGE_ACCESS_KEY={config.get('storage_access_key', '')}",
                f"STORAGE_SECRET_KEY={config.get('storage_secret_key', '')}",
            ]
        )
        if config.get("storage_endpoint_url"):
            lines.append(f"STORAGE_ENDPOINT_URL={config['storage_endpoint_url']}")

    # Azure storage config
    elif config.get("storage_backend") == "azure":
        lines.extend(
            [
                f"STORAGE_CONNECTION_STRING={config.get('storage_connection_string', '')}",
                f"STORAGE_CONTAINER={config.get('storage_container', 'evidence')}",
            ]
        )

    # GCS storage config
    elif config.get("storage_backend") == "gcs":
        lines.extend(
            [
                f"STORAGE_BUCKET={config.get('storage_bucket', '')}",
                "GOOGLE_APPLICATION_CREDENTIALS=/opt/eleanor/gcs-key.json",
            ]
        )

    # Authentication configuration
    lines.extend(
        [
            "",
            "# =========================================",
            "# Authentication Configuration",
            "# =========================================",
            f"AUTH_LOCAL_ENABLED={str(config.get('auth_local_enabled', True)).lower()}",
            f"SAM_ENABLED={str(config.get('auth_local_enabled', True)).lower()}",
            f"OIDC_ENABLED={str(config.get('auth_oidc_enabled', False)).lower()}",
        ]
    )

    if config.get("auth_oidc_enabled"):
        hostname = config.get("hostname", "eleanor")
        lines.extend(
            [
                f"OIDC_ISSUER={config.get('oidc_issuer', '')}",
                f"OIDC_CLIENT_ID={config.get('oidc_client_id', '')}",
                f"OIDC_CLIENT_SECRET={config.get('oidc_client_secret', '')}",
                f"OIDC_REDIRECT_URI=https://{hostname}/auth/callback",
                f"OIDC_SCOPES={config.get('oidc_scopes', 'openid profile email')}",
            ]
        )

    # Security keys
    lines.extend(
        [
            "",
            "# =========================================",
            "# Security",
            "# =========================================",
            f"SECRET_KEY={secret_key}",
            f"JWT_SECRET={jwt_secret}",
        ]
    )

    # Application settings
    profile = config.get("profile", "small")
    profile_config = DEPLOYMENT_PROFILES.get(profile, DEPLOYMENT_PROFILES["small"])

    lines.extend(
        [
            "",
            "# =========================================",
            "# Application Settings",
            "# =========================================",
            "ELEANOR_VERSION=1.0.0",
            f"DEPLOYMENT_PROFILE={profile}",
            f"CELERY_WORKER_COUNT={profile_config['worker_count']}",
            f"ES_JAVA_OPTS=-Xms{profile_config['elasticsearch_heap']} -Xmx{profile_config['elasticsearch_heap']}",
        ]
    )

    # Redis/Elasticsearch
    lines.extend(
        [
            "",
            "# =========================================",
            "# Services",
            "# =========================================",
            "REDIS_URL=redis://redis:6379",
            "ELASTICSEARCH_URL=http://elasticsearch:9200",
        ]
    )

    # Integrations (if configured)
    if config.get("velociraptor_url"):
        lines.extend(
            [
                "",
                "# Velociraptor Integration",
                "VELOCIRAPTOR_ENABLED=true",
                f"VELOCIRAPTOR_URL={config['velociraptor_url']}",
                f"VELOCIRAPTOR_API_KEY={config.get('velociraptor_api_key', '')}",
            ]
        )

    if config.get("iris_url"):
        lines.extend(
            [
                "",
                "# IRIS Integration",
                "IRIS_ENABLED=true",
                f"IRIS_URL={config['iris_url']}",
                f"IRIS_API_KEY={config.get('iris_api_key', '')}",
            ]
        )

    if config.get("opencti_url"):
        lines.extend(
            [
                "",
                "# OpenCTI Integration",
                "OPENCTI_ENABLED=true",
                f"OPENCTI_URL={config['opencti_url']}",
                f"OPENCTI_API_KEY={config.get('opencti_api_key', '')}",
            ]
        )

    # Write file
    env_file.write_text("\n".join(lines) + "\n")
    os.chmod(env_file, 0o600)


def configure_docker_compose(profile: str, config: dict):
    """Configure docker-compose based on deployment profile."""
    profile_config = DEPLOYMENT_PROFILES.get(profile, DEPLOYMENT_PROFILES["small"])
    compose_file = ELEANOR_DIR / "docker-compose.yml"

    # Read existing compose file
    if compose_file.exists():
        with open(compose_file) as f:
            compose_content = f.read()

        # Update Elasticsearch heap settings
        es_heap = profile_config["elasticsearch_heap"]
        # The compose file should use ${ES_JAVA_OPTS} from .env

        # For external database, we might need to modify the compose file
        if config.get("db_type") == "external":
            # Remove or disable the postgres service dependency
            # This is handled by the docker-compose.override.yml approach
            override_file = ELEANOR_DIR / "docker-compose.override.yml"
            override_content = """version: '3.8'
services:
  backend:
    depends_on: []
  celery-worker:
    depends_on:
      - redis
  celery-beat:
    depends_on:
      - redis
"""
            override_file.write_text(override_content)


def wait_for_services():
    """Wait for Docker services to be healthy."""
    max_attempts = 60
    for i in range(max_attempts):
        update_status("health", 50 + (i * 20 // max_attempts), f"Waiting for services... ({i * 5}s)")

        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                cwd=ELEANOR_DIR,
            )

            if result.returncode == 0 and result.stdout.strip():
                try:
                    # Try parsing as JSON array
                    services = json.loads(result.stdout)
                    if isinstance(services, list):
                        running = all(
                            s.get("State") == "running" for s in services
                        )
                        if running and len(services) >= 3:
                            return
                except json.JSONDecodeError:
                    # Try line-by-line JSON
                    lines = result.stdout.strip().split("\n")
                    services = [json.loads(line) for line in lines if line.strip()]
                    running = all(s.get("State") == "running" for s in services)
                    if running and len(services) >= 3:
                        return
        except Exception:
            pass

        time.sleep(5)

    raise Exception("Services did not start within timeout")


def run_migrations():
    """Run database migrations."""
    result = subprocess.run(
        ["docker", "exec", "eleanor-backend", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=ELEANOR_DIR,
    )
    if result.returncode != 0:
        # Try with different container name
        result = subprocess.run(
            ["docker", "exec", "eleanor_backend_1", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=ELEANOR_DIR,
        )
    if result.returncode != 0:
        raise Exception(f"Migration failed: {result.stderr}")


def create_admin_user(config: dict):
    """Create the admin user via API or direct database."""
    username = config.get("admin_username", "admin")
    email = config.get("admin_email", f"{username}@eleanor.local")
    password = config.get("admin_password", "")

    if not password:
        raise Exception("Admin password is required")

    # Try via API first
    try:
        import time

        # Wait a bit for the API to be ready
        time.sleep(5)

        response = requests.post(
            "http://localhost:8000/api/v1/auth/setup",
            json={"username": username, "email": email, "password": password},
            timeout=30,
        )
        if response.status_code in (200, 201):
            return
    except Exception:
        pass

    # Fallback: Create via Python in container
    admin_script = f'''
import asyncio
from app.database import async_session_maker
from app.models.user import User, AuthProvider
from app.utils.password import hash_password

async def create():
    async with async_session_maker() as db:
        user = User(
            username="{username}",
            email="{email}",
            display_name="{username}",
            auth_provider=AuthProvider.SAM,
            password_hash=hash_password("{password}"),
            is_admin=True,
            is_active=True,
            roles=["admin"],
        )
        db.add(user)
        await db.commit()
        print("Admin user created")

asyncio.run(create())
'''

    result = subprocess.run(
        ["docker", "exec", "eleanor-backend", "python", "-c", admin_script],
        capture_output=True,
        text=True,
        cwd=ELEANOR_DIR,
    )
    if result.returncode != 0 and "already exists" not in result.stderr.lower():
        # Try alternate container name
        result = subprocess.run(
            ["docker", "exec", "eleanor_backend_1", "python", "-c", admin_script],
            capture_output=True,
            text=True,
            cwd=ELEANOR_DIR,
        )


@app.route("/api/setup/progress")
def get_progress():
    """Get setup progress."""
    if STATUS_FILE.exists():
        with open(STATUS_FILE) as f:
            return jsonify(json.load(f))

    return jsonify({"step": "idle", "progress": 0, "message": "Ready to start setup"})


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    # Ensure static folder exists
    static_path = Path(__file__).parent / "static"
    static_path.mkdir(exist_ok=True)

    # Check for SSL certificates
    cert_file = Path("/etc/nginx/ssl/eleanor.crt")
    key_file = Path("/etc/nginx/ssl/eleanor.key")

    if cert_file.exists() and key_file.exists():
        app.run(
            host="0.0.0.0",
            port=9443,
            ssl_context=(str(cert_file), str(key_file)),
        )
    else:
        # Run without SSL for development/testing
        app.run(host="0.0.0.0", port=9443)
