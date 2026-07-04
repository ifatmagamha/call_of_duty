from app.models import AgentRecommendation, ResupplyOption
from app.config import get_settings
from app.services.llm_agent import (
    build_llm_payload,
    generate_critical_llm_note,
    parse_llm_response_content,
)


def critical_clinic():
    return {
        "id": "clinic-x",
        "name": "Critical Clinic",
        "test_kits_available": 0,
        "people_waiting": 24,
        "nurses_available": 2,
        "threshold_min_kits": 50,
        "testing_capacity_per_hour": 24,
        "queue_delay_hours": 1.0,
        "operations_remaining_hours": 0.0,
        "risk_level": "critical",
    }


def normal_clinic():
    clinic = critical_clinic()
    clinic.update(
        {
            "test_kits_available": 120,
            "operations_remaining_hours": 5.0,
            "risk_level": "normal",
        }
    )
    return clinic


def warehouse_option():
    return ResupplyOption(
        source_id="warehouse-w1",
        source_name="Central Medical Warehouse",
        source_type="warehouse",
        available_stock=1000,
        delivery_time_minutes=25,
        road_status="open",
        recommended_transfer_quantity=96,
        supplier_remaining_stock_after_transfer=904,
        supplier_operations_remaining_after_transfer=None,
        is_safe_for_supplier=True,
        can_fully_supply=True,
        rank=1,
        reason="Can restore the clinic to four hours of operations.",
    )


def deterministic_recommendation():
    return AgentRecommendation(
        clinic_id="clinic-x",
        clinic="Critical Clinic",
        status="critical",
        reasoning=["Critical Clinic is critical risk."],
        recommendation=(
            "Resupply Critical Clinic from Central Medical Warehouse with 96 test kits."
        ),
        options=[warehouse_option()],
    )


def test_llm_payload_is_warehouse_only_and_neo4j_scoped():
    payload = build_llm_payload(
        critical_clinic(), [warehouse_option()], deterministic_recommendation()
    )

    assert "Warehouse-to-Clinic" in payload["data_contract"]
    assert "Clinic-to-clinic stock is not allowed" in payload["data_contract"]
    assert payload["warehouse_only_options"][0]["source_type"] == "warehouse"
    assert "latitude" not in payload["clinic"]


def test_llm_note_only_appears_for_critical_clinics(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")

    note = generate_critical_llm_note(
        normal_clinic(), [warehouse_option()], deterministic_recommendation()
    )

    assert note is None


def test_critical_llm_note_reports_when_key_missing(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()

    note = generate_critical_llm_note(
        critical_clinic(), [warehouse_option()], deterministic_recommendation()
    )

    assert note is not None
    assert note.available is False
    assert "Set LLM_API_KEY" in note.proposed_action
    assert note.reasoning_summary == []
    get_settings.cache_clear()


def test_parse_llm_response_accepts_fenced_json():
    parsed = parse_llm_response_content(
        """```json
{"reasoning_summary":["Uses warehouse route only."],"proposed_action":"Send kits from W1."}
```"""
    )

    assert parsed.reasoning_summary == ["Uses warehouse route only."]
    assert parsed.proposed_action == "Send kits from W1."


def test_parse_llm_response_accepts_string_reasoning_summary():
    parsed = parse_llm_response_content(
        '{"reasoning_summary":"Uses warehouse route only.","proposed_action":"Send kits from W1."}'
    )

    assert parsed.reasoning_summary == ["Uses warehouse route only."]


def test_parse_llm_response_accepts_object_proposed_action():
    parsed = parse_llm_response_content(
        (
            '{"reasoning_summary":"Uses warehouse route only.",'
            '"proposed_action":{"action":"Send kits from W1.","quantity":96}}'
        )
    )

    assert parsed.proposed_action == "Send kits from W1."
