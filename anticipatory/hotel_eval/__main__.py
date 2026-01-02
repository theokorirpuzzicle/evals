#!/usr/bin/env python3
"""
Hotel Booking Voice Agent Evaluation System - Main Entry Point

Usage:
    python -m hotel_eval --help
    python -m hotel_eval -s scenarios.json -n 5
    python -m hotel_eval -s scenarios.json --ids basic_coorg_booking new_year_eve
    python -m hotel_eval -s scenarios.json --list
"""

import asyncio
import argparse
import logging
import os
from datetime import datetime

from .config import GEMINI_API_KEY, OPENAI_API_KEY, DEFAULT_TIMEOUT, DEFAULT_PROVIDER
from .evaluation import run_evaluation, list_scenarios

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
)
logger = logging.getLogger("eval-runner")

logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(
        description="Run hotel booking voice agent evaluations"
    )
    parser.add_argument(
        "--scenarios", "-s",
        default="scenarios/scenarios.json",
        help="Scenarios JSON file (default: scenarios/scenarios.json)",
    )
    parser.add_argument(
        "--audio-dir", "-a",
        default="results/audio",
        help="Directory for audio files (default: results/audio)",
    )
    parser.add_argument(
        "--transcript-dir",
        default="results/transcripts",
        help="Directory for transcript files (default: results/transcripts)",
    )
    parser.add_argument(
        "--results-dir",
        default="results",
        help="Directory for results files (default: results)",
    )
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=None,
        help="Number of random scenarios to run (default: all)",
    )
    parser.add_argument(
        "--ids", "-i",
        nargs="+",
        default=None,
        help="Specific scenario IDs to run (space-separated)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available scenarios and exit",
    )
    parser.add_argument(
        "--text-mode", "-t",
        action="store_true",
        help="Run in text-only mode (no audio, no LiveKit)",
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["gemini", "openai"],
        default=DEFAULT_PROVIDER,
        help=f"AI provider to use (default: {DEFAULT_PROVIDER})",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model to use (overrides provider default)",
    )

    args = parser.parse_args()

    # Check scenarios file exists
    if not os.path.exists(args.scenarios):
        raise FileNotFoundError(f"Scenarios file not found: {args.scenarios}")

    # List mode
    if args.list:
        list_scenarios(args.scenarios)
        return

    # Check API key for selected provider
    if args.provider == "gemini" and not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY not set")
    elif args.provider == "openai" and not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    # Override model if specified
    if args.model:
        import hotel_eval.config as config
        if args.provider == "gemini":
            config.GEMINI_MODEL = args.model
        else:
            config.OPENAI_MODEL = args.model
        logger.info(f"Using model: {args.model}")

    logger.info(f"Using provider: {args.provider}")

    # Run evaluation
    asyncio.run(run_evaluation(
        args.scenarios,
        args.audio_dir,
        args.transcript_dir,
        args.results_dir,
        count=args.count,
        scenario_ids=args.ids,
        text_mode=args.text_mode,
        provider=args.provider,
    ))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
