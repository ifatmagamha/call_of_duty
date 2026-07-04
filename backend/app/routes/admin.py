from fastapi import APIRouter, Depends

from app.neo4j_client import Neo4jClient, get_neo4j_client
from app.services.seed_data import seed_demo_graph

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset-demo-data")
def reset_demo_data(client: Neo4jClient = Depends(get_neo4j_client)):
    seeded = seed_demo_graph(client)
    return {"status": "ok", **seeded}
