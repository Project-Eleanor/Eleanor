"""Graph builder service for investigation visualizations.

Extracts entity relationships from Elasticsearch events and builds
graph structures for visualization.
"""

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from elasticsearch import AsyncElasticsearch

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GraphBuilder:
    """Builds investigation graphs from case events."""

    def __init__(self, es_client: AsyncElasticsearch):
        self.es = es_client

    async def build_case_graph(
        self,
        case_id: str,
        max_nodes: int = 100,
        entity_types: list[str] | None = None,
        time_range: tuple[datetime, datetime] | None = None,
    ) -> dict[str, Any]:
        """Build a graph from all events in a case.

        Args:
            case_id: Case UUID
            max_nodes: Maximum number of nodes to return
            entity_types: Filter to specific entity types
            time_range: Optional time filter

        Returns:
            Graph with nodes and edges
        """
        if entity_types is None:
            entity_types = ["host", "user", "ip", "process", "file", "domain"]

        index_name = f"{settings.elasticsearch_index_prefix}-events-{case_id}"

        # Build aggregations for each entity type
        aggs = {}

        if "host" in entity_types:
            aggs["hosts"] = {
                "terms": {"field": "host.name", "size": max_nodes},
                "aggs": {
                    "first_seen": {"min": {"field": "@timestamp"}},
                    "last_seen": {"max": {"field": "@timestamp"}},
                    "event_count": {"value_count": {"field": "@timestamp"}},
                }
            }

        if "user" in entity_types:
            aggs["users"] = {
                "terms": {"field": "user.name", "size": max_nodes},
                "aggs": {
                    "first_seen": {"min": {"field": "@timestamp"}},
                    "last_seen": {"max": {"field": "@timestamp"}},
                    "hosts": {"terms": {"field": "host.name", "size": 10}},
                }
            }

        if "ip" in entity_types:
            aggs["source_ips"] = {
                "terms": {"field": "source.ip", "size": max_nodes},
                "aggs": {
                    "first_seen": {"min": {"field": "@timestamp"}},
                    "last_seen": {"max": {"field": "@timestamp"}},
                    "dest_ips": {"terms": {"field": "destination.ip", "size": 10}},
                }
            }
            aggs["dest_ips"] = {
                "terms": {"field": "destination.ip", "size": max_nodes},
            }

        if "process" in entity_types:
            aggs["processes"] = {
                "terms": {"field": "process.name", "size": max_nodes},
                "aggs": {
                    "hosts": {"terms": {"field": "host.name", "size": 10}},
                    "users": {"terms": {"field": "user.name", "size": 10}},
                }
            }

        if "file" in entity_types:
            aggs["files"] = {
                "terms": {"field": "file.name", "size": max_nodes},
                "aggs": {
                    "hosts": {"terms": {"field": "host.name", "size": 10}},
                    "processes": {"terms": {"field": "process.name", "size": 10}},
                }
            }

        if "domain" in entity_types:
            aggs["domains"] = {
                "terms": {"field": "url.domain", "size": max_nodes},
                "aggs": {
                    "hosts": {"terms": {"field": "host.name", "size": 10}},
                }
            }

        # Build query
        query: dict[str, Any] = {"match_all": {}}
        if time_range:
            query = {
                "range": {
                    "@timestamp": {
                        "gte": time_range[0].isoformat(),
                        "lte": time_range[1].isoformat(),
                    }
                }
            }

        # Execute aggregation query
        result = await self.es.search(
            index=index_name,
            query=query,
            aggs=aggs,
            size=0,
        )

        # Build graph from aggregations
        nodes = []
        edges = []
        node_ids = set()

        aggregations = result.get("aggregations", {})

        # Process hosts
        for bucket in aggregations.get("hosts", {}).get("buckets", []):
            node_id = f"host:{bucket['key']}"
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "label": bucket["key"],
                    "type": "host",
                    "event_count": bucket.get("event_count", {}).get("value", bucket["doc_count"]),
                    "first_seen": bucket.get("first_seen", {}).get("value_as_string"),
                    "last_seen": bucket.get("last_seen", {}).get("value_as_string"),
                })

        # Process users and create user->host edges
        for bucket in aggregations.get("users", {}).get("buckets", []):
            node_id = f"user:{bucket['key']}"
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "label": bucket["key"],
                    "type": "user",
                    "event_count": bucket["doc_count"],
                    "first_seen": bucket.get("first_seen", {}).get("value_as_string"),
                    "last_seen": bucket.get("last_seen", {}).get("value_as_string"),
                })

            # Create edges to hosts
            for host_bucket in bucket.get("hosts", {}).get("buckets", []):
                host_id = f"host:{host_bucket['key']}"
                if host_id in node_ids:
                    edges.append({
                        "source": node_id,
                        "target": host_id,
                        "relationship": "logged_into",
                        "weight": host_bucket["doc_count"],
                    })

        # Process IPs and create network edges
        ip_nodes = set()
        for bucket in aggregations.get("source_ips", {}).get("buckets", []):
            node_id = f"ip:{bucket['key']}"
            if node_id not in node_ids:
                node_ids.add(node_id)
                ip_nodes.add(node_id)
                nodes.append({
                    "id": node_id,
                    "label": bucket["key"],
                    "type": "ip",
                    "event_count": bucket["doc_count"],
                    "first_seen": bucket.get("first_seen", {}).get("value_as_string"),
                    "last_seen": bucket.get("last_seen", {}).get("value_as_string"),
                })

            # Create edges to destination IPs
            for dest_bucket in bucket.get("dest_ips", {}).get("buckets", []):
                dest_id = f"ip:{dest_bucket['key']}"
                if dest_id not in node_ids:
                    node_ids.add(dest_id)
                    ip_nodes.add(dest_id)
                    nodes.append({
                        "id": dest_id,
                        "label": dest_bucket["key"],
                        "type": "ip",
                        "event_count": dest_bucket["doc_count"],
                    })

                edges.append({
                    "source": node_id,
                    "target": dest_id,
                    "relationship": "connected_to",
                    "weight": dest_bucket["doc_count"],
                })

        # Process processes
        for bucket in aggregations.get("processes", {}).get("buckets", []):
            node_id = f"process:{bucket['key']}"
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "label": bucket["key"],
                    "type": "process",
                    "event_count": bucket["doc_count"],
                })

            # Create edges to hosts
            for host_bucket in bucket.get("hosts", {}).get("buckets", []):
                host_id = f"host:{host_bucket['key']}"
                if host_id in node_ids:
                    edges.append({
                        "source": host_id,
                        "target": node_id,
                        "relationship": "executed",
                        "weight": host_bucket["doc_count"],
                    })

            # Create edges to users
            for user_bucket in bucket.get("users", {}).get("buckets", []):
                user_id = f"user:{user_bucket['key']}"
                if user_id in node_ids:
                    edges.append({
                        "source": user_id,
                        "target": node_id,
                        "relationship": "ran",
                        "weight": user_bucket["doc_count"],
                    })

        # Process files
        for bucket in aggregations.get("files", {}).get("buckets", []):
            node_id = f"file:{bucket['key']}"
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "label": bucket["key"],
                    "type": "file",
                    "event_count": bucket["doc_count"],
                })

            # Create edges to processes
            for proc_bucket in bucket.get("processes", {}).get("buckets", []):
                proc_id = f"process:{proc_bucket['key']}"
                if proc_id in node_ids:
                    edges.append({
                        "source": proc_id,
                        "target": node_id,
                        "relationship": "accessed",
                        "weight": proc_bucket["doc_count"],
                    })

        # Process domains
        for bucket in aggregations.get("domains", {}).get("buckets", []):
            node_id = f"domain:{bucket['key']}"
            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "label": bucket["key"],
                    "type": "domain",
                    "event_count": bucket["doc_count"],
                })

            # Create edges to hosts
            for host_bucket in bucket.get("hosts", {}).get("buckets", []):
                host_id = f"host:{host_bucket['key']}"
                if host_id in node_ids:
                    edges.append({
                        "source": host_id,
                        "target": node_id,
                        "relationship": "resolved",
                        "weight": host_bucket["doc_count"],
                    })

        # Deduplicate edges
        seen_edges = set()
        unique_edges = []
        for edge in edges:
            edge_key = f"{edge['source']}|{edge['target']}|{edge['relationship']}"
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                unique_edges.append(edge)

        return {
            "nodes": nodes[:max_nodes],
            "edges": unique_edges,
            "metadata": {
                "case_id": case_id,
                "total_nodes": len(nodes),
                "total_edges": len(unique_edges),
                "truncated": len(nodes) > max_nodes,
            }
        }

    async def expand_node(
        self,
        case_id: str,
        node_id: str,
        max_connections: int = 20,
    ) -> dict[str, Any]:
        """Expand a node to show its direct connections.

        Args:
            case_id: Case UUID
            node_id: Node ID in format "type:value"
            max_connections: Maximum connections to return

        Returns:
            New nodes and edges to add to graph
        """
        parts = node_id.split(":", 1)
        if len(parts) != 2:
            return {"nodes": [], "edges": []}

        node_type, node_value = parts
        index_name = f"{settings.elasticsearch_index_prefix}-events-{case_id}"

        # Build query based on node type
        field_map = {
            "host": "host.name",
            "user": "user.name",
            "ip": ["source.ip", "destination.ip"],
            "process": "process.name",
            "file": "file.name",
            "domain": "url.domain",
        }

        fields = field_map.get(node_type)
        if not fields:
            return {"nodes": [], "edges": []}

        if isinstance(fields, str):
            fields = [fields]

        should_clauses = [{"term": {field: node_value}} for field in fields]

        # Build aggregations for related entities
        aggs = {
            "hosts": {"terms": {"field": "host.name", "size": max_connections}},
            "users": {"terms": {"field": "user.name", "size": max_connections}},
            "source_ips": {"terms": {"field": "source.ip", "size": max_connections}},
            "dest_ips": {"terms": {"field": "destination.ip", "size": max_connections}},
            "processes": {"terms": {"field": "process.name", "size": max_connections}},
            "files": {"terms": {"field": "file.name", "size": max_connections}},
            "domains": {"terms": {"field": "url.domain", "size": max_connections}},
        }

        result = await self.es.search(
            index=index_name,
            query={"bool": {"should": should_clauses, "minimum_should_match": 1}},
            aggs=aggs,
            size=0,
        )

        nodes = []
        edges = []
        node_ids = {node_id}
        aggregations = result.get("aggregations", {})

        # Process each aggregation
        type_agg_map = {
            "hosts": "host",
            "users": "user",
            "source_ips": "ip",
            "dest_ips": "ip",
            "processes": "process",
            "files": "file",
            "domains": "domain",
        }

        relationship_map = {
            "host": {"user": "logged_into", "process": "executed", "ip": "has_ip", "domain": "resolved"},
            "user": {"host": "logged_into", "process": "ran"},
            "ip": {"ip": "connected_to", "host": "from_host"},
            "process": {"host": "ran_on", "user": "ran_by", "file": "accessed"},
            "file": {"process": "accessed_by", "host": "on_host"},
            "domain": {"host": "resolved_by"},
        }

        for agg_name, entity_type in type_agg_map.items():
            for bucket in aggregations.get(agg_name, {}).get("buckets", []):
                new_node_id = f"{entity_type}:{bucket['key']}"

                if new_node_id == node_id:
                    continue

                if new_node_id not in node_ids:
                    node_ids.add(new_node_id)
                    nodes.append({
                        "id": new_node_id,
                        "label": bucket["key"],
                        "type": entity_type,
                        "event_count": bucket["doc_count"],
                    })

                # Determine relationship
                rel = relationship_map.get(node_type, {}).get(entity_type, "related_to")

                edges.append({
                    "source": node_id,
                    "target": new_node_id,
                    "relationship": rel,
                    "weight": bucket["doc_count"],
                })

        return {
            "nodes": nodes,
            "edges": edges,
        }

    async def find_path(
        self,
        case_id: str,
        source_node: str,
        target_node: str,
        max_hops: int = 5,
    ) -> dict[str, Any]:
        """Find path between two entities.

        Uses breadth-first search through event relationships.

        Args:
            case_id: Case UUID
            source_node: Starting node ID
            target_node: Target node ID
            max_hops: Maximum path length

        Returns:
            Path with nodes and edges, or empty if not found
        """
        # Simple BFS implementation
        visited = {source_node}
        queue = [(source_node, [source_node], [])]

        while queue and max_hops > 0:
            current, path_nodes, path_edges = queue.pop(0)

            if current == target_node:
                return {
                    "found": True,
                    "path_nodes": path_nodes,
                    "path_edges": path_edges,
                    "hops": len(path_edges),
                }

            # Expand current node
            expansion = await self.expand_node(case_id, current, max_connections=50)

            for edge in expansion.get("edges", []):
                next_node = edge["target"]
                if next_node not in visited:
                    visited.add(next_node)
                    new_path_nodes = path_nodes + [next_node]
                    new_path_edges = path_edges + [edge]

                    if len(new_path_nodes) <= max_hops + 1:
                        queue.append((next_node, new_path_nodes, new_path_edges))

            max_hops -= 1

        return {
            "found": False,
            "path_nodes": [],
            "path_edges": [],
            "hops": 0,
        }

    async def get_entity_relationships(
        self,
        case_id: str,
        entity_type: str,
        entity_value: str,
    ) -> dict[str, Any]:
        """Get all relationships for a specific entity.

        Args:
            case_id: Case UUID
            entity_type: Entity type (host, user, ip, etc.)
            entity_value: Entity value

        Returns:
            Entity details with relationships
        """
        node_id = f"{entity_type}:{entity_value}"
        expansion = await self.expand_node(case_id, node_id, max_connections=50)

        # Group by relationship type
        relationships_by_type: dict[str, list[dict]] = {}
        for edge in expansion.get("edges", []):
            rel_type = edge["relationship"]
            if rel_type not in relationships_by_type:
                relationships_by_type[rel_type] = []
            relationships_by_type[rel_type].append({
                "entity_id": edge["target"],
                "entity_type": edge["target"].split(":")[0],
                "entity_value": edge["target"].split(":", 1)[1],
                "event_count": edge["weight"],
            })

        return {
            "entity_id": node_id,
            "entity_type": entity_type,
            "entity_value": entity_value,
            "relationships": relationships_by_type,
            "related_entities": expansion.get("nodes", []),
        }
