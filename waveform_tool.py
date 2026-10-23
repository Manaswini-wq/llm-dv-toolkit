"""MCP tool for VCD waveform analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class VCDParser:
    """Minimal VCD (Value Change Dump) parser for signal extraction."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._signals: dict[str, str] = {}  # code -> signal_path
        self._values: dict[str, list[tuple[int, str]]] = {}  # signal -> [(time, value)]
        self._parse()

    def _parse(self) -> None:
        """Parse VCD file for signal definitions and value changes."""
        content = self.path.read_text(errors="replace")
        current_scope: list[str] = []
        in_definitions = True
        current_time = 0

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("$scope"):
                parts = line.split()
                if len(parts) >= 3:
                    current_scope.append(parts[2])
            elif line.startswith("$upscope"):
                if current_scope:
                    current_scope.pop()
            elif line.startswith("$var"):
                parts = line.split()
                if len(parts) >= 5:
                    code = parts[3]
                    name = parts[4]
                    full_path = ".".join(current_scope + [name])
                    self._signals[code] = full_path
                    self._values[full_path] = []
            elif line.startswith("$enddefinitions"):
                in_definitions = False
            elif not in_definitions:
                if line.startswith("#"):
                    current_time = int(line[1:])
                elif len(line) >= 2 and line[0] in "01xzXZ":
                    value = line[0]
                    code = line[1:]
                    if code in self._signals:
                        sig = self._signals[code]
                        self._values[sig].append((current_time, value))
                elif line.startswith("b"):
                    parts = line.split()
                    if len(parts) >= 2:
                        value = parts[0][1:]
                        code = parts[1]
                        if code in self._signals:
                            sig = self._signals[code]
                            self._values[sig].append((current_time, value))

    def get_signal(self, path: str) -> list[tuple[int, str]]:
        """Get all value changes for a signal."""
        if path in self._values:
            return self._values[path]
        # Fuzzy match
        for sig, vals in self._values.items():
            if sig.endswith(path) or path in sig:
                return vals
        return []

    def list_signals(self) -> list[str]:
        """List all signal paths."""
        return list(self._values.keys())


class WaveformTool:
    """MCP tool for waveform signal analysis."""

    _cache: dict[str, VCDParser] = {}

    def _get_parser(self, vcd_path: str) -> VCDParser:
        if vcd_path not in self._cache:
            path = Path(vcd_path)
            if not path.exists():
                raise FileNotFoundError(f"VCD file not found: {vcd_path}")
            self._cache[vcd_path] = VCDParser(path)
        return self._cache[vcd_path]

    def get_signal_values(
        self, vcd_path: str, signal_path: str,
        start_time: int = 0, end_time: int = -1,
    ) -> dict[str, Any]:
        """Extract signal values within a time range."""
        try:
            parser = self._get_parser(vcd_path)
            values = parser.get_signal(signal_path)

            if end_time >= 0:
                values = [(t, v) for t, v in values if start_time <= t <= end_time]
            elif start_time > 0:
                values = [(t, v) for t, v in values if t >= start_time]

            return {
                "signal": signal_path,
                "num_transitions": len(values),
                "values": [{"time": t, "value": v} for t, v in values[:1000]],
                "truncated": len(values) > 1000,
            }
        except Exception as e:
            return {"error": str(e)}

    def find_transitions(
        self, vcd_path: str, signal_path: str, target_value: str,
    ) -> dict[str, Any]:
        """Find times when signal transitions to target value."""
        try:
            parser = self._get_parser(vcd_path)
            values = parser.get_signal(signal_path)

            transitions = [t for t, v in values if v == target_value]
            return {
                "signal": signal_path,
                "target_value": target_value,
                "num_transitions": len(transitions),
                "times": transitions[:500],
            }
        except Exception as e:
            return {"error": str(e)}

    def compare_signals(
        self, vcd_path: str, signal1: str, signal2: str,
        start_time: int = 0, end_time: int = -1,
    ) -> dict[str, Any]:
        """Compare two signals for mismatches."""
        try:
            parser = self._get_parser(vcd_path)
            vals1 = dict(parser.get_signal(signal1))
            vals2 = dict(parser.get_signal(signal2))

            all_times = sorted(set(vals1.keys()) | set(vals2.keys()))
            if end_time >= 0:
                all_times = [t for t in all_times if start_time <= t <= end_time]

            mismatches: list[dict[str, Any]] = []
            v1, v2 = "x", "x"
            for t in all_times:
                v1 = vals1.get(t, v1)
                v2 = vals2.get(t, v2)
                if v1 != v2:
                    mismatches.append({"time": t, "signal1": v1, "signal2": v2})

            return {
                "signal1": signal1, "signal2": signal2,
                "total_mismatches": len(mismatches),
                "mismatches": mismatches[:100],
            }
        except Exception as e:
            return {"error": str(e)}
