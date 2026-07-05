def test_new_backend_boundaries_are_importable():
    from app.api.routers import briefings, ingestion, observations
    from app.core.config import Settings
    from app.inference.model_router import ModelRouter
    from app.infrastructure.crusoe.client import CrusoeClient
    from app.infrastructure.neo4j.client import Neo4jClient
    from app.repositories.observations import Neo4jObservationRepository
    from app.repositories.situation import SituationRepository
    from app.schemas import Observation, SituationBriefing

    assert Settings and ModelRouter and CrusoeClient and Neo4jClient
    assert Neo4jObservationRepository and SituationRepository
    assert Observation and SituationBriefing
    assert briefings.router and ingestion.router and observations.router
