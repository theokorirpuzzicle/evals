"""
Chart creation utilities for Excel reports.
"""

import logging

logger = logging.getLogger("eval-runner")


def create_trend_chart(ws, last_row: int):
    """
    Create or update a trend chart showing success rate over time.

    Args:
        ws: The openpyxl worksheet
        last_row: The last row with data
    """
    try:
        from openpyxl.chart import LineChart, Reference
        from openpyxl.chart.label import DataLabelList
        from openpyxl.chart.marker import Marker
    except ImportError:
        logger.debug("openpyxl chart modules not available")
        return

    # Remove existing chart if present
    if ws._charts:
        ws._charts.clear()

    # Only create chart if we have at least 2 data points
    if last_row < 3:
        return

    # Create line chart
    chart = LineChart()
    chart.title = "Booking Success Rate Trend"
    chart.style = 10
    chart.y_axis.title = "Success Rate (%)"
    chart.x_axis.title = "Run #"
    chart.y_axis.scaling.min = 0
    chart.y_axis.scaling.max = 100
    chart.y_axis.majorUnit = 10  # Show tick marks every 10%
    chart.y_axis.tickLblPos = "nextTo"  # Position labels next to axis
    chart.x_axis.tickLblPos = "nextTo"  # Position labels next to axis
    chart.height = 12
    chart.width = 18

    # Hide the legend (single series doesn't need one)
    chart.legend = None

    # Data reference (Success Rate column = G, from row 2 to last_row, no header)
    data = Reference(ws, min_col=7, min_row=2, max_row=last_row)
    categories = Reference(ws, min_col=1, min_row=2, max_row=last_row)

    chart.add_data(data, titles_from_data=False)
    chart.set_categories(categories)

    # Style the line
    series = chart.series[0]
    series.graphicalProperties.line.width = 25000  # ~2pt
    series.graphicalProperties.line.solidFill = "4472C4"
    series.marker = Marker(symbol="circle", size=8)
    series.marker.graphicalProperties.solidFill = "4472C4"
    series.marker.graphicalProperties.line.solidFill = "4472C4"

    # Add data labels - show only the Y values (success rate %), not series name or category
    series.dLbls = DataLabelList()
    series.dLbls.showVal = True  # Show Y value (success rate)
    series.dLbls.showSerName = False  # Don't show series name
    series.dLbls.showCatName = False  # Don't show category name (Run #)
    series.dLbls.showLegendKey = False  # Don't show legend key

    # Position chart to the right of the data
    chart.anchor = "I2"
    ws.add_chart(chart)
