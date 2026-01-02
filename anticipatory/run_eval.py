#!/usr/bin/env python3
"""
Standalone runner for Hotel Booking Voice Agent Evaluation.

This script can be run directly without installing the package:
    python run_eval.py -n 5
"""

import sys
import os

# Add the parent directory to path so we can import hotel_eval
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hotel_eval.__main__ import main

if __name__ == "__main__":
    main()
