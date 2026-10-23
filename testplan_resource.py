"""MCP resource for test plan access."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class TestPlanResource:
    """Expose test plan as MCP resource."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def _find_testplan(self) -> Path | None:
        """Find test plan YAML in project."""
        for pattern in ["testplan.yaml", "testplan.yml", "docs/testplan.yaml", "docs/test_plan.yaml"]:
            p = self.project_root / pattern
            if p.exists():
                return p
        return None

    def list_resources(self) -> list[dict[str, Any]]:
        """List available test plan resources."""
        resources = []
        tp = self._find_testplan()
        if tp:
            resources.append({
                "uri": f"testplan:///{tp.name}",
                "name": "Verification Test Plan",
                "description": "Project test plan with features, items, and status",
                "mimeType": "application/yaml",
            })
        return resources

    def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a test plan resource by URI."""
        tp = self._find_testplan()
        if not tp:
            return {"uri": uri, "mimeType": "text/plain", "text": "No test plan found"}

        content = yaml.safe_load(tp.read_text())

        # Compute metrics
        items = []
        for feat in content.get("features", []):
            items.extend(feat.get("items", []))
            for sf in feat.get("sub_features", []):
                items.extend(sf.get("items", []))

        total = len(items)
        done = sum(1 for i in items if i.get("status") == "Done")

        summary = {
            "project": content.get("project", ""),
            "total_items": total,
            "completed": done,
            "completion_pct": round(done / total * 100, 1) if total > 0 else 0,
            "content": content,
        }

        return {
            "uri": uri,
            "mimeType": "application/json",
            "text": str(summary),
        }
