from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.models import Warehouse, WarehouseUpdate
from app.neo4j_client import Neo4jClient, get_neo4j_client
from app.services.risk_engine import utc_now_iso

router = APIRouter(tags=["warehouses"])


def _warehouse_or_404(warehouse: dict[str, Any] | None) -> dict[str, Any]:
    if warehouse is None:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return warehouse


@router.get("/warehouses", response_model=list[Warehouse])
def list_warehouses(client: Neo4jClient = Depends(get_neo4j_client)):
    def work(tx):
        result = tx.run("MATCH (w:Warehouse) RETURN w ORDER BY w.name")
        return [dict(record["w"]) for record in result]

    return client.read(work)


@router.get("/warehouses/{warehouse_id}", response_model=Warehouse)
def get_warehouse(
    warehouse_id: str, client: Neo4jClient = Depends(get_neo4j_client)
):
    def work(tx):
        record = tx.run(
            "MATCH (w:Warehouse {id: $warehouse_id}) RETURN w",
            warehouse_id=warehouse_id,
        ).single()
        return dict(record["w"]) if record else None

    return _warehouse_or_404(client.read(work))


@router.patch("/warehouses/{warehouse_id}", response_model=Warehouse)
def update_warehouse(
    warehouse_id: str,
    update: WarehouseUpdate,
    client: Neo4jClient = Depends(get_neo4j_client),
):
    def work(tx):
        record = tx.run(
            """
            MATCH (w:Warehouse {id: $warehouse_id})
            SET w.test_kits_stock = $test_kits_stock,
                w.last_updated_at = $last_updated_at
            RETURN w
            """,
            warehouse_id=warehouse_id,
            test_kits_stock=update.test_kits_stock,
            last_updated_at=utc_now_iso(),
        ).single()
        return dict(record["w"]) if record else None

    return _warehouse_or_404(client.write(work))
