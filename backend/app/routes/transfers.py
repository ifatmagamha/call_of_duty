from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import Transfer, TransferCreate
from app.neo4j_client import Neo4jClient, get_neo4j_client
from app.services.transfer_engine import (
    TransferError,
    create_transfer,
    list_transfers,
)

router = APIRouter(tags=["transfers"])


@router.post("/clinics/{clinic_id}/transfers", response_model=Transfer)
def approve_transfer(
    clinic_id: str,
    transfer: TransferCreate,
    client: Neo4jClient = Depends(get_neo4j_client),
):
    try:
        return create_transfer(client, clinic_id, transfer.source_id)
    except TransferError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/transfers", response_model=list[Transfer])
def get_transfers(
    status: Optional[str] = Query(default="ongoing"),
    client: Neo4jClient = Depends(get_neo4j_client),
):
    return list_transfers(client, status)
