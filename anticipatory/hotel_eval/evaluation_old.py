"""
Evaluation runner - handles running multiple scenarios and generating reports.
"""

import asyncio
import json
import csv
import random
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path

from .config import DEFAULT_TIMEOUT
from .orchestrator import HotelBookingOrchestrator
from .results_tracker import update_results_excel, print_historical_summary

logger = logging.getLogger("eval-runner")


async def run_evaluation(
    scenarios_file: str,
    audio_dir: str = "audio",
    transcript_dir: str = "transcripts",
    results_dir: str = "results",
    count: Optional[int] = None,
    scenario_ids: Optional[List[str]] = None,
    text_mode: bool = False,
    provider: str = "gemini",
):
    """Run evaluation across multiple scenarios."""
    with open(scenarios_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_scenarios = data.get("scenarios", [])

    # Select scenarios to run
    if scenario_ids:
        scenarios = [s for s in all_scenarios if s.get("id") in scenario_ids]
        if not scenarios:
            raise ValueError(f"No scenarios found matching IDs: {scenario_ids}")
        logger.info(f"Running {len(scenarios)} specified scenarios")
    elif count is not None:
        if count > len(all_scenarios):
            logger.warning(f"Requested {count} scenarios but only {len(all_scenarios)} available")
            count = len(all_scenarios)
        scenarios = random.sample(all_scenarios, count)
        logger.info(f"Randomly selected {count} scenarios from {len(all_scenarios)} available")
    else:
        scenarios = all_scenarios

    results = []
    Path(audio_dir).mkdir(parents=True, exist_ok=True)
    Path(transcript_dir).mkdir(parents=True, exist_ok=True)
    Path(results_dir).mkdir(parents=True, exist_ok=True)

    logger.info(f"{'=' * 60}")
    logger.info(f"STARTING EVALUATION: {len(scenarios)} scenarios")
    logger.info(f"Audio output: {audio_dir}/")
    logger.info(f"Transcripts: {transcript_dir}/")
    logger.info(f"Results: {results_dir}/")
    logger.info(f"{'=' * 60}")

    for i, scenario in enumerate(scenarios):
        logger.info(f"\n{'=' * 60}")
        logger.info(f"SCENARIO {i + 1}/{len(scenarios)}: {scenario.get('name', 'unnamed')}")
        logger.info(f"ID: {scenario.get('id', 'unknown')}")
        logger.info(f"Customer: {scenario.get('customer', {}).get('name', 'Unknown')}")
        style = scenario.get("conversation_style", {})
        logger.info(f"Style: {style.get('tone', 'normal')} / {style.get('opening', 'standard')}")
        logger.info(f"Timeout: {scenario.get('timeout', DEFAULT_TIMEOUT)}s")
        logger.info(f"{'=' * 60}\n")

        orchestrator = HotelBookingOrchestrator(scenario, audio_dir, transcript_dir, provider)
        result = await orchestrator.run(
            timeout=scenario.get("timeout", DEFAULT_TIMEOUT),
            text_mode=text_mode
        )
        results.append(result)

        # Log result
        success = result["success_results"]
        is_confirmed = success.get("booking_confirmed", False)
        status = "✅ PASSED" if is_confirmed else "❌ FAILED"

        logger.info(f"\n{'=' * 40}")
        logger.info(f"RESULT: {status}")
        logger.info(f"{'=' * 40}")
        logger.info(f"Messages: {result['transcript_count']}")
        logger.info(f"Duration: {result['duration_seconds']}s")
        logger.info(f"Stage: {success.get('conversation_stage', 'UNKNOWN')}")
        logger.info(f"Booking confirmed: {is_confirmed}")
        logger.info(f"Booking number: {success.get('booking_number', 'None')}")

        if result.get("audio_files", {}).get("conversation"):
            logger.info(f"Audio: {result['audio_files']['conversation']}")

        if result.get("error"):
            logger.info(f"Error: {result['error']}")

        if i < len(scenarios) - 1:
            logger.info("\n⏳ Waiting 10 seconds...\n")
            await asyncio.sleep(10)

    # Save results to results folder
    excel_file = os.path.join(results_dir, "evaluation_results.xlsx")
    excel_file = update_results_excel(results, excel_file)

    print_summary(results, excel_file, audio_dir, transcript_dir)


def write_results_csv(results: List[Dict], output_file: str):
    """Write evaluation results to CSV."""
    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)

        writer.writerow([
            "Scenario ID",
            "Scenario Name",
            "Duration (s)",
            "Message Count",
            "Conversation Stage",
            "Booking Confirmed",
            "Booking Number",
            "Correct Hotel",
            "Provided Name",
            "Provided Phone",
            "Provided Email",
            "Error",
            "Passed",
            "Combined Audio",
            "Full Transcript",
        ])

        for r in results:
            success = r.get("success_results", {})
            provided = success.get("provided_info", {})
            audio_files = r.get("audio_files", {})

            passed = success.get("booking_confirmed", False)

            # Format transcript
            transcript_lines = []
            for i, t in enumerate(r.get("transcripts", []), 1):
                role = "CUSTOMER" if t["role"] == "customer" else "AGENT"
                transcript_lines.append(f"[{i}] {role}:\r\n{t['content']}")
            transcript = "\r\n\r\n".join(transcript_lines)
            if len(transcript) > 32000:
                transcript = transcript[:32000] + "\r\n\r\n[... TRUNCATED ...]"

            writer.writerow([
                r.get("scenario_id", ""),
                r.get("scenario_name", ""),
                r.get("duration_seconds", 0),
                r.get("transcript_count", 0),
                success.get("conversation_stage", "UNKNOWN"),
                "YES" if success.get("booking_confirmed", False) else "NO",
                success.get("booking_number", "") or "",
                "YES" if success.get("correct_hotel") else "NO",
                "YES" if provided.get("name", False) else "NO",
                "YES" if provided.get("phone", False) else "NO",
                "YES" if provided.get("email", False) else "NO",
                r.get("error", "") or "",
                "PASS" if passed else "FAIL",
                audio_files.get("conversation", ""),
                transcript,
            ])

    logger.info(f"📊 CSV saved: {output_file}")


def print_summary(results: List[Dict], excel_file: str, audio_dir: str, transcript_dir: str):
    """Print evaluation summary."""
    logger.info(f"\n{'=' * 60}")
    logger.info("EVALUATION COMPLETE")
    logger.info(f"{'=' * 60}")

    total = len(results)
    passed = sum(1 for r in results if r.get("success_results", {}).get("booking_confirmed", False))
    failed = total - passed

    logger.info(f"Total scenarios: {total}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Success rate: {passed / total * 100:.1f}%" if total > 0 else "N/A")

    # Show failure breakdown
    failed_stages = [
        r["success_results"].get("conversation_stage", "UNKNOWN")
        for r in results
        if not r.get("success_results", {}).get("booking_confirmed", False)
    ]

    if failed_stages:
        logger.info(f"\nFailed at stages:")
        stage_counts = {}
        for stage in failed_stages:
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
        for stage in sorted(stage_counts.keys()):
            logger.info(f"  - {stage}: {stage_counts[stage]}")

    errors = [r.get("error") for r in results if r.get("error")]
    if errors:
        logger.info(f"\nErrors: {len(errors)}")

    logger.info(f"\nOutput files:")
    logger.info(f"   Results: {excel_file}")
    logger.info(f"   Audio: {audio_dir}/")
    logger.info(f"   Transcripts: {transcript_dir}/")

    # Print historical summary
    print_historical_summary()


def list_scenarios(scenarios_file: str):
    """List all available scenarios."""
    with open(scenarios_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    all_scenarios = data.get("scenarios", [])
    
    logger.info(f"\n📋 Available scenarios in {scenarios_file}:")
    logger.info(f"{'=' * 60}")
    for i, s in enumerate(all_scenarios, 1):
        style = s.get("conversation_style", {})
        logger.info(f"{i:2}. [{s.get('id', 'unknown'):30}] {s.get('name', 'unnamed')}")
        logger.info(f"     Customer: {s.get('customer', {}).get('name', 'N/A')}")
        logger.info(f"     Style: {style.get('tone', 'normal')} / {style.get('opening', 'standard')}")
    logger.info(f"\nTotal: {len(all_scenarios)} scenarios")
