from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import (
    AgentRecommendation,
    Alert,
    Clinic,
    ClinicUpdate,
    ResupplyOption,
    TimelineEntry,
)
from app.infrastructure.neo4j.client import Neo4jClient, get_neo4j_client
from app.api.routers.observations import get_observation_service
from app.repositories import clinics as clinic_repo
from app.services.observation_service import ObservationService, direct_event
from app.services.recommendation_service import (
    get_agent_recommendation,
    get_priority_actions,
    get_resupply_options,
)
from app.services.observation_service import FIELD_EVENTS
from app.services.risk_service import compute_clinic_metrics, utc_now_iso
from app.services.timeline_service import get_timeline

router = APIRouter(tags=["clinics"])


def _clinic_or_404(clinic: dict[str, Any] | None) -> dict[str, Any]:
    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return clinic


@router.get("/clinics", response_model=list[Clinic])
def list_clinics(client: Neo4jClient = Depends(get_neo4j_client)):
    return clinic_repo.list_clinics(client)


@router.get("/clinics/{clinic_id}", response_model=Clinic)
def get_clinic(
    clinic_id: str, client: Neo4jClient = Depends(get_neo4j_client)
):
    return _clinic_or_404(clinic_repo.get_clinic(client, clinic_id))


@router.patch("/clinics/{clinic_id}", response_model=Clinic)
def update_clinic(
    clinic_id: str,
    update: ClinicUpdate,
    client: Neo4jClient = Depends(get_neo4j_client),
    observations: ObservationService = Depends(get_observation_service),
):
    updates = update.model_dump(exclude_none=True)
    clinic = _clinic_or_404(clinic_repo.get_clinic(client, clinic_id))
    # Operational numbers go through the observation audit trail (timeline).
    for field in FIELD_EVENTS:
        if field in updates:
            observations.process(
                direct_event(
                    clinic_id, field, updates[field],
                    source_type="manual", model_id="operator",
                    evidence_summary="Manual update from the operations console.",
                )
            )
    # The threshold is configuration, not an observation: write it directly.
    threshold = updates.get("threshold_min_kits")
    if threshold is None:
        return clinic_repo.get_clinic(client, clinic_id)

    def work(tx):
        current = clinic_repo.fetch_clinic(tx, clinic_id)
        raw = {**current, "threshold_min_kits": threshold}
        props = {
            "threshold_min_kits": threshold,
            **compute_clinic_metrics(raw),
            "last_updated_at": utc_now_iso(),
        }
        record = tx.run(
            "MATCH (c:Clinic {id: $clinic_id}) SET c += $props RETURN c",
            clinic_id=clinic_id, props=props,
        ).single()
        return dict(record["c"])

    return client.write(work)


@router.get("/clinics/{clinic_id}/timeline", response_model=list[TimelineEntry])
def clinic_timeline(
    clinic_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    client: Neo4jClient = Depends(get_neo4j_client),
):
    return get_timeline(client, clinic_id, limit)


@router.get("/timeline", response_model=list[TimelineEntry])
def global_timeline(
    limit: int = Query(default=50, ge=1, le=200),
    client: Neo4jClient = Depends(get_neo4j_client),
):
    return get_timeline(client, None, limit)


@router.get("/actions", response_model=list[AgentRecommendation])
def priority_actions(client: Neo4jClient = Depends(get_neo4j_client)):
    return get_priority_actions(client)


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
    alerts = []
    for clinic in clinic_repo.list_alert_clinics(client):
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
                "operations_remaining_hours": clinic["operations_remaining_hours"],
                "queue_delay_hours": clinic["queue_delay_hours"],
                "reason": ", ".join(reasons),
            }
        )
    return alerts
