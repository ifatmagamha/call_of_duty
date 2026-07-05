import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.api.routers.ingestion import get_crusoe_client


def test_missing_crusoe_key_returns_service_unavailable_before_route_work():
    with pytest.raises(HTTPException) as exc_info:
        get_crusoe_client(Settings(_env_file=None))
    assert exc_info.value.status_code == 503
    assert "not configured" in exc_info.value.detail
