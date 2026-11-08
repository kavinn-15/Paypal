import re
import logging
from typing import List, Set, Union

logger = logging.getLogger("llm_validator")


def extract_numbers_from_text(text: str) -> List[float]:
    """
    Extracts all numbers and currency amounts from text.
    Handles formats like: $1,200, $1400.50, 14, 5%, 85.0
    """
    # Pattern matches integers and decimals, with optional commas and dollar signs
    pattern = r"\$?\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b%?"
    matches = re.findall(pattern, text)
    numbers = []

    for m in matches:
        cleaned = m.replace("$", "").replace("%", "").replace(",", "").strip()
        try:
            val = float(cleaned)
            # Exclude trivial dates like years 2024, 2025, 2026 or small day offsets if needed
            numbers.append(val)
        except ValueError:
            pass

    return numbers


def validate_llm_numbers(
    generated_text: str,
    allowed_numbers: List[Union[int, float]],
    tolerance: float = 0.05
) -> bool:
    """
    Validates that any numerical amounts cited in the LLM text match the computed values.
    Returns True if all numbers are authorized, False if an unauthorized or altered number is found.
    """
    extracted = extract_numbers_from_text(generated_text)
    allowed_set = [float(x) for x in allowed_numbers]

    # Common innocent numbers allowed (e.g. 1st, 2, 3 plans, 2026 year, 0, 100)
    innocent_numbers = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0, 12.0, 14.0, 24.0, 2024.0, 2025.0, 2026.0}

    for num in extracted:
        if num in innocent_numbers:
            continue

        # Check if number matches any allowed number within tolerance
        matched = False
        for allowed in allowed_set:
            if abs(num - allowed) <= tolerance:
                matched = True
                break
            # Also allow percentage conversions (e.g. 0.03 vs 3.0, or 0.85 vs 85.0)
            if abs(num - (allowed * 100)) <= tolerance or abs((num * 100) - allowed) <= tolerance:
                matched = True
                break

        if not matched:
            logger.warning(
                f"LLM Number Validation Failed! Detected unauthorized number '{num}' in text: '{generated_text[:120]}...'"
            )
            return False

    return True

