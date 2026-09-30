from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import Transfer, TransferCreate
from app.infrastructure.neo4j.client import Neo4jClient, get_neo4j_client
from app.services.transfer_service import (
    TransferError,
    complete_transfer,
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


@router.post("/transfers/{transfer_id}/complete", response_model=Transfer)
def mark_transfer_delivered(
    transfer_id: str, client: Neo4jClient = Depends(get_neo4j_client)
):
    try:
        return complete_transfer(client, transfer_id)
    except TransferError as exc:
        status = 404 if str(exc) == "Transfer not found." else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc
