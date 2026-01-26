"""Celery task definitions for Eleanor.

This module provides the Celery application factory and task definitions
for asynchronous processing of parsing, enrichment, and indexing operations.
"""

from app.tasks.celery_app import celery_app

__all__ = ["celery_app"]
