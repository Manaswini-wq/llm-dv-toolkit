"""MCP tool for regression status queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RegressionTool:
    """Query regression results from JSON result files."""

    def __init__(self, results_dir: Path) -> None:
        self.results_dir = results_dir

    def _load_latest(self) -> dict[str, Any] | None:
        """Load the most recent regression results file."""
        if not self.results_dir.exists():
            return None
        files = sorted(self.results_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return None
        return json.loads(files[0].read_text())

    def get_status(self) -> dict[str, Any]:
        """Get current regression summary."""
        data = self._load_latest()
        if not data:
            return {"error": "No regression results found", "status": "unknown"}

        return {
            "project": data.get("project_name", ""),
            "total_tests": data.get("total_tests", 0),
            "passed": data.get("passed", 0),
            "failed": data.get("failed", 0),
            "pass_rate": data.get("pass_rate", 0),
            "status": "PASS" if data.get("failed", 0) == 0 else "FAIL",
        }

    def get_failing_tests(self) -> dict[str, Any]:
        """List all failing tests with details."""
        data = self._load_latest()
        if not data:
            return {"error": "No regression results found", "failures": []}

        failures = [
            {
                "test_name": t.get("test_name", ""),
                "seed": t.get("seed", 0),
                "status": t.get("status", ""),
                "error": t.get("error_message", ""),
                "sim_time": t.get("sim_time_seconds", 0),
            }
            for t in data.get("tests", [])
            if t.get("status") != "PASS"
        ]
        return {
            "total_failures": len(failures),
            "failures": failures,
        }

    def get_test_history(self, test_name: str) -> dict[str, Any]:
        """Get historical results for a specific test across runs."""
        if not self.results_dir.exists():
            return {"error": "No regression results found", "history": []}

        history: list[dict[str, Any]] = []
        for f in sorted(self.results_dir.glob("*.json")):
            data = json.loads(f.read_text())
            for t in data.get("tests", []):
                if t.get("test_name") == test_name:
                    history.append({
                        "run_file": f.name,
                        "status": t.get("status", ""),
                        "seed": t.get("seed", 0),
                        "error": t.get("error_message", ""),
                    })

        pass_count = sum(1 for h in history if h["status"] == "PASS")
        return {
            "test_name": test_name,
            "total_runs": len(history),
            "pass_count": pass_count,
            "fail_count": len(history) - pass_count,
            "flaky": 0 < pass_count < len(history),
            "history": history[-20:],  # Last 20 entries
        }
