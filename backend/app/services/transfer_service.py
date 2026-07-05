from __future__ import annotations

from typing import Optional
from uuid import uuid4

from app.schemas import Transfer
from app.infrastructure.neo4j.client import Neo4jClient
from app.services.recommendation_service import SAFE_ROAD_STATUSES
from app.services.risk_service import recommended_transfer_quantity, utc_now_iso


class TransferError(ValueError):
    pass


def _transfer_from_record(record) -> Transfer:
    transfer = dict(record["transfer"])
    source = dict(record["source"])
    target = dict(record["target"])
    return Transfer(
        id=transfer["id"],
        status=transfer["status"],
        source_id=source["id"],
        source_name=source["name"],
        target_clinic_id=target["id"],
        target_clinic_name=target["name"],
        quantity=transfer["quantity"],
        delivery_time_minutes=transfer["delivery_time_minutes"],
        road_status=transfer["road_status"],
        created_at=transfer["created_at"],
        updated_at=transfer["updated_at"],
    )


def create_transfer(
    client: Neo4jClient, clinic_id: str, source_id: str
) -> Transfer:
    def work(tx):
        existing = tx.run(
            """
            MATCH (transfer:Transfer {status: 'ongoing'})
                  -[:TRANSFER_TARGET]->(:Clinic {id: $clinic_id})
            RETURN count(transfer) AS ongoing_count
            """,
            clinic_id=clinic_id,
        ).single()
        if existing and existing["ongoing_count"] > 0:
            raise TransferError("An ongoing transfer already exists for this clinic.")

        record = tx.run(
            """
            MATCH (source:Warehouse {id: $source_id})
                  -[route:CAN_SUPPLY]->(target:Clinic {id: $clinic_id})
            WHERE route.road_status IN $road_statuses
            RETURN source, route, target
            """,
            clinic_id=clinic_id,
            source_id=source_id,
            road_statuses=sorted(SAFE_ROAD_STATUSES),
        ).single()
        if record is None:
            raise TransferError("No usable warehouse supply route found.")

        source = dict(record["source"])
        route = dict(record["route"])
        target = dict(record["target"])
        needed = recommended_transfer_quantity(target)
        if needed <= 0:
            raise TransferError("This clinic does not currently need a transfer.")

        available_stock = source["test_kits_stock"]
        route_limit = route.get("max_transfer_kits")
        route_cap = available_stock
        if route_limit is not None:
            route_cap = min(route_cap, route_limit)

        quantity = min(needed, route_cap)
        if quantity <= 0:
            raise TransferError("The selected warehouse has no available stock.")

        now = utc_now_iso()
        transfer_id = f"transfer-{uuid4()}"
        created = tx.run(
            """
            MATCH (source:Warehouse {id: $source_id})
                  -[route:CAN_SUPPLY]->(target:Clinic {id: $clinic_id})
            WHERE source.test_kits_stock >= $quantity
            SET source.test_kits_stock = source.test_kits_stock - $quantity,
                source.last_updated_at = $now
            CREATE (transfer:Transfer {
                id: $transfer_id,
                status: 'ongoing',
                quantity: $quantity,
                delivery_time_minutes: route.delivery_time_minutes,
                road_status: route.road_status,
                created_at: $now,
                updated_at: $now
            })
            CREATE (source)-[:TRANSFER_SOURCE]->(transfer)
            CREATE (transfer)-[:TRANSFER_TARGET]->(target)
            RETURN transfer, source, target
            """,
            clinic_id=clinic_id,
            source_id=source_id,
            quantity=quantity,
            transfer_id=transfer_id,
            now=now,
        ).single()
        if created is None:
            raise TransferError("Warehouse stock changed before the transfer could be reserved.")
        return _transfer_from_record(created)

    return client.write(work)


def list_transfers(
    client: Neo4jClient, status: Optional[str] = "ongoing"
) -> list[Transfer]:
    def work(tx):
        if status:
            result = tx.run(
                """
                MATCH (source:Warehouse)-[:TRANSFER_SOURCE]->(transfer:Transfer)
                      -[:TRANSFER_TARGET]->(target:Clinic)
                WHERE transfer.status = $status
                RETURN transfer, source, target
                ORDER BY transfer.created_at DESC
                """,
                status=status,
            )
        else:
            result = tx.run(
                """
                MATCH (source:Warehouse)-[:TRANSFER_SOURCE]->(transfer:Transfer)
                      -[:TRANSFER_TARGET]->(target:Clinic)
                RETURN transfer, source, target
                ORDER BY transfer.created_at DESC
                """
            )
        return [_transfer_from_record(record) for record in result]

    return client.read(work)
