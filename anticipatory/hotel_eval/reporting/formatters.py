"""
Text formatting utilities for reports.
"""

from typing import List, Dict, Optional, Tuple

from ..booking import (
    CONVERSATION_STEPS,
    get_stage_progress as _get_stage_progress,
    get_failed_at_description as _get_failed_at_description,
)


def format_stage_progress(stage: str) -> str:
    """
    Format stage progress as a string like "5/15".

    Args:
        stage: The conversation stage name

    Returns:
        Formatted progress string
    """
    step_num, total_steps = _get_stage_progress(stage)
    return f"{step_num}/{total_steps}"


def format_error_description(
    success: Dict,
    transcripts: Optional[List[Dict[str, str]]] = None,
    error: str = ""
) -> str:
    """
    Format error description for a failed scenario.

    Args:
        success: Success results dict from scenario
        transcripts: Optional list of conversation transcripts
        error: Original error message if any

    Returns:
        Human-readable error description
    """
    is_passed = success.get("booking_confirmed", False)
    stage = success.get("conversation_stage", "UNKNOWN")

    if is_passed:
        return ""

    if error:
        return error

    # Check for invalid booking number first
    if success.get("invalid_booking_number"):
        invalid_value = success.get("invalid_booking_number_value", "unknown")
        return f"Agent provided invalid booking number: '{invalid_value}' (not a valid number format)"

    return _get_failed_at_description(stage, transcripts)


def format_transcript(transcripts: List[Dict[str, str]], max_length: int = 32000) -> str:
    """
    Format transcripts for CSV/text export.

    Args:
        transcripts: List of conversation transcripts
        max_length: Maximum output length before truncation

    Returns:
        Formatted transcript string
    """
    lines = []
    for i, t in enumerate(transcripts, 1):
        role = "CUSTOMER" if t["role"] == "customer" else "AGENT"
        lines.append(f"[{i}] {role}:\r\n{t['content']}")

    transcript = "\r\n\r\n".join(lines)

    if len(transcript) > max_length:
        transcript = transcript[:max_length] + "\r\n\r\n[... TRUNCATED ...]"

    return transcript


def format_run_summary(results: List[Dict]) -> Dict:
    """
    Calculate summary statistics for a run.

    Args:
        results: List of scenario results

    Returns:
        Dict with summary statistics
    """
    total = len(results)
    passed = sum(1 for r in results if r.get("success_results", {}).get("booking_confirmed", False))
    failed = total - passed
    success_rate = (passed / total * 100) if total > 0 else 0

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "success_rate": round(success_rate, 1),
    }
