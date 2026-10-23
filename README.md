# LLM-DV Toolkit: AI-Powered Design Verification

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)
![MCP Protocol](https://img.shields.io/badge/MCP-2024--11--05-purple)

**Integrate Large Language Models into your ASIC/FPGA verification workflows.**

LLM-DV Toolkit bridges the gap between AI assistants and hardware verification
by exposing coverage databases, regression results, waveform data, and test
plans to LLM agents via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).
It also provides LLM-powered UVM test generation and intelligent failure analysis.

---

## Features

- **MCP Server** -- Expose coverage, regression, and waveform tools to LLM agents (Claude Desktop, Devin, Cursor, etc.)
- **LLM-Based Test Generation** -- Generate UVM sequences, tests, and covergroups from natural language descriptions
- **AI-Powered Debug Assistant** -- Automatic failure classification, root cause analysis, and fix suggestions
- **Embedding-Based Knowledge Base** -- Learn from past failures to accelerate future debugging
- **VCD Waveform Parser** -- Extract and analyze signal values from Value Change Dump files
- **SystemVerilog Validator** -- Catch common LLM code generation errors before compilation

---

## Architecture

```
                          +------------------+
                          |   LLM Agent      |
                          | (Claude/GPT/etc) |
                          +--------+---------+
                                   |
                            MCP Protocol
                          (JSON-RPC / stdio)
                                   |
                    +--------------+--------------+
                    |    MCP Server               |
                    |  dv-verification-toolkit    |
                    +-+----------+----------+---+-+
                      |          |          |   |
               +------+--+ +----+----+ +---+---+---+ +----------+
               | Coverage | |Regression| | Waveform | | TestPlan |
               |   Tool   | |  Tool    | |   Tool   | | Resource |
               +------+---+ +----+----+ +---+------+ +----+-----+
                      |          |           |             |
                 +----+---+ +---+------+ +--+-----+ +----+------+
                 |Coverage| |Regression| |  VCD   | | testplan  |
                 |  .db   | | .json    | | files  | |  .yaml    |
                 +--------+ +----------+ +--------+ +-----------+
```

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repo-url> llm_dv_toolkit
cd llm_dv_toolkit

# Install in development mode
pip install -e ".[dev]"
```

### Environment Variables

```bash
export LLM_PROVIDER=openai          # or "anthropic"
export LLM_MODEL=gpt-4             # or "claude-3-5-sonnet-20241022"
export OPENAI_API_KEY=sk-...       # your API key
export DV_PROJECT_ROOT=/path/to/dv/project
export COVERAGE_DB=/path/to/coverage.db
export REGRESSION_DIR=/path/to/regression_results
```

### Generate a UVM Test

```bash
llm-dv generate
```

```python
import asyncio
from llm_dv_toolkit.test_generator.generator import TestGenerator
from llm_dv_toolkit.utils.config import Config

async def main():
    gen = TestGenerator(Config.from_env())
    result = await gen.generate(
        "Write a sequence that performs write-then-read-back "
        "on registers 0-15 using walking 1s pattern",
        gen_type="sequence",
    )
    print(result.code)

asyncio.run(main())
```

### Analyze a Simulation Failure

```python
import asyncio
from pathlib import Path
from llm_dv_toolkit.debug_assistant.root_cause_engine import RootCauseEngine
from llm_dv_toolkit.utils.config import Config

async def main():
    engine = RootCauseEngine(Config.from_env())
    analyses = await engine.analyze(Path("sim.log"))
    for rca in analyses:
        print(f"[{rca.category.value}] {rca.root_cause}")
        print(f"  Fix: {rca.suggested_fix}")

asyncio.run(main())
```

---

## MCP Server Setup

### Claude Desktop

Add to your Claude Desktop MCP configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dv-verification-toolkit": {
      "command": "python",
      "args": ["-m", "llm_dv_toolkit.mcp_server.server"],
      "env": {
        "DV_PROJECT_ROOT": "/path/to/your/project",
        "COVERAGE_DB": "/path/to/coverage.db",
        "REGRESSION_DIR": "/path/to/regression_results"
      }
    }
  }
}
```

### Devin / Cursor / Other MCP Clients

Use the provided `mcp_config.json` file or start the server manually:

```bash
llm-dv-mcp
# or
python -m llm_dv_toolkit.mcp_server.server
```

---

## Tool Reference

### MCP Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `query_coverage` | Query functional coverage data by group name | `group_name`, `threshold` |
| `get_coverage_holes` | Find all uncovered bins (0 hits) across coverage groups | -- |
| `get_regression_status` | Get pass/fail summary of latest regression run | -- |
| `get_failing_tests` | List all failing tests with error messages | -- |
| `get_test_history` | Get pass/fail history for a specific test (flaky detection) | `test_name` |
| `get_signal_values` | Extract signal value changes from VCD waveform | `vcd_path`, `signal_path`, `start_time`, `end_time` |
| `find_signal_transitions` | Find timestamps when a signal hits a target value | `vcd_path`, `signal_path`, `target_value` |

### MCP Resources

| Resource | Description |
|----------|-------------|
| `testplan:///testplan.yaml` | Verification test plan with completion metrics |

---

## Example Output

### Test Generation

```
--- Test 1: Write a sequence that performs write-then-read-back... ---
Status: PASS
Tokens: 100, Iterations: 1
Time: 0.1s

class generated_seq extends uvm_sequence #(axi4_lite_seq_item);
    `uvm_object_utils(generated_seq)
    function new(string name = "generated_seq");
        super.new(name);
    endfunction
    task body();
        `uvm_info(get_type_name(), "Running generated test", UVM_MEDIUM)
    endtask
endclass
```

### Debug Analysis

```
Found 2 errors in log

  [ERROR] DATA MISMATCH addr=0x04 expected=0xA5A5A5A5 actual=0xA5A50000
  [ASSERTION] a_wvalid_stable at time 4520ns

--- Root Cause Analysis ---

  Error: DATA MISMATCH addr=0x04 expected=0xA5A5A5A5 actual=0xA5A50000
  Category: rtl_bug
  Root Cause: Data mismatch between DUT output and expected value
  Fix: Compare RTL waveforms at the reported timestamp against reference model
  Confidence: 0.55
  Reasoning:
    1. Failure Classification: Category: rtl_bug (confidence: 0.40)
    2. Context Analysis: No additional context patterns found
```

---

## Prompt Engineering Documentation

Detailed guides for crafting effective prompts for each use case:

| Guide | Description |
|-------|-------------|
| [`prompts/test_generation.md`](prompts/test_generation.md) | System prompts, few-shot examples, and temperature settings for UVM code generation |
| [`prompts/debug_analysis.md`](prompts/debug_analysis.md) | Error context formatting, root cause analysis prompts, structured output |
| [`prompts/coverage_review.md`](prompts/coverage_review.md) | Coverage hole analysis, test suggestion prompts, closure strategies |

---

## Project Structure

```
llm_dv_toolkit/
+-- llm_dv_toolkit/             # Main package
|   +-- __init__.py
|   +-- __main__.py             # CLI entry point
|   +-- utils/
|   |   +-- config.py           # Configuration management
|   +-- mcp_server/
|   |   +-- server.py           # MCP JSON-RPC server
|   |   +-- tools/
|   |   |   +-- coverage_tool.py    # Coverage DB queries
|   |   |   +-- regression_tool.py  # Regression result queries
|   |   |   +-- waveform_tool.py    # VCD waveform analysis
|   |   +-- resources/
|   |       +-- testplan_resource.py # Test plan resource
|   +-- test_generator/
|   |   +-- generator.py        # LLM-based test generation
|   |   +-- prompt_templates.py # Prompt templates
|   |   +-- sv_parser.py        # SystemVerilog validator
|   +-- debug_assistant/
|       +-- log_analyzer.py     # Log parsing and analysis
|       +-- failure_classifier.py   # Embedding-based classifier
|       +-- root_cause_engine.py    # Multi-step RCA engine
+-- prompts/                    # Prompt engineering guides
+-- examples/                   # Usage examples
|   +-- sample_logs/            # Sample simulation logs
+-- tests/                      # Test suite
+-- pyproject.toml              # Project metadata
+-- mcp_config.json             # MCP server configuration
+-- README.md
```

---

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --tb=short
```

---

## License

MIT License

Copyright (c) 2025 DV Engineering

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
