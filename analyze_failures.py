#!/usr/bin/env python3
"""Example: Analyze simulation failures using LLM-DV Toolkit."""

import asyncio
from pathlib import Path

from llm_dv_toolkit.debug_assistant.log_analyzer import LogAnalyzer, LogParser
from llm_dv_toolkit.debug_assistant.failure_classifier import FailureClassifier, FailureCategory
from llm_dv_toolkit.debug_assistant.root_cause_engine import RootCauseEngine
from llm_dv_toolkit.utils.config import Config


async def main():
    config = Config.from_env()
    log_path = Path(__file__).parent / "sample_logs" / "sim_failure.log"

    print("=== LLM-DV Debug Assistant ===\n")

    # Step 1: Parse log
    parser = LogParser()
    errors = parser.parse(log_path)
    print(f"Found {len(errors)} errors in log\n")

    for err in errors:
        print(f"  [{err.severity}] {err.message[:100]}")

    # Step 2: Classify failures
    print("\n--- Failure Classification ---")
    classifier = FailureClassifier()
    for err in errors:
        result = classifier.classify(err.message)
        print(f"  Category: {result.category.value} (confidence: {result.confidence:.2f})")
        if result.similar_failures:
            print(f"  Similar: {result.similar_failures[0].get('message', '')[:80]}")

    # Step 3: Full root cause analysis
    print("\n--- Root Cause Analysis ---")
    engine = RootCauseEngine(config)
    analyses = await engine.analyze(log_path)

    for rca in analyses:
        print(f"\n  Error: {rca.error.message[:80]}")
        print(f"  Category: {rca.category.value}")
        print(f"  Root Cause: {rca.root_cause}")
        print(f"  Fix: {rca.suggested_fix}")
        print(f"  Confidence: {rca.confidence:.2f}")
        if rca.reasoning_chain:
            print("  Reasoning:")
            for step in rca.reasoning_chain:
                print(f"    {step.step_number}. {step.action}: {step.finding}")

    classifier.close()


if __name__ == "__main__":
    asyncio.run(main())
