# Prompt Engineering Guide: Debug Analysis

## Overview

This guide covers prompt design for LLM-assisted simulation failure
analysis, root cause identification, and fix recommendation in ASIC
design verification workflows.

---

## 1. Debug Expert Persona System Prompt

```text
You are a senior ASIC Design Verification debug engineer with deep expertise
in UVM testbench architecture, SystemVerilog assertions, and AXI/AHB/APB
bus protocols. You specialize in root cause analysis of simulation failures.

When analyzing errors:
1. Identify the error category (RTL bug, testbench bug, environment issue,
   seed-sensitive failure, infrastructure problem)
2. Trace the causal chain from symptom to root cause
3. Suggest specific, actionable fixes with file/signal references
4. Rate your confidence level (0.0-1.0)

Output format:
- CATEGORY: <category>
- ROOT_CAUSE: <one-line summary>
- ANALYSIS: <detailed reasoning>
- FIX: <specific steps to resolve>
- CONFIDENCE: <0.0-1.0>
- SIGNALS_TO_CHECK: <comma-separated signal list>
```

---

## 2. Error Context Formatting Template

When sending simulation errors to an LLM for analysis, structure the
context to maximize signal-to-noise ratio:

### Template

```text
SIMULATION FAILURE REPORT
=========================

SIMULATOR: <VCS/Questa/Xcelium>
TEST NAME: <test_name>
SEED: <random_seed>
TOTAL SIM TIME: <time>

ERROR DETAILS:
  Severity:  <UVM_ERROR/UVM_FATAL/ASSERTION>
  Component: <reporting component path>
  Sim Time:  <timestamp when error occurred>
  Message:   <full error message>

CONTEXT (10 lines before error):
<pre-error log lines>

CONTEXT (10 lines after error):
<post-error log lines>

RECENT TRANSACTIONS:
<last 5 transactions from scoreboard/monitor if available>

COVERAGE STATE:
  Overall: <X%>
  Related groups: <coverage groups relevant to this test>

HISTORY:
  This test has <PASSED/FAILED> in <N> of last <M> runs.
  First failure seen: <date>
```

### Why This Format Works

- **Structured fields** make it easy for the LLM to extract key information
- **Context lines** provide temporal locality around the failure
- **Transaction history** helps identify protocol violations
- **Coverage state** suggests whether the failure is in well-tested logic
- **Run history** distinguishes deterministic bugs from flaky tests

---

## 3. Few-Shot Examples

### Example 1: Data Mismatch Error

**Input:**
```text
SIMULATION FAILURE REPORT
=========================

SIMULATOR: VCS 2023.03
TEST NAME: test_reg_access
SEED: 0x12345678

ERROR DETAILS:
  Severity:  UVM_ERROR
  Component: uvm_test_top.env.scoreboard
  Sim Time:  4500ns
  Message:   DATA MISMATCH addr=0x04 expected=0xA5A5A5A5 actual=0xA5A50000

CONTEXT (5 lines before):
  UVM_INFO @ 4400ns [monitor] AXI Write: addr=0x04 data=0xA5A5A5A5 strb=4'hF
  UVM_INFO @ 4420ns [monitor] Write response: OKAY
  UVM_INFO @ 4440ns [monitor] AXI Read: addr=0x04
  UVM_INFO @ 4460ns [driver] Driving read response
  UVM_INFO @ 4480ns [monitor] Read data: 0xA5A50000

CONTEXT (5 lines after):
  UVM_INFO @ 4520ns [scoreboard] Checking next transaction...
  UVM_INFO @ 4600ns [monitor] AXI Write: addr=0x08 data=0xDEADBEEF
```

**Expected LLM Output:**
```text
CATEGORY: rtl_bug
ROOT_CAUSE: Lower 16 bits of register at address 0x04 are not being stored
  correctly. Write data 0xA5A5A5A5 was acknowledged with OKAY response but
  readback returns 0xA5A50000, indicating bits [15:0] are stuck at zero.
ANALYSIS: The write transaction completed successfully (OKAY response) with
  full strobe (4'hF), meaning all byte lanes were enabled. The upper 16 bits
  (0xA5A5) are correct, but lower 16 bits read as 0x0000 instead of 0xA5A5.
  This pattern suggests either:
  (a) The register write enable for the lower half-word is not connected, or
  (b) A byte-lane routing issue in the register file for address 0x04.
FIX: Check RTL register file at address 0x04:
  1. Verify wr_en signal reaches bits [15:0] of the register
  2. Check wstrb decoding logic for byte lanes 0 and 1
  3. Review waveform for signals: reg_file[1].wr_en, s_axi_wstrb, s_axi_wdata
CONFIDENCE: 0.85
SIGNALS_TO_CHECK: s_axi_wdata, s_axi_wstrb, reg_wr_en[1], reg_file_0x04
```

### Example 2: Timeout Failure

**Input:**
```text
ERROR DETAILS:
  Severity:  UVM_FATAL
  Component: uvm_test_top.env.agent.driver
  Sim Time:  1000000ns
  Message:   TIMEOUT waiting for BVALID after 10000 cycles

CONTEXT (5 lines before):
  UVM_INFO @ 990000ns [driver] Driving AXI Write: addr=0xFF00 data=0x1
  UVM_INFO @ 990050ns [monitor] AWVALID asserted
  UVM_INFO @ 990100ns [monitor] WVALID asserted
  UVM_INFO @ 990150ns [monitor] AWREADY received
  -- no further activity --
```

**Expected LLM Output:**
```text
CATEGORY: rtl_bug
ROOT_CAUSE: DUT is not generating BVALID response for write to address
  0xFF00. The write address and data channels completed handshake but
  the write response channel is stuck.
ANALYSIS: Address 0xFF00 is likely outside the valid register map or
  hits a decode hole. The AW and W channels completed successfully
  (READY signals received), but no BVALID was ever asserted. This
  suggests the write response logic does not handle accesses to
  unmapped addresses - it should return DECERR/SLVERR instead of
  hanging. Alternatively, the write response FIFO may be full.
FIX:
  1. Check address decoder for 0xFF00 - is it mapped?
  2. Verify default slave response for unmapped addresses
  3. Check b_valid generation logic in RTL for edge cases
  4. Add assertion: a_bvalid_timeout to catch this earlier
CONFIDENCE: 0.75
SIGNALS_TO_CHECK: s_axi_bvalid, s_axi_bready, addr_decode_hit, b_fifo_full
```

---

## 4. Structured Output Format

Always request structured output from the LLM to enable automated
parsing and knowledge base storage:

```json
{
  "category": "rtl_bug | testbench_bug | environment_issue | seed_sensitive | infrastructure",
  "root_cause": "One-line summary of the root cause",
  "detailed_analysis": "Multi-sentence explanation of the causal chain",
  "suggested_fix": {
    "description": "What needs to change",
    "files_to_check": ["rtl/reg_file.sv", "tb/scoreboard.sv"],
    "signals_to_check": ["s_axi_wdata", "reg_wr_en"],
    "steps": [
      "Step 1: Check register write enable for addr 0x04",
      "Step 2: Verify wstrb decoding in axi_slave.sv line 142",
      "Step 3: Add assertion for write-readback consistency"
    ]
  },
  "confidence": 0.85,
  "is_flaky": false,
  "related_bugs": ["BUG-1234"]
}
```

### Confidence Level Guidelines

| Range | Meaning | Action |
|-------|---------|--------|
| 0.9-1.0 | Very high confidence, clear evidence | Apply fix directly |
| 0.7-0.9 | High confidence, likely correct | Review and apply |
| 0.5-0.7 | Medium confidence, needs verification | Investigate further |
| 0.3-0.5 | Low confidence, best guess | Manual debug required |
| 0.0-0.3 | Very low confidence | Insufficient information |

---

## 5. Advanced Techniques

### Multi-Turn Debug Dialogue

For complex failures, use a multi-turn approach:

1. **Turn 1**: Send error + context, get initial hypothesis
2. **Turn 2**: Send relevant waveform data, refine hypothesis
3. **Turn 3**: Send coverage data, finalize root cause
4. **Turn 4**: Request specific fix with code diff

### Differential Analysis Prompt

When a test is flaky (sometimes passes, sometimes fails):

```text
This test is FLAKY. It passes with seed 0x1111 but fails with seed 0x2222.

PASSING RUN KEY EVENTS:
<transactions from passing run>

FAILING RUN KEY EVENTS:
<transactions from failing run>

What is different between the two runs that causes the failure?
Focus on ordering, timing, and randomized values.
```
