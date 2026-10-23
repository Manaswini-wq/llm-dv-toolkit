"""MCP tool for coverage queries against SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class CoverageTool:
    """Query coverage data from SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def query_coverage(self, group_name: str = "", threshold: float = 0.0) -> dict[str, Any]:
        """Query coverage by group name and threshold.

        Returns coverage groups matching the filter criteria with
        their coverage percentages and bin details.
        """
        if not self.db_path.exists():
            return {"error": "Coverage database not found", "groups": []}

        conn = self._get_conn()
        try:
            if group_name:
                rows = conn.execute(
                    "SELECT group_name, coverage_pct FROM coverage_groups WHERE group_name LIKE ? AND coverage_pct >= ?",
                    (f"%{group_name}%", threshold),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT group_name, coverage_pct FROM coverage_groups WHERE coverage_pct >= ?",
                    (threshold,),
                ).fetchall()

            groups = [{"name": r[0], "coverage_pct": r[1]} for r in rows]

            overall = sum(g["coverage_pct"] for g in groups) / max(len(groups), 1)
            return {
                "overall_coverage": round(overall, 2),
                "num_groups": len(groups),
                "groups": groups,
            }
        finally:
            conn.close()

    def get_holes(self) -> dict[str, Any]:
        """Find all coverage bins with zero hits."""
        if not self.db_path.exists():
            return {"error": "Coverage database not found", "holes": []}

        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT cg.group_name, cb.item_name, cb.bin_name
                FROM coverage_bins cb
                JOIN coverage_groups cg ON cb.group_id = cg.id
                WHERE cb.hits = 0
                ORDER BY cg.group_name, cb.item_name
            """).fetchall()

            holes = [{"group": r[0], "item": r[1], "bin": r[2]} for r in rows]
            return {
                "total_holes": len(holes),
                "holes": holes,
                "recommendation": f"Found {len(holes)} uncovered bins. Consider adding targeted tests.",
            }
        finally:
            conn.close()

    def get_trend(self, days: int = 30) -> dict[str, Any]:
        """Get coverage trend over time."""
        if not self.db_path.exists():
            return {"error": "Coverage database not found", "trend": []}

        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT timestamp, overall_pct FROM coverage_runs
                ORDER BY timestamp DESC LIMIT ?
            """, (days,)).fetchall()
            return {
                "data_points": len(rows),
                "trend": [{"timestamp": r[0], "coverage_pct": r[1]} for r in reversed(rows)],
            }
        finally:
            conn.close()
