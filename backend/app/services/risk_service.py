from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

TESTS_PER_NURSE_PER_HOUR = 12
LOW_OPERATIONS_THRESHOLD_HOURS = 2
HIGH_QUEUE_DELAY_THRESHOLD_HOURS = 3


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def round_hours(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(value, 2)


def calculate_testing_capacity_per_hour(nurses_available: int) -> int:
    return max(0, nurses_available) * TESTS_PER_NURSE_PER_HOUR


def calculate_queue_delay_hours(
    people_waiting: int, nurses_available: int
) -> Optional[float]:
    capacity = calculate_testing_capacity_per_hour(nurses_available)
    if capacity == 0:
        return None
    return round_hours(people_waiting / capacity)


def calculate_operations_remaining_hours(
    test_kits_available: int, nurses_available: int
) -> Optional[float]:
    capacity = calculate_testing_capacity_per_hour(nurses_available)
    if capacity == 0:
        return None
    return round_hours(test_kits_available / capacity)


def calculate_risk_level(
    *,
    test_kits_available: int,
    people_waiting: int,
    nurses_available: int,
    threshold_min_kits: int,
    operations_remaining_hours: Optional[float],
    queue_delay_hours: Optional[float],
) -> str:
    if test_kits_available == 0:
        return "critical"
    if nurses_available == 0 and people_waiting > 0:
        return "critical"
    if (
        operations_remaining_hours is not None
        and operations_remaining_hours < 1
    ):
        return "critical"
    if (
        operations_remaining_hours is not None
        and operations_remaining_hours < LOW_OPERATIONS_THRESHOLD_HOURS
    ):
        return "high"
    if test_kits_available < threshold_min_kits:
        return "high"
    if (
        queue_delay_hours is not None
        and queue_delay_hours >= HIGH_QUEUE_DELAY_THRESHOLD_HOURS
    ):
        return "medium"
    return "normal"


def compute_clinic_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    capacity = calculate_testing_capacity_per_hour(raw["nurses_available"])
    queue_delay = calculate_queue_delay_hours(
        raw["people_waiting"], raw["nurses_available"]
    )
    operations_remaining = calculate_operations_remaining_hours(
        raw["test_kits_available"], raw["nurses_available"]
    )
    risk_level = calculate_risk_level(
        test_kits_available=raw["test_kits_available"],
        people_waiting=raw["people_waiting"],
        nurses_available=raw["nurses_available"],
        threshold_min_kits=raw["threshold_min_kits"],
        operations_remaining_hours=operations_remaining,
        queue_delay_hours=queue_delay,
    )
    return {
        "testing_capacity_per_hour": capacity,
        "queue_delay_hours": queue_delay,
        "operations_remaining_hours": operations_remaining,
        "risk_level": risk_level,
        "last_computed_at": utc_now_iso(),
    }


def target_stock_for_four_hours(nurses_available: int) -> int:
    return calculate_testing_capacity_per_hour(nurses_available) * 4


def recommended_transfer_quantity(clinic: dict[str, Any]) -> int:
    return max(
        0,
        target_stock_for_four_hours(clinic["nurses_available"])
        - clinic["test_kits_available"],
    )
