from app.services.situation_service import calculate_trends, snapshot_global_status


def test_deterministic_trends_use_audit_values_and_transfer_timestamps():
    observations = [
        {
            "id": "obs-q",
            "event_type": "QUEUE_COUNT_UPDATED",
            "clinic_id": "clinic-b",
            "previous_value": 80,
            "new_value": 96,
            "observed_at": "2026-07-05T09:00:00+00:00",
        },
        {
            "id": "obs-k",
            "event_type": "TEST_KITS_UPDATED",
            "clinic_id": "clinic-b",
            "previous_value": 35,
            "new_value": 20,
            "observed_at": "2026-07-05T09:30:00+00:00",
            "previous_risk_level": "high",
            "new_risk_level": "critical",
        },
    ]
    transfers = [
        {
            "id": "transfer-1",
            "status": "ongoing",
            "target_clinic_id": "clinic-b",
            "created_at": "2026-07-05T09:45:00+00:00",
        }
    ]
    trends = calculate_trends(observations, transfers)
    assert "clinic-b queue increased from 80 to 96" in trends
    assert "clinic-b kits decreased from 35 to 20" in trends
    assert "clinic-b risk changed from high to critical" in trends
    assert "active transfer transfer-1 started for clinic-b" in trends


def test_snapshot_status_is_derived_from_current_risk_counts():
    assert snapshot_global_status([{"risk_level": "critical"}]) == "critical"
    assert snapshot_global_status([{"risk_level": "high"}]) == "degrading"
    assert snapshot_global_status([{"risk_level": "medium"}]) == "watch"
    assert snapshot_global_status([{"risk_level": "normal"}]) == "stable"


class FakeResult(list):
    pass


class FakeTx:
    def run(self, query, **kwargs):
        if "MATCH (c:Clinic)" in query and "RETURN c ORDER BY" in query:
            return FakeResult([{"c": {"id": "clinic-b", "name": "B", "risk_level": "high", "test_kits_available": 20, "people_waiting": 96, "nurses_available": 2, "threshold_min_kits": 50, "testing_capacity_per_hour": 24, "queue_delay_hours": 4.0, "operations_remaining_hours": 0.83}}])
        if "MATCH (w:Warehouse)-[r:CAN_SUPPLY]" in query:
            return FakeResult([{"w": {"id": "warehouse-w1", "name": "W1", "test_kits_stock": 100}, "target_ids": ["clinic-b"]}])
        if "MATCH (t:Transfer)" in query:
            return FakeResult([])
        if "MATCH (o:Observation)" in query:
            return FakeResult([{"o": {"id": "obs-1", "event_type": "TEST_KITS_UPDATED", "clinic_id": "clinic-b", "previous_value": 35, "new_value": 20, "observed_at": "2026-07-05T09:00:00+00:00", "created_at": "2026-07-05T09:00:00+00:00", "status": "applied"}}])
        raise AssertionError(query)


class FakeClient:
    def read(self, work, **kwargs):
        return work(FakeTx(), **kwargs)


def test_snapshot_contains_bounded_graph_facts_and_observation_ids():
    from app.services.situation_service import SituationService

    snapshot = SituationService(FakeClient()).build_snapshot(24)
    assert snapshot["window_hours"] == 24
    assert snapshot["clinics"][0]["id"] == "clinic-b"
    assert snapshot["alerts"][0]["clinic_id"] == "clinic-b"
    assert snapshot["recent_observations"][0]["id"] == "obs-1"
    assert snapshot["source_observation_ids"] == ["obs-1"]
    assert "clinic-b kits decreased from 35 to 20" in snapshot["deterministic_trends"]
