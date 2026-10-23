"""LLM-powered simulation log analyzer for root cause identification."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ErrorEntry:
    """Single error extracted from simulation log."""
    severity: str  # ERROR, FATAL, ASSERTION, CRASH
    message: str
    source: str = ""  # Component that reported the error
    timestamp: str = ""  # Simulation time
    context_before: list[str] = field(default_factory=list)
    context_after: list[str] = field(default_factory=list)
    line_number: int = 0

    @property
    def fingerprint(self) -> str:
        """Unique hash for dedup/caching."""
        return hashlib.md5(f"{self.severity}:{self.message}".encode()).hexdigest()[:12]


@dataclass
class ErrorAnalysis:
    """LLM analysis result for an error."""
    error: ErrorEntry
    category: str = ""  # rtl_bug, tb_bug, env_issue, seed_sensitive, infra
    root_cause: str = ""
    suggested_fix: str = ""
    confidence: float = 0.0
    related_signals: list[str] = field(default_factory=list)


_ERROR_PATTERNS = {
    "uvm_error": re.compile(r"UVM_ERROR\s+(?:@\s*(\d+(?:\.\d+)?\s*\w*)\s*:?\s*)?(\[?\w+[\].]*)?\s*:?\s*(.*)"),
    "uvm_fatal": re.compile(r"UVM_FATAL\s+(?:@\s*(\d+(?:\.\d+)?\s*\w*)\s*:?\s*)?(\[?\w+[\].]*)?\s*:?\s*(.*)"),
    "assertion": re.compile(r"(?:Assertion|SVA)\s+(?:error|failure).*?:\s*(.*)"),
    "mismatch": re.compile(r"(?:MISMATCH|mismatch).*?(?:exp(?:ected)?[=:]\s*(?:0x)?[\da-fA-F]+).*?(?:got|act(?:ual)?)[=:]\s*(?:0x)?[\da-fA-F]+"),
    "timeout": re.compile(r"(?:TIMEOUT|timeout|Watchdog)"),
    "segfault": re.compile(r"Segmentation fault|SIGSEGV|core dumped"),
}


class LogParser:
    """Parse simulation logs from various simulator formats."""

    def __init__(self, context_lines: int = 10) -> None:
        self.context_lines = context_lines

    def parse(self, log_path: Path) -> list[ErrorEntry]:
        """Parse log file and extract all errors."""
        if not log_path.exists():
            return [ErrorEntry(severity="ERROR", message=f"Log not found: {log_path}")]

        lines = log_path.read_text(errors="replace").splitlines()
        errors: list[ErrorEntry] = []

        for i, line in enumerate(lines):
            for pat_name, pattern in _ERROR_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    entry = ErrorEntry(
                        severity=self._severity_from_pattern(pat_name),
                        message=match.group(0).strip(),
                        source=match.group(2).strip("[]") if match.lastindex and match.lastindex >= 2 else "",
                        timestamp=match.group(1) if match.lastindex and match.lastindex >= 1 else "",
                        line_number=i + 1,
                        context_before=lines[max(0, i - self.context_lines):i],
                        context_after=lines[i + 1:i + 1 + self.context_lines],
                    )
                    errors.append(entry)
                    break  # Only first matching pattern per line

        return errors

    def _severity_from_pattern(self, pat_name: str) -> str:
        mapping = {
            "uvm_error": "ERROR", "uvm_fatal": "FATAL",
            "assertion": "ASSERTION", "mismatch": "ERROR",
            "timeout": "FATAL", "segfault": "CRASH",
        }
        return mapping.get(pat_name, "ERROR")


class LogAnalyzer:
    """Analyze simulation logs using LLM for root cause identification."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.parser = LogParser()
        self._cache: dict[str, ErrorAnalysis] = {}

    async def analyze(self, log_path: Path) -> list[ErrorAnalysis]:
        """Analyze all errors in a log file."""
        errors = self.parser.parse(log_path)
        analyses: list[ErrorAnalysis] = []

        for error in errors:
            # Check cache first
            if error.fingerprint in self._cache:
                analyses.append(self._cache[error.fingerprint])
                continue

            analysis = await self._analyze_single(error)
            self._cache[error.fingerprint] = analysis
            analyses.append(analysis)

        return analyses

    async def _analyze_single(self, error: ErrorEntry) -> ErrorAnalysis:
        """Analyze a single error using LLM."""
        context = self._build_context(error)

        # For now return rule-based analysis; LLM integration follows same pattern as test_generator
        analysis = self._rule_based_analysis(error)

        return analysis

    def _build_context(self, error: ErrorEntry) -> str:
        """Build context string for LLM prompt."""
        parts = [
            f"SEVERITY: {error.severity}",
            f"MESSAGE: {error.message}",
            f"SOURCE: {error.source}",
            f"TIME: {error.timestamp}",
            "\nCONTEXT BEFORE:",
            "\n".join(error.context_before[-5:]),
            "\nERROR LINE:",
            error.message,
            "\nCONTEXT AFTER:",
            "\n".join(error.context_after[:5]),
        ]
        return "\n".join(parts)

    def _rule_based_analysis(self, error: ErrorEntry) -> ErrorAnalysis:
        """Quick rule-based classification (fallback when LLM unavailable)."""
        msg_lower = error.message.lower()

        if "mismatch" in msg_lower or "expected" in msg_lower:
            return ErrorAnalysis(
                error=error,
                category="rtl_bug",
                root_cause="Data mismatch between DUT output and expected value from reference model",
                suggested_fix="Compare RTL waveforms at the reported timestamp against reference model. Check data path logic and pipeline stages.",
                confidence=0.7,
                related_signals=self._extract_signals(error.message),
            )
        elif "timeout" in msg_lower:
            return ErrorAnalysis(
                error=error, category="env_issue",
                root_cause="Simulation hung - possible deadlock or missing handshake",
                suggested_fix="Check for missing valid/ready handshakes. Verify DUT is not stuck waiting for a stimulus that was never driven.",
                confidence=0.6,
            )
        elif "assertion" in msg_lower or "sva" in msg_lower:
            return ErrorAnalysis(
                error=error, category="rtl_bug",
                root_cause="Protocol assertion violation",
                suggested_fix="Review the assertion specification and check waveform for protocol violation at reported time.",
                confidence=0.8,
            )
        else:
            return ErrorAnalysis(
                error=error, category="unknown",
                root_cause="Unable to classify automatically",
                suggested_fix="Manual investigation required. Check waveforms at reported timestamp.",
                confidence=0.3,
            )

    def _extract_signals(self, message: str) -> list[str]:
        """Extract signal-like names from error message."""
        return re.findall(r"\b(?:s_axi_|axi_|dut\.)\w+", message)
