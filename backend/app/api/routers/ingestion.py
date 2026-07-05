from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas import AudioIngestionResponse, ImageIngestionResponse
from app.infrastructure.neo4j.client import Neo4jClient, get_neo4j_client
from app.api.routers.observations import get_observation_service
from app.infrastructure.crusoe.client import CrusoeClient, CrusoeError
from app.inference.media import MediaService, MediaValidationError
from app.inference.agents import AudioObservationAgent, ImageObservationAgent
from app.services.observation_service import ObservationService
from app.services.recommendation_service import get_agent_recommendation


router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def get_crusoe_client(settings: Settings = Depends(get_settings)) -> CrusoeClient:
    if not settings.crusoe_api_key:
        raise HTTPException(
            status_code=503, detail="Crusoe inference is not configured."
        )
    return CrusoeClient(settings)


def _clinic_ids(client: Neo4jClient) -> list[str]:
    def work(tx):
        return [record["id"] for record in tx.run("MATCH (c:Clinic) RETURN c.id AS id")]

    return client.read(work)


def _clinic(client: Neo4jClient, clinic_id: str):
    def work(tx):
        record = tx.run(
            "MATCH (c:Clinic {id: $clinic_id}) RETURN c", clinic_id=clinic_id
        ).single()
        return dict(record["c"]) if record else None

    return client.read(work)


def _raise_media(exc: MediaValidationError):
    status = 413 if "size limit" in str(exc) else 400
    raise HTTPException(status_code=status, detail=str(exc)) from exc


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
    try:
        data_url = MediaService(
            max_image_bytes=settings.max_image_upload_bytes,
            max_audio_bytes=settings.max_audio_upload_bytes,
        ).prepare_image(data, file.content_type or "")
        known_ids = _clinic_ids(graph)
        if clinic_hint and clinic_hint not in known_ids:
            raise HTTPException(status_code=400, detail="Unknown clinic hint")
        result = await ImageObservationAgent(crusoe, settings).extract(
            data_url, known_ids, clinic_hint
        )
        observation = observations.process(
            result.event, token_usage=result.metadata.token_usage
        )
    except MediaValidationError as exc:
        _raise_media(exc)
    except CrusoeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail="Crusoe returned an invalid observation."
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    clinic = _clinic(graph, observation.event.clinic_id) if observation.status == "applied" else None
    recommendation = (
        get_agent_recommendation(graph, observation.event.clinic_id)
        if observation.status == "applied"
        else None
    )
    return ImageIngestionResponse(
        observation=observation, clinic=clinic, recommendation=recommendation
    )


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
    try:
        data_url = MediaService(
            max_image_bytes=settings.max_image_upload_bytes,
            max_audio_bytes=settings.max_audio_upload_bytes,
        ).prepare_audio(data, file.content_type or "")
        known_ids = _clinic_ids(graph)
        if clinic_hint and clinic_hint not in known_ids:
            raise HTTPException(status_code=400, detail="Unknown clinic hint")
        result = await AudioObservationAgent(crusoe, settings).extract(
            data_url, known_ids, clinic_hint
        )
        observation = observations.process(
            result.extraction.event, token_usage=result.metadata.token_usage
        )
    except MediaValidationError as exc:
        _raise_media(exc)
    except CrusoeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail="Crusoe returned an invalid observation."
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    clinic = _clinic(graph, observation.event.clinic_id) if observation.status == "applied" else None
    recommendation = (
        get_agent_recommendation(graph, observation.event.clinic_id)
        if observation.status == "applied"
        else None
    )
    return AudioIngestionResponse(
        transcript=result.extraction.transcript,
        observation=observation,
        clinic=clinic,
        recommendation=recommendation,
    )
