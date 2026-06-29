# Mock Exam Design Guide

## Exam Structure

Each problem is tagged on TWO axes per the calibration in [SKILL.md](SKILL.md): **Reading** (R) and **Operations** (O). Mock exam composition is chosen by selecting a mix of (R, O) tags — not by a single "Easy/Medium/Hard" label.

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

### Folder-Based Input Requirement (mandatory for Python / PySpark)

Per the Input Convention in [SKILL.md](SKILL.md), every Python / PySpark / Debug problem in a mock MUST use folder-based input. SQL problems are exempt (they use the DB tables directly).

For each Python / PySpark / Debug problem, the problem designer MUST:

1. Specify the input folder path (e.g., `challenges/mockN/qK/input/`)
2. List the **target files** the user should process (with extension and naming convention)
3. List the **decoy files** that must be filtered out
4. Note if subdirectories are present (and whether they should be recursed into)
5. Optionally include encoding traps or empty files

### Decoy mix per difficulty

| Calibration | Min decoys | Decoy types to include |
|---|---|---|
| **O:Easy** | 1-2 | Wrong extension, or hidden file |
| **O:Medium** | 2-3 | Wrong extension + backup file (.bak) + hidden |
| **O:Hard** | 3-5 | All of medium + subdirectory + empty file + encoding edge case |

### Sample problem header (use this format)

```
# Q3 — Python scenario [R:M, O:M] (target 15 min)

## Input
Folder: `mock1/q3/input/`

Target files:
  - access-YYYY-MM-DD.log (10 files, one per day)

Decoy files (must be filtered out):
  - .DS_Store (hidden)
  - access-2026-05-31.log.bak (backup)
  - README.md (documentation)
  - archive/ (subdirectory — do NOT recurse)

## Task
... (the actual problem)

## Pre-Submit Ritual
1. Empty set behavior?
2. Aggregates in arithmetic → COALESCE?
3. INNER vs LEFT JOIN?
4. Boundary cases?
PLUS: did I filter the decoy files correctly? Sanity-print the file list before processing.
```

This format reinforces the "read the spec carefully" reading-load axis AND the file-filtering reflex on every problem.

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

## Q1-Q2: SQL Problem Design

### Q1 (Easy) — Pick from:
- Basic JOIN + GROUP BY + HAVING
- Simple aggregation with NULL handling
- CASE WHEN for conditional counting
- Self-join for comparison within same table

### Q2 (Medium) — Pick from:
- Window functions (RANK, ROW_NUMBER, running total)
- CTE with multiple steps
- Gap-and-Island pattern
- Complex JOIN (CROSS JOIN + LEFT JOIN for "show zeros")
- Subquery correlation

### SQL Sources
- LeetCode Database section (filter by DE-relevant topics)
- HackerRank SQL domain

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
