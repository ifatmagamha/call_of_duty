from fastapi import APIRouter, Depends

from app.demo.seed import seed_demo_graph
from app.infrastructure.neo4j.client import Neo4jClient, get_neo4j_client

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset-demo-data")
def reset_demo_data(client: Neo4jClient = Depends(get_neo4j_client)):
    return {"status": "ok", **seed_demo_graph(client)}
