"""Simple SystemVerilog validator for LLM output validation."""

from __future__ import annotations

import re


class SVValidator:
    """Validate basic SystemVerilog syntax in LLM-generated code."""

    def validate(self, code: str) -> list[str]:
        """Run all validation checks and return list of issues."""
        issues: list[str] = []
        issues.extend(self._check_balanced_blocks(code))
        issues.extend(self._check_uvm_macros(code))
        issues.extend(self._check_semicolons(code))
        issues.extend(self._check_common_errors(code))
        return issues

    def _check_balanced_blocks(self, code: str) -> list[str]:
        """Check for balanced begin/end, class/endclass, etc."""
        issues: list[str] = []
        pairs = [
            ("begin", "end"),
            ("class", "endclass"),
            ("module", "endmodule"),
            ("function", "endfunction"),
            ("task", "endtask"),
            ("package", "endpackage"),
        ]
        for opener, closer in pairs:
            # Count whole-word occurrences
            open_count = len(re.findall(rf"\b{opener}\b", code))
            close_count = len(re.findall(rf"\b{closer}\b", code))
            if open_count != close_count:
                issues.append(
                    f"Unbalanced {opener}/{closer}: {open_count} opens vs {close_count} closes"
                )
        return issues

    def _check_uvm_macros(self, code: str) -> list[str]:
        """Check for proper UVM macro usage."""
        issues: list[str] = []
        if re.search(r"\bclass\b.*\bextends\b.*\buvm_", code):
            has_utils = bool(re.search(r"`uvm_(object|component)_utils", code))
            if not has_utils:
                issues.append("UVM class missing `uvm_object_utils or `uvm_component_utils")
        return issues

    def _check_semicolons(self, code: str) -> list[str]:
        """Check for missing semicolons on likely statement lines."""
        issues: list[str] = []
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("`"):
                continue
            # Lines that should end with semicolons
            if re.match(r"^\s*(input|output|logic|bit|int|string|rand)\s+", line):
                if not stripped.endswith(";") and not stripped.endswith(","):
                    issues.append(f"Line {i}: possible missing semicolon: '{stripped[:60]}'")
        return issues

    def _check_common_errors(self, code: str) -> list[str]:
        """Detect common LLM code generation errors."""
        issues: list[str] = []
        # Check for Python-style syntax leaking in
        if "def " in code and "endfunction" not in code:
            issues.append("Possible Python syntax detected ('def' keyword)")
        if "self." in code:
            issues.append("Python 'self.' detected - use 'this.' in SystemVerilog")
        if re.search(r"\bprint\s*\(", code):
            issues.append("Python print() detected - use $display or `uvm_info")
        # Brackets
        if code.count("(") != code.count(")"):
            issues.append(f"Unbalanced parentheses: {code.count('(')} open vs {code.count(')')} close")
        return issues

    def extract_classes(self, code: str) -> list[str]:
        """Extract class names from code."""
        return re.findall(r"\bclass\s+(\w+)", code)

    def extract_functions(self, code: str) -> list[tuple[str, str]]:
        """Extract function/task signatures: [(type, name), ...]."""
        results: list[tuple[str, str]] = []
        for match in re.finditer(r"\b(function|task)\b.*?\b(\w+)\s*[\(;]", code):
            results.append((match.group(1), match.group(2)))
        return results
