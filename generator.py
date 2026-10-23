"""LLM-based UVM test generator from natural language descriptions."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from llm_dv_toolkit.test_generator.prompt_templates import PromptTemplates
from llm_dv_toolkit.test_generator.sv_parser import SVValidator
from llm_dv_toolkit.utils.config import Config, LLMConfig


@dataclass
class GenerationResult:
    """Result of a test generation request."""
    code: str = ""
    language: str = "systemverilog"
    generation_type: str = ""  # sequence, test, covergroup
    tokens_used: int = 0
    iterations: int = 0
    validation_issues: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


class LLMClient:
    """Unified client for OpenAI and Anthropic APIs."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._total_tokens = 0

    async def complete(self, system: str, user: str) -> tuple[str, int]:
        """Send completion request and return (response, tokens_used)."""
        if self.config.provider == "openai":
            return await self._openai_complete(system, user)
        elif self.config.provider == "anthropic":
            return await self._anthropic_complete(system, user)
        raise ValueError(f"Unknown provider: {self.config.provider}")

    async def _openai_complete(self, system: str, user: str) -> tuple[str, int]:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.config.api_key)
            response = await client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
            text = response.choices[0].message.content or ""
            tokens = response.usage.total_tokens if response.usage else 0
            self._total_tokens += tokens
            return text, tokens
        except ImportError:
            return self._mock_response(user), 100

    async def _anthropic_complete(self, system: str, user: str) -> tuple[str, int]:
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self.config.api_key)
            response = await client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = response.content[0].text if response.content else ""
            tokens = response.usage.input_tokens + response.usage.output_tokens
            self._total_tokens += tokens
            return text, tokens
        except ImportError:
            return self._mock_response(user), 100

    def _mock_response(self, prompt: str) -> str:
        """Fallback mock for when API libraries are not installed."""
        return (
            "class generated_seq extends uvm_sequence #(axi4_lite_seq_item);\n"
            "    `uvm_object_utils(generated_seq)\n"
            "    function new(string name = \"generated_seq\");\n"
            "        super.new(name);\n"
            "    endfunction\n"
            "    task body();\n"
            "        // Generated test logic\n"
            "        `uvm_info(get_type_name(), \"Running generated test\", UVM_MEDIUM)\n"
            "    endtask\n"
            "endclass\n"
        )

    @property
    def total_tokens(self) -> int:
        return self._total_tokens


class TestGenerator:
    """Generate UVM test code from natural language descriptions."""

    MAX_ITERATIONS = 3

    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = LLMClient(config.llm)
        self.validator = SVValidator()
        self.templates = PromptTemplates()

    async def generate(
        self, description: str,
        gen_type: str = "sequence",
        context: str = "",
    ) -> GenerationResult:
        """Generate UVM code from natural language description.

        Args:
            description: Natural language description of desired test behavior.
            gen_type: Type of code to generate (sequence, test, covergroup).
            context: Additional context (existing code, interface info).

        Returns:
            GenerationResult with generated code and metadata.
        """
        start = time.monotonic()
        system_prompt = self.templates.system_prompt()

        if gen_type == "sequence":
            user_prompt = self.templates.sequence_generation(description, context)
        elif gen_type == "test":
            user_prompt = self.templates.test_generation(description, context)
        elif gen_type == "covergroup":
            user_prompt = self.templates.coverage_generation(description, context)
        else:
            user_prompt = self.templates.sequence_generation(description, context)

        total_tokens = 0
        code = ""
        issues: list[str] = []

        for iteration in range(1, self.MAX_ITERATIONS + 1):
            response, tokens = await self.client.complete(system_prompt, user_prompt)
            total_tokens += tokens
            code = self._extract_code(response)
            issues = self.validator.validate(code)

            if not issues:
                break

            # Feed errors back for refinement
            user_prompt = self.templates.refinement_prompt(code, issues)

        return GenerationResult(
            code=code,
            generation_type=gen_type,
            tokens_used=total_tokens,
            iterations=iteration,
            validation_issues=issues,
            elapsed_seconds=time.monotonic() - start,
        )

    def _extract_code(self, response: str) -> str:
        """Extract SystemVerilog code from LLM response."""
        # Look for code blocks
        if "```systemverilog" in response:
            start = response.index("```systemverilog") + len("```systemverilog")
            end = response.index("```", start)
            return response[start:end].strip()
        if "```sv" in response:
            start = response.index("```sv") + len("```sv")
            end = response.index("```", start)
            return response[start:end].strip()
        if "```" in response:
            start = response.index("```") + 3
            end = response.index("```", start)
            return response[start:end].strip()
        return response.strip()

    async def generate_batch(
        self, descriptions: list[str], gen_type: str = "sequence",
    ) -> list[GenerationResult]:
        """Generate multiple tests in parallel."""
        tasks = [self.generate(desc, gen_type) for desc in descriptions]
        return await asyncio.gather(*tasks)
