from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas import (
    AudioIngestionResponse,
    CameraReading,
    ImageIngestionResponse,
    Observation,
    ObservationCandidate,
    TextReport,
    VideoIngestionResponse,
)
from app.infrastructure.neo4j.client import Neo4jClient, get_neo4j_client
from app.api.routers.observations import get_observation_service
from app.infrastructure.crusoe.client import CrusoeClient, CrusoeError
from app.inference.media import MediaService, MediaTooLargeError, MediaValidationError
from app.inference.agents import (
    AudioObservationAgent,
    ImageObservationAgent,
    TextObservationAgent,
    VideoObservationAgent,
)
from app.repositories.clinics import get_clinic, list_clinic_ids
from app.services.observation_service import ObservationService, direct_event
from app.services.recommendation_service import get_agent_recommendation


router = APIRouter(prefix="/ingestion", tags=["ingestion"])

# An extraction returns the validated event, its token usage, and extra response fields.
Extraction = tuple[ObservationCandidate, dict[str, int] | None, dict[str, Any]]


def get_crusoe_client(settings: Settings = Depends(get_settings)) -> CrusoeClient:
    if not settings.crusoe_api_key:
        raise HTTPException(
            status_code=503, detail="Crusoe inference is not configured."
        )
    return CrusoeClient(settings)


def _media(settings: Settings) -> MediaService:
    return MediaService(
        max_image_bytes=settings.max_image_upload_bytes,
        max_audio_bytes=settings.max_audio_upload_bytes,
        max_video_bytes=settings.max_video_upload_bytes,
        max_video_seconds=settings.max_video_duration_seconds,
        video_frames=settings.video_sample_frames,
    )


def _known_clinic_ids(graph: Neo4jClient, clinic_hint: str | None) -> list[str]:
    known_ids = list_clinic_ids(graph)
    if clinic_hint and clinic_hint not in known_ids:
        raise HTTPException(status_code=400, detail="Unknown clinic hint")
    return known_ids


async def _ingest(
    extract: Callable[[], Awaitable[Extraction]],
    graph: Neo4jClient,
    observations: ObservationService,
) -> dict[str, Any]:
    """Shared pipeline: extract, persist the observation, attach refreshed state."""
    try:
        event, token_usage, extra = await extract()
        observation = observations.process(event, token_usage=token_usage)
    except MediaTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except MediaValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CrusoeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail="Crusoe returned an invalid observation."
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    applied = observation.status == "applied"
    clinic_id = observation.event.clinic_id
    return {
        **extra,
        "observation": observation,
        "clinic": get_clinic(graph, clinic_id) if applied else None,
        "recommendation": get_agent_recommendation(graph, clinic_id) if applied else None,
    }


@router.post("/image", response_model=ImageIngestionResponse)
async def ingest_image(
    file: UploadFile = File(...),
    clinic_hint: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    graph: Neo4jClient = Depends(get_neo4j_client),
    crusoe: CrusoeClient = Depends(get_crusoe_client),
    observations: ObservationService = Depends(get_observation_service),
):
    data = await file.read(settings.max_image_upload_bytes + 1)

    async def extract() -> Extraction:
        data_url = _media(settings).prepare_image(data, file.content_type or "")
        known_ids = _known_clinic_ids(graph, clinic_hint)
        result = await ImageObservationAgent(crusoe, settings).extract(
            data_url, known_ids, clinic_hint
        )
        return result.event, result.metadata.token_usage, {}

    return await _ingest(extract, graph, observations)


@router.post("/audio", response_model=AudioIngestionResponse)
async def ingest_audio(
    file: UploadFile = File(...),
    clinic_hint: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    graph: Neo4jClient = Depends(get_neo4j_client),
    crusoe: CrusoeClient = Depends(get_crusoe_client),
    observations: ObservationService = Depends(get_observation_service),
):
    data = await file.read(settings.max_audio_upload_bytes + 1)

    async def extract() -> Extraction:
        data_url = _media(settings).prepare_audio(data, file.content_type or "")
        known_ids = _known_clinic_ids(graph, clinic_hint)
        result = await AudioObservationAgent(crusoe, settings).extract(
            data_url, known_ids, clinic_hint
        )
        return (
            result.extraction.event,
            result.metadata.token_usage,
            {"transcript": result.extraction.transcript},
        )

    return await _ingest(extract, graph, observations)


@router.post("/video", response_model=VideoIngestionResponse)
async def ingest_video(
    file: UploadFile = File(...),
    clinic_hint: str | None = Form(default=None),
    settings: Settings = Depends(get_settings),
    graph: Neo4jClient = Depends(get_neo4j_client),
    crusoe: CrusoeClient = Depends(get_crusoe_client),
    observations: ObservationService = Depends(get_observation_service),
):
    data = await file.read(settings.max_video_upload_bytes + 1)

    async def extract() -> Extraction:
        sheet_url, frames, duration = _media(settings).prepare_video(
            data, file.content_type or ""
        )
        known_ids = _known_clinic_ids(graph, clinic_hint)
        result = await VideoObservationAgent(crusoe, settings).extract(
            sheet_url, known_ids, clinic_hint
        )
        return (
            result.event,
            result.metadata.token_usage,
            {"sampled_frames": frames, "duration_seconds": duration},
        )

    return await _ingest(extract, graph, observations)


@router.post("/text", response_model=ImageIngestionResponse)
async def ingest_text(
    report: TextReport,
    settings: Settings = Depends(get_settings),
    graph: Neo4jClient = Depends(get_neo4j_client),
    crusoe: CrusoeClient = Depends(get_crusoe_client),
    observations: ObservationService = Depends(get_observation_service),
):
    if len(report.text) > settings.max_text_report_chars:
        raise HTTPException(status_code=413, detail="Report text is too long.")

    async def extract() -> Extraction:
        known_ids = _known_clinic_ids(graph, report.clinic_hint)
        result = await TextObservationAgent(crusoe, settings).extract(
            report.text, report.channel, known_ids, report.clinic_hint
        )
        return result.event, result.metadata.token_usage, {}

    return await _ingest(extract, graph, observations)


@router.post("/camera", response_model=Observation)
def ingest_camera_reading(
    reading: CameraReading,
    observations: ObservationService = Depends(get_observation_service),
):
    """People count pushed by an edge camera counter; no paid inference involved."""
    event = direct_event(
        reading.clinic_id, "people_waiting", reading.people_count,
        source_type="camera", model_id=f"camera:{reading.camera_id}",
        confidence=reading.confidence,
        evidence_summary=f"Camera {reading.camera_id} counted {reading.people_count} people waiting.",
    )
    try:
        return observations.process(event)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
