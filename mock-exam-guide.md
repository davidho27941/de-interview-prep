# Mock Exam Design Guide

## Exam Structure

Each problem is tagged on TWO axes per the calibration in [SKILL.md](SKILL.md): **Reading** (R) and **Operations** (O). Mock exam composition is chosen by selecting a mix of (R, O) tags — not by a single "Easy/Medium/Hard" label.

## Structural Rules (apply to EVERY mock)

These rules are non-negotiable. A mock that violates them is mis-calibrated regardless of question content.

### Rule 1: Each question is fully independent

```
challenges/
└── mock{N}/
    ├── q1/
    │   ├── q1.ipynb            # this question's notebook
    │   ├── input/              # this question's input files (+ decoys)
    │   └── output/             # this question's solution writes here
    ├── q2/
    │   ├── q2.ipynb
    │   ├── input/
    │   └── output/
    └── ...
```

- Own folder per question
- Own notebook per question (NOT one shared notebook with multiple sections)
- Own `input/` and `output/` subfolders
- No cross-question data leakage; no shared module / shared `df` variable

### Rule 2: Python / PySpark questions include full I/O lifecycle

Senior DE work owns the full pipeline, not just the transform. Every Python / PySpark question:

1. **Reads from disk** via `spark.read.csv/json/parquet/text(...)` (or Python `open()` / `pathlib`)
2. Transforms
3. **Writes to disk** via `df.write.mode('overwrite').parquet/csv/json(...)` (or Python `open('w')`)
4. **Tests verify the output file** by reading it back — not by inspecting an in-memory return value

A mock question whose solution looks like `def solve(df): return df.groupBy(...).agg(...)` is NOT O:Hard, regardless of how complex the transform is.

### Rule 3: SQL questions use LeetCode + structured wrapper

Do NOT use PySpark SQL or DataFrame API to fake a SQL question — that's testing Spark, not SQL.

SQL question format:

```markdown
# Q1 — SQL [calibration tag] (target X min)

## Problem
- **Platform:** LeetCode
- **Number / Title:** LeetCode 1280 | Students and Examinations
- **URL:** https://leetcode.com/problems/students-and-examinations/
- **Difficulty:** Medium
- **Pattern:** CROSS JOIN + LEFT JOIN + GROUP BY (show-zeros)

## Why this matters
Tests the "show zero counts" pattern — the classic LEFT JOIN trap where students with no exams get filtered out by an INNER JOIN.

## Before coding (think first, write second)
1. Should students with zero exams appear in output? (Yes — that's the whole point)
2. What's the canonical "all-pairs then filter" SQL pattern?
3. Where does NULL appear and what does COUNT(col) vs COUNT(*) do?

## Common mistakes
- INNER JOIN instead of LEFT JOIN → students with zero exams drop
- GROUP BY only by student → loses subject dimension
- COUNT(*) instead of COUNT(exam_id) → zero-count rows show as 1

## Completion record
- Time spent: ___
- Passed first try? Y / N
- Mistake (if any): ___
- Pattern learned: ___
- Within target time? Y / N

## Takeaway
[Cheat-card lesson worth promoting to the final-review pile]
```

The user solves on LeetCode itself; local machine doesn't execute SQL. The wrapper trains: pattern recognition → clarifying questions → known traps → reflective scoring.

### Standard Mock (default — graduated difficulty matching typical DE assessment)

| Q | Type | Reading | Operations | Target Time | Focus |
|---|---|---|---|---|---|
| Q1 | SQL | **R:Easy** (~1 min) | **O:Easy** (1-5) | 10 min | Basic JOIN, GROUP BY, filtering |
| Q2 | SQL | **R:Medium** (~3 min) | **O:Medium** (5-10) | 15 min | Window functions, CTE, multi-step |
| Q3 | Python scenario | **R:Medium** (~3 min) | **O:Medium** (5-10) | 15 min | Standard library data processing |
| Q4 | Python or PySpark scenario | **R:Hard** (~5 min) | **O:Hard** (10-15) | 25 min | Complex pipeline with edge cases |
| Q5 | Debug or PySpark | **R:Medium** (~3 min) | **O:Medium** (5-10) | 15 min | Bugs in pipeline OR Spark transform |
| — | Buffer | — | — | 10 min | Review and edge case checking |

### Target-Simulation Mock (for users who underperform on reading load)

Shift the reading-load distribution upward — closer to target tests where most problems are R:Hard. Use this when the gap analysis shows reading comprehension as the failure mode.

| Q | Type | Reading | Operations | Target Time |
|---|---|---|---|---|
| Q1 | SQL | **R:Medium** | **O:Easy** | 10 min |
| Q2 | SQL | **R:Hard** | **O:Medium** | 18 min |
| Q3 | Python scenario | **R:Hard** | **O:Medium** | 18 min |
| Q4 | Python/PySpark scenario | **R:Hard** | **O:Hard** | 25 min |
| Q5 | Debug or PySpark | **R:Medium** | **O:Medium** | 15 min |

### Speed-Run Mock (early prep / confidence reset)

All problems below the Standard mix — focus on Pre-Submit Ritual execution, not problem-solving stress.

| Q | Type | Reading | Operations | Target Time |
|---|---|---|---|---|
| Q1-Q5 | mixed | **R:Easy** or **R:Medium** | **O:Easy** or **O:Medium** | 8-12 min each |

### Mock Selection Rule

- **First mock of a cycle (early)** → Standard mock. Establishes baseline and exposes gaps neutrally.
- **Second mock (mid/late)** → Match the actual target test format. For long-prompt assessments: Target-Simulation. For shorter-prompt formats: Standard.
- **Confidence reset** (after a bad mock, or pre-exam day) → Speed-Run.

### Operation Budget per Problem (sanity check)

If a problem you're designing has more than 15 operations, split it — that's beyond Hard and approaches take-home territory. If it has fewer than 1 (just "SELECT * FROM table"), it's not a problem, it's a syntax check.

### Folder-Based Input + Output Requirement (mandatory for Python / PySpark)

Per Rule 2 above, every Python / PySpark / Debug problem must use folder-based input AND write to a folder-based output. SQL problems use LeetCode (see Rule 3).

For each Python / PySpark / Debug problem, the problem designer MUST:

1. Specify the input folder path (`challenges/mockN/qK/input/`)
2. Specify the output folder path (`challenges/mockN/qK/output/`) and the expected file format (parquet / csv / json)
3. List the **target input files** in the spec (extension + naming convention + schema + sample content)
4. **Plant decoy files physically in the input folder** but do NOT list them in the spec — the user discovers them by `ls` and applies filtering reflex
5. Note if subdirectories are present in the spec only if they're part of the canonical structure (e.g., `orders/` containing daily files); a decoy subdirectory like `archive/` stays unmentioned
6. Optionally include encoding traps or empty files (also unmentioned in spec)
7. Write tests that **read the output file back** and assert its contents — not asserts on a returned object

### Decoy mix per difficulty (designer reference — NOT exposed in spec)

These are physical files the designer puts in `input/`; the user must discover and filter them. They are NEVER listed in the problem markdown.

| Calibration | Min decoys | Decoy types to include |
|---|---|---|
| **O:Easy** | 1-2 | Wrong extension, or hidden file |
| **O:Medium** | 2-3 | Wrong extension + backup file (.bak) + hidden |
| **O:Hard** | 3-5 | All of medium + subdirectory + empty file + encoding edge case |

### Notebook vs Notion content split

The notebook problem markdown is the **assessment-realistic surface**. The paired Notion prep/retro page is where scaffolding lives. Per [SKILL.md](SKILL.md):

| In notebook (assessment surface) | In Notion (prep/retro) |
|---|---|
| Scenario (paragraph + rule subsections + bullet examples) | Pre-Submit Ritual prompts |
| Input section (schema + sample content per source) | Decoy listing (for retro: "did the user filter correctly?") |
| Output section (schema + sort + sample rows) | Solving steps / approach hints |
| Solution scaffold cell + tests cell | Common mistakes for this pattern |
|   | Completion record (time, passed, mistake, takeaway) |
|   | Calibration tags + scoring |

### Canonical two-file structure (LeetCode-style split view)

Each problem lives as TWO files in its per-Q folder:

- `problem.md` — full problem statement (below template)
- `qK.ipynb` — short pointer cell + setup + solution + tests

Rationale: the user opens `problem.md` in a left pane and the notebook in a right pane, so re-reading the spec while coding is instant (no scrolling inside the notebook).

### Canonical `problem.md` template (platform-style)

```
# Q{N} — {Problem name} [R:{level}, O:{level}] (target {N} min)

## Description
{Business context paragraph, then data-landscape paragraph(s), then computation
 semantics WOVEN INTO PROSE: output grain, derived-column definitions,
 inclusion/exclusion rules, boundary semantics. FINAL paragraph = deliverable
 sentence: "Write the result to output/ as {format}, partitioned by X,
 sorted by A ASC" — or "row order is not required (tests sort before
 comparing)". NO numbered solution steps.
 NO function/algorithm hints. NO trailing clarifications section.}

### Rule 1 — {Name}   (R:Hard: ≥3 named rule subsections)
{1 paragraph prose stating the rule.}

Examples:
- {Example bullet — concrete IDs and values}
- {Edge case bullet — NULL / zero / boundary}
- {Contrast bullet — positive case}
- {Optional pathological case}

## Example(s)
{LeetCode-style worked example: input excerpt → output rows → explanation.}

## Input

Folder: `challenges/mockN/qK/input/`

### {source-1 folder or file}/
{Brief format description.}
Schema (every column MUST have explicit type):
- `col1: string`
- `col2: date`
- `col3: double`

`{filename}` sample content (logical view if parquet):

| col1 | col2 | ... |
|---|---|---|
| {sample row using IDs from scenario rule examples} |
| {another sample row including an edge case} |
| ... |

### {source-2}
{Brief format description.}

\`\`\`
header,row,format
{sample row}
...
\`\`\`

> {Optional 1-line note tying sample data back to scenario examples}

### {source-3} ...
### {source-4} ...

## Output

Folder: `challenges/mockN/qK/output/`
Format: {parquet/csv/json}, partitioned by ...

Schema:

| field | type |
|---|---|
| ... | ... |

{Ordering contract restated: exact sort keys, or "row order is not required"}

Sample (first N rows, for schema comparison):

| ... |

## Constraints
{Data size, value domains, format guarantees, and which boundary conditions
 EXIST in data (duplicates / exact-boundary gaps / midnight-crossing /
 orphan keys) — LeetCode-style disclosure.}
```

**Key structural rules** (also in [SKILL.md](SKILL.md) Calibration section):

- **Requirements woven into Description/Rules — never appended.** Ordering, return format, partitioning, derived-column formulas all appear in the statement body. A separate clarifications dump = the statement failed. (Retired anti-pattern: `## Task` numbered-steps + trailing clarifications sections — Task steps leak the solution recipe.)
- **The deliverable is a sentence, not a recipe.** Final Description paragraph states WHAT to produce and WHERE to write. Never name functions or algorithm steps (`to_date`, "GroupBy → count", "lag → cumsum").
- **Ordering contract explicit and verifiable.** Exact order → single sorted file, test compares write order strictly. Otherwise "order is not required" → test re-sorts. Never demand a sort the test can't physically verify (global order inside a partitioned dataset is not a real contract).
- **No off-topic terminology** — don't mention concepts from sibling problems (e.g., "session" inside a plain counting problem).
- Examples are **bullets, not prose-embedded** — easier to parse individually; reading load comes from quantity + cross-referencing.
- **Each input source must include sample content**, not just schema. Parquet → logical-view table. CSV/JSONL/TXT → raw text in fenced block.
- Sample IDs cross-reference scenario rule examples (e.g., if Rule 1 mentions `O8803 / refund_amount=NULL`, refunds.json sample must contain that row).
- **Every schema column MUST have an explicit type.** `col: string` / `col: timestamp` / `col: double`, never bare `col1, col2, col3`. Implicit types leak decisions to the reader (e.g., `payment_ts` could be timestamp or date).
- **Money columns MUST use `decimal(p, 2)` OR spec must state explicit rounding.** `DoubleType` + `sum + ==` on currency silently misclassifies via IEEE 754 accumulator drift. If your canonical solution does any equality/inequality comparison on aggregated money, commit to precision handling in the spec. Real failure mode: a reconciliation problem shipped with `DoubleType` amounts and `matched: paid_total == invoice_amount` — an invoice of $2508.06 got misclassified as overpaid because the payment sum drifted to `2508.0600000000004`.
- **No decoy listing, no Pre-Submit Ritual** in the notebook markdown — they go to Notion. Decoys still exist physically in `input/`.

### Canonical notebook cell-0 pointer (LeetCode-style split)

```
# QK — {Problem name}

📖 **Problem:** `problem.md`

| | |
|---|---|
| Calibration | `[R:H, O:{level}]` |
| Target time | {N} min |
| Focus | {pattern being drilled} |
| Input | `input/...` (list files/subfolders) |
| Output | `output/` (Parquet, partitioned by {key}) |
```

Cells 1-3: setup + solution scaffold + tests (DO NOT MODIFY). All spec content stays in `problem.md`.

### Canonical example

Two reference shapes that exercise the full template:

- **"Monthly Cohort Retention (1-month)"** `[R:H, O:M]`, target 20 min — sources: orders parquet (multi-file daily dumps), customers CSV, refunds JSONL (with a NULL-means-full-refund convention), blacklist TXT. Rules: net amount after refunds, acquisition month from first net-positive order, next-month retention flag.
- **"Merchant Payout Reconciliation"** `[R:H, O:M]`, target 25 min — sources: invoices parquet, payments JSONL (many payments per invoice), merchant CSV, disputed-ids TXT. Rules: exclusion list with partial/full payment activity, `paid_total` aggregation with `decimal(12,2)`, matched/underpaid/overpaid/unpaid classification.

Both demonstrate the two-file split (`problem.md` + pointer notebook), typed schemas, sample content per source, and exclusion-list entries that HAVE activity so a skipped filter changes the counts.

## Time Management Strategy

- **Read all 5 problems first** (2-3 min) — identify easy wins
- **Start with Q1** — build confidence with an easy SQL
- **Skip if stuck > 5 min** — move to next, come back later
- **Q5 Debug is often fastest** — consider doing it early if comfortable
- **Save 5 min at end** — review output sorting, edge cases, NULL handling

## Pre-Code Annotation (Optional, < 1 min per problem)

Writing a brief annotation before coding improves accuracy:

```
# Goal: [1 sentence — what the problem asks]
# Strategy: [pattern name — e.g., "Sliding Window"]
# Steps: [max 3 lines]
```

Keep it under 1 minute. The goal is to anchor your thinking, not write documentation.

## Q1-Q2: SQL Problem Design (LeetCode-based)

Per Rule 3, SQL questions reference a real LeetCode problem and use the structured prep wrapper. Do not invent SQL problems against a local engine. The wrapper structure is in Rule 3 above; here's the source guidance.

### Q1 (Easy) — Pick LeetCode problems testing:
- Basic JOIN + GROUP BY + HAVING
- Simple aggregation with NULL handling
- CASE WHEN for conditional counting
- WHERE + NULL-safe negative filtering (`<>` vs `IS NOT NULL`)
- LIKE pattern matching
- Self-join for comparison within same table

Examples: LeetCode 584 (Find Customer Referee), 1527 (Patients With a Condition), 1757 (Recyclable and Low Fat Products), 570 (Managers with at Least 5 Direct Reports).

### Q2 (Medium) — Pick LeetCode problems testing:
- Window functions (RANK, ROW_NUMBER, running total)
- CTE with multiple steps
- Gap-and-Island pattern
- Complex JOIN (CROSS JOIN + LEFT JOIN for "show zeros")
- Subquery correlation
- Multi-pattern composition (window + LEFT JOIN + COALESCE)

Examples: LeetCode 1280 (Students and Examinations), 550 (Game Play Analysis IV), 185 (Department Top Three Salaries).

### SQL Sources
- **Primary:** LeetCode Database section (filter by DE-relevant topics)
- Secondary: HackerRank SQL domain

User solves on the platform; we host the prep wrapper (Problem focus / Pattern / Target time / Before coding / Common mistakes / Completion record / Takeaway).

## Q3-Q4: Python Problem Design

### Q3 (Medium) — Pick from:
- Counter / frequency analysis with sorting
- Two Pointers on sorted data
- Sliding Window (fixed or variable)
- Prefix Sum (especially with negative numbers)
- Binary Search application

### Q4 (Hard) — Custom DE scenario:
- Log parsing and session analysis
- Data dedup and aggregation pipeline
- Event stream processing
- Time-series anomaly detection
- ETL transformation with complex rules

### Q4 Custom Problem Template
```python
# Scenario: [realistic DE context]
# Rules:
#   - [dedup rule]
#   - [null/invalid handling]
#   - [aggregation logic]
#   - [output format and sort]
# Constraints: standard library only, [time limit]

data = [...]  # 10-20 records with edge cases

expected_output = [...]
```

Include in test data:
- Duplicate records (same key)
- Null/None values
- Zero values (test truthiness)
- Edge case groups (single member, all invalid)

## Q5: Debug Problem Design

See [debug-checklist.md](debug-checklist.md) for the full guide.

Key rules:
- 3-5 bugs per problem
- Include error log with hints
- Only one function to fix
- 10-15 minute target time

## Scoring and Assessment

After the mock exam, evaluate:

### Pass Criteria
| Score | Assessment | Recommendation |
|---|---|---|
| 5/5 | Ready | Take the real exam |
| 4/5 | Strong | Take exam, review missed pattern |
| 3/5 | Needs work | 1-2 more days of targeted practice |
| 2/5 or below | Not ready | Continue structured practice |

### Analysis Dimensions
1. **Accuracy**: How many problems fully correct?
2. **Speed**: Finished within time? Which problems took longest?
3. **Pattern recognition**: Did the user identify the right approach quickly?
4. **Bug patterns**: What types of mistakes? (off-by-one, sort, None, dedup)
5. **Fatigue curve**: Did quality drop on later problems?

### Common Failure Modes
- **Time pressure**: Spending too long on Q2 and rushing Q3-Q5
- **Missing edge cases**: Solution works on happy path but fails on zeros/nulls
- **Wrong pattern**: Using brute force when a known pattern applies
- **Forgetting sort**: Correct computation but wrong output order
