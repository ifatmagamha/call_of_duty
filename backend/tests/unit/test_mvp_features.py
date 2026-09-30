import os
import tempfile

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.routers.observations import get_observation_service
from app.core.config import Settings
from app.inference.media import MediaService, MediaValidationError
from app.main import app
from app.services.observation_service import ObservationService, direct_event
from app.services.timeline_service import observation_entry, transfer_entries
from tests.unit.test_observation_service import MemoryStore, candidate


CLINIC = {"id": "clinic-b", "name": "Lingwala"}


# --- review policy -------------------------------------------------------------

@pytest.mark.parametrize("source", ["text", "video"])
def test_numeric_text_and_video_events_always_wait_for_review(source):
    store = MemoryStore()
    result = ObservationService(store).process(candidate(confidence=0.99, source_type=source))
    assert result.status == "pending_review"
    assert store.applied == []


def test_text_status_report_still_auto_applies_because_it_mutates_nothing():
    store = MemoryStore()
    event = candidate("CLINIC_STATUS_REPORTED", confidence=0.95, source_type="text")
    assert ObservationService(store).process(event).status == "applied"


def test_direct_event_builds_allowlisted_camera_event():
    event = direct_event(
        "clinic-b", "people_waiting", 42, source_type="camera",
        model_id="camera:cam-1", evidence_summary="counted", confidence=0.97,
    )
    assert event.event_type == "QUEUE_COUNT_UPDATED"
    assert event.people_waiting == 42 and event.source_type == "camera"


# --- HTTP: camera readings and manual updates are audited observations -----------

@pytest.fixture
def api_store():
    store = MemoryStore()
    app.dependency_overrides[get_observation_service] = lambda: ObservationService(store)
    yield store
    app.dependency_overrides.clear()


def test_camera_reading_endpoint_auto_applies_confident_counts(api_store):
    response = TestClient(app).post(
        "/ingestion/camera",
        json={"clinic_id": "clinic-b", "camera_id": "cam-1", "people_count": 57},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "applied"
    assert body["event"]["source_type"] == "camera"
    assert body["event"]["people_waiting"] == 57


def test_camera_reading_below_threshold_waits_and_rejects_negative_counts(api_store):
    client = TestClient(app)
    low = client.post(
        "/ingestion/camera",
        json={"clinic_id": "clinic-b", "camera_id": "cam-1", "people_count": 5, "confidence": 0.4},
    )
    assert low.json()["status"] == "pending_review"
    bad = client.post(
        "/ingestion/camera",
        json={"clinic_id": "clinic-b", "camera_id": "cam-1", "people_count": -1},
    )
    assert bad.status_code == 422


def test_camera_reading_for_unknown_clinic_is_404():
    app.dependency_overrides[get_observation_service] = lambda: ObservationService(
        MemoryStore(clinic_exists=False)
    )
    try:
        response = TestClient(app).post(
            "/ingestion/camera",
            json={"clinic_id": "nope", "camera_id": "cam-1", "people_count": 3},
        )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


# --- timeline -----------------------------------------------------------------

def test_applied_observation_timeline_entry_shows_before_and_after():
    entry = observation_entry(
        {
            "id": "o1", "event_type": "QUEUE_COUNT_UPDATED", "status": "applied",
            "people_waiting": 120, "previous_value": 96, "created_at": "2026-01-01T10:00",
            "reviewed_at": "2026-01-01T10:01", "source_type": "camera",
            "evidence_summary": "Camera cam-1 counted 120 people waiting.",
        },
        CLINIC,
    )
    assert entry.title == "People waiting 96 → 120"
    assert entry.at == "2026-01-01T10:01"
    assert (entry.field, entry.value, entry.source_type) == ("people_waiting", 120, "camera")


def test_pending_observation_entry_has_no_plotted_value():
    entry = observation_entry(
        {
            "id": "o2", "event_type": "TEST_KITS_UPDATED", "status": "pending_review",
            "test_kits_available": 5, "created_at": "2026-01-01T10:00",
            "evidence_summary": "SMS", "source_type": "text",
        },
        CLINIC,
    )
    assert entry.title == "Test kits reported: 5"
    assert entry.value is None


def test_completed_transfer_yields_dispatch_and_delivery_entries():
    transfer = {
        "id": "t1", "status": "completed", "quantity": 61, "delivery_time_minutes": 25,
        "road_status": "open", "created_at": "2026-01-01T10:00",
        "updated_at": "2026-01-01T10:30", "completed_at": "2026-01-01T10:30",
    }
    entries = transfer_entries(transfer, {"name": "Central"}, CLINIC)
    assert [e.status for e in entries] == ["dispatched", "completed"]
    assert entries[1].at == "2026-01-01T10:30"


# --- video sampling -------------------------------------------------------------

def _mp4(seconds: float, fps: int = 10) -> bytes:
    handle, path = tempfile.mkstemp(suffix=".mp4")
    os.close(handle)
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 48))
    for index in range(int(seconds * fps)):
        writer.write(np.full((48, 64, 3), index % 255, dtype=np.uint8))
    writer.release()
    with open(path, "rb") as file:
        data = file.read()
    os.remove(path)
    return data


def test_video_is_sampled_into_one_jpeg_contact_sheet_without_leaving_files():
    before = set(os.listdir(tempfile.gettempdir()))
    url, frames, duration = MediaService().prepare_video(_mp4(3), "video/mp4")
    assert url.startswith("data:image/jpeg;base64,")
    assert frames == 6
    assert duration == pytest.approx(3, abs=0.2)
    leftovers = {f for f in set(os.listdir(tempfile.gettempdir())) - before if f.endswith(".mp4")}
    assert leftovers == set()


def test_video_rejects_wrong_type_corrupt_data_and_long_clips():
    service = MediaService(max_video_seconds=2)
    with pytest.raises(MediaValidationError, match="MP4"):
        service.prepare_video(b"x", "video/webm")
    with pytest.raises(MediaValidationError, match="valid video"):
        service.prepare_video(b"not a video", "video/mp4")
    with pytest.raises(MediaValidationError, match="exceeds"):
        service.prepare_video(_mp4(3), "video/mp4")


# --- configuration --------------------------------------------------------------

def test_blank_env_values_keep_defaults(tmp_path):
    env = tmp_path / ".env"
    env.write_text("NEO4J_URI=\nCRUSOE_API_KEY=k\n")
    settings = Settings(_env_file=env)
    assert settings.neo4j_uri == "bolt://localhost:7687"
    assert settings.crusoe_api_key == "k"
