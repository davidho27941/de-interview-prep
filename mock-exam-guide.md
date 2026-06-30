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
- **Number / Title:** LeetCode 1280｜Students and Examinations
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
[Cheat-card lesson worth promoting to D14 review pile]
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

### Canonical R:Hard Python / PySpark notebook template

```
# Q{N} — {Problem name} [R:H, O:{level}] (target {N} min)

## Scenario
{1 paragraph: business context — who needs this, why, what's at stake.}

### 資料來源
{1 short paragraph intro, then 3-4 bullets — one per input source.
 Each bullet calls out the format AND any quirk (NULL convention,
 SCD2 property, file naming pattern, blacklist semantics, etc.).}

### Rule 1 — {Name (e.g., Net amount)}
{1 paragraph prose stating the rule.}

範例：
- {Example bullet — concrete IDs and values}
- {Edge case bullet — NULL / zero / boundary}
- {Contrast bullet — positive case}
- {Optional pathological case}

### Rule 2 — {Name}
{Prose + bullet examples.}

### Rule 3 — {Name}
{Prose + bullet examples.}

## Input

Folder: `challenges/mockN/qK/input/`

### {source-1 folder or file}/
{Brief format description.}
Schema: `col1, col2, ...`

`{filename}` 內容範例（logical view if parquet）：

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

Sort: {key} ASC → {key} ASC → ...

Sample（前 N 列，供 schema 與 sort key 比對）：

| ... |
```

**Key structural rules** (also in [SKILL.md](SKILL.md) Calibration section):

- Examples are **bullets, not prose-embedded** — easier to parse individually; reading load comes from quantity + cross-referencing.
- **Each input source must include sample content**, not just schema. Parquet → logical-view table. CSV/JSONL/TXT → raw text in fenced block.
- Sample IDs cross-reference scenario rule examples (e.g., if Rule 1 mentions `O8803 / refund_amount=NULL`, refunds.json sample must contain that row).
- **No decoy listing, no Pre-Submit Ritual** in the notebook markdown — they go to Notion. Decoys still exist physically in `input/`.

### Canonical example

The reference R:Hard problem worked through during 2026-06 calibration was "Q4 — Monthly Cohort Retention (1-month)" `[R:H, O:M]` target 20 min, with sources: orders parquet (multi-file), customers CSV, refunds JSONL, blacklist TXT. See the memory `feedback_hard_calibration_anchors.md` for the full rendered example.

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
