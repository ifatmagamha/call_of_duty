from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.models import AgentRecommendation, Alert, Clinic, ClinicUpdate, ResupplyOption
from app.neo4j_client import Neo4jClient, get_neo4j_client
from app.services.recommendation_engine import (
    get_agent_recommendation,
    get_resupply_options,
)
from app.services.risk_engine import compute_clinic_metrics, utc_now_iso

router = APIRouter(tags=["clinics"])


def _clinic_or_404(clinic: dict[str, Any] | None) -> dict[str, Any]:
    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return clinic


@router.get("/clinics", response_model=list[Clinic])
def list_clinics(client: Neo4jClient = Depends(get_neo4j_client)):
    def work(tx):
        result = tx.run("MATCH (c:Clinic) RETURN c ORDER BY c.name")
        return [dict(record["c"]) for record in result]

    return client.read(work)


@router.get("/clinics/{clinic_id}", response_model=Clinic)
def get_clinic(
    clinic_id: str, client: Neo4jClient = Depends(get_neo4j_client)
):
    def work(tx):
        record = tx.run(
            "MATCH (c:Clinic {id: $clinic_id}) RETURN c", clinic_id=clinic_id
        ).single()
        return dict(record["c"]) if record else None

    return _clinic_or_404(client.read(work))


@router.patch("/clinics/{clinic_id}", response_model=Clinic)
def update_clinic(
    clinic_id: str,
    update: ClinicUpdate,
    client: Neo4jClient = Depends(get_neo4j_client),
):
    updates = update.model_dump(exclude_unset=True)

    def work(tx):
        record = tx.run(
            "MATCH (c:Clinic {id: $clinic_id}) RETURN c", clinic_id=clinic_id
        ).single()
        if record is None:
            return None
        current = dict(record["c"])
        raw = {**current, **updates}
        props = {
            **updates,
            **compute_clinic_metrics(raw),
            "last_updated_at": utc_now_iso(),
        }
        updated = tx.run(
            """
            MATCH (c:Clinic {id: $clinic_id})
            SET c += $props
            RETURN c
            """,
            clinic_id=clinic_id,
            props=props,
        ).single()
        return dict(updated["c"])

    return _clinic_or_404(client.write(work))


@router.get(
    "/clinics/{clinic_id}/resupply-options", response_model=list[ResupplyOption]
)
def resupply_options(
    clinic_id: str, client: Neo4jClient = Depends(get_neo4j_client)
):
    try:
        return get_resupply_options(client, clinic_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/clinics/{clinic_id}/agent-recommendation",
    response_model=AgentRecommendation,
)
def agent_recommendation(
    clinic_id: str, client: Neo4jClient = Depends(get_neo4j_client)
):
    try:
        return get_agent_recommendation(client, clinic_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/alerts", response_model=list[Alert])
def list_alerts(client: Neo4jClient = Depends(get_neo4j_client)):
    def work(tx):
        result = tx.run(
            """
            MATCH (c:Clinic)
            WHERE c.risk_level IN ['critical', 'high']
               OR c.operations_remaining_hours < 2
               OR c.test_kits_available < c.threshold_min_kits
            RETURN c
            ORDER BY
              CASE c.risk_level
                WHEN 'critical' THEN 0
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                ELSE 3
              END,
              c.operations_remaining_hours ASC
            """
        )
        alerts = []
        for record in result:
            clinic = dict(record["c"])
            reasons = []
            if clinic["risk_level"] in {"critical", "high"}:
                reasons.append(f"{clinic['risk_level']} risk")
            if (
                clinic["operations_remaining_hours"] is not None
                and clinic["operations_remaining_hours"] < 2
            ):
                reasons.append("less than 2 hours of operations remaining")
            if clinic["test_kits_available"] < clinic["threshold_min_kits"]:
                reasons.append("stock below minimum threshold")
            alerts.append(
                {
                    "clinic_id": clinic["id"],
                    "clinic": clinic["name"],
                    "risk_level": clinic["risk_level"],
                    "operations_remaining_hours": clinic[
                        "operations_remaining_hours"
                    ],
                    "queue_delay_hours": clinic["queue_delay_hours"],
                    "reason": ", ".join(reasons),
                }
            )
        return alerts

    return client.read(work)
