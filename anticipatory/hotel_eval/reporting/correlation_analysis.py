"""
Multi-scenario correlation analysis.
Identifies patterns and correlations across evaluation runs.
"""

from typing import List, Dict, Optional
from collections import defaultdict, Counter
import statistics


def analyze_scenario_correlations(results: List[Dict]) -> Dict[str, any]:
    """
    Analyze correlations and patterns across multiple scenario results.
    
    Args:
        results: List of evaluation results from multiple scenarios
        
    Returns:
        Dictionary with correlation analysis:
        - common_failure_points: Stages where failures cluster
        - criteria_correlation: Which criteria tend to fail together
        - success_patterns: Common patterns in successful scenarios
        - failure_patterns: Common patterns in failed scenarios
    """
    if not results:
        return {}
    
    # Collect data
    successful_results = [r for r in results if r.get("booking_confirmed", False)]
    failed_results = [r for r in results if not r.get("booking_confirmed", False)]
    
    # Analysis
    common_failures = find_common_failure_points(failed_results)
    criteria_corr = find_criteria_correlations(results)
    success_patterns = identify_success_patterns(successful_results)
    failure_patterns = identify_failure_patterns(failed_results)
    stage_analysis = analyze_stage_distribution(results)
    
    return {
        "total_scenarios": len(results),
        "successful_count": len(successful_results),
        "failed_count": len(failed_results),
        "success_rate": len(successful_results) / len(results) * 100 if results else 0,
        "common_failure_points": common_failures,
        "criteria_correlations": criteria_corr,
        "success_patterns": success_patterns,
        "failure_patterns": failure_patterns,
        "stage_distribution": stage_analysis
    }


def find_common_failure_points(failed_results: List[Dict]) -> Dict[str, any]:
    """Find stages where conversations commonly fail."""
    if not failed_results:
        return {}
    
    failure_stages = Counter()
    failure_reasons = defaultdict(list)
    
    for result in failed_results:
        stage = result.get("conversation_stage", "UNKNOWN")
        failure_stages[stage] += 1
        
        # Collect failure reasons
        failed_at_desc = result.get("failed_at_description", "")
        if failed_at_desc:
            failure_reasons[stage].append(failed_at_desc)
    
    # Calculate percentages
    total_failures = len(failed_results)
    failure_percentages = {
        stage: (count / total_failures * 100)
        for stage, count in failure_stages.items()
    }
    
    return {
        "failure_stages": dict(failure_stages),
        "failure_percentages": failure_percentages,
        "most_common_stage": failure_stages.most_common(1)[0] if failure_stages else None,
        "failure_reasons_by_stage": dict(failure_reasons)
    }


def find_criteria_correlations(results: List[Dict]) -> Dict[str, any]:
    """Find which criteria tend to fail together."""
    if not results:
        return {}
    
    # Collect criteria results
    all_criteria = set()
    criteria_results = []
    
    for result in results:
        criteria = result.get("criteria_results", {})
        all_criteria.update(criteria.keys())
        criteria_results.append(criteria)
    
    # Find co-failures
    co_failures = defaultdict(int)
    
    for criteria in criteria_results:
        failed_criteria = [name for name, result in criteria.items() if result == "FAIL"]
        
        # Count co-occurrences
        for i, c1 in enumerate(failed_criteria):
            for c2 in failed_criteria[i+1:]:
                pair = tuple(sorted([c1, c2]))
                co_failures[pair] += 1
    
    # Sort by frequency
    sorted_co_failures = sorted(
        co_failures.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]  # Top 10
    
    return {
        "total_criteria": len(all_criteria),
        "co_failing_criteria": [
            {"criteria": list(pair), "count": count}
            for pair, count in sorted_co_failures
        ]
    }


def identify_success_patterns(successful_results: List[Dict]) -> Dict[str, any]:
    """Identify common patterns in successful bookings."""
    if not successful_results:
        return {}
    
    # Collect patterns
    booking_numbers_valid = sum(
        1 for r in successful_results
        if r.get("booking_number") and len(r.get("booking_number", "")) >= 3
    )
    
    avg_messages = statistics.mean(
        len(r.get("transcripts", [])) for r in successful_results
    ) if successful_results else 0
    
    common_final_stages = Counter(
        r.get("conversation_stage", "UNKNOWN") for r in successful_results
    )
    
    return {
        "total_successful": len(successful_results),
        "avg_message_count": round(avg_messages, 1),
        "booking_numbers_valid": booking_numbers_valid,
        "common_final_stages": dict(common_final_stages.most_common(3))
    }


def identify_failure_patterns(failed_results: List[Dict]) -> Dict[str, any]:
    """Identify common patterns in failed bookings."""
    if not failed_results:
        return {}
    
    avg_messages = statistics.mean(
        len(r.get("transcripts", [])) for r in failed_results
    ) if failed_results else 0
    
    # Most common failure reasons
    failure_reasons = [
        r.get("failed_at_description", "Unknown") for r in failed_results
    ]
    common_reasons = Counter(failure_reasons).most_common(5)
    
    return {
        "total_failed": len(failed_results),
        "avg_message_count": round(avg_messages, 1),
        "common_failure_reasons": [
            {"reason": reason, "count": count}
            for reason, count in common_reasons
        ]
    }


def analyze_stage_distribution(results: List[Dict]) -> Dict[str, any]:
    """Analyze distribution of final conversation stages."""
    if not results:
        return {}
    
    stage_counts = Counter(
        r.get("conversation_stage", "UNKNOWN") for r in results
    )
    
    total = len(results)
    stage_percentages = {
        stage: (count / total * 100)
        for stage, count in stage_counts.items()
    }
    
    return {
        "stage_counts": dict(stage_counts),
        "stage_percentages": stage_percentages,
        "most_common_stage": stage_counts.most_common(1)[0] if stage_counts else None
    }
