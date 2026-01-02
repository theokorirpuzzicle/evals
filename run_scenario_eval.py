#!/usr/bin/env python3
"""
Run hotel booking evaluations using bidirectional WebSocket pattern.
Loads scenarios from JSON and runs them one by one.
"""
import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Import the working bidirectional pattern
import bidirectional_test

# Import eval utilities
sys.path.insert(0, 'anticipatory')
from hotel_eval.prompt_builder import build_system_instruction
from hotel_eval.voice_selection import select_voice_for_customer
from hotel_eval.booking import (
    is_booking_confirmed,
    extract_booking_number,
    get_conversation_stage,
    get_stage_progress,
    get_failed_at_description,
)
from hotel_eval.reporting import update_results_excel, DEFAULT_RESULTS_FILE
from hotel_eval.criteria_evaluator import evaluate_criteria

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger("eval-runner")


class ScenarioRunner(bidirectional_test.VoiceBridge):
    """Extends VoiceBridge to use scenario data instead of hardcoded customer."""
    
    def __init__(self, scenario):
        super().__init__()
        self.scenario = scenario
        self.start_time = datetime.now()
        
    async def connect(self):
        """Override connect to use scenario-based system instruction."""
        # Production requires "media" subprotocol, staging doesn't
        if "caller.anticipatory.com" in bidirectional_test.VOICE_AGENT_URL:
            self.voice_ws = await bidirectional_test.websockets.connect(
                bidirectional_test.VOICE_AGENT_URL, subprotocols=["media"]
            )
        else:
            self.voice_ws = await bidirectional_test.websockets.connect(
                bidirectional_test.VOICE_AGENT_URL
            )
        logger.info(f"Connected to {bidirectional_test.VOICE_AGENT_URL}")
        
        self.gemini_ws = await bidirectional_test.websockets.connect(
            bidirectional_test.GEMINI_URL
        )
        
        # Build system instruction from scenario
        system_instruction = build_system_instruction(self.scenario)
        
        # Select voice based on customer persona
        selected_voice = select_voice_for_customer(self.scenario)
        customer_name = self.scenario.get('customer', {}).get('name', 'Unknown')
        logger.info(f"Selected voice: {selected_voice} for customer {customer_name}")
        
        setup_message = {
            "setup": {
                "model": f"models/{bidirectional_test.GEMINI_MODEL}",
                "generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {"voice_name": selected_voice}
                        }
                    },
                    "thinking_config": {"thinking_budget": 0},
                },
                # Disable automatic VAD - we control turn-taking manually
                "realtime_input_config": {
                    "automatic_activity_detection": {"disabled": True}
                },
                "output_audio_transcription": {},
                "input_audio_transcription": {},
                "system_instruction": {
                    "parts": [{"text": system_instruction}]
                },
            }
        }
        
        await self.gemini_ws.send(json.dumps(setup_message))
        logger.info("Waiting for Gemini setup...")
        
        async def wait_for_setup():
            async for raw in self.gemini_ws:
                try:
                    data = json.loads(raw)
                    if "setupComplete" in data:
                        self.gemini_ready.set()
                        return
                except json.JSONDecodeError:
                    continue
        
        await asyncio.wait_for(wait_for_setup(), timeout=10)
        logger.info("Gemini ready")
    
    def get_results(self):
        """Return evaluation results."""
        # Convert transcript format for booking module
        transcript_dicts = [
            {'role': role, 'content': text}
            for role, text in self.transcripts
        ]

        duration = (datetime.now() - self.start_time).seconds
        booking_confirmed = is_booking_confirmed(transcript_dicts)
        booking_number = extract_booking_number(transcript_dicts)
        stage = get_conversation_stage(transcript_dicts)
        stage_progress = get_stage_progress(transcript_dicts)
        failed_at = get_failed_at_description(transcript_dicts) if not booking_confirmed else None

        # Evaluate scenario-specific criteria
        criteria_results = evaluate_criteria(self.scenario, transcript_dicts)

        # Build success_results for Excel export compatibility
        success_results = {
            'booking_confirmed': booking_confirmed,
            'booking_number': booking_number,
            'conversation_stage': stage,
            'stage_progress': stage_progress,
            'failed_at': failed_at,
        }

        return {
            'scenario_id': self.scenario.get('id', 'unknown'),
            'scenario_name': self.scenario.get('name', 'Unknown'),
            'duration_seconds': duration,
            'transcript_count': len(self.transcripts),
            'transcripts': transcript_dicts,
            'booking_confirmed': booking_confirmed,
            'booking_number': booking_number,
            'success': self.booking_confirmed,
            'success_results': success_results,
            'criteria_results': criteria_results,
            'scenario': self.scenario,
            'timestamp': self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
        }


async def run_scenario(scenario):
    """Run a single scenario evaluation."""
    logger.info("")
    logger.info("╔" + "═" * 78 + "╗")
    logger.info(f"║ SCENARIO: {scenario.get('name', 'Unknown'):<69} ║")
    logger.info("╠" + "═" * 78 + "╣")
    logger.info(f"║ ID: {scenario.get('id', 'unknown'):<74} ║")
    logger.info(f"║ Customer: {scenario.get('customer', {}).get('name', 'Unknown'):<67} ║")
    logger.info(f"║ Phone: {scenario.get('customer', {}).get('phone', 'N/A'):<71} ║")
    logger.info(f"║ Email: {scenario.get('customer', {}).get('email', 'N/A'):<71} ║")
    
    # Show what we're testing
    criteria = scenario.get('evaluation_criteria', {})
    if criteria:
        logger.info("╠" + "═" * 78 + "╣")
        logger.info(f"║ Testing {len(criteria)} criteria:{' ' * 56} ║")
        for i, (criterion_name, criterion_def) in enumerate(list(criteria.items())[:3], 1):
            critical_tag = " [CRITICAL]" if criterion_def.get('critical') else ""
            criterion_display = f"{criterion_name}{critical_tag}"
            padding = 73 - len(criterion_display)
            logger.info(f"║  {i}. {criterion_display}{' ' * padding} ║")
        if len(criteria) > 3:
            remaining = len(criteria) - 3
            logger.info(f"║  ... and {remaining} more{' ' * (63 - len(str(remaining)))} ║")
    
    logger.info("╚" + "═" * 78 + "╝")
    logger.info("")
    
    runner = ScenarioRunner(scenario)
    
    try:
        await runner.run()
    except Exception as e:
        logger.error(f"Error running scenario: {e}")
    
    # Get results
    results = runner.get_results()

    # Save transcript to file
    import os
    os.makedirs("results/transcripts", exist_ok=True)
    timestamp = runner.start_time.strftime("%Y%m%d_%H%M%S")
    scenario_id = scenario.get('id', 'unknown')
    transcript_file = f"results/transcripts/{scenario_id}_{timestamp}_transcript.txt"

    with open(transcript_file, 'w', encoding='utf-8') as f:
        f.write(f"Scenario: {results['scenario_name']}\n")
        f.write(f"Customer: {scenario.get('customer', {}).get('name', 'Unknown')}\n")
        f.write(f"Timestamp: {results['timestamp']}\n")
        f.write(f"Duration: {results['duration_seconds']}s\n")
        f.write(f"Booking Confirmed: {results['booking_confirmed']}\n")
        f.write(f"Booking Number: {results['booking_number']}\n")
        f.write("=" * 60 + "\n\n")

        for idx, msg in enumerate(results['transcripts'], 1):
            role = "CUSTOMER" if msg['role'] == 'customer' else "AGENT"
            f.write(f"[{idx}] {role}: {msg['content']}\n")

    logger.info(f"📝 Transcript saved: {transcript_file}")

    # Save audio
    if hasattr(runner, "audio_mixer") and runner.audio_mixer:
        try:
            os.makedirs("results/audio", exist_ok=True)
            audio_file_wav = f"results/audio/{scenario_id}_{timestamp}_conversation.wav"
            audio_file_mp3 = f"results/audio/{scenario_id}_{timestamp}_conversation.mp3"
            
            # Mix and save as WAV first
            mixed_audio = runner.audio_mixer.mix_audio()
            if mixed_audio:
                import wave
                with wave.open(audio_file_wav, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(24000)
                    wav_file.writeframes(mixed_audio)
                logger.info(f"🎵 Audio saved: {audio_file_wav}")
                
                # Convert to MP3 using lameenc
                try:
                    import lameenc
                    
                    # Read WAV data
                    with wave.open(audio_file_wav, 'rb') as wav:
                        channels = wav.getnchannels()
                        sample_rate = wav.getframerate()
                        wav_frames = wav.readframes(wav.getnframes())
                    
                    # Encode to MP3
                    encoder = lameenc.Encoder()
                    encoder.set_bit_rate(128)
                    encoder.set_in_sample_rate(sample_rate)
                    encoder.set_channels(channels)
                    encoder.set_quality(2)  # High quality
                    
                    mp3_data = encoder.encode(wav_frames)
                    mp3_data += encoder.flush()
                    
                    # Write MP3
                    with open(audio_file_mp3, 'wb') as f:
                        f.write(mp3_data)
                    
                    logger.info(f"🎵 MP3 saved: {audio_file_mp3}")
                    # Remove WAV file to save space
                    os.remove(audio_file_wav)
                except ImportError:
                    logger.warning("lameenc not installed (pip install lameenc), keeping WAV file")
                except Exception as e:
                    logger.warning(f"MP3 conversion failed: {e}, keeping WAV file")
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")

    # Print summary
    logger.info("")
    logger.info("╔" + "═" * 78 + "╗")
    logger.info(f"║ RESULTS: {scenario.get('name', 'Unknown'):<67} ║")
    logger.info("╠" + "═" * 78 + "╣")
    logger.info(f"║ Duration: {results['duration_seconds']}s{' ' * (71 - len(str(results['duration_seconds'])))} ║")
    logger.info(f"║ Messages: {results['transcript_count']}{' ' * (71 - len(str(results['transcript_count'])))} ║")
    logger.info(f"║ Booking confirmed: {'YES' if results['booking_confirmed'] else 'NO':<62} ║")
    logger.info(f"║ Booking number: {results['booking_number'] or 'N/A':<64} ║")
    
    # Show criteria results
    criteria_results = results.get('criteria_results', {})
    if criteria_results:
        passed = sum(1 for r in criteria_results.values() if r == 'PASS')
        total = len(criteria_results)
        logger.info("╠" + "═" * 78 + "╣")
        logger.info(f"║ Criteria: {passed}/{total} passed{' ' * (66 - len(f'{passed}/{total}'))} ║")
        
        # Show failed criteria
        failed = [name for name, result in criteria_results.items() if result == 'FAIL']
        if failed:
            logger.info(f"║ Failed criteria:{' ' * 63} ║")
            for criterion in failed[:3]:
                logger.info(f"║  - {criterion:<74} ║")
            if len(failed) > 3:
                logger.info(f"║  ... and {len(failed) - 3} more{' ' * (62 - len(str(len(failed) - 3)))} ║")
    
    success_marker = '✅ PASS' if results['success'] else '❌ FAIL'
    logger.info("╠" + "═" * 78 + "╣")
    logger.info(f"║ Overall: {success_marker:<70} ║")
    logger.info("╚" + "═" * 78 + "╝")
    logger.info("")

    return results


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run scenario evaluations")
    parser.add_argument("-s", "--scenarios", default="anticipatory/scenarios/scenarios.json",
                       help="Path to scenarios JSON file")
    parser.add_argument("-i", "--ids", nargs="+", help="Specific scenario IDs to run")
    parser.add_argument("-n", "--count", type=int, help="Number of random scenarios")
    parser.add_argument("-l", "--list", action="store_true", help="List scenarios")
    
    args = parser.parse_args()
    
    # Load scenarios
    with open(args.scenarios, 'r', encoding='utf-8') as f:
        data = json.load(f)
        all_scenarios = data.get('scenarios', [])
    
    if args.list:
        logger.info(f"\nAvailable scenarios in {args.scenarios}:")
        logger.info("=" * 60)
        for i, scenario in enumerate(all_scenarios, 1):
            logger.info(f"{i}. [{scenario.get('id')}] {scenario.get('name')}")
            logger.info(f"   Customer: {scenario.get('customer', {}).get('name')}")
        return
    
    # Select scenarios to run
    if args.ids:
        scenarios = [s for s in all_scenarios if s.get('id') in args.ids]
    elif args.count:
        import random
        scenarios = random.sample(all_scenarios, min(args.count, len(all_scenarios)))
    else:
        scenarios = all_scenarios
    
    logger.info(f"\nRunning {len(scenarios)} scenario(s)...")
    
    # Run scenarios
    all_results = []
    for scenario in scenarios:
        results = await run_scenario(scenario)
        all_results.append(results)
    
    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 60)
    passed = sum(1 for r in all_results if r['success'])
    logger.info(f"Total: {len(all_results)}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {len(all_results) - passed}")
    logger.info(f"Success rate: {passed/len(all_results)*100:.1f}%")

    # Export to Excel
    logger.info("")
    logger.info("Exporting results to Excel...")
    excel_path = update_results_excel(all_results, DEFAULT_RESULTS_FILE)
    if excel_path:
        logger.info(f"✅ Results saved to: {excel_path}")
    else:
        logger.warning("⚠️  Excel export skipped (openpyxl not installed)")


if __name__ == "__main__":
    if not bidirectional_test.GEMINI_API_KEY:
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY")
        sys.exit(1)
    
    asyncio.run(main())
