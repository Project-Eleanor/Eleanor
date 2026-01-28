"""Graph builder service for investigation visualizations.

Extracts entity relationships from Elasticsearch events and builds
graph structures for visualization.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from elasticsearch import AsyncElasticsearch

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# PATTERN: Configuration-Driven Entity Processing
# Entity type configurations drive the graph building process uniformly.
# Each config defines how to extract nodes and edges for that entity type,
# eliminating repeated processing logic for each entity type.
@dataclass
class EntityTypeConfig:
    """Configuration for processing a specific entity type in graph building."""
    node_type: str
    agg_key: str
    sub_agg_configs: list[dict[str, str]] = field(default_factory=list)
    include_timestamps: bool = True


# Entity type configuration mapping
ENTITY_TYPE_CONFIGS: dict[str, EntityTypeConfig] = {
    "host": EntityTypeConfig(
        node_type="host",
        agg_key="hosts",
        include_timestamps=True,
    ),
    "user": EntityTypeConfig(
        node_type="user",
        agg_key="users",
        sub_agg_configs=[
            {"sub_agg": "hosts", "target_type": "host", "relationship": "logged_into"}
        ],
        include_timestamps=True,
    ),
    "process": EntityTypeConfig(
        node_type="process",
        agg_key="processes",
        sub_agg_configs=[
            {"sub_agg": "hosts", "target_type": "host", "relationship": "executed", "reverse": True},
            {"sub_agg": "users", "target_type": "user", "relationship": "ran", "reverse": True},
        ],
        include_timestamps=False,
    ),
    "file": EntityTypeConfig(
        node_type="file",
        agg_key="files",
        sub_agg_configs=[
            {"sub_agg": "processes", "target_type": "process", "relationship": "accessed", "reverse": True},
        ],
        include_timestamps=False,
    ),
    "domain": EntityTypeConfig(
        node_type="domain",
        agg_key="domains",
        sub_agg_configs=[
            {"sub_agg": "hosts", "target_type": "host", "relationship": "resolved", "reverse": True},
        ],
        include_timestamps=False,
    ),
}


class GraphBuilder:
    """Builds investigation graphs from case events."""

    def __init__(self, es_client: AsyncElasticsearch):
        self.es = es_client

    def _process_entity_buckets(
        self,
        aggregations: dict[str, Any],
        config: EntityTypeConfig,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        node_ids: set[str],
    ) -> None:
        """Process aggregation buckets for an entity type and extract nodes/edges.

        PATTERN: Template Method for Entity Processing
        This method provides a uniform way to process all entity types based on
        their configuration, eliminating code duplication across different
        entity type handlers.

        Algorithm:
        1. Extract buckets from the configured aggregation key
        2. For each bucket, create a node with the entity type prefix
        3. Extract optional timestamp metadata (first_seen, last_seen)
        4. Process sub-aggregations to create edges to related entities

        Args:
            aggregations: Elasticsearch aggregation results
            config: Entity type configuration defining processing behavior
            nodes: List to append new nodes to (mutated in place)
            edges: List to append new edges to (mutated in place)
            node_ids: Set of existing node IDs for deduplication (mutated in place)
        """
        buckets = aggregations.get(config.agg_key, {}).get("buckets", [])

        for bucket in buckets:
            node_id = f"{config.node_type}:{bucket['key']}"
            if node_id in node_ids:
                continue

            node_ids.add(node_id)
            node_data: dict[str, Any] = {
                "id": node_id,
                "label": bucket["key"],
                "type": config.node_type,
                "event_count": bucket.get("event_count", {}).get("value", bucket["doc_count"]),
            }

            if config.include_timestamps:
                node_data["first_seen"] = bucket.get("first_seen", {}).get("value_as_string")
                node_data["last_seen"] = bucket.get("last_seen", {}).get("value_as_string")

            nodes.append(node_data)

            # Process sub-aggregations to create edges
            for sub_config in config.sub_agg_configs:
                sub_agg = sub_config["sub_agg"]
                target_type = sub_config["target_type"]
                relationship = sub_config["relationship"]
                reverse = sub_config.get("reverse", False)

                for sub_bucket in bucket.get(sub_agg, {}).get("buckets", []):
                    target_id = f"{target_type}:{sub_bucket['key']}"
                    if target_id in node_ids:
                        source, target = (target_id, node_id) if reverse else (node_id, target_id)
                        edges.append({
                            "source": source,
                            "target": target,
                            "relationship": relationship,
                            "weight": sub_bucket["doc_count"],
                        })

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
        # PATTERN: Two-pass graph construction
        # Pass 1: Create all nodes first so node_ids set is populated for edge validation
        # Pass 2: Process configurations to create edges between existing nodes
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        node_ids: set[str] = set()

        aggregations = result.get("aggregations", {})

        # Process standard entity types using configuration-driven approach
        for entity_type in ["host", "user", "process", "file", "domain"]:
            if entity_type in entity_types and entity_type in ENTITY_TYPE_CONFIGS:
                self._process_entity_buckets(
                    aggregations,
                    ENTITY_TYPE_CONFIGS[entity_type],
                    nodes,
                    edges,
                    node_ids,
                )

        # Process IPs specially due to source->dest relationship pattern
        # IP processing requires special handling for the bidirectional
        # source_ip -> dest_ip relationship which creates edges dynamically
        if "ip" in entity_types:
            for bucket in aggregations.get("source_ips", {}).get("buckets", []):
                node_id = f"ip:{bucket['key']}"
                if node_id not in node_ids:
                    node_ids.add(node_id)
                    nodes.append({
                        "id": node_id,
                        "label": bucket["key"],
                        "type": "ip",
                        "event_count": bucket["doc_count"],
                        "first_seen": bucket.get("first_seen", {}).get("value_as_string"),
                        "last_seen": bucket.get("last_seen", {}).get("value_as_string"),
                    })

                # Create edges to destination IPs (and create dest nodes if needed)
                for dest_bucket in bucket.get("dest_ips", {}).get("buckets", []):
                    dest_id = f"ip:{dest_bucket['key']}"
                    if dest_id not in node_ids:
                        node_ids.add(dest_id)
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

        # Deduplicate edges
        # Edge deduplication ensures that multiple events creating the same
        # relationship only result in a single edge (weight captures frequency)
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
