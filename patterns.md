# Pattern Reference

DE-relevant patterns only. Pure-algorithm content (3Sum, Two Pointers, Binary Search templates) has been deprioritized — these rarely match the DE assessment format. Focus is SQL breadth, Python data-processing reflexes, and scenario-style problem templates.

For Spark/PySpark, see the [spark/](spark/) reference folder.
For Python DE-specific reflexes (regex, pathlib, datetime, JSON), see [python-de-toolbox.md](python-de-toolbox.md).

---

# SQL — Full Breadth

## Pattern Signal Table

| Signal in Problem Statement | Pattern to Use |
|---|---|
| "each X with every Y, show 0 if none" | `CROSS JOIN` + `LEFT JOIN` |
| "latest/first record per group" | `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` + `WHERE rn = 1` |
| "running total / moving average" | `SUM/AVG OVER (ORDER BY ... ROWS BETWEEN ...)` |
| "consecutive rows / streaks" | Gap-and-Island: `id - ROW_NUMBER()` as group key |
| "ratio / percentage" | `AVG(CASE WHEN condition THEN 1 ELSE 0 END)` or `ROUND(SUM(CASE...) / COUNT(*), 2)` |
| "find employees who..." (subject = entity) | `INNER JOIN` (filter to matches) |
| "for each department, show..." (subject = group) | `LEFT JOIN` (keep all groups, including empty) |
| "second highest / Nth value" | Scalar subquery with `DENSE_RANK` or `LIMIT/OFFSET` |
| "compare each row to next/prev" | `LAG()` / `LEAD()` window function |
| "diff vs second highest" | Scalar subquery: `value - (SELECT ... ORDER BY ... LIMIT 1 OFFSET 1)` |
| "hierarchy / report-chain / tree" | `WITH RECURSIVE` CTE |
| "fill missing dates / generate series" | Recursive CTE for date generation, or LEFT JOIN against a date dimension |
| "pivot / reshape rows to columns" | `SUM(CASE WHEN ... THEN value END)` — use NULL not 0 to preserve missing |
| "find rows where range contains a value" | Range join: `JOIN ... ON v BETWEEN low AND high` |

## JOIN Decision Rule

Read the problem subject:
- **"Find employees who have..."** → query filters employees → `INNER JOIN`
- **"For each department, list..."** → query must show all departments, including empty → `LEFT JOIN`

LEFT JOIN trap: filters on the right table in the `WHERE` clause turn it back into an INNER JOIN. Move those filters into the `ON` clause to preserve unmatched left-side rows.

```sql
-- WRONG: this becomes an inner join in disguise
SELECT d.name, COUNT(e.id)
FROM dept d LEFT JOIN emp e ON e.dept_id = d.id
WHERE e.status = 'active'         -- ← excludes depts with no active emp
GROUP BY d.name;

-- RIGHT:
SELECT d.name, COUNT(e.id)
FROM dept d LEFT JOIN emp e
    ON e.dept_id = d.id AND e.status = 'active'
GROUP BY d.name;
```

## Window Function Cheat Sheet

| Function | Ties | Gaps | Use when |
|---|---|---|---|
| `ROW_NUMBER()` | Arbitrary | None (1,2,3) | "the latest record per group" — pick exactly one |
| `RANK()` | Same rank | Gaps after ties (1,1,3) | "top 3 with ties" if you want to award ties the same rank but skip next |
| `DENSE_RANK()` | Same rank | No gaps (1,1,2) | "Nth highest distinct value" |
| `LAG(col, n)` | — | — | Compare row to one N rows earlier |
| `LEAD(col, n)` | — | — | Compare row to one N rows later |
| `SUM/AVG/COUNT OVER` | — | — | Running totals, moving averages, partition totals |

### Window Frame (when it matters)

```sql
-- Running total up to and including current row
SUM(amount) OVER (PARTITION BY user_id ORDER BY ts
                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)

-- Trailing 7-day window (assumes day-level rows)
SUM(amount) OVER (PARTITION BY user_id ORDER BY day
                  ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
```

Default frame for an ordered window with an aggregate is `UNBOUNDED PRECEDING → CURRENT ROW` — be explicit when you want partition total or trailing window.

## Recursive CTE

When to reach for it (signal recognition):
- The data has a **parent-child reference** within one table (employee→manager, comment→parent_comment, category tree).
- You need to **fold a sequence of dependent operations** (state replay where step N depends on result of step N-1, and you can't decompose with window functions because state is non-monotonic).
- You need to **generate a series** (dates, numbers) and there's no convenient external source.

When you DON'T need it (avoid the trap):
- Per-group state machine where state only goes forward — window functions handle this.
- "Latest per group" — `ROW_NUMBER` over `ORDER BY ts DESC`.
- Running totals — `SUM OVER`.

### Template — Hierarchy Walk

```sql
WITH RECURSIVE org AS (
    -- anchor: roots (no manager)
    SELECT emp_id, name, manager_id, 0 AS depth, CAST(name AS CHAR(500)) AS path
    FROM employees
    WHERE manager_id IS NULL

    UNION ALL

    -- recursive: join children to known parents
    SELECT e.emp_id, e.name, e.manager_id, o.depth + 1,
           CONCAT(o.path, ' > ', e.name)
    FROM employees e JOIN org o ON e.manager_id = o.emp_id
)
SELECT * FROM org ORDER BY depth, name;
```

**MySQL gotchas:**
- `CAST(name AS CHAR(500))` in the anchor — without it, the recursive `CONCAT` truncates because the column type is inferred from anchor width.
- `cte_max_recursion_depth` defaults to 1000. For very deep trees: `SET SESSION cte_max_recursion_depth = 10000;`
- Must use `UNION ALL` (not `UNION`) for true recursion in standard syntax.

### Template — Date Series

```sql
WITH RECURSIVE dates AS (
    SELECT DATE '2026-01-01' AS d
    UNION ALL
    SELECT d + INTERVAL 1 DAY FROM dates WHERE d < DATE '2026-01-31'
)
SELECT d, COALESCE(SUM(amount), 0) AS revenue
FROM dates LEFT JOIN sales ON sales.sale_date = dates.d
GROUP BY d ORDER BY d;
```

## NULL Reflex (common DE-assessment gap — make it automatic)

```sql
-- Scalar subquery returning NULL when no matches
-- This will make the whole expression NULL:
SELECT value - (SELECT SUM(amount) FROM ...) AS remaining     -- BAD

-- Wrap with COALESCE:
SELECT value - COALESCE((SELECT SUM(amount) FROM ...), 0) AS remaining   -- GOOD

-- LEFT JOIN aggregate where some rows have no match:
SELECT d.name, COALESCE(SUM(e.salary), 0) AS total
FROM dept d LEFT JOIN emp e ON e.dept_id = d.id
GROUP BY d.name;

-- Comparing nullable columns: NULL != NULL
WHERE a.col = b.col              -- false when either is NULL
WHERE a.col <=> b.col            -- MySQL null-safe equality
WHERE COALESCE(a.col, '') = COALESCE(b.col, '')   -- portable
```

## Scalar Subquery Pattern

When you need a single value to use in a column expression:

```sql
-- Second highest salary
SELECT (
    SELECT DISTINCT salary
    FROM employee
    ORDER BY salary DESC
    LIMIT 1 OFFSET 1
) AS second_highest;

-- Diff from max
SELECT name, salary,
       (SELECT MAX(salary) FROM employee) - salary AS diff_from_top
FROM employee;
```

**Trap:** if the subquery returns no rows, the result is NULL → wrap arithmetic with `COALESCE`.

## Gap-and-Island

```sql
-- Find consecutive day streaks of activity per user
SELECT user_id, MIN(activity_date) AS streak_start, MAX(activity_date) AS streak_end, COUNT(*) AS streak_days
FROM (
    SELECT user_id, activity_date,
           DATE_SUB(activity_date,
                    INTERVAL ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY activity_date) DAY) AS grp
    FROM activity
) sub
GROUP BY user_id, grp;
```

The trick: subtract a row number from a sequential value — consecutive items get the same group key, gaps create new groups.

## Date Functions (cross-dialect quick ref)

| Need | MySQL | Postgres |
|---|---|---|
| Add 7 days | `d + INTERVAL 7 DAY` | `d + INTERVAL '7 days'` |
| Diff in days | `DATEDIFF(a, b)` | `a - b` (integer) |
| ISO week | `WEEK(d, 3)` | `EXTRACT(WEEK FROM d)` |
| Year-month | `DATE_FORMAT(d, '%Y-%m')` | `TO_CHAR(d, 'YYYY-MM')` |
| Truncate to month | `DATE_FORMAT(d, '%Y-%m-01')` | `DATE_TRUNC('month', d)` |

`WEEK()` in MySQL has 8 modes (0-7) controlling week-start day and first-week rule. For ISO 8601 weeks, use mode 3 or `YEARWEEK(d, 3)`. Read the spec when in doubt; don't guess.

---

# Python — DE-Relevant Patterns Only

For DE-specific Python toolbox (regex, pathlib, datetime, JSON, error handling), see [python-de-toolbox.md](python-de-toolbox.md).

## Sliding Window (genuinely useful in DE — keep)

### When to Use
- Contiguous subarray / substring problem
- Longest / shortest / min / max of a contiguous span
- Window-with-condition problems (e.g., "longest period with < 3 errors")

### Shrink Rule
- **Finding shortest** → `while` (shrink as much as possible after each expansion)
- **Finding longest** → `if` (slide; only shrink once per step)
- Always sync auxiliary state (set/dict/Counter) when removing elements

### Template
```python
left = 0
for right in range(len(s)):
    # expand: add s[right] to window state
    while/if SHRINK_CONDITION:
        # shrink: remove s[left] from window state
        left += 1
    # update answer
```

## Prefix Sum + HashMap (useful in DE — keep)

### When to Use
- "Number of subarrays whose sum equals K" — especially with negatives (sliding window breaks)
- Cumulative state + "looking for a complement" — same shape as Two Sum

### Template
```python
from collections import defaultdict

def subarray_sum(nums, k):
    seen = defaultdict(int)
    seen[0] = 1                       # empty prefix
    prefix = 0
    count = 0
    for num in nums:
        prefix += num
        count += seen[prefix - k]     # CHECK first
        seen[prefix] += 1             # then UPDATE
    return count
```

Order matters: check before update, otherwise current element can be both start and end of a zero-length subarray.

## De-emphasized (here for reference only)

These patterns rarely match the DE assessment style. Recognize the signal; don't drill the templates.

| Pattern | When to recognize | Action |
|---|---|---|
| Two Pointers (sorted array) | Two-pair sum, container, palindrome | Know it exists; not worth template practice for DE |
| 3Sum / NSum | Triplet/Nth sum problems | Same — recognize but don't drill |
| Binary Search | Sorted lookup, "find boundary" | Know `bisect_left`/`bisect_right`; skip implementing from scratch |
| Tree/Graph traversal | Hierarchy/network problems | In SQL DE work, recursive CTE replaces this. In Python, only if explicitly asked |
| DP | Optimal-subproblem combinatorics | Effectively never in DE assessments |

---

# Scenario Templates (real DE-assessment patterns — drill these)

These are the *real* shapes DE assessments take. Use them as templates when designing or solving practice problems.

## Template A — Log File Pipeline

**Setup:** given a folder of log files, read all, regex-extract ERROR (or some event) lines, aggregate/report.

**Tests for:**
- File enumeration: `pathlib.Path.glob("**/*.log")` or `os.scandir` for nested traversal
- Streaming read: `for line in f` (not `f.read()` — files may be large)
- Encoding handling: open with explicit encoding, handle `UnicodeDecodeError` (try latin-1 fallback, or `errors='replace'`)
- Regex compile placement: `re.compile(pattern)` OUTSIDE the loop, not inside (recompiles every line)
- Structured output: usually a dict aggregation or write to a new file in CSV/JSON

**Senior signals:**
- Handles empty files and missing folder gracefully
- Doesn't load full file into memory
- Captures encoding errors with context (which file, which line)
- Separates parsing from aggregation (testable in isolation)

**Skeleton:**
```python
import re
from pathlib import Path
from collections import defaultdict

ERROR_RE = re.compile(r'^\[(?P<ts>[^\]]+)\]\s+ERROR\s+(?P<code>\w+):\s+(?P<msg>.*)$')

def scan_logs(folder: Path) -> dict:
    counts = defaultdict(int)
    for path in folder.glob("**/*.log"):
        try:
            with path.open(encoding='utf-8') as f:
                for line in f:
                    m = ERROR_RE.match(line)
                    if m:
                        counts[m.group('code')] += 1
        except UnicodeDecodeError:
            # fallback or log and skip — make the choice deliberate
            ...
    return dict(counts)
```

## Template B — Description-Based Field Validation (Semantic Disambiguation)

**Setup:** records with a free-text `description` plus structured fields. Validate the structured fields against the description.

**Example:** "1-bedroom near yoga studio" → property_type should be "1-bedroom", not "studio" (the word "studio" appears but as part of "yoga studio" — not the property type).

**Tests for:**
- Pattern priority: try the more specific pattern first (`\d+-bedroom`), fall back to simpler (`studio`)
- Negative context: "near X" / "next to X" / "across from X" means X is a neighbor, not the entity
- Case insensitivity: `re.IGNORECASE`
- Variants: singular/plural (bedroom/bedrooms), numeric vs written (1-bedroom vs one-bedroom)
- Conflict reporting: when description says one thing and the field says another, what's the output?

**Naive solution that fails:** `if 'studio' in description.lower(): property_type = 'studio'`

**Better:**
```python
import re

BEDROOM_RE = re.compile(r'\b(\d+|one|two|three|four|five)[-\s]?(?:bed|bedroom)s?\b', re.IGNORECASE)
STUDIO_RE = re.compile(r'\bstudio\b', re.IGNORECASE)
NEGATIVE_PREFIX_RE = re.compile(r'(?:near|next to|across from|by the)\s+\w+\s+studio', re.IGNORECASE)

def infer_property_type(desc: str) -> str:
    if BEDROOM_RE.search(desc):
        return 'bedroom'
    if STUDIO_RE.search(desc) and not NEGATIVE_PREFIX_RE.search(desc):
        return 'studio'
    return 'unknown'
```

## Template C — Multi-Step Transformation Pipeline

**Setup:** input records go through 4-6 transformation rules: filter invalid → dedup → join with reference data → derive new fields → aggregate → sort.

**Tests for:**
- Reading the spec carefully (each rule is one line buried in a long prompt)
- Sequencing — dedup before or after filter changes output
- Operating consistently on None / empty / missing
- Final sort key (very commonly forgotten)
- Output format: dict-of-lists vs list-of-dicts vs CSV-shaped tuples

**Senior signals:**
- Each step is a separate function — easy to test, easy to swap order
- Validation/filtering at the boundary, business logic uses clean data
- Returns immutable structures, doesn't mutate input

## Template D — Sessionization

**Setup:** event stream with timestamps; events within N minutes of each other are one session. Compute session count per user, session duration, etc.

**Pattern:** sort by user + ts → compute gap to previous event → mark "new session" when gap > threshold → cumulative sum of new-session flags = session id.

See [spark/window-sessionization.md](spark/window-sessionization.md) for the Spark version. In pandas: `df.sort_values([uid, ts]).groupby(uid)[ts].diff().gt(threshold).cumsum()`.

---

# Pre-Submit Ritual (the 4 questions)

After writing ANY query (SQL, Spark, or Python aggregation), before submitting, answer:

1. **What does this return for the empty set?** (No matching rows. Does it return 0? NULL? Crash?)
2. **Is there a SUM/AVG/COUNT used in arithmetic afterward?** → wrap with `COALESCE(..., 0)` / `F.coalesce(..., F.lit(0))` reflexively.
3. **INNER vs LEFT JOIN — should unmatched rows be preserved?** (LEFT JOIN with WHERE on right table = INNER JOIN trap.)
4. **Do boundary cases (first/last/single row) behave correctly?** (LAG/LEAD on first row returns NULL — handle it.)

These 4 questions take 30 seconds and catch most of the hidden test failures.
