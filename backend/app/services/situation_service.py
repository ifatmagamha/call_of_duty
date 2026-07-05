from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.repositories.situation import SituationRepository


TREND_LABELS = {
    "QUEUE_COUNT_UPDATED": "queue",
    "TEST_KITS_UPDATED": "kits",
    "NURSES_AVAILABLE_UPDATED": "nurses",
}


def calculate_trends(
    observations: list[dict[str, Any]], transfers: list[dict[str, Any]]
) -> list[str]:
    trends: list[str] = []
    for observation in observations:
        label = TREND_LABELS.get(observation.get("event_type"))
        previous = observation.get("previous_value")
        current = observation.get("new_value")
        if label is None or previous is None or current is None or previous == current:
            continue
        direction = "increased" if current > previous else "decreased"
        trends.append(
            f"{observation['clinic_id']} {label} {direction} from {previous} to {current}"
        )
        previous_risk = observation.get("previous_risk_level")
        new_risk = observation.get("new_risk_level")
        if previous_risk and new_risk and previous_risk != new_risk:
            trends.append(
                f"{observation['clinic_id']} risk changed from {previous_risk} to {new_risk}"
            )
    for transfer in transfers:
        if transfer.get("status") == "ongoing":
            trends.append(
                "active transfer "
                f"{transfer['id']} started for {transfer['target_clinic_id']}"
            )
    return trends


def snapshot_global_status(clinics: list[dict[str, Any]]) -> str:
    risks = {clinic.get("risk_level") for clinic in clinics}
    if "critical" in risks:
        return "critical"
    if "high" in risks:
        return "degrading"
    if "medium" in risks:
        return "watch"
    return "stable"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "iso_format"):
        return value.iso_format()
    return value


class SituationService:
    def __init__(self, client=None, repository=None):
        self.repository = repository or SituationRepository(client)

    def build_snapshot(self, window_hours: int = 24) -> dict[str, Any]:
        if not 1 <= window_hours <= 168:
            raise ValueError("window_hours must be between 1 and 168")
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()

        clinics, warehouses, transfers, observations = self.repository.load(cutoff)
        alerts = []
        for clinic in clinics:
            if clinic.get("risk_level") not in {"high", "critical"}:
                continue
            alerts.append(
                {
                    "clinic_id": clinic["id"],
                    "risk_level": clinic["risk_level"],
                    "operations_remaining_hours": clinic.get(
                        "operations_remaining_hours"
                    ),
                    "reason": f"{clinic['risk_level']} deterministic risk",
                }
            )
        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_hours": window_hours,
            "global_status": snapshot_global_status(clinics),
            "clinics": clinics,
            "warehouses": warehouses,
            "active_or_recent_transfers": transfers,
            "alerts": alerts,
            "recent_observations": observations,
            "deterministic_trends": calculate_trends(observations, transfers),
            "source_observation_ids": [item["id"] for item in observations],
        }
        return _json_safe(snapshot)
