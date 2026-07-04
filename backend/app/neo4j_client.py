from __future__ import annotations

from collections.abc import Callable
from typing import Any

from neo4j import GraphDatabase

from .config import get_settings


class Neo4jClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self.driver.close()

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def read(self, work: Callable[..., Any], **kwargs: Any) -> Any:
        with self.driver.session() as session:
            return session.execute_read(work, **kwargs)

    def write(self, work: Callable[..., Any], **kwargs: Any) -> Any:
        with self.driver.session() as session:
            return session.execute_write(work, **kwargs)


neo4j_client = Neo4jClient()


def get_neo4j_client() -> Neo4jClient:
    return neo4j_client


def props(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "items"):
        return dict(value)
    return value
