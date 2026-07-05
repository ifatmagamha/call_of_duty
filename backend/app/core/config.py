from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"
    crusoe_api_key: str = ""
    crusoe_base_url: str = "https://api.inference.crusoecloud.com/v1/"
    crusoe_image_model: str = "google/gemma-4-31b-it"
    crusoe_audio_model: str = "nvidia/Nemotron-3-Nano-Omni-Reasoning-30B-A3B"
    crusoe_situation_model: str = "moonshotai/Kimi-K2.6"
    crusoe_timeout_seconds: float = 60
    crusoe_max_retries: int = 2
    observation_auto_apply_confidence: float = 0.90
    max_image_upload_bytes: int = 10_485_760
    max_audio_upload_bytes: int = 26_214_400
    api_cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
