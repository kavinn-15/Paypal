import pytest
from backend.app.llm.validator import extract_numbers_from_text, validate_llm_numbers
from backend.app.llm.client import LLMService


def test_extract_numbers():
    text = "Starting with $1,800.00 balance, you will be short by $1,400 before Marcus on Nov 13. Risk: 85%."
    nums = extract_numbers_from_text(text)
    assert 1800.0 in nums
    assert 1400.0 in nums
    assert 85.0 in nums or 0.85 in nums


def test_validate_llm_numbers_success():
    text = "You will be short by $1,400.00 before your contractor payout on Friday, with a starting balance of $1,800."
    allowed = [1800.0, 1400.0]
    assert validate_llm_numbers(text, allowed) is True


def test_validate_llm_numbers_detects_hallucination():
    # LLM hallucinates an unauthorized number: $2,500 instead of $1,400
    text = "You will be short by $2,500.00 before your contractor payout on Friday."
    allowed = [1800.0, 1400.0]
    assert validate_llm_numbers(text, allowed) is False


def test_llm_service_template_fallback():
    service = LLMService()
    service.provider = "template"
    explanation = service.generate_driver_explanation(
        starting_balance=1800.0,
        shortfall_amount=1400.0,
        target_date_str="Friday, Nov 13",
        contractor_name="Marcus Sterling",
        top_client_name="Apex Design Studio",
        top_client_delay=14,
        p_shortfall=0.88
    )
    assert "$1,400.00" in explanation
    assert "Apex Design Studio" in explanation
    assert "Marcus Sterling" in explanation
    assert "88%" in explanation

