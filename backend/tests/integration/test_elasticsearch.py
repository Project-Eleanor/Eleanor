"""Integration tests for Elasticsearch.

These tests require a running Elasticsearch instance.
Run with: pytest tests/integration/test_elasticsearch.py --live
"""

import os
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from elasticsearch import AsyncElasticsearch

from app.config import get_settings


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.fixture
def elasticsearch_config():
    """Get Elasticsearch configuration from environment."""
    settings = get_settings()
    return {
        "url": os.getenv("ELASTICSEARCH_URL", settings.elasticsearch_url),
        "index_prefix": os.getenv("ELASTICSEARCH_INDEX_PREFIX", "eleanor-test"),
    }


@pytest.fixture
async def es_client(elasticsearch_config):
    """Create Elasticsearch client."""
    client = AsyncElasticsearch(
        hosts=[elasticsearch_config["url"]],
        verify_certs=False,
    )
    yield client
    await client.close()


@pytest.fixture
def test_index_name(elasticsearch_config):
    """Generate unique test index name."""
    return f"{elasticsearch_config['index_prefix']}-test-{uuid4().hex[:8]}"


class TestElasticsearchConnection:
    """Tests for Elasticsearch connectivity."""

    async def test_cluster_health(self, es_client):
        """Test cluster health check."""
        health = await es_client.cluster.health()

        assert health is not None
        assert health["status"] in ["green", "yellow", "red"]
        assert health["number_of_nodes"] >= 1

    async def test_ping(self, es_client):
        """Test Elasticsearch ping."""
        result = await es_client.ping()

        assert result is True


class TestElasticsearchIndexOperations:
    """Tests for index management."""

    async def test_create_index(self, es_client, test_index_name):
        """Test creating an index."""
        try:
            result = await es_client.indices.create(
                index=test_index_name,
                body={
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0,
                    },
                    "mappings": {
                        "properties": {
                            "@timestamp": {"type": "date"},
                            "message": {"type": "text"},
                            "severity": {"type": "keyword"},
                        }
                    },
                },
            )

            assert result["acknowledged"] is True

            # Verify index exists
            exists = await es_client.indices.exists(index=test_index_name)
            assert exists is True

        finally:
            await es_client.indices.delete(index=test_index_name, ignore=[404])

    async def test_delete_index(self, es_client, test_index_name):
        """Test deleting an index."""
        # Create index first
        await es_client.indices.create(index=test_index_name)

        # Delete it
        result = await es_client.indices.delete(index=test_index_name)

        assert result["acknowledged"] is True

        # Verify deleted
        exists = await es_client.indices.exists(index=test_index_name)
        assert exists is False

    async def test_get_mapping(self, es_client, test_index_name):
        """Test getting index mappings."""
        try:
            # Create index with mappings
            await es_client.indices.create(
                index=test_index_name,
                body={
                    "mappings": {
                        "properties": {
                            "host": {
                                "properties": {
                                    "name": {"type": "keyword"},
                                    "ip": {"type": "ip"},
                                }
                            },
                            "event_type": {"type": "keyword"},
                        }
                    }
                },
            )

            # Get mapping
            mapping = await es_client.indices.get_mapping(index=test_index_name)

            assert test_index_name in mapping
            assert "mappings" in mapping[test_index_name]
            assert "properties" in mapping[test_index_name]["mappings"]

        finally:
            await es_client.indices.delete(index=test_index_name, ignore=[404])


class TestElasticsearchIndexTemplates:
    """Tests for index templates."""

    async def test_create_index_template(self, es_client, elasticsearch_config):
        """Test creating an index template."""
        template_name = f"{elasticsearch_config['index_prefix']}-test-template"

        try:
            result = await es_client.indices.put_index_template(
                name=template_name,
                body={
                    "index_patterns": [f"{elasticsearch_config['index_prefix']}-events-*"],
                    "template": {
                        "settings": {
                            "number_of_shards": 1,
                        },
                        "mappings": {
                            "properties": {
                                "@timestamp": {"type": "date"},
                            }
                        },
                    },
                },
            )

            assert result["acknowledged"] is True

        finally:
            await es_client.indices.delete_index_template(
                name=template_name, ignore=[404]
            )

    async def test_list_index_templates(self, es_client, elasticsearch_config):
        """Test listing index templates."""
        templates = await es_client.indices.get_index_template()

        assert "index_templates" in templates
        assert isinstance(templates["index_templates"], list)


class TestElasticsearchDocumentOperations:
    """Tests for document operations."""

    async def test_index_document(self, es_client, test_index_name):
        """Test indexing a document."""
        try:
            # Create index
            await es_client.indices.create(index=test_index_name)

            # Index document
            doc = {
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Test event",
                "severity": "info",
                "host": {"name": "test-host"},
            }

            result = await es_client.index(
                index=test_index_name,
                body=doc,
                refresh=True,
            )

            assert result["result"] in ["created", "updated"]
            assert "_id" in result

        finally:
            await es_client.indices.delete(index=test_index_name, ignore=[404])

    async def test_bulk_index(self, es_client, test_index_name):
        """Test bulk indexing documents."""
        try:
            # Create index
            await es_client.indices.create(index=test_index_name)

            # Prepare bulk operations
            operations = []
            for i in range(10):
                operations.append({"index": {"_index": test_index_name}})
                operations.append({
                    "@timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": f"Test event {i}",
                    "sequence": i,
                })

            result = await es_client.bulk(body=operations, refresh=True)

            assert result["errors"] is False
            assert len(result["items"]) == 10

        finally:
            await es_client.indices.delete(index=test_index_name, ignore=[404])

    async def test_get_document(self, es_client, test_index_name):
        """Test getting a document by ID."""
        try:
            # Create index and document
            await es_client.indices.create(index=test_index_name)

            index_result = await es_client.index(
                index=test_index_name,
                body={"message": "Test document"},
                refresh=True,
            )

            doc_id = index_result["_id"]

            # Get document
            doc = await es_client.get(index=test_index_name, id=doc_id)

            assert doc["found"] is True
            assert doc["_source"]["message"] == "Test document"

        finally:
            await es_client.indices.delete(index=test_index_name, ignore=[404])

    async def test_delete_document(self, es_client, test_index_name):
        """Test deleting a document."""
        try:
            # Create index and document
            await es_client.indices.create(index=test_index_name)

            index_result = await es_client.index(
                index=test_index_name,
                body={"message": "Document to delete"},
                refresh=True,
            )

            doc_id = index_result["_id"]

            # Delete document
            result = await es_client.delete(
                index=test_index_name,
                id=doc_id,
                refresh=True,
            )

            assert result["result"] == "deleted"

        finally:
            await es_client.indices.delete(index=test_index_name, ignore=[404])


class TestElasticsearchSearch:
    """Tests for search operations."""

    async def test_simple_search(self, es_client, test_index_name):
        """Test simple search query."""
        try:
            # Create index with documents
            await es_client.indices.create(
                index=test_index_name,
                body={
                    "mappings": {
                        "properties": {
                            "@timestamp": {"type": "date"},
                            "message": {"type": "text"},
                            "severity": {"type": "keyword"},
                        }
                    }
                },
            )

            # Add test documents
            docs = [
                {"@timestamp": "2024-01-20T10:00:00Z", "message": "Error occurred", "severity": "error"},
                {"@timestamp": "2024-01-20T10:01:00Z", "message": "Warning detected", "severity": "warning"},
                {"@timestamp": "2024-01-20T10:02:00Z", "message": "Info message", "severity": "info"},
            ]

            for doc in docs:
                await es_client.index(index=test_index_name, body=doc)

            await es_client.indices.refresh(index=test_index_name)

            # Search
            result = await es_client.search(
                index=test_index_name,
                body={"query": {"match_all": {}}},
            )

            assert result["hits"]["total"]["value"] == 3

        finally:
            await es_client.indices.delete(index=test_index_name, ignore=[404])

    async def test_term_query(self, es_client, test_index_name):
        """Test term query."""
        try:
            # Create index with documents
            await es_client.indices.create(
                index=test_index_name,
                body={
                    "mappings": {
                        "properties": {
                            "severity": {"type": "keyword"},
                        }
                    }
                },
            )

            # Add documents
            await es_client.index(
                index=test_index_name,
                body={"severity": "error"},
                refresh=True,
            )
            await es_client.index(
                index=test_index_name,
                body={"severity": "warning"},
                refresh=True,
            )

            # Search with term query
            result = await es_client.search(
                index=test_index_name,
                body={"query": {"term": {"severity": "error"}}},
            )

            assert result["hits"]["total"]["value"] == 1
            assert result["hits"]["hits"][0]["_source"]["severity"] == "error"

        finally:
            await es_client.indices.delete(index=test_index_name, ignore=[404])

    async def test_range_query(self, es_client, test_index_name):
        """Test range query."""
        try:
            # Create index with documents
            await es_client.indices.create(
                index=test_index_name,
                body={
                    "mappings": {
                        "properties": {
                            "@timestamp": {"type": "date"},
                        }
                    }
                },
            )

            # Add documents
            await es_client.index(
                index=test_index_name,
                body={"@timestamp": "2024-01-20T10:00:00Z"},
                refresh=True,
            )
            await es_client.index(
                index=test_index_name,
                body={"@timestamp": "2024-01-21T10:00:00Z"},
                refresh=True,
            )

            # Search with range
            result = await es_client.search(
                index=test_index_name,
                body={
                    "query": {
                        "range": {
                            "@timestamp": {
                                "gte": "2024-01-21T00:00:00Z",
                            }
                        }
                    }
                },
            )

            assert result["hits"]["total"]["value"] == 1

        finally:
            await es_client.indices.delete(index=test_index_name, ignore=[404])

    async def test_aggregations(self, es_client, test_index_name):
        """Test aggregation queries."""
        try:
            # Create index with documents
            await es_client.indices.create(
                index=test_index_name,
                body={
                    "mappings": {
                        "properties": {
                            "severity": {"type": "keyword"},
                            "count": {"type": "integer"},
                        }
                    }
                },
            )

            # Add documents
            for severity in ["error", "error", "warning", "info", "info", "info"]:
                await es_client.index(
                    index=test_index_name,
                    body={"severity": severity, "count": 1},
                )

            await es_client.indices.refresh(index=test_index_name)

            # Aggregation query
            result = await es_client.search(
                index=test_index_name,
                body={
                    "size": 0,
                    "aggs": {
                        "by_severity": {
                            "terms": {"field": "severity"}
                        }
                    },
                },
            )

            assert "aggregations" in result
            assert "by_severity" in result["aggregations"]

            buckets = result["aggregations"]["by_severity"]["buckets"]
            severity_counts = {b["key"]: b["doc_count"] for b in buckets}

            assert severity_counts.get("info") == 3
            assert severity_counts.get("error") == 2
            assert severity_counts.get("warning") == 1

        finally:
            await es_client.indices.delete(index=test_index_name, ignore=[404])
