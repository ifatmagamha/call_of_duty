from functools import lru_cache
import os

from pydantic import BaseModel
from dotenv import load_dotenv


class Settings(BaseModel):
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    api_cors_origins: list[str]


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    cors_origins = os.getenv(
        "API_CORS_ORIGINS",
        (
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:5174,http://127.0.0.1:5174"
        ),
    )
    return Settings(
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", "password"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.mistral.ai/v1"),
        llm_model=os.getenv("LLM_MODEL", "mistral-small-latest"),
        api_cors_origins=[
            origin.strip()
            for origin in cors_origins.split(",")
            if origin.strip()
        ],
    )
