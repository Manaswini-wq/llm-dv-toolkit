"""Prompt templates for LLM-based test generation."""

from __future__ import annotations


class PromptTemplates:
    """Organized prompt templates for DV code generation."""

    def system_prompt(self) -> str:
        return (
            "You are an expert ASIC Design Verification engineer with deep expertise in "
            "SystemVerilog and UVM methodology. You write clean, correct, synthesizable "
            "verification code following industry best practices.\n\n"
            "Rules:\n"
            "- Always use proper UVM macros and factory registration\n"
            "- Include `uvm_object_utils or `uvm_component_utils\n"
            "- Use start_item/finish_item for sequence transactions\n"
            "- Include proper constructor with string name parameter\n"
            "- Add meaningful `uvm_info messages for debug\n"
            "- Use constraints for randomization\n"
            "- Handle edge cases and error conditions\n"
            "- Output ONLY SystemVerilog code in a ```systemverilog code block\n"
        )

    def sequence_generation(self, description: str, context: str = "") -> str:
        prompt = (
            f"Generate a UVM sequence based on this description:\n\n"
            f"DESCRIPTION: {description}\n\n"
        )
        if context:
            prompt += f"EXISTING CODE CONTEXT:\n{context}\n\n"
        prompt += (
            "Requirements:\n"
            "- Extend uvm_sequence or a base sequence class\n"
            "- Implement body() task with the described behavior\n"
            "- Use constrained randomization where appropriate\n"
            "- Include error checking and meaningful messages\n"
            "- Make the sequence configurable via class properties\n"
        )
        return prompt

    def test_generation(self, description: str, context: str = "") -> str:
        prompt = (
            f"Generate a complete UVM test based on this description:\n\n"
            f"DESCRIPTION: {description}\n\n"
        )
        if context:
            prompt += f"CONTEXT:\n{context}\n\n"
        prompt += (
            "Requirements:\n"
            "- Extend uvm_test or a base test class\n"
            "- Create sequences in run_phase with objection handling\n"
            "- Include proper phase management\n"
            "- Report PASS/FAIL in report_phase\n"
        )
        return prompt

    def coverage_generation(self, description: str, context: str = "") -> str:
        prompt = (
            f"Generate a SystemVerilog covergroup based on this description:\n\n"
            f"DESCRIPTION: {description}\n\n"
        )
        if context:
            prompt += f"CONTEXT:\n{context}\n\n"
        prompt += (
            "Requirements:\n"
            "- Include meaningful coverpoints and cross coverage\n"
            "- Use bins with descriptive names\n"
            "- Add illegal_bins and ignore_bins where appropriate\n"
            "- Set option.per_instance = 1\n"
        )
        return prompt

    def refinement_prompt(self, code: str, issues: list[str]) -> str:
        return (
            f"The following SystemVerilog code has validation issues. "
            f"Fix them and return the corrected code.\n\n"
            f"CODE:\n```systemverilog\n{code}\n```\n\n"
            f"ISSUES:\n" + "\n".join(f"- {i}" for i in issues) + "\n\n"
            f"Return ONLY the fixed code in a ```systemverilog code block."
        )
