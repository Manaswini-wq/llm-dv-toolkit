"""Tests for MCP server module."""

import json
import sqlite3
from pathlib import Path

import pytest

from llm_dv_toolkit.mcp_server.tools.coverage_tool import CoverageTool
from llm_dv_toolkit.mcp_server.tools.regression_tool import RegressionTool
from llm_dv_toolkit.mcp_server.tools.waveform_tool import VCDParser, WaveformTool


@pytest.fixture
def coverage_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_cov.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE coverage_runs (id INTEGER PRIMARY KEY, timestamp TEXT, commit_hash TEXT, test_name TEXT, overall_pct REAL);
        CREATE TABLE coverage_groups (id INTEGER PRIMARY KEY, run_id INTEGER, group_name TEXT, coverage_pct REAL);
        CREATE TABLE coverage_bins (id INTEGER PRIMARY KEY, group_id INTEGER, item_name TEXT, bin_name TEXT, hits INTEGER, goal INTEGER);
        INSERT INTO coverage_runs VALUES (1, '2024-01-01', 'abc123', 'test1', 85.0);
        INSERT INTO coverage_groups VALUES (1, 1, 'cg_axi', 90.0);
        INSERT INTO coverage_groups VALUES (2, 1, 'cg_err', 80.0);
        INSERT INTO coverage_bins VALUES (1, 1, 'cp_addr', 'reg0', 10, 1);
        INSERT INTO coverage_bins VALUES (2, 1, 'cp_addr', 'reg1', 0, 1);
    """)
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def regression_dir(tmp_path: Path) -> Path:
    d = tmp_path / "results"
    d.mkdir()
    data = {
        "project_name": "test", "total_tests": 10, "passed": 9, "failed": 1,
        "pass_rate": 90.0,
        "tests": [
            {"test_name": "test_pass", "seed": 1, "status": "PASS", "error_message": ""},
            {"test_name": "test_fail", "seed": 1, "status": "FAIL", "error_message": "Data mismatch"},
        ]
    }
    (d / "run_001.json").write_text(json.dumps(data))
    return d


def test_coverage_query(coverage_db: Path):
    tool = CoverageTool(coverage_db)
    result = tool.query_coverage()
    assert result["num_groups"] == 2
    assert result["overall_coverage"] > 0


def test_coverage_holes(coverage_db: Path):
    tool = CoverageTool(coverage_db)
    result = tool.get_holes()
    assert result["total_holes"] >= 1
    assert any(h["bin"] == "reg1" for h in result["holes"])


def test_regression_status(regression_dir: Path):
    tool = RegressionTool(regression_dir)
    result = tool.get_status()
    assert result["total_tests"] == 10
    assert result["status"] == "FAIL"


def test_regression_failing(regression_dir: Path):
    tool = RegressionTool(regression_dir)
    result = tool.get_failing_tests()
    assert result["total_failures"] == 1
    assert result["failures"][0]["test_name"] == "test_fail"


def test_vcd_parser(tmp_path: Path):
    vcd_content = """$timescale 1ns $end
$scope module top $end
$var wire 1 ! clk $end
$var wire 1 " data $end
$upscope $end
$enddefinitions $end
#0
0!
0"
#10
1!
1"
#20
0!
#30
1!
0"
"""
    vcd = tmp_path / "test.vcd"
    vcd.write_text(vcd_content)
    parser = VCDParser(vcd)
    signals = parser.list_signals()
    assert len(signals) == 2

    clk_vals = parser.get_signal("clk")
    assert len(clk_vals) >= 3


def test_waveform_tool(tmp_path: Path):
    vcd_content = """$timescale 1ns $end
$scope module tb $end
$var wire 1 A valid $end
$upscope $end
$enddefinitions $end
#0
0A
#100
1A
#200
0A
"""
    vcd = tmp_path / "test.vcd"
    vcd.write_text(vcd_content)

    tool = WaveformTool()
    result = tool.get_signal_values(str(vcd), "valid")
    assert result["num_transitions"] == 3

    result = tool.find_transitions(str(vcd), "valid", "1")
    assert 100 in result["times"]
