from pydantic import BaseModel, Field


class Neo4jDiagnostic(BaseModel):
    connected: bool
    database: str
    constraints: list[str] = Field(default_factory=list)
    required_constraints: list[str] = Field(default_factory=list)
    missing_constraints: list[str] = Field(default_factory=list)
    required_constraints_present: bool
    node_counts: dict[str, int] = Field(default_factory=dict)
    observation_links: int = 0
    error: str | None = None


class CrusoeDiagnostic(BaseModel):
    configured: bool
    required_model_ids: list[str] = Field(default_factory=list)
    accessible_model_ids: list[str] = Field(default_factory=list)
    missing_model_ids: list[str] = Field(default_factory=list)
    all_models_accessible: bool
    error: str | None = None
