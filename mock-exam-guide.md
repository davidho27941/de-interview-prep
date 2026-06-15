# Mock Exam Design Guide

## Exam Structure

Standard DE coding assessment (90 minutes, 5 questions):

| Question | Type | Difficulty | Target Time | Focus |
|---|---|---|---|---|
| Q1 | SQL | Easy | 10 min | Basic JOIN, GROUP BY, filtering |
| Q2 | SQL | Medium | 15 min | Window functions, CTE, complex joins |
| Q3 | Python | Medium | 15 min | Data processing with standard library |
| Q4 | Python | Hard | 25 min | Complex pipeline (dedup, aggregation, edge cases) |
| Q5 | Debug | Medium | 15 min | Find and fix 3-5 bugs in a data pipeline |
| — | Buffer | — | 10 min | Review and edge case checking |

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
