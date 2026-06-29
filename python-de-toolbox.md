# Python DE Toolbox

The "boring" reflexes that show up in every DE scenario problem: regex, file traversal, datetime parsing, JSON streaming, error handling at boundaries. Strong DE candidates have these as muscle memory; weak ones look them up mid-exam and lose 10 minutes per problem.

## Regex (`re`)

```python
import re

ERROR_RE = re.compile(r'^\[(?P<ts>[^\]]+)\]\s+(?P<level>\w+)\s+(?P<msg>.*)$')  # named groups

m = ERROR_RE.match(line)        # match from start
m = ERROR_RE.search(line)       # find anywhere
matches = ERROR_RE.findall(text)        # list of all matches
for m in ERROR_RE.finditer(text):       # iterator of match objects (preserves groups)
    ts = m.group('ts')

# Substitution
clean = re.sub(r'\s+', ' ', text)              # collapse whitespace
masked = re.sub(r'\b\d{4}-\d{4}-\d{4}-\d{4}\b', '****', text)  # mask card numbers

# Flags
re.compile(pattern, re.IGNORECASE | re.MULTILINE)
```

**Reflexes:**
- **Compile outside loops.** `re.compile(...)` at module level. Calling `re.match(pattern, line)` inside a loop recompiles every iteration (Python caches up to 512 patterns but you should be explicit).
- **Use raw strings.** `r'\d+'` not `'\d+'` — avoids backslash hell.
- **Use named groups** for anything with > 2 captures. `m.group('ts')` reads better than `m.group(1)`.
- **`\b` for word boundary** matters: `r'\bstudio\b'` matches "studio" but not "studios" or "yoga-studio".
- **Greedy vs lazy:** `.*` is greedy (longest match), `.*?` is lazy (shortest). `<.*>` on `<a><b>` matches `<a><b>`; `<.*?>` matches `<a>` and `<b>`.

## File I/O

```python
from pathlib import Path

# Single file — text
with Path('data.csv').open(encoding='utf-8') as f:
    for line in f:                      # STREAMING — never f.read() for unknown size
        process(line.rstrip('\n'))

# Single file — bytes (binary or unknown encoding)
with Path('data.bin').open('rb') as f:
    chunk = f.read(8192)

# Folder traversal
for path in Path('logs/').glob('*.log'):           # non-recursive
    ...
for path in Path('logs/').glob('**/*.log'):        # recursive (also rglob)
    ...
for path in Path('logs/').rglob('*.log'):          # same as glob('**/*.log')
    ...

# Write
with Path('out.csv').open('w', encoding='utf-8', newline='') as f:
    import csv
    writer = csv.writer(f)
    writer.writerow(['id', 'name'])
    writer.writerows(rows)
```

**Reflexes:**
- `pathlib.Path` > `os.path`. Cleaner, type-stable, joins with `/`.
- **Always specify `encoding='utf-8'`** when opening text files. The default is platform-dependent (cp1252 on Windows, utf-8 on Mac/Linux) — production bugs await.
- **Stream lines, don't `read()` whole files.** Even if "the input is small", showing you reach for streaming is a senior signal.
- `csv.writer` with `newline=''` on the file open avoids double-newlines on Windows.

## File Filtering Traps (the #1 IO failure mode)

Per the Input Convention in [SKILL.md](SKILL.md), every problem's input folder contains decoy files. Naive enumeration will pick them up and crash or skew results. Build these reflexes:

### Enumeration patterns (pick deliberately)

```python
from pathlib import Path

folder = Path('input/')

# WRONG — picks up everything including .DS_Store, README, .bak files
for p in folder.iterdir(): ...
for p in folder.glob('*'): ...
import os; os.listdir('input/')

# RIGHT — explicit extension filter
for p in folder.glob('*.log'): ...

# RIGHT — multiple extensions
for p in folder.glob('*.csv'):
    ...
for p in folder.glob('*.tsv'):
    ...
# or with itertools.chain
from itertools import chain
for p in chain(folder.glob('*.csv'), folder.glob('*.tsv')):
    ...

# Recursive — ONLY when the spec says so
for p in folder.rglob('*.log'): ...

# Defensive: skip hidden + zero-byte files
def is_valid(p: Path) -> bool:
    return (
        p.is_file()
        and not p.name.startswith('.')
        and not p.name.endswith(('.bak', '.tmp'))
        and p.stat().st_size > 0
    )

for p in filter(is_valid, folder.glob('*.log')):
    process(p)
```

### Decoy categories you must filter against

| Decoy type | Example | Filter |
|---|---|---|
| Backup files | `data.log.bak` | exclude `*.bak` `*.tmp` `*~` |
| Hidden files | `.DS_Store` `._data.log` | exclude `name.startswith('.')` |
| Wrong extension | `notes.txt` in `*.log` folder | use `glob('*.log')` not `glob('*')` |
| Documentation | `README.md` | excluded by extension filter |
| Subdirectory data | `archive/old.log` | use `glob` (non-recursive) by default; `rglob` only if spec requires |
| Empty files | `empty.log` (0 bytes) | check `p.stat().st_size > 0`, OR process and produce empty result gracefully |
| Schema/metadata files | `schema.json` among data `*.json` | name-prefix filter, or content sniff |
| Corrupted/binary | binary bytes in `data.log` | try/except `UnicodeDecodeError`; log and skip |

### Test your filtering before running the logic

```python
# Sanity print BEFORE the main loop — costs nothing, catches bugs early
files = sorted(folder.glob('*.log'))
print(f"Found {len(files)} files: {[p.name for p in files]}")
```

A 5-second sanity print here saves 30 minutes of debugging "why is my count off?"

### Edge case: file with right extension, wrong content

Even after extension filtering, a file may contain garbage. Read defensively:

```python
for p in folder.glob('*.log'):
    try:
        with p.open(encoding='utf-8') as f:
            for line in f:
                m = ERROR_RE.match(line)
                if m:
                    counts[m.group('code')] += 1
    except (UnicodeDecodeError, OSError) as e:
        # Decide: skip silently? collect to error log? halt?
        # In an exam, prefer skip + collect to error log
        errors.append((p.name, str(e)))
```

### What this protects against (real DE-assessment scenarios)

- Folder has 5 valid logs + `README.md` + `.DS_Store` → naive `iterdir()` returns 7 items, your regex fails on README, you debug for 10 minutes
- Folder has `data.csv` + `data.csv.bak` → naive `glob('*.csv*')` picks up both, you double-count
- Folder has `archive/` subdirectory with last-month's data → naive `rglob` includes old data when the spec said "this month only"
- File `data.log` actually contains a binary protocol dump → naive open crashes, the rest of the folder is never processed

## Encoding Errors

```python
try:
    with path.open(encoding='utf-8') as f:
        data = f.read()
except UnicodeDecodeError:
    # Option A: explicit fallback encoding
    with path.open(encoding='latin-1') as f:
        data = f.read()
    # Option B: replace bad bytes (lossy but won't crash)
    with path.open(encoding='utf-8', errors='replace') as f:
        data = f.read()
```

`errors='strict'` (default) → raise on bad byte; `'replace'` → use `?`; `'ignore'` → drop the byte; `'backslashreplace'` → escape it. Pick deliberately and document why.

## CSV

```python
import csv
from pathlib import Path

# Read — dict per row (column names from header)
with Path('data.csv').open(encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        process(row['user_id'], row['amount'])

# Read — tuple per row (positional)
with Path('data.csv').open(encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        ...

# Write
with Path('out.csv').open('w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['id', 'name', 'amount'])
    writer.writeheader()
    writer.writerows(records)
```

**Trap:** `csv.DictReader` reads every value as a string. Cast types explicitly: `int(row['amount'])`. Empty cells come through as `''`, not `None` — convert with `row['amount'] or None`.

## JSON

```python
import json
from pathlib import Path

# Single JSON document
with Path('data.json').open(encoding='utf-8') as f:
    data = json.load(f)

# JSON Lines (one JSON object per line — common for logs/events)
with Path('events.jsonl').open(encoding='utf-8') as f:
    for line in f:
        event = json.loads(line)
        process(event)

# Write — pretty for humans, compact for machines
Path('out.json').write_text(json.dumps(data, indent=2, ensure_ascii=False))
Path('out.jsonl').write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in records))
```

**Reflexes:**
- `ensure_ascii=False` keeps non-ASCII characters readable (Chinese, emoji). Default `True` escapes them to `\uXXXX`.
- **JSON Lines (jsonl)** for large datasets — stream-friendly, each line independent. `json.load(f)` on a huge file blows memory.
- Use `default=str` in `json.dumps` to handle datetime / decimal without writing a custom encoder.

## Datetime

```python
from datetime import datetime, date, timedelta, timezone

# Parse
dt = datetime.strptime('2026-06-24 15:30:00', '%Y-%m-%d %H:%M:%S')
dt = datetime.fromisoformat('2026-06-24T15:30:00')        # 3.11+ handles 'Z' suffix
ts = datetime.fromtimestamp(1735000000)                   # unix → naive local
ts = datetime.fromtimestamp(1735000000, tz=timezone.utc)  # unix → UTC-aware

# Format
s = dt.strftime('%Y-%m-%d')
s = dt.isoformat()

# Arithmetic
yesterday = datetime.now() - timedelta(days=1)
seven_days = timedelta(days=7)
diff_seconds = (dt2 - dt1).total_seconds()
diff_days = (date2 - date1).days

# Truncate to day / hour / minute
day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
hour = dt.replace(minute=0, second=0, microsecond=0)
```

**Reflexes:**
- **Aware vs naive.** Always know which you have. Mixing them raises `TypeError`. For interview data, prefer aware (`tz=timezone.utc`) — the explicit reasoning shows seniority.
- **Don't compute durations across DST with naive datetimes** — answer is wrong by an hour twice a year. Use UTC.
- `total_seconds()` on a `timedelta` gives a float — use this, not `.seconds` (which is the seconds-within-the-day component, wrong for > 1 day).

## Collections

```python
from collections import Counter, defaultdict, OrderedDict, deque

# Counter — frequency
counts = Counter(['a', 'b', 'a', 'c', 'a'])         # {'a': 3, 'b': 1, 'c': 1}
counts.most_common(3)                                # [('a',3), ('b',1), ('c',1)]
counts.update(['a', 'd'])                            # adds (not replace)

# defaultdict — auto-init missing keys
groups = defaultdict(list)
for user, score in records:
    groups[user].append(score)

# defaultdict with non-callable default → use lambda
counts_by_type = defaultdict(lambda: defaultdict(int))
counts_by_type['errors']['401'] += 1

# deque — fast pop from both ends (use for sliding window state, FIFO queues)
from collections import deque
window = deque(maxlen=5)        # auto-evicts when full
```

**Reflexes:**
- `defaultdict(list)` for "group by key, append values" — beats `if k not in d: d[k] = []`.
- `Counter` for any frequency / "most common" question. Use `.most_common(n)` instead of sorting yourself.
- `Counter` supports `+`, `-`, `&` (intersection min), `|` (union max) for multiset arithmetic.

## Sorting with Tiebreakers

```python
# Sort by count desc, then by name asc (alphabetical tiebreaker)
sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

# Sort dicts by nested field
sorted(records, key=lambda r: (r['priority'], -r['amount']))

# Stable sort: two passes from least to most significant key
records.sort(key=lambda r: r['name'])            # secondary
records.sort(key=lambda r: r['priority'])        # primary (last sort wins)
```

**Reflex:** when output sort matters (it almost always does in DE problems), write the sort BEFORE returning, not "if I have time." The 4-question pre-submit ritual includes "did I sort?".

## Truthiness vs `is not None`

```python
# WRONG — filters out 0, '', [], False
if value:
    process(value)

# RIGHT — only skips actual nulls
if value is not None:
    process(value)
```

DE data has legitimate `0` values (counts, deltas, balances). Truthiness check silently drops them and skews aggregates. This is the #1 bug pattern in debug-style DE questions.

## Error Handling at Boundaries

Validate at the boundary (input parsing, external calls). Trust internal code. Don't wrap every function in try/except.

```python
def parse_event(line: str) -> dict | None:
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None         # or log + skip — decide explicitly

# Caller filters
events = [e for e in (parse_event(l) for l in lines) if e is not None]
```

**Anti-pattern:** wrapping `event['amount']` in try/except KeyError — better to assert schema once at input boundary, then trust.

## Common Iteration Idioms

```python
# Zip with index
for i, item in enumerate(items, start=1):
    ...

# Pair up adjacent items (for diff/lag calculations)
for prev, curr in zip(items, items[1:]):
    ...

# Group consecutive equal items (requires pre-sorted!)
from itertools import groupby
for key, group in groupby(sorted(items, key=keyfn), key=keyfn):
    members = list(group)        # group is a one-shot iterator — materialize it

# Flatten one level
flat = [item for sublist in nested for item in sublist]
# or
from itertools import chain
flat = list(chain.from_iterable(nested))
```

**`itertools.groupby` trap:** it groups *consecutive* equal items, not all equal items. You must sort by the same key first. The `group` value is a single-use iterator — materialize with `list()` if you need to iterate it twice.

## In-Place vs Reassignment

```python
def deduplicate(items):
    items[:] = list(dict.fromkeys(items))       # IN-PLACE — caller sees change
    # items = list(dict.fromkeys(items))        # REASSIGN — caller does NOT see change
```

When asked "modify in place" — use slice assignment `lst[:] = ...`, not `lst = ...`.

## Final Reflexes Cheat Card

| When you see... | Reach for... |
|---|---|
| Folder of files | `pathlib.Path.rglob` + streaming read with explicit encoding |
| Extract fields from text | `re.compile` at module level, named groups |
| "Group records by..." | `defaultdict(list)` or `itertools.groupby` (sorted first) |
| "Count occurrences of..." | `Counter`, then `.most_common(n)` |
| "Latest per group" | `sorted` desc + dict comprehension; or pandas/Spark window |
| Time arithmetic | `timedelta`, `total_seconds()`, aware datetime (UTC) |
| "Validate field against description" | Specific regex first, fallback regex second, negative-context regex |
| JSON file ending in `.jsonl` | Stream line-by-line, `json.loads(line)` per line |
| "Modify in place" | `lst[:] = ...`, not `lst = ...` |
| Output requires sort | Write the sort BEFORE returning, not as an afterthought |
