"""
Results tracking utilities - backward compatibility shim.

This module re-exports all results tracking functions from the new
modular reporting subpackage for backward compatibility.
"""

from .reporting import (
    update_results_excel,
    DEFAULT_RESULTS_FILE,
    get_historical_stats,
    print_historical_summary,
)

__all__ = [
    "update_results_excel",
    "DEFAULT_RESULTS_FILE",
    "get_historical_stats",
    "print_historical_summary",
]
