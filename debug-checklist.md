# Debug Problem Checklist

## Top 5 Bug Patterns in Data Pipelines

These are the most common intentional bugs in DE debug questions, ordered by frequency:

### 1. Missing Status Filter
**Bug:** All records processed regardless of status (e.g., `resigned`, `refunded`, `pending` included)
**Signal:** Log shows unexpected record count, or aggregates include inactive entities
**Fix:** Add `if record["status"] == "active":` or equivalent filter early in the pipeline

### 2. No Dedup on ID
**Bug:** Duplicate records inflate counts and sums
**Signal:** Log mentions "duplicate ID detected", counts are higher than expected
**Fix:** Track seen IDs with a set: `if record["id"] in seen: continue; seen.add(record["id"])`

### 3. Truthiness vs None Check
**Bug:** `if value:` filters out legitimate zero values (`0`, `""`, `[]`)
**Signal:** Records with zero values are silently dropped, averages are skewed high
**Fix:** Use `if value is not None:` to only skip actual nulls

### 4. Missing Output Sort
**Bug:** Results returned in insertion/arbitrary order instead of required order
**Signal:** QA check says "output not sorted by X"
**Fix:** Add `result.sort(key=lambda x: -x["metric"])` or appropriate sort

### 5. Division by Zero
**Bug:** No guard when computing averages on empty groups
**Signal:** ZeroDivisionError or NaN in output
**Fix:** `avg = total / count if count > 0 else 0`

## How to Read Error Logs

Debug problems typically include an error log. Read it systematically:

1. **Count mismatches** — "expected N, got M" tells you exactly which bug category
   - Too many records → missing filter or missing dedup
   - Value too high → duplicates inflating sums, or wrong records included
   - Value too low → legitimate records being filtered out (truthiness bug)
   
2. **WARNING lines** — often directly hint at the bug
   - "Duplicate ID detected" → dedup bug
   - "N records with value=None" → None handling bug
   
3. **Output order** — "not sorted by X" → missing sort

## Creating Debug Problems

When designing a debug problem for practice:

### Data Design
- Include at least one duplicate record (same ID, same values)
- Include at least one inactive/invalid status record
- Include at least one legitimate zero value (salary=0, count=0)
- Include at least one None/null value
- Use 3-4 groups for aggregation (enough to verify sort)

### Bug Placement
- Place 3-5 bugs in a single function
- Each bug should be independently fixable
- Bugs should produce subtly wrong output, not crashes
- Include an error log that hints at (but doesn't directly state) each bug

### Verification
- Provide expected output for comparison
- Expected output should reflect ALL fixes applied together
- Include edge cases in the expected output (groups with zero, single-member groups)

## Debug Problem Template

Debug problems follow the same folder-based layout as every other problem ([problem-design.md](problem-design.md)) — the data is in files, never an in-script literal.

```
challenges/{dNN|mockN}/qK/
├── problem.md     # pipeline description, expected behavior as business rules, error log excerpt
├── qK.ipynb       # setup / buggy pipeline function (user fixes in place) / tests
├── input/         # records as CSV / JSONL (+ decoys) — the edge cases live in these files
└── output/        # the fixed pipeline writes here; tests read it back
```

`problem.md` states the expected behavior (filter rule, dedup rule, None handling, aggregates, output sort) and includes the error log, which hints at each bug without giving away the fix. Constraint line: only modify `[function_name]`, time limit `[N]` minutes.

Notebook solution cell:

```python
def run_pipeline(input_dir: Path, output_dir: Path) -> None:
    # reads input_dir, aggregates, writes output_dir — contains the planted bugs
    ...
```

The bug list (BUG 1..N with descriptions) is designer-only: keep it in `_verify_problem.py`, where each bug doubles as a mutation — reverting any single fix must make the tests fail. Never leave `# BUG n` comments in the published notebook.
