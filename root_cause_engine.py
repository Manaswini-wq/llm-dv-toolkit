"""Root cause analysis engine combining log, waveform, and coverage data."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm_dv_toolkit.debug_assistant.log_analyzer import LogAnalyzer, ErrorEntry, ErrorAnalysis
from llm_dv_toolkit.debug_assistant.failure_classifier import FailureClassifier, FailureCategory


@dataclass
class DebugStep:
    """Single step in the debug reasoning chain."""
    step_number: int
    action: str
    finding: str
    confidence: float = 0.0


@dataclass
class RootCauseAnalysis:
    """Complete root cause analysis result."""
    error: ErrorEntry
    category: FailureCategory
    root_cause: str
    suggested_fix: str
    confidence: float
    reasoning_chain: list[DebugStep] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    related_signals: list[str] = field(default_factory=list)


class RootCauseEngine:
    """Multi-step root cause analysis engine.

    Combines:
    1. Log analysis (error extraction and context)
    2. Failure classification (pattern matching against knowledge base)
    3. Waveform data (signal values at error time)
    4. Coverage data (related uncovered scenarios)
    5. Chain-of-thought LLM reasoning for complex bugs
    """

    def __init__(self, config: Any, kb_path: Path | None = None) -> None:
        self.analyzer = LogAnalyzer(config)
        self.classifier = FailureClassifier(kb_path)

    async def analyze(self, log_path: Path, vcd_path: Path | None = None) -> list[RootCauseAnalysis]:
        """Perform full root cause analysis on a simulation failure."""
        # Step 1: Extract errors from log
        log_analyses = await self.analyzer.analyze(log_path)

        results: list[RootCauseAnalysis] = []
        for analysis in log_analyses:
            rca = await self._analyze_error(analysis, vcd_path)
            results.append(rca)

        return results

    async def _analyze_error(
        self, analysis: ErrorAnalysis, vcd_path: Path | None,
    ) -> RootCauseAnalysis:
        """Analyze a single error through the full debug pipeline."""
        steps: list[DebugStep] = []
        evidence: list[str] = []

        # Step 1: Classify the failure
        classification = self.classifier.classify(analysis.error.message)
        steps.append(DebugStep(
            step_number=1,
            action="Failure Classification",
            finding=f"Category: {classification.category.value} (confidence: {classification.confidence:.2f})",
            confidence=classification.confidence,
        ))

        if classification.similar_failures:
            evidence.append(f"Similar past failure: {classification.similar_failures[0].get('message', '')}")
            steps.append(DebugStep(
                step_number=2,
                action="Knowledge Base Lookup",
                finding=f"Found {len(classification.similar_failures)} similar past failures",
                confidence=classification.confidence,
            ))

        # Step 2: Analyze error context
        context_finding = self._analyze_context(analysis.error)
        steps.append(DebugStep(
            step_number=len(steps) + 1,
            action="Context Analysis",
            finding=context_finding,
            confidence=0.5,
        ))

        # Step 3: Determine root cause
        root_cause = classification.resolution or analysis.root_cause or "Manual investigation required"
        suggested_fix = analysis.suggested_fix or "Review waveforms at the reported timestamp"

        overall_confidence = min(
            (classification.confidence + analysis.confidence) / 2, 1.0
        )

        return RootCauseAnalysis(
            error=analysis.error,
            category=classification.category,
            root_cause=root_cause,
            suggested_fix=suggested_fix,
            confidence=overall_confidence,
            reasoning_chain=steps,
            evidence=evidence,
            related_signals=analysis.related_signals,
        )

    def _analyze_context(self, error: ErrorEntry) -> str:
        """Analyze the context lines around an error."""
        context = error.context_before + error.context_after
        context_text = " ".join(context).lower()

        findings: list[str] = []
        if "reset" in context_text:
            findings.append("Reset activity detected near error")
        if "timeout" in context_text:
            findings.append("Timeout conditions present in context")
        if "phase" in context_text:
            findings.append("UVM phase transition near error")

        return "; ".join(findings) if findings else "No additional context patterns found"
