# Hotel Booking Voice Agent Evaluation System

Comprehensive automated evaluation framework for testing hotel booking voice agents using bidirectional WebSocket connections with Gemini Live API to simulate realistic customer conversations.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Features](#features)
- [Evaluation Methods](#evaluation-methods)
- [Excel Dashboard](#excel-dashboard)
- [Running Evaluations](#running-evaluations)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

This system evaluates voice agents by simulating diverse customer personas making hotel booking inquiries. It measures success rates, captures audio recordings, tracks performance trends over time, and provides visual dashboards with detailed criteria evaluation.

### Key Features

- **4 focused test scenarios** based on real feedback from Tamara voice agent test calls
- **Hybrid evaluation** - Pattern-based (fast, objective) + LLM-based (contextual, subjective)
- **Audio recording** - Full conversation audio saved as MP3 files
- **Visual dashboards** - Colorful heatmaps, trend charts, and funnel analysis
- **Persistent tracking** - Excel file with historical trend analysis across runs
- **20 evaluation criteria** - 16 critical, 4 non-critical with automated evaluation
- **State machine validation** - Formal conversation flow validation
- **Quality scoring** - Conversation quality metrics beyond just completion

## Quick Start

### Prerequisites

- Python 3.10+
- Gemini API key ([Get one here](https://aistudio.google.com/apikey))

### Installation

```bash
# Clone the repository
git clone https://github.com/puzzicle/evals.git
cd evals

# Install dependencies
pip install -r requirements.txt

# Set your API key
export GEMINI_API_KEY="your-gemini-api-key"
# Windows: set GEMINI_API_KEY=your-api-key
```

### Run Evaluation

```bash
# Run all scenarios
python run_scenario_eval.py

# Run specific scenarios
python run_scenario_eval.py -i info_capture_test pricing_accuracy_test

# List available scenarios
python run_scenario_eval.py --list
```

## Architecture

### Connection Flow

**Direct WebSocket Connection (No LiveKit)**

```
Customer AI (Gemini) ←→ Evaluation System ←→ Voice Agent (WebSocket)
        24kHz PCM              |                   16kHz PCM
                               |
                          AudioMixer
                               ↓
                         results/audio/
                          (MP3 files)
```

**Key components:**
1. **Gemini WebSocket** - Simulates customer with realistic personas
2. **Voice Agent WebSocket** - Direct connection to hotel booking agent
3. **Audio Mixer** - Resamples and mixes both streams into single timeline
4. **Criteria Evaluator** - Automated pass/fail evaluation
5. **Excel Exporter** - Visual dashboards and trend tracking

### Audio Flow

- **Customer → Agent**: 24kHz audio resampled to 16kHz
- **Agent → Customer**: 16kHz audio forwarded directly
- **Recording**: Both streams mixed into single 24kHz MP3 file
- **Keep-alive**: Automatic silence packets prevent connection timeout

## Features

### 1. Test Scenarios

Four focused scenarios based on real test call feedback:

| Scenario | Focus Area | Criteria Count |
|----------|-----------|----------------|
| **Info Capture Test** | Name/phone/email accuracy | 5 |
| **Pricing Accuracy Test** | Pricing clarity, budget sensitivity | 5 |
| **Child Policy Empathy Test** | Policy handling with empathy | 5 |
| **Room Capacity Policy Test** | Room occupancy, extra bed policies | 5 |

### 2. Evaluation Criteria (20 Total)

**Critical Criteria (16):**
- Customer name captured correctly
- Phone number captured correctly
- Email captured correctly
- Pricing clarity (per night vs total)
- Child policy communicated
- Room capacity accurate
- Extra bed policy correct
- Alternative property offered
- Booking confirmation sent
- Budget sensitivity shown
- No unrealistic pricing
- Meal plan explained
- Superior cottage capacity correct
- Suite cottage suggested for 3 adults
- Activity pricing accurate

**Non-Critical Criteria (4):**
- Agent shows patience
- Retention attempt made
- Negotiation handled well
- Courteous closing

### 3. Audio Recording

All conversations are recorded and saved as MP3 files:
- **Location**: `results/audio/`
- **Format**: MP3 (128kbps, high quality)
- **Naming**: `{scenario_id}_{timestamp}_conversation.mp3`
- **Content**: Mixed agent + customer audio on single timeline
- **Encoder**: `lameenc` (pure Python, no external dependencies)

### 4. Advanced Features

**Booking Detection:**
- Letter-only codes (e.g., "TCWFO", "ABC")
- Spelled-out numbers (e.g., "T. C. W. F. O." → "TCWFO")
- Pattern matching with false positive filtering

**Conversation Analysis:**
- Stage progression validation
- State machine verification
- Sanity checks (turn alternation, content quality)
- Quality scoring (naturalness, professionalism, clarity)

**Multi-run Tracking:**
- Correlation analysis across runs
- Common failure point detection
- Criteria correlation analysis

## Evaluation Methods

### Pattern-Based Evaluation (Objective Criteria)

**Fast, deterministic, no API costs**

Used for objective criteria verifiable through keyword matching:
- Name/phone/email captured
- Pricing clarity ("per night", "total", etc.)
- Policy adherence (child policy, room capacity)
- Booking confirmation

**Features:**
- Contextual analysis (checks surrounding text)
- Multi-keyword requirements (2+ indicators)
- Negative pattern detection

### LLM-Based Evaluation (Subjective Criteria)

**Contextual, accurate, understands nuance**

Used for subjective criteria requiring judgment:
- Empathy expressed
- Patience demonstrated
- Courteous closing
- Budget sensitivity
- Retention attempts

**How it works:**
1. Sends conversation + criterion to Gemini API
2. LLM evaluates based on context, tone, appropriateness
3. Returns PASS/FAIL with reasoning
4. Falls back to pattern-based if API unavailable

**Enable/Disable:**
```bash
# Enable LLM evaluation (default)
export USE_LLM_EVAL=true

# Disable (use only pattern-based)
export USE_LLM_EVAL=false
```

## Excel Dashboard

### Sheet 1: Runs Summary
**Quick overview of all test runs**
- Run number, timestamp, date
- Total scenarios, passed, failed
- Success rate with color coding (🟢 >75%, 🟡 50-75%, 🔴 <50%)
- Trend chart showing success rate over time

### Sheet 2: All Results
**Detailed results for every scenario**
- Scenario ID, name, customer
- Duration, message count
- Conversation stage reached
- Booking status (YES/NO with colors)
- **Dynamic criteria columns** - one column per criterion
- Error descriptions
- Final result (PASS/FAIL)

### Sheet 3: Stage Breakdown
**Conversation funnel analysis**
- Count of scenarios reaching each stage
- Color-coded cells (🟢 booking confirmed, 🔴 failed earlier)
- Identifies where conversations typically fail

### Sheet 4: Run Visualizations
**Visual dashboard for each run**

Each run gets a colorful section with:

#### Success Metrics
- Total scenarios
- Passed/Failed counts
- Success rate gauge
- Critical failures count

#### Criteria Heatmap
- Grid view: scenarios × criteria
- Color coding:
  - 🟢 Green = PASS
  - 🔴 Red = FAIL
  - ⚪ Gray = N/A
  - ➖ Dash = Not applicable

#### Conversation Stage Funnel
- Visual bars showing progression
- See how many scenarios reached each stage
- Identify drop-off points

#### Legend
- Color coding guide
- Evaluation method explanations
- Criterion definitions

## Running Evaluations

### Basic Usage

```bash
# Run all scenarios
python run_scenario_eval.py

# Run specific scenario
python run_scenario_eval.py -i info_capture_test

# Run multiple scenarios
python run_scenario_eval.py -i info_capture_test pricing_accuracy_test

# List available scenarios
python run_scenario_eval.py --list
```

### Advanced Options

```bash
# Custom scenarios file
python run_scenario_eval.py -s path/to/scenarios.json

# Run random subset
python run_scenario_eval.py -n 2
```

### Output Files

After each run, files are generated in `results/`:

| File | Description |
|------|-------------|
| `evaluation_results.xlsx` | **Persistent** results with trend charts (accumulates) |
| `audio/{scenario}_{timestamp}.mp3` | Conversation recordings |
| `transcripts/{scenario}_{timestamp}.txt` | Text transcripts |

## Project Structure

```
evals/
├── run_scenario_eval.py              # Main entry point
├── bidirectional_test.py             # Voice bridge (WebSocket handler)
├── requirements.txt                  # Python dependencies
│
├── anticipatory/
│   ├── scenarios/
│   │   └── scenarios.json            # Test scenario definitions
│   │
│   └── hotel_eval/
│       ├── __init__.py
│       ├── config.py                 # Configuration constants
│       ├── audio_mixer.py            # Audio mixing & resampling
│       ├── prompt_builder.py         # Customer persona prompts
│       ├── voice_selection.py        # Dynamic voice selection
│       │
│       ├── booking/                  # Booking detection module
│       │   ├── __init__.py
│       │   ├── constants.py          # Conversation stages
│       │   ├── patterns.py           # Regex patterns
│       │   ├── validation.py         # Booking number validation
│       │   ├── extraction.py         # Booking number extraction
│       │   ├── number_parser.py      # STT error handling
│       │   ├── stages.py             # Stage detection
│       │   ├── sanity_checks.py      # Conversation validation
│       │   └── state_machine.py      # Formal flow validation
│       │
│       ├── criteria_evaluator.py     # Criteria evaluation logic
│       ├── quality_scorer.py         # Conversation quality scoring
│       │
│       └── reporting/                # Results & visualization
│           ├── __init__.py
│           ├── excel_exporter.py     # Excel dashboard generator
│           ├── visualization.py      # Charts and heatmaps
│           └── correlation_analysis.py # Multi-run patterns
│
└── results/                          # Generated outputs
    ├── evaluation_results.xlsx       # Main results file
    ├── audio/                        # MP3 recordings
    └── transcripts/                  # Text transcripts
```

## Configuration

Edit `anticipatory/hotel_eval/config.py`:

```python
# Voice Agent Connection
VOICE_AGENT_URL = "wss://caller.anticipatory.com/ws/booking"

# Gemini Settings
GEMINI_MODEL = "gemini-2.0-flash-exp"
GEMINI_URL = "wss://generativelanguage.googleapis.com/..."

# Audio Settings
AGENT_SAMPLE_RATE = 16000      # Voice agent uses 16kHz
CUSTOMER_SAMPLE_RATE = 24000   # Gemini uses 24kHz
OUTPUT_SAMPLE_RATE = 24000     # Output recordings at 24kHz

# Timeouts
DEFAULT_TIMEOUT = 600          # 10 minutes per scenario
INACTIVITY_TIMEOUT = 45        # Stall detection

# LLM Evaluation
USE_LLM_EVAL = True           # Enable/disable LLM evaluation
```

## Best Practices

### 1. Review Visualizations First
Start with the "Run Visualizations" sheet for quick overview, then drill into details.

### 2. Track Trends Over Time
Compare success rates across runs to see improvements/regressions.

### 3. Focus on Critical Failures
Red cells in critical criteria columns need immediate attention.

### 4. Use LLM for Subjective Criteria
Let the AI evaluate nuanced criteria like empathy - it's more accurate than keyword matching.

### 5. Validate LLM Results
Spot-check LLM evaluations by reading transcripts to ensure accuracy.

### 6. Analyze Drop-off Points
Use the stage funnel to identify where conversations typically fail.

### 7. Review Audio Recordings
Listen to recordings when criteria results are unexpected.

## Troubleshooting

### API Key Issues
```bash
# Check API key is set
echo $GEMINI_API_KEY

# Set API key
export GEMINI_API_KEY="your-key"

# Windows
set GEMINI_API_KEY=your-key
```

### LLM Evaluation Not Working
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python run_scenario_eval.py

# Disable LLM evaluation (use pattern-only)
export USE_LLM_EVAL=false
```

### Excel File Won't Open
- Ensure openpyxl is installed: `pip install openpyxl`
- Check file isn't already open in Excel
- Delete `evaluation_results.xlsx` and regenerate

### Audio Distortion
The system includes advanced audio processing:
- Segment-based mixing (prevents crackling)
- RMS normalization (balanced volume)
- Crossfade smoothing (seamless transitions)

### Criteria Shows "N/A"
- Criterion name doesn't match any pattern
- Add custom logic in `criteria_evaluator.py`
- Or rename criterion to match existing patterns

### WebSocket Connection Issues
```bash
# Check voice agent URL
echo $VOICE_AGENT_WS_URL

# Test with production
export VOICE_AGENT_WS_URL="wss://caller.anticipatory.com/ws/booking"

# Test with staging
export VOICE_AGENT_WS_URL="wss://staging-caller.anticipatory.com/ws/booking"

# Local testing
export VOICE_AGENT_WS_URL="ws://localhost:8000/ws/booking"
```

## Success Criteria

A scenario passes when:
1. ✅ Booking is confirmed
2. ✅ Valid booking number provided
3. ✅ All critical criteria pass

## Advanced: Custom Criteria

### Add to Scenario
Edit `anticipatory/scenarios/scenarios.json`:

```json
{
  "id": "my_test",
  "name": "My Custom Test",
  "evaluation_criteria": {
    "my_criterion": {
      "description": "What should happen",
      "critical": true
    }
  }
}
```

### Add Evaluation Logic
Edit `anticipatory/hotel_eval/criteria_evaluator.py`:

```python
elif "my_custom_criterion" in criterion_name.lower():
    result = _evaluate_my_custom(conversation_text_lower)
    reason = "Custom evaluation logic"
    results[criterion_name] = _create_detailed_result(
        criterion_name, result, "PATTERN", reason
    )
```

Implement the evaluation function:

```python
def _evaluate_my_custom(conversation: str) -> str:
    """Check for my custom condition."""
    if "expected phrase" in conversation:
        return "PASS"
    return "FAIL"
```

## Migration History

### From LiveKit to WebSocket (Dec 2024)
- Replaced LiveKit room-based connection with direct WebSocket
- Simplified architecture, reduced latency
- Manual keep-alive with silence packets
- Better control over audio streaming

### From Generic to Focused Scenarios (Dec 2024)
- Migrated from 2000+ generic scenarios to 4 focused scenarios
- Based on real Tamara voice agent test call feedback
- Added 20 specific evaluation criteria
- Implemented hybrid pattern + LLM evaluation

### Audio Recording Enhancement (Dec 2024)
- Added audio mixer integration
- Implemented MP3 conversion using `lameenc`
- Pure Python solution (no external dependencies)
- High-quality 128kbps MP3 encoding

### Advanced Features (Dec 2024)
- Added conversation quality scoring
- Implemented state machine validation
- Created correlation analysis across runs
- Enhanced booking number validation (letter codes, spelled numbers)

## License

Proprietary - Puzzicle

## Support

For issues or questions, contact the Puzzicle team.
