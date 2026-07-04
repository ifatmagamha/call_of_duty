from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.neo4j_client import neo4j_client
from app.routes import admin, clinics, graph, transfers, warehouses

settings = get_settings()

app = FastAPI(
    title="Ebola Test Kit Resupply Platform API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(clinics.router)
app.include_router(graph.router)
app.include_router(transfers.router)
app.include_router(warehouses.router)


@app.get("/health")
def health():
    neo4j_client.verify_connectivity()
    return {"status": "ok", "neo4j": "connected"}


@app.on_event("shutdown")
def shutdown_event():
    neo4j_client.close()
