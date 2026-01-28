"""Velociraptor adapter implementation.

Provides integration with Velociraptor for:
- Endpoint inventory and status
- Artifact collection
- Hunt management
- Live response actions

Uses gRPC with pyvelociraptor for secure programmatic access via client certificates.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

import grpc
import httpx
from grpc import RpcError
from pyvelociraptor import api_pb2, api_pb2_grpc

from app.adapters.base import (
    AdapterConfig,
    AdapterHealth,
    AdapterStatus,
    CollectionAdapter,
    CollectionArtifact,
    CollectionJob,
    Endpoint,
    Hunt,
)
from app.adapters.velociraptor.schemas import (
    VelociraptorArtifact,
    VelociraptorClient,
    VelociraptorFlow,
    VelociraptorHunt,
)

logger = logging.getLogger(__name__)


class VelociraptorAdapter(CollectionAdapter):
    """Adapter for Velociraptor endpoint visibility and collection."""

    name = "velociraptor"
    description = "Velociraptor endpoint collection and response"

    def __init__(self, config: AdapterConfig):
        """Initialize Velociraptor adapter."""
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._grpc_channel: grpc.Channel | None = None
        self._grpc_stub: api_pb2_grpc.APIStub | None = None
        self._version: str | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            # Build client configuration
            headers: dict[str, str] = {
                "Content-Type": "application/json",
            }

            # Support multiple auth methods:
            # 1. Bearer token (api_key)
            # 2. Basic auth (username/password in extra)
            # 3. Client certificates (client_cert/client_key in extra)
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            kwargs: dict[str, Any] = {
                "base_url": self.config.url.rstrip("/"),
                "timeout": self.config.timeout,
                "verify": self.config.verify_ssl,
                "headers": headers,
            }

            # Add Basic auth if username/password provided
            username = self.config.extra.get("username")
            password = self.config.extra.get("password")
            if username and password:
                kwargs["auth"] = (username, password)

            # Add client certificate if provided
            cert_path = self.config.extra.get("client_cert")
            key_path = self.config.extra.get("client_key")
            if cert_path and key_path:
                kwargs["cert"] = (cert_path, key_path)

            self._client = httpx.AsyncClient(**kwargs)

        return self._client

    def _get_grpc_channel(self) -> grpc.Channel:
        """Create gRPC channel with certificate authentication."""
        if self._grpc_channel is None:
            # Read certificates
            ca_cert_path = self.config.extra.get("ca_cert")
            client_cert_path = self.config.extra.get("client_cert")
            client_key_path = self.config.extra.get("client_key")

            with open(ca_cert_path, "rb") as f:
                ca_cert = f.read()
            with open(client_cert_path, "rb") as f:
                client_cert = f.read()
            with open(client_key_path, "rb") as f:
                client_key = f.read()

            credentials = grpc.ssl_channel_credentials(
                root_certificates=ca_cert,
                private_key=client_key,
                certificate_chain=client_cert,
            )

            server_name = self.config.extra.get("grpc_server_name", "VelociraptorServer")
            options = [("grpc.ssl_target_name_override", server_name)]

            self._grpc_channel = grpc.secure_channel(self.config.url, credentials, options=options)
            self._grpc_stub = api_pb2_grpc.APIStub(self._grpc_channel)

        return self._grpc_channel

    def _vql_query_sync(self, query: str, env: dict | None = None) -> list[dict]:
        """Execute VQL query synchronously via gRPC."""
        self._get_grpc_channel()

        vql_env = []
        if env:
            for key, value in env.items():
                vql_env.append(api_pb2.VQLEnv(key=key, value=str(value)))

        request = api_pb2.VQLCollectorArgs(
            max_row=10000,
            max_wait=10,
            Query=[api_pb2.VQLRequest(Name="Query", VQL=query)],
            env=vql_env,
        )

        results = []
        for response in self._grpc_stub.Query(request):
            if response.Response:
                rows = json.loads(response.Response)
                if isinstance(rows, list):
                    results.extend(rows)
                else:
                    results.append(rows)

        return results

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an API request to Velociraptor.

        Args:
            method: HTTP method.
            path: API path.
            **kwargs: Additional request arguments.

        Returns:
            Response JSON.

        Raises:
            httpx.HTTPError: On request failure.
        """
        client = await self._get_client()
        response = await client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _vql_query(
        self,
        query: str,
        env: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute VQL query asynchronously via gRPC.

        Args:
            query: VQL query string.
            env: Environment variables for query.

        Returns:
            List of result rows.
        """
        return await asyncio.to_thread(self._vql_query_sync, query, env)

    async def health_check(self) -> AdapterHealth:
        """Check Velociraptor connectivity via gRPC."""
        try:
            # Query server version from config
            rows = await self._vql_query("SELECT config.version.version as Version FROM config")
            if rows:
                self._version = rows[0].get("Version", "unknown")

            self._status = AdapterStatus.CONNECTED
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.CONNECTED,
                version=self._version,
                message="Connected to Velociraptor via gRPC",
            )
        except RpcError as e:
            logger.error("Velociraptor gRPC health check failed: %s", e.details())
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=f"gRPC error: {e.details()}",
            )
        except httpx.HTTPError as e:
            logger.error("Velociraptor health check failed: %s", e)
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=f"HTTP error: {e}",
            )
        except Exception as e:
            logger.error("Velociraptor health check failed: %s", e)
            self._status = AdapterStatus.ERROR
            return AdapterHealth(
                adapter_name=self.name,
                status=AdapterStatus.ERROR,
                message=str(e),
            )

    async def get_config(self) -> dict[str, Any]:
        """Get adapter configuration (sanitized)."""
        return {
            "url": self.config.url,
            "transport": "gRPC",
            "has_ca_cert": bool(self.config.extra.get("ca_cert")),
            "has_client_cert": bool(self.config.extra.get("client_cert")),
            "has_client_key": bool(self.config.extra.get("client_key")),
            "grpc_server_name": self.config.extra.get("grpc_server_name", "VelociraptorServer"),
        }

    # =========================================================================
    # Endpoint Management
    # =========================================================================

    async def list_endpoints(
        self,
        limit: int = 100,
        offset: int = 0,
        search: str | None = None,
        online_only: bool = False,
    ) -> list[Endpoint]:
        """List Velociraptor clients."""
        # Build VQL query
        query = "SELECT * FROM clients()"
        if search:
            query = f"SELECT * FROM clients(search='{search}')"
        if online_only:
            # Filter to clients seen in last 15 minutes
            query = (
                query.replace("FROM clients", "FROM clients") + " WHERE last_seen_at > now() - 900"
            )

        query += f" LIMIT {limit} OFFSET {offset}"

        rows = await self._vql_query(query)

        endpoints = []
        for row in rows:
            client = VelociraptorClient(**row)
            endpoints.append(
                Endpoint(
                    client_id=client.client_id,
                    hostname=client.hostname or client.fqdn,
                    os=client.os,
                    os_version=client.os_version,
                    ip_addresses=[client.last_ip] if client.last_ip else [],
                    last_seen=client.last_seen_at,
                    labels={label: "true" for label in client.labels},
                    online=client.is_online,
                    metadata={
                        "fqdn": client.fqdn,
                        "agent_info": client.agent_info,
                    },
                )
            )

        return endpoints

    async def get_endpoint(self, client_id: str) -> Endpoint | None:
        """Get a specific endpoint."""
        rows = await self._vql_query(f"SELECT * FROM clients(client_id='{client_id}')")
        if not rows:
            return None

        client = VelociraptorClient(**rows[0])
        return Endpoint(
            client_id=client.client_id,
            hostname=client.hostname or client.fqdn,
            os=client.os,
            os_version=client.os_version,
            ip_addresses=[client.last_ip] if client.last_ip else [],
            last_seen=client.last_seen_at,
            labels={label: "true" for label in client.labels},
            online=client.is_online,
            metadata={
                "fqdn": client.fqdn,
                "os_info": client.os_info,
                "agent_info": client.agent_info,
            },
        )

    async def search_endpoints(self, query: str) -> list[Endpoint]:
        """Search endpoints by hostname, IP, or label."""
        return await self.list_endpoints(search=query)

    # =========================================================================
    # Artifact Collection
    # =========================================================================

    async def list_artifacts(
        self,
        category: str | None = None,
    ) -> list[CollectionArtifact]:
        """List available Velociraptor artifacts."""
        query = "SELECT * FROM artifact_definitions()"
        if category:
            query = f"SELECT * FROM artifact_definitions() WHERE type = '{category}'"

        rows = await self._vql_query(query)

        artifacts = []
        for row in rows:
            velo_artifact = VelociraptorArtifact(**row)
            artifacts.append(
                CollectionArtifact(
                    name=velo_artifact.name,
                    description=velo_artifact.description,
                    parameters={
                        parameter.get("name"): parameter.get("default")
                        for parameter in velo_artifact.parameters
                    },
                    category=velo_artifact.type,
                )
            )

        return artifacts

    async def collect_artifact(
        self,
        client_id: str,
        artifact_name: str,
        parameters: dict[str, Any] | None = None,
        urgent: bool = False,
    ) -> CollectionJob:
        """Collect an artifact from an endpoint via gRPC."""
        # Build VQL query to schedule collection
        env_str = ""
        if parameters:
            env_pairs = [f"`{k}`='{v}'" for k, v in parameters.items()]
            env_str = ", " + ", ".join(env_pairs) if env_pairs else ""

        urgent_str = ", urgent=TRUE" if urgent else ""

        query = f"""
        SELECT collect_client(
            client_id='{client_id}',
            artifacts=['{artifact_name}']{env_str}{urgent_str}
        ) AS Flow FROM scope()
        """

        rows = await self._vql_query(query)

        flow_id = ""
        if rows and rows[0].get("Flow"):
            flow_data = rows[0]["Flow"]
            if isinstance(flow_data, dict):
                flow_id = flow_data.get("flow_id", "")

        return CollectionJob(
            job_id=flow_id,
            client_id=client_id,
            artifact_name=artifact_name,
            status="pending",
            started_at=datetime.utcnow(),
        )

    async def get_collection_status(self, job_id: str) -> CollectionJob:
        """Get status of a collection job (flow)."""
        # Extract client_id from flow_id or use VQL
        rows = await self._vql_query(f"SELECT * FROM flows(flow_id='{job_id}')")

        if not rows:
            return CollectionJob(
                job_id=job_id,
                client_id="unknown",
                artifact_name="unknown",
                status="unknown",
                error="Flow not found",
            )

        flow = VelociraptorFlow(**rows[0])

        # Map Velociraptor state to our status
        status_map = {
            "UNSET": "pending",
            "RUNNING": "running",
            "FINISHED": "completed",
            "ERROR": "failed",
        }

        return CollectionJob(
            job_id=flow.flow_id,
            client_id=flow.client_id,
            artifact_name=flow.artifact_names[0] if flow.artifact_names else "unknown",
            status=status_map.get(flow.state, "unknown"),
            started_at=flow.start_time,
            completed_at=flow.active_time if flow.state == "FINISHED" else None,
            result_count=flow.total_collected_rows,
            error=flow.status if flow.state == "ERROR" else None,
        )

    async def get_collection_results(
        self,
        job_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get results from a collection job."""
        rows = await self._vql_query(
            f"SELECT * FROM flow_results(flow_id='{job_id}') LIMIT {limit}"
        )
        return rows

    # =========================================================================
    # Hunt Management
    # =========================================================================

    async def list_hunts(
        self,
        limit: int = 50,
        state: str | None = None,
    ) -> list[Hunt]:
        """List hunts."""
        query = f"SELECT * FROM hunts() LIMIT {limit}"
        if state:
            query = f"SELECT * FROM hunts() WHERE state = '{state}' LIMIT {limit}"

        rows = await self._vql_query(query)

        hunts = []
        for row in rows:
            velo_hunt = VelociraptorHunt(**row)
            hunts.append(
                Hunt(
                    hunt_id=velo_hunt.hunt_id,
                    name=velo_hunt.hunt_id,  # Velociraptor uses ID as name
                    description=velo_hunt.hunt_description,
                    artifact_name=velo_hunt.artifact_names[0] if velo_hunt.artifact_names else "",
                    state=velo_hunt.state.lower(),
                    created_at=velo_hunt.create_time,
                    started_at=velo_hunt.start_time,
                    expires_at=velo_hunt.expires,
                    total_clients=velo_hunt.total_clients_scheduled,
                    completed_clients=velo_hunt.total_clients_with_results,
                )
            )

        return hunts

    async def create_hunt(
        self,
        name: str,
        artifact_name: str,
        description: str | None = None,
        parameters: dict[str, Any] | None = None,
        target_labels: dict[str, str] | None = None,
        expires_hours: int = 168,
    ) -> Hunt:
        """Create a new hunt via gRPC."""
        desc = description or name
        expires_seconds = expires_hours * 3600

        # Build parameters for VQL
        params_str = ""
        if parameters:
            param_pairs = [f"`{k}`='{v}'" for k, v in parameters.items()]
            params_str = ", " + ", ".join(param_pairs) if param_pairs else ""

        query = f"""
        SELECT hunt(
            description='{desc}',
            artifacts=['{artifact_name}']{params_str},
            expires=now() + {expires_seconds}
        ) AS Hunt FROM scope()
        """

        rows = await self._vql_query(query)

        hunt_id = ""
        if rows and rows[0].get("Hunt"):
            hunt_data = rows[0]["Hunt"]
            if isinstance(hunt_data, dict):
                hunt_id = hunt_data.get("hunt_id", "")

        return Hunt(
            hunt_id=hunt_id,
            name=name,
            description=description,
            artifact_name=artifact_name,
            state="paused",
            created_at=datetime.utcnow(),
        )

    async def start_hunt(self, hunt_id: str) -> Hunt:
        """Start a paused hunt via gRPC."""
        query = f"""
        SELECT hunt_update(
            hunt_id='{hunt_id}',
            state='RUNNING'
        ) FROM scope()
        """
        await self._vql_query(query)

        hunts = await self.list_hunts()
        for hunt in hunts:
            if hunt.hunt_id == hunt_id:
                return hunt

        # Return basic info if not found in list
        return Hunt(
            hunt_id=hunt_id,
            name=hunt_id,
            artifact_name="",
            state="running",
            started_at=datetime.utcnow(),
        )

    async def stop_hunt(self, hunt_id: str) -> Hunt:
        """Stop a running hunt via gRPC."""
        query = f"""
        SELECT hunt_update(
            hunt_id='{hunt_id}',
            state='STOPPED'
        ) FROM scope()
        """
        await self._vql_query(query)

        hunts = await self.list_hunts()
        for hunt in hunts:
            if hunt.hunt_id == hunt_id:
                return hunt

        return Hunt(
            hunt_id=hunt_id,
            name=hunt_id,
            artifact_name="",
            state="stopped",
        )

    async def get_hunt_results(
        self,
        hunt_id: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get aggregated results from a hunt."""
        rows = await self._vql_query(
            f"SELECT * FROM hunt_results(hunt_id='{hunt_id}') LIMIT {limit}"
        )
        return rows

    # =========================================================================
    # Response Actions
    # =========================================================================

    async def isolate_host(self, client_id: str) -> bool:
        """Isolate a host using Velociraptor's quarantine artifact."""
        try:
            await self.collect_artifact(
                client_id=client_id,
                artifact_name="Windows.Remediation.Quarantine",
                parameters={"MessageToUser": "Host isolated by Eleanor DFIR"},
                urgent=True,
            )
            return True
        except Exception as e:
            logger.error("Failed to isolate host %s: %s", client_id, e)
            return False

    async def unisolate_host(self, client_id: str) -> bool:
        """Remove isolation from a host."""
        try:
            await self.collect_artifact(
                client_id=client_id,
                artifact_name="Windows.Remediation.Quarantine",
                parameters={"RemovePolicy": "Y"},
                urgent=True,
            )
            return True
        except Exception as e:
            logger.error("Failed to unisolate host %s: %s", client_id, e)
            return False

    async def quarantine_file(
        self,
        client_id: str,
        file_path: str,
    ) -> bool:
        """Quarantine a file on an endpoint."""
        try:
            await self.collect_artifact(
                client_id=client_id,
                artifact_name="Windows.Remediation.QuarantineFile",
                parameters={"Path": file_path},
                urgent=True,
            )
            return True
        except Exception as e:
            logger.error("Failed to quarantine file on %s: %s", client_id, e)
            return False

    async def kill_process(
        self,
        client_id: str,
        pid: int,
    ) -> bool:
        """Kill a process on an endpoint."""
        try:
            await self.collect_artifact(
                client_id=client_id,
                artifact_name="Generic.Client.KillProcess",
                parameters={"Pid": str(pid)},
                urgent=True,
            )
            return True
        except Exception as e:
            logger.error("Failed to kill process %d on %s: %s", pid, client_id, e)
            return False

    async def disconnect(self) -> None:
        """Close gRPC channel and HTTP client."""
        if self._grpc_channel:
            self._grpc_channel.close()
            self._grpc_channel = None
            self._grpc_stub = None
        if self._client:
            await self._client.aclose()
            self._client = None
        await super().disconnect()
