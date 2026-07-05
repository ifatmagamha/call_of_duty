from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.schemas import BriefingGenerateRequest, SituationBriefing
from app.infrastructure.neo4j.client import Neo4jClient, get_neo4j_client
from app.api.routers.ingestion import get_crusoe_client
from app.infrastructure.crusoe.client import CrusoeClient, CrusoeError
from app.inference.situation_agent import SituationAgent
from app.services.situation_service import SituationService


router = APIRouter(prefix="/briefings", tags=["briefings"])


@router.post("/generate", response_model=SituationBriefing)
async def generate_briefing(
    request: BriefingGenerateRequest,
    settings: Settings = Depends(get_settings),
    graph: Neo4jClient = Depends(get_neo4j_client),
    crusoe: CrusoeClient = Depends(get_crusoe_client),
):
    snapshot = SituationService(graph).build_snapshot(request.window_hours)
    try:
        briefing = await SituationAgent(crusoe, settings).generate(snapshot)
    except CrusoeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=502, detail="Crusoe returned an invalid situation briefing."
        ) from exc
    return briefing.model_copy(
        update={
            "generated_at": datetime.now(timezone.utc),
            "model_id": settings.crusoe_situation_model,
            "source_observation_ids": snapshot["source_observation_ids"],
        }
    )
