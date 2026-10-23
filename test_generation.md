# Prompt Engineering Guide: UVM Test Generation

## Overview

This guide covers best practices for crafting prompts that produce correct,
synthesizable SystemVerilog/UVM verification code from Large Language Models.

---

## 1. System Prompt Design (DV Expert Persona)

The system prompt establishes the LLM's role, constraints, and output format.
A well-designed persona dramatically improves code quality.

### Recommended System Prompt

```text
You are an expert ASIC Design Verification engineer with 15+ years of experience
in SystemVerilog and UVM methodology. You specialize in writing clean, correct,
and reusable verification IP.

Rules:
- Always use proper UVM macros and factory registration
- Include `uvm_object_utils or `uvm_component_utils for every class
- Use start_item/finish_item for sequence transactions
- Include proper constructor with string name parameter and default value
- Add meaningful `uvm_info messages at UVM_MEDIUM or UVM_HIGH verbosity
- Use constraints for randomization; avoid over-constraining
- Handle edge cases and error conditions with `uvm_error
- Output ONLY SystemVerilog code in a ```systemverilog code block
- Do NOT include Python, C++, or pseudocode
- Do NOT use $display; use `uvm_info, `uvm_warning, or `uvm_error
```

### Key Persona Elements

| Element | Purpose | Example |
|---------|---------|---------|
| Expertise level | Prevents beginner mistakes | "15+ years of experience" |
| Domain specificity | Focuses on DV, not RTL design | "Design Verification engineer" |
| Methodology | Ensures UVM compliance | "UVM methodology" |
| Negative constraints | Prevents common errors | "Do NOT include Python" |
| Output format | Ensures parseable output | "```systemverilog code block" |

---

## 2. Few-Shot Examples

Providing input-output examples dramatically improves generation quality.

### Example 1: Register Read-Back Sequence

**User Prompt:**
```text
Generate a UVM sequence that writes a walking-1s pattern to register at
address 0x10, then reads it back and checks the value matches.

CONTEXT: Sequence item is axi4_lite_seq_item with fields: addr (32-bit),
data (32-bit), write (1-bit), strb (4-bit).
```

**Expected Output:**
```systemverilog
class walking_ones_readback_seq extends uvm_sequence #(axi4_lite_seq_item);
    `uvm_object_utils(walking_ones_readback_seq)

    bit [31:0] target_addr = 32'h0000_0010;
    int unsigned num_iterations = 32;

    function new(string name = "walking_ones_readback_seq");
        super.new(name);
    endfunction

    task body();
        axi4_lite_seq_item wr_item, rd_item;
        bit [31:0] pattern;

        for (int i = 0; i < num_iterations; i++) begin
            pattern = 32'h1 << i;

            // Write walking-1s pattern
            wr_item = axi4_lite_seq_item::type_id::create($sformatf("wr_%0d", i));
            start_item(wr_item);
            wr_item.addr  = target_addr;
            wr_item.data  = pattern;
            wr_item.write = 1'b1;
            wr_item.strb  = 4'hF;
            finish_item(wr_item);

            // Read back and verify
            rd_item = axi4_lite_seq_item::type_id::create($sformatf("rd_%0d", i));
            start_item(rd_item);
            rd_item.addr  = target_addr;
            rd_item.write = 1'b0;
            finish_item(rd_item);

            if (rd_item.data !== pattern) begin
                `uvm_error(get_type_name(),
                    $sformatf("MISMATCH at bit %0d: wrote 0x%08h, read 0x%08h",
                              i, pattern, rd_item.data))
            end else begin
                `uvm_info(get_type_name(),
                    $sformatf("PASS bit %0d: 0x%08h", i, rd_item.data), UVM_HIGH)
            end
        end

        `uvm_info(get_type_name(),
            $sformatf("Walking 1s test completed: %0d iterations", num_iterations),
            UVM_MEDIUM)
    endtask
endclass
```

### Example 2: Constrained-Random Burst Sequence

**User Prompt:**
```text
Generate a UVM sequence that sends 100 random AXI4-Lite transactions with
a mix of reads and writes, biasing 70% toward writes.
```

**Expected Output:**
```systemverilog
class random_traffic_seq extends uvm_sequence #(axi4_lite_seq_item);
    `uvm_object_utils(random_traffic_seq)

    int unsigned num_transactions = 100;
    int unsigned write_weight = 70;
    int unsigned read_weight = 30;

    function new(string name = "random_traffic_seq");
        super.new(name);
    endfunction

    task body();
        axi4_lite_seq_item item;

        `uvm_info(get_type_name(),
            $sformatf("Starting random traffic: %0d transactions (W:%0d%% R:%0d%%)",
                      num_transactions, write_weight, read_weight), UVM_MEDIUM)

        for (int i = 0; i < num_transactions; i++) begin
            item = axi4_lite_seq_item::type_id::create($sformatf("txn_%0d", i));
            start_item(item);
            if (!item.randomize() with {
                write dist {1 := write_weight, 0 := read_weight};
                addr[1:0] == 2'b00;  // Word-aligned
                addr < 32'h0000_1000; // Valid address range
            }) begin
                `uvm_error(get_type_name(), $sformatf("Randomization failed for txn %0d", i))
            end
            finish_item(item);
        end

        `uvm_info(get_type_name(), "Random traffic sequence complete", UVM_MEDIUM)
    endtask
endclass
```

---

## 3. Chain-of-Thought Reasoning

For complex test scenarios, instruct the LLM to reason step-by-step before
writing code. This improves correctness for multi-phase protocols.

### Chain-of-Thought Prompt Template

```text
I need a UVM sequence for the following scenario. Before writing code,
think through these steps:

1. What protocol rules must be followed?
2. What are the possible error conditions?
3. What timing constraints exist?
4. What should be randomized vs. directed?

Then write the complete SystemVerilog code.

SCENARIO: [description]
```

### Example: AXI Outstanding Transaction Test

```text
Think step by step:

1. AXI4-Lite does NOT support outstanding transactions, so we must wait
   for each response before sending the next request.
2. Error conditions: SLVERR/DECERR responses, timeout if slave never responds.
3. Timing: No minimum delay between transactions, but we should add
   configurable inter-transaction delay for stress testing.
4. Randomize: addresses, data, read/write mix. Direct: protocol compliance.

Now generate the sequence...
```

---

## 4. Token Optimization Tips

LLM API costs scale with token usage. Optimize prompts for efficiency:

| Technique | Savings | Example |
|-----------|---------|---------|
| Concise descriptions | 20-30% | "Write-read-back seq" vs lengthy paragraph |
| Reuse system prompt | ~40% per call | Cache system prompt across generations |
| Specify output only | 15-25% | "Output ONLY code, no explanations" |
| Limit context window | Variable | Only include relevant interface definitions |
| Use abbreviations | 5-10% | "SV" for SystemVerilog, "cg" for covergroup |

### Prompt Size Guidelines

- **System prompt**: 200-400 tokens (reuse across calls)
- **User prompt**: 100-300 tokens (description + minimal context)
- **Context code**: Only include the sequence item class and relevant base classes
- **Max total input**: Keep under 2000 tokens for simple generations

---

## 5. Temperature Recommendations

Temperature controls randomness in LLM output. For code generation:

| Temperature | Use Case | Rationale |
|-------------|----------|-----------|
| **0.1** | Bug fixes, refinement | Deterministic, precise corrections |
| **0.2** | Standard test generation | Reliable, consistent code output |
| **0.3** | Creative test scenarios | Slightly more variety in approaches |
| **0.5+** | Brainstorming test ideas | Higher creativity, but more errors |

### Best Practice

- Start at **0.2** for all code generation tasks
- Drop to **0.1** for iterative refinement (fixing validation errors)
- Never exceed **0.5** for code that must compile
- Use **0.0** for deterministic regression of prompt quality

---

## 6. Common Pitfalls and Mitigations

### Python Syntax Leaking

LLMs trained on mixed corpora often inject Python patterns:

| Python Pattern | SystemVerilog Equivalent | Detection |
|----------------|------------------------|-----------|
| `self.value` | `this.value` or just `value` | Regex: `self\.` |
| `def func():` | `function void func();` | Regex: `\bdef\s+` |
| `print(msg)` | `` `uvm_info(ID, msg, UVM_MEDIUM) `` | Regex: `\bprint\s*\(` |
| `for x in range(n):` | `for (int x = 0; x < n; x++)` | Regex: `\bin range\(` |
| `if x == True:` | `if (x == 1'b1)` | Regex: `True\|False` |

### Missing UVM Macros

The most common LLM error is omitting factory registration:

```systemverilog
// WRONG - missing factory registration
class my_seq extends uvm_sequence #(my_item);
    function new(string name = "my_seq");
        super.new(name);
    endfunction
endclass

// CORRECT
class my_seq extends uvm_sequence #(my_item);
    `uvm_object_utils(my_seq)
    function new(string name = "my_seq");
        super.new(name);
    endfunction
endclass
```

### Unbalanced Blocks

LLMs sometimes lose track of `begin`/`end` or `class`/`endclass` pairs,
especially in long outputs. The `SVValidator` class in this toolkit
automatically detects and reports these issues for iterative refinement.

### Incorrect Randomization

Watch for:
- Missing `rand` keyword on fields that should be randomized
- Using `$random` instead of `item.randomize()`
- Forgetting the `with` constraint block syntax
- Not checking randomization return value
