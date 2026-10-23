# Prompt Engineering Guide: Coverage Analysis

## Overview

This guide covers prompt design for LLM-assisted functional coverage
analysis, including identifying coverage holes, suggesting targeted
tests, and optimizing coverage closure strategies.

---

## 1. Coverage Expert Persona

```text
You are an expert ASIC verification engineer specializing in functional
coverage analysis and coverage-driven verification. You have deep knowledge
of SystemVerilog covergroups, coverpoints, cross coverage, and coverage
closure strategies.

Your role:
- Analyze coverage holes and identify patterns in uncovered scenarios
- Suggest minimal, targeted tests to close coverage gaps efficiently
- Prioritize coverage items by risk and verification importance
- Identify redundant or unreachable coverage bins

Output format:
For each coverage hole, provide:
1. HOLE: <group.coverpoint.bin>
2. RISK: <high/medium/low> - impact if this scenario has a bug
3. REASON: Why this bin is likely uncovered
4. TEST: Natural language description of a test to cover it
5. PRIORITY: <1-5> - suggested order to address
```

---

## 2. Coverage Hole Analysis Template

### Prompt Template

```text
COVERAGE ANALYSIS REQUEST
==========================

PROJECT: <project_name>
OVERALL COVERAGE: <X%>
TARGET: <Y%>
GAP: <Y-X> percentage points to close

UNCOVERED BINS:
| Group | Coverpoint | Bin | Description | Hits |
|-------|-----------|-----|-------------|------|
<table of uncovered bins>

EXISTING TESTS (for context):
<list of tests already in the regression>

Questions:
1. Which uncovered bins represent the highest verification risk?
2. What is the minimum set of new tests needed to close these holes?
3. Are any bins likely unreachable (should be marked ignore_bins)?
4. Can any existing tests be modified with different seeds/configs to
   hit the missing bins?
```

---

## 3. Few-Shot Examples

### Example 1: AXI Protocol Coverage Holes

**Input:**
```text
COVERAGE ANALYSIS REQUEST
==========================

OVERALL COVERAGE: 78%
TARGET: 95%

UNCOVERED BINS:
| Group        | Coverpoint    | Bin              | Hits |
|-------------|---------------|------------------|------|
| cg_axi_txn  | cp_burst_len  | len_256          | 0    |
| cg_axi_txn  | cp_burst_size | size_128byte     | 0    |
| cg_axi_txn  | cp_resp       | resp_decerr      | 0    |
| cg_axi_txn  | cp_resp       | resp_slverr      | 0    |
| cg_axi_cross| cx_wr_narrow  | wr_size1_len16   | 0    |
| cg_axi_cross| cx_wr_narrow  | wr_size2_len8    | 0    |
| cg_addr_map | cp_region     | region_reserved   | 0    |
| cg_ordering | cp_ooo_resp   | ooo_4_outstanding| 0    |

EXISTING TESTS:
- test_basic_rw (read/write to mapped registers)
- test_burst_sweep (burst lengths 1-16)
- test_random_traffic (1000 random transactions)
```

**Expected LLM Output:**
```text
COVERAGE ANALYSIS RESULTS
=========================

1. HOLE: cg_axi_txn.cp_resp.resp_decerr
   RISK: HIGH - DECERR response path untested; bugs here cause silent failures
   REASON: No test targets unmapped addresses that would trigger DECERR
   TEST: Write a sequence that sends read/write transactions to addresses
     outside the valid register map (e.g., 0xFFFF_0000). Verify the DUT
     returns DECERR (2'b11) and no data corruption occurs on valid registers.
   PRIORITY: 1

2. HOLE: cg_axi_txn.cp_resp.resp_slverr
   RISK: HIGH - Slave error handling untested
   REASON: No test triggers slave error conditions (e.g., write to read-only)
   TEST: Write a sequence that attempts writes to read-only registers and
     reads from write-only registers. Verify SLVERR response and that the
     protected registers are unchanged after the rejected write.
   PRIORITY: 1

3. HOLE: cg_axi_txn.cp_burst_len.len_256
   RISK: MEDIUM - Maximum burst length may have counter overflow issues
   REASON: test_burst_sweep only covers lengths 1-16
   TEST: Modify test_burst_sweep configuration to include burst lengths
     [1, 2, 4, 8, 16, 64, 128, 256]. Alternatively, create a directed
     sequence with ARLEN=255 (256-beat burst) to both aligned and
     unaligned addresses.
   PRIORITY: 2

4. HOLE: cg_axi_cross.cx_wr_narrow.wr_size1_len16
   RISK: MEDIUM - Narrow writes with long bursts stress byte-lane steering
   REASON: Random traffic does not sufficiently bias toward narrow transfers
   TEST: Create a narrow write sequence: set AWSIZE=0 (1 byte) with
     AWLEN=15 (16 beats), cycling through all byte lanes. Verify each
     byte lane is independently written correctly.
   PRIORITY: 3

5. HOLE: cg_addr_map.cp_region.region_reserved
   RISK: LOW - Reserved regions should return error, but may be unreachable
   REASON: No address generator targets reserved regions
   TEST: Add reserved region addresses to the address generator constraints.
     If the DUT is not designed to respond to reserved regions, mark this
     bin as ignore_bins in the covergroup.
   PRIORITY: 4

6. HOLE: cg_ordering.cp_ooo_resp.ooo_4_outstanding
   RISK: MEDIUM - Out-of-order with 4 outstanding tests reorder buffer depth
   REASON: Test environment may not support >1 outstanding transaction
   TEST: Configure the AXI agent to allow 4 outstanding read requests.
     Send 4 reads to addresses with different slave latencies to force
     out-of-order responses. Verify response ID matching.
   PRIORITY: 2

SUMMARY:
- New tests needed: 4 (error responses, max burst, narrow writes, OOO)
- Tests to modify: 1 (burst_sweep config change)
- Bins to review for ignore: 1 (reserved region)
- Estimated coverage after fixes: ~93%
```

### Example 2: FSM State Coverage

**Input:**
```text
UNCOVERED BINS:
| Group       | Coverpoint  | Bin             | Hits |
|-------------|-------------|-----------------|------|
| cg_fsm      | cp_state    | ST_ERROR        | 0    |
| cg_fsm      | cp_state    | ST_RETRY        | 0    |
| cg_fsm_trans| cp_arc      | IDLE_to_ERROR   | 0    |
| cg_fsm_trans| cp_arc      | ERROR_to_IDLE   | 0    |
| cg_fsm_trans| cp_arc      | ACTIVE_to_RETRY | 0    |
```

**Expected LLM Output:**
```text
1. HOLE: cg_fsm.cp_state.ST_ERROR
   RISK: HIGH - Error state handling is completely untested
   REASON: No test injects error conditions that drive FSM to ST_ERROR
   TEST: Inject a protocol violation or parity error during an active
     transaction to force the FSM into ST_ERROR state. Verify the FSM
     correctly transitions to ST_ERROR, asserts the error interrupt,
     and can recover to IDLE via the error-clear register write.
   PRIORITY: 1

2. HOLE: cg_fsm_trans.cp_arc.ACTIVE_to_RETRY
   RISK: MEDIUM - Retry mechanism untested under active conditions
   REASON: Retry conditions (e.g., resource busy) not stimulated
   TEST: Create a scenario where the downstream resource signals busy
     while the FSM is in ACTIVE state. Use a constrained-random
     sequence that toggles the busy signal at various points during
     the active phase. Verify the FSM transitions to RETRY and
     eventually completes the transaction.
   PRIORITY: 2
```

---

## 4. Coverage Optimization Strategies

### Prompt for Coverage Closure Plan

```text
Given the following coverage data, create a coverage closure plan
that minimizes the number of new tests while maximizing coverage gain.

Current: 82%  Target: 95%  Deadline: 2 weeks

Constraints:
- Each new test takes ~2 hours to develop and debug
- Simulation farm can run 500 tests/night
- Some coverage items may be unreachable (mark as waived)

Prioritize by:
1. Verification risk (high-risk uncovered items first)
2. Coverage gain per test (prefer tests that hit multiple holes)
3. Development effort (prefer simple tests over complex ones)
```

### Identifying Unreachable Coverage

```text
Review these uncovered bins and identify which ones are UNREACHABLE
given the DUT design constraints. An unreachable bin should be marked
as ignore_bins to avoid inflating the coverage gap.

For each unreachable bin, explain WHY it cannot be hit and confirm
it is safe to waive from a verification perspective.
```
