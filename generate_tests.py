#!/usr/bin/env python3
"""Example: Generate UVM tests using LLM-DV Toolkit."""

import asyncio
from llm_dv_toolkit.test_generator.generator import TestGenerator
from llm_dv_toolkit.utils.config import Config


async def main():
    config = Config.from_env()
    generator = TestGenerator(config)

    descriptions = [
        "Write a sequence that performs write-then-read-back on all general purpose registers (3-15), verifying each read returns the written value. Use walking 1s pattern.",
        "Write a sequence that attempts writes to read-only register 0 (ID register at 0x00) and verifies the value is unchanged at 0xDEADBEEF after the write attempt.",
        "Write a constrained-random sequence that generates 1000 random AXI4-Lite transactions mixing reads and writes with various strobe patterns.",
    ]

    print("=== LLM-DV Test Generator ===\n")
    for i, desc in enumerate(descriptions, 1):
        print(f"--- Test {i}: {desc[:80]}... ---")
        result = await generator.generate(desc, gen_type="sequence")
        print(f"Status: {'PASS' if not result.validation_issues else 'ISSUES'}")
        print(f"Tokens: {result.tokens_used}, Iterations: {result.iterations}")
        print(f"Time: {result.elapsed_seconds:.1f}s")
        if result.validation_issues:
            for issue in result.validation_issues:
                print(f"  Issue: {issue}")
        print(f"\n{result.code}\n")
        print("=" * 60)

    print(f"\nTotal tokens used: {generator.client.total_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
