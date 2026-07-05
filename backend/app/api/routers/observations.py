from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.schemas import Observation
from app.infrastructure.neo4j.client import Neo4jClient, get_neo4j_client
from app.repositories.observations import Neo4jObservationRepository
from app.services.observation_service import ObservationService


router = APIRouter(prefix="/observations", tags=["observations"])


def get_observation_service(
    client: Neo4jClient = Depends(get_neo4j_client),
    settings: Settings = Depends(get_settings),
) -> ObservationService:
    return ObservationService(
        Neo4jObservationRepository(client), settings.observation_auto_apply_confidence
    )


@router.get("", response_model=list[Observation])
def list_observations(
    status: Literal["pending_review", "applied", "rejected", "failed"] | None = None,
    clinic_id: str | None = None,
    source_type: Literal["image", "audio", "manual"] | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    service: ObservationService = Depends(get_observation_service),
):
    return service.store.list(
        status=status, clinic_id=clinic_id, source_type=source_type, limit=limit
    )


@router.get("/{observation_id}", response_model=Observation)
def get_observation(
    observation_id: str,
    service: ObservationService = Depends(get_observation_service),
):
    result = service.store.get(observation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Observation not found")
    return result


@router.post("/{observation_id}/apply", response_model=Observation)
def apply_observation(
    observation_id: str,
    service: ObservationService = Depends(get_observation_service),
):
    try:
        return service.apply(observation_id)
    except ValueError as exc:
        status = 404 if str(exc) == "Observation not found" else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/{observation_id}/reject", response_model=Observation)
def reject_observation(
    observation_id: str,
    service: ObservationService = Depends(get_observation_service),
):
    try:
        return service.reject(observation_id)
    except ValueError as exc:
        status = 404 if str(exc) == "Observation not found" else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc
