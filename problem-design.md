# Problem Design Guide

Read this before authoring or editing ANY practice problem (warm-up day, drill, or mock question). It is the single source of truth for input layout, notebook layout, the `problem.md` template, calibration tags, and the pre-publish checks. Coaching-side material (Pre-Submit Ritual, 4-Stage Solving Template, code review) lives in [SKILL.md](SKILL.md); mock composition and scoring live in [mock-exam-guide.md](mock-exam-guide.md).

## Contents

- Input Convention (folder-based, with decoys)
- Challenge File Convention (Jupyter + assert)
- Problem Design Pre-flight Checklist (Rules 0 / 0.5 / 0.75 + Checks 1-9)
- Problem Calibration (Reading × Operations, `problem.md` template, cell-0 pointer)

## Input Convention (folder-based, with decoys)

**All practice problems use folder-based input.** Never use in-script literals like `data = [(1,'a'), ...]` — that hides the real-world IO/parsing skill that DE assessments test.

### Standard layout

```
challenges/dXX/
├── input/                  # the user's solution reads from here
│   ├── ...real files...
│   └── ...decoy files...
└── expected_output.json    # for verification
```

### Decoy files (always include)

Every input folder MUST include decoy files to test the user's file-filtering reflex. The minimum scales with the problem's Operation Depth tag (see Problem Calibration):

| Calibration | Min decoys | Decoy types to include |
|---|---|---|
| **O:Easy** | 1-2 | Wrong extension, or hidden file |
| **O:Medium** | 2-3 | Wrong extension + backup file (.bak) + hidden |
| **O:Hard** | 3-5 | All of medium + subdirectory + empty file + encoding edge case |

Decoys are planted physically in `input/` and are NEVER listed in the problem statement — the user discovers them.

**Decoy content rule — at least one decoy per problem must be format-valid.** A decoy holding `junk` only proves the solution survives garbage: a naive reader crashes loudly (which the user fixes by adding a try/except, not by fixing the glob) or the junk lands in a malformed-row counter. The decoy that trains the reflex is a stale backup or archive file whose rows parse cleanly and would CHANGE the output if read — extra counts, a different latest-record winner, an extra group. Its rows use keys or dates that appear in no target file, so a leak is attributable. Do not label them (`DECOY-001`) — the file name is the only tell.

Common decoys:

- `*.bak` / `*.tmp` — backup or temp files (must be excluded)
- `README.md` / `NOTES.txt` — human-readable junk
- `.DS_Store` / `._*` — macOS hidden files
- `*.csv` mixed in a `*.log` folder (or vice versa)
- `schema.json` in a folder of data `*.json` files
- Sub-folder `archive/` with older files (does the user know to recurse or not?)
- Empty file (`empty.log` with 0 bytes)
- A file with the right extension but wrong content (binary garbage in `data.log`)

### Reflexes this trains

- `pathlib.Path('input/').glob('*.log')` — explicit extension filter
- `Path.rglob` only when the spec says to recurse, NOT by default
- Skip hidden files: `if not p.name.startswith('.')`
- Handle empty files: `if p.stat().st_size == 0: continue` (or process and produce 0 results gracefully)
- Wrap file open in try/except for `UnicodeDecodeError`

### Anti-patterns (failure modes to watch for)

- `os.listdir()` returning everything including `.DS_Store`
- `glob('*')` matching every file regardless of extension
- Assuming `Path.iterdir()` excludes hidden files (it doesn't)
- Assuming all files in the folder are valid input
- Reading every file as utf-8 with no error handling
- Loading `f.read()` on a file of unknown size

### Coaching rule

When the user submits a solution to a folder-based problem, the first thing to check is the file enumeration line. If it's `os.listdir()` or `glob('*')`, that's a Pre-Submit Ritual miss — even if the rest of the logic is correct, the hidden test case with decoys would fail.

## Challenge File Convention (Jupyter + assert)

Problems live in Jupyter notebooks, one notebook per day. The user can run cells in any order, edit solutions in place, and the assert-based tests at the bottom of each problem tell them pass/fail without needing the coach to verify.

### Folder layout

```
challenges/
├── d{NN}/                   # warm-up / practice day (d01, d02, ...)
│   ├── d{NN}.ipynb          # single notebook holding all problems for the day
│   └── input/               # data files per Input Convention (target + decoys)
│       ├── ...target...
│       └── ...decoys...
└── mock{N}/                 # mock exam (mock1, mock2, ...) — DIFFERENT layout
    ├── q1/
    │   ├── q1.ipynb         # per-question notebook (one Q = one notebook)
    │   ├── input/           # this question's input files (with decoys)
    │   └── output/          # this question's solution writes here
    ├── q2/
    │   ├── q2.ipynb
    │   ├── input/
    │   └── output/
    └── ...
```

Examples: `challenges/d01/d01.ipynb`, `challenges/mock1/q3/input/access-2026-06-01.log`.

**Why mocks differ from practice days:** Mock questions must be fully independent — own folder, own I/O, own notebook — to simulate the real assessment (each problem is a self-contained pipeline the user owns end-to-end). Practice days share a notebook to keep iteration fast. See [mock-exam-guide.md](mock-exam-guide.md) for the full mock structure rules.

### 3-Part Notebook Structure (warm-up days)

To balance teaching depth with realistic exam preparation, use a 3-part layered structure:

**Part 1: Core (teaching-style)** — 5 problems with full trade-off discussions in problem markdown, diagnostic hints in tests. Reading time and time targets generous.

**Part 1.5: Extensions (reflection)** — After each Core problem's tests pass, a 🔬 Extension markdown cell poses 2-4 "what if?" questions. No new code required (or optional). Builds depth without bloating problem count.
  - Examples: "What if users table was 1B rows?", "What if amount column was sometimes NULL?", "Why doesn't Spark broadcast both sides?"

**Part 2: Sub-pattern (advanced variants)** — 3 problems exploring related techniques the Core didn't cover (e.g., self-join, conditional ANTI, explicit schema). Still has problem statement context but less trade-off scaffolding.

**Part 3: Cold problem (cold-start, no scaffolding)** — 1 problem at the end with:
  - Full business context narrative (multi-paragraph statement)
  - NO trade-off list, NO diagnostic hints, NO "use this approach" suggestion
  - Single assert block with overall expected output
  - User must self-decide join type, dedup approach, output format
  - Followed by a retro markdown for self-reflection (time taken, where stuck, which Pre-Submit Ritual missed)

This layered structure trains: idiom recognition (Core) → depth thinking (Extension) → variant fluency (Sub) → exam-style independence (Cold).

### Single-section notebook structure (per Core/Sub problem)

```
[Markdown] # D{NN} — <day title>
[Markdown] ## Setup (imports + Spark session if needed)
[Code]     # imports, SparkSession.builder...

[Markdown] ## DN-P1 — <problem name>
[Markdown] **Target:** X min. **Calibration:** [R:_, O:_]
           Problem statement. Input folder. Expected output. Trap cases.
[Code]     # SOLUTION — user fills in
           def solve_p1(...):
               ...
[Code]     # TESTS — already written, just run
           # assert correctness, edge cases, output shape, sorting
           print("✓ DN-P1 passed")

[Markdown] ## DN-P2 — <problem name>
[Code]     # SOLUTION
[Code]     # TESTS
... and so on
```

### Assert test design rules

Tests must catch what hidden test cases would catch — happy path, edge cases, NULL/empty handling, output ordering. Each `assert` carries a clear message so failures point at the bug, not the assertion line.

```python
# Required test categories per problem (when applicable):
# 1. Happy path
result = solve(sample_input)
assert result == expected_happy, f"Happy path: expected {expected_happy}, got {result}"

# 2. Empty input — commit to ONE expected value per problem; `a or b` accepts both and tests nothing
assert run_on(empty_dir) == [], "Empty input must produce an empty result, not a crash"
# 3. Single element / single row
# 4. Boundary (first / last / single group)
# 5. NULL / missing value handling
# 6. Output sort key
assert result == sorted(result, key=...), "Output not sorted by required key"
# 7. For folder problems: decoy leak — assert on the solution's OUTPUT.
#    Never glob inside the test and count files: that checks the test's own glob, not the solution.
leaked = [r for r in result if r['order_id'] in DECOY_ONLY_IDS]   # ids that exist only in decoy files
assert not leaked, f"Decoy leak — rows from non-target files reached the output: {leaked[:3]}"

print("✓ DN-PX passed all checks")
```

### Why this design

- **Self-verification:** running the test cell is unambiguous — green text or red traceback. No back-and-forth needed.
- **Iteration speed:** user edits solution cell, re-runs both cells, sees result immediately.
- **Matches real exam format:** CodeSignal-style assessments give you sample tests up front + hidden tests behind. The user-visible assert cell mirrors the sample tests; the coach occasionally adds "stretch" asserts that mirror hidden tests.
- **Decoy leak gets its own assert for the message, not the detection:** with a format-valid decoy the happy-path equality already fails on a leak; the dedicated assert just names the cause instead of showing a row diff.
- **Catches Pre-Submit Ritual misses automatically:** the empty / NULL / boundary asserts ARE the Pre-Submit Ritual in code form.

### Coaching workflow

When creating a new problem:
1. Edit the day's notebook with NotebookEdit (cell_type=markdown for statement, code for solution scaffold + tests)
2. Solution cell starts as `def solve_pN(...): raise NotImplementedError("TODO")` — clearly unfinished
3. Tests cell is COMPLETE — the user can run it immediately after writing the solution
4. When the user reports back, ask them to share the test output. Green = pass, red = read the trace + ritual + edit solution.
5. Once the attempt is reviewed, record it in the progress log ([SKILL.md](SKILL.md) §Progress Log).

### What to keep OUT of the notebook

- No in-script literal data (`data = [(1,'a'), ...]`) — per Input Convention, all data lives in `input/` folder files
- No solutions in the same notebook as the problem (resist filling in solve_pN unless user asks for guidance)
- No `# expected output: ...` comments where assert can do the same work — the assert IS the expected output

## Problem Design Pre-flight Checklist (MANDATORY before publishing a new problem)

Walk through every check below before adding a problem to a notebook or Notion. Skip a check ONLY if the design intentionally tests that property — and document that intent in the problem markdown so it's visible to the user.

### 🚨 Rule 0: ACTUALLY RUN the canonical solution

Before writing any assert or expected output, **run the canonical solution against the actual test data** (or trace it exhaustively row-by-row). Copy the real output. Don't mental-trace, don't guess, don't trust "I think this should be X".

Empirically, almost all design bugs would have been caught by running the canonical solution once before writing the assert:
- Forgotten data interactions surface in the actual output
- Library-specific output strings appear in real form (e.g., `df.dtypes` returns `'int'` not `'integer'`)
- Edge cases either trigger or don't, visibly
- Gaps in test data that fail to exercise required steps become obvious

**Rule:** test design is data + assertion. If you write the assertion without measuring against the data, you're guessing. Stop guessing.

### 🚨 Rule 0.5: Mutation-verify before publishing (automated "test must bite")

Running the canonical solution proves the expected values are right; it does NOT prove the test catches wrong solutions. Before publishing, run a **mutation harness** (a `_verify_problem.py` script alongside the problem):

1. Implement the canonical solution — its output defines `expected`.
2. Implement **≥3 plausible wrong solutions** (mutations) — one per required step / trap: skip-the-filter, wrong comparison operator (`>=` vs `>`), wrong join type, missing sort, dedup-when-you-shouldn't, hardcoded config, wrong date anchor, misuse of read options. **Folder problems always include the naive-enumeration mutation** (file filter replaced by `glob('*')` / `rglob('*')`); see Check 7.
3. Assert every mutation's output **differs** from canonical (or raises). A mutation with identical output = the test data does not bite that failure mode → **redesign the data**, then re-run.

Empirically this catches gaps that survive all manual checks: on its first run against a freshly designed problem set it found (a) no duplicate timestamps existed, so dedup-style wrong answers passed; (b) a "more than 30 minutes" rule had no exactly-30-minute gap in the data, so `>=` vs `>` was indistinguishable. Manual review had walked past both.

Publish only when the harness prints all-caught.

### 🚨 Rule 0.75: Adversarial spec review (fresh-eyes pass on the PROSE)

Rule 0 and Rule 0.5 verify the data-and-test layer; **neither can see defects in the problem statement's wording** — and author blindness guarantees you won't either. Before publishing, have a reviewer with **no authoring context** (a fresh subagent given only the problem.md) attack the statement:

1. **Counting-unit consistency** — does every output column name the unit that exists *after* the transforms? (A dedup rule followed by a `line_count` column is a contradiction — the unit became requests.)
2. **Antecedent check** — every pronoun/reference ("that row", "its timestamp") must resolve unambiguously *even where rules interact* (which row's timestamp, after dedup merges rows across days?).
3. **No negative implementation warnings** — "do not use X as the basis" telegraphs the planted trap. State the semantics and disclose the data property; the wrong approach must fall out, not be labeled.
4. **Forcing constraints stated** — any design choice that looks arbitrary (a global count in a sidecar file, a fixed config in code) must carry the constraint that forces it, or it invites a justified "why?" that the statement can't answer.
5. **Value domains** — stated when the output shape depends on them (pivot columns, zero-rows, fixed classification buckets); explicitly declared open when the logic must be value-agnostic.
6. **Premise realism** (Sub-check 8c) — would the business story survive one design-review question from a senior?

The reviewer's job is to find the question a careful candidate would be forced to ask mid-exam. Every such question found = a fix before publishing. Empirically this layer produced more escaped defects than the data layer once the mutation harness existed — the harness moved the bottleneck to the prose.

### ☑ Check 1: Test bites every required step

This is the design-time form of Rule 0.5: ask the question below while building the data, then let the mutation harness (one mutation per required step) prove the answer. The harness result is authoritative.

For each step in the canonical solution, ask: **"If the user skips this step, does ANY assert fail?"**

- If no → the test is broken. Fix by: redesigning data, changing parameters, or adding an explicit step-checking assert.
- Common case: a "filter by date" or similar step where all test data happens to satisfy the filter — student can skip the filter and still pass. Fix by inserting data points that fall OUTSIDE the filter so the filter actually drops rows.

**Sub-check 1b: Sort verification must NOT rely on accidental data order**

If spec requires `sort by X`, the test must catch a missing sort. `assert result == expected` (list equality) only catches it IF the input data wouldn't naturally come out in that order. For small data + Window/groupBy operations, Spark often produces output that's already sorted by partition key — which masks a missing final `.orderBy()` in user code.

**Fix patterns:**
- Insert input data in scrambled order so unsorted output is visibly wrong
- OR add explicit assertion: `assert result == sorted(result, key=lambda r: r[0])` (independent of expected list)
- OR shuffle input within test cell before passing to user solution

Counter-example: a test where input is `[s1, s2, s3, ..., s8]` and user does `Window.partitionBy('student_id')` will get output in s1..s8 order even without explicit `.orderBy('student_id')`. Test passes, but production data would shuffle this and break.

### ☑ Check 2: Expected output reconciled against an enumeration table

- The expected values come from RUNNING the canonical solution (Rule 0) — never from a hand trace
- The enumeration table below is the independent cross-check: every row of the measured output must be explainable from it. A row you can't explain is either a bug in the canonical solution or a data interaction you forgot — resolve it before publishing
- Common miss: forgetting how data designed for one problem (e.g., a dedup pair) affects another problem's count or aggregate

**How to actually enumerate (not skip-checking):**

For a problem with filter + join + groupBy logic, build a table BEFORE accepting the measured output as expected:

| entity | All its data | Matches filter? | In expected? |
|---|---|---|---|
| entity_1 | rows A, B, C | row A matches | depends on logic |
| entity_2 | rows D, E | both match | depends on logic |
| entity_3 | row F | doesn't match | depends on logic |
| ... | ... | ... | ... |

Don't skip rows. Don't trust "I think this entity has no X". Verify EVERY data point.

**Sub-check 2a: Library-specific output strings must be MEASURED, not guessed**

When tests compare against library output strings (e.g., `df.dtypes` output, error messages, plan strings), the canonical answer must be MEASURED, not assumed from type names.

Common traps:
- PySpark `df.dtypes`: `IntegerType` → `'int'` (NOT `'integer'`), `LongType` → `'bigint'`, `ShortType` → `'smallint'`
- Spark plan strings differ between Spark versions (3.x vs 4.x output formatting)
- Error messages can change between minor versions

Rule: for any assert that depends on a string the library produces, run the canonical solution once before publishing. Copy actual output, don't guess.

### ☑ Check 3: Cross-problem data interactions

When sharing data across problems in a single day, trace through **EACH problem** to ensure each has the right expected.

- For each problem, list which "data quirks" are relevant
- For each quirk, decide explicitly: is its effect on this problem intentional, or a side effect?
- Example: a dedup pair (intentional for a dedup-test problem) will ALSO appear as 2 separate rows in a count-per-day problem — that count must reflect both rows, not "the deduped 1".

### ☑ Check 4: Ambiguity audit

Where could two reasonable people disagree on the expected output? Common sources:
- Whether to dedup before counting (when input has suspicious-looking duplicates)
- Whether NULL counts as 0 / skipped / its own category
- Inclusive vs exclusive date boundaries (`>` vs `>=`)
- Sort tie-breaking when ties exist
- **Entity scope: "every X" — does X mean "every X in master table" or "every X mentioned in fact table"?** (E.g., "for each student" could mean students.student_id or distinct enrollments.student_id. Different if orphan enrollments exist.)
- **Multi-table reference: which table is canonical source of truth?**

**For each ambiguity, pick one of:**
- **A.** Pick one interpretation and state it EXPLICITLY in problem markdown (test enforces that interpretation)
- **B.** Turn it into a critical-thinking lesson — show all valid readings, explain why test uses one, mention the senior 3-step pattern (detect → ask → state assumption)

Never leave ambiguity silent.

### ☑ Check 5: ID semantics (when dedup is involved)

If dedup is part of the canonical solution:
- Is there a proper business-event ID in the data? (`order_id`, `idempotency_key`, `transaction_id`)
- If only row PK (`event_id`) exists, the "duplicate" is ambiguous — could be system bug OR legitimate concurrent transaction
- Dedup by row PK is **never** semantically dedup; it's just deduping by uniqueness
- Dedup by (user_id, ts, type, amount) without a proper ID is **heuristic** — could kill real transactions

If you intentionally exclude business ID to test critical thinking, make this lesson visible in the markdown.

### ☑ Check 6: Edge case enumeration via Pre-Submit Ritual

The 4 Pre-Submit questions (defined in [SKILL.md](SKILL.md)) applied to TEST DESIGN (not just solution):

1. **Empty set**: Does test penalize a solution that crashes on empty input? (Add a "no matching rows" scenario)
2. **Aggregate in arithmetic**: If solution requires COALESCE, does data have an all-NULL group to expose this?
3. **INNER vs LEFT**: Does data have orphan rows or unmatched lefts to make the join-type choice matter?
4. **Boundary**: Does data exercise first/last/single-row cases? Does test enforce output sort?

### ☑ Check 7: Decoy file alignment

- Are decoys placed per Input Convention (count per O level, at least one format-valid)?
- Does the mutation harness include a **naive-enumeration mutation** — the canonical solution with its file filter replaced by `glob('*')` / `rglob('*')` / `iterdir()` — and is it CAUGHT by a wrong output, not merely by a crash?
- Does the test detect the leak from the solution's output? A test that globs the folder itself and asserts the file count verifies nothing about the solution.

### ☑ Check 8: Solving template alignment

- Problem statement maps to the 4-Stage Solving Template ([SKILL.md](SKILL.md))
- Pre-Submit Ritual lives in the paired Notion prep/retro page and, in code form, in the edge-case asserts — never as a checklist in `problem.md` or the notebook markdown
- For warm-up days: Extension question follows the problem (markdown cell with 🔬 prefix)
- For Cold problems: NO trade-off discussion, NO diagnostic hints, NO scaffold — only statement + assert

**Sub-check 8a: Don't frame problems by tool name**

- Frame problems by **goal** (e.g., "find users with 2+ same-day purchases"), not by **tool** (e.g., "self-join problem")
- If the title or problem says "use X", the natural solution must actually need X
- Common failure: writer wants to cover technique X, fabricates a problem whose natural solution is technique Y → "use X" framing forces over-engineering
- Rule: pick a tool first, then construct a problem where that tool is the natural solution. Don't pick a problem and force-fit a tool name.

**Sub-check 8b: No thinking-aloud in problem statements (final polish)**

- Problem statements must read like **finished spec**, not like a draft with the author's mind-changing visible
- Anti-patterns to remove before publishing:
  - "Find X — wait, this is too complex, let me simplify to..."
  - "Find X (or maybe Y, depending on how you read this)"
  - "**Simplified restatement:** ..." (signals the original was ambiguous and wasn't replaced)
  - "Note: actually this might be ambiguous so..." (use Check 4 ambiguity audit format instead)
- Rule: decide the final problem before writing. If during writing you realize the original frame doesn't work, rewrite from scratch, don't leave both versions.
- If the problem GENUINELY has multiple valid readings (ambiguity audit, Check 4), present them in a structured way (A/B/C readings) NOT as inline iteration.

**Sub-check 8c: Requirements must be motivated by realistic premises**

- Don't invent a contrived business story to force an implementation choice. Failure example: "the business team edits this config file directly, so your solution MUST read it dynamically — hardcoding is forbidden." In a real org, a config whose change alters report semantics goes through review + redeploy anyway, so a reviewed constant in code is a defensible (often better) choice — the mandate teaches the wrong engineering judgment and collapses under one design-review question.
- To genuinely test parameterization, make the parameter **part of the input data**: a config/dimension file among the run's input datasets, or a multi-tenant framing (many products, each definition arrives as data) where hardcoding is self-evidently absurd. The requirement then emerges from the scenario instead of being decreed.
- Litmus test: if a candidate can argue "that premise wouldn't survive in a real org, therefore the requirement is wrong," the problem loses authority. Fix the premise, not the candidate.
- This defect class is invisible to the mutation harness (Rule 0.5) — only a design review against production reality catches it.

### ☑ Check 9: Numeric precision commitment (money / measurement)

If the canonical solution does any equality / inequality comparison on aggregated numeric fields (money, quantities, ratios, timestamps-as-numbers), the spec MUST commit to precision handling. Silence = broken test.

**The failure mode:**
- Amount stored as `DoubleType`
- Canonical does `F.sum(amount) == target` or similar
- IEEE 754 accumulator drift (~1e-13) causes false negative → misclassification
- Concrete: `$2508.06` summed once → `2508.0600000000004` → `==` returns false

**Fix (one of):**
- **A**: Use `DecimalType(precision, 2)` end-to-end in schema. Test expected computed with Decimal. `==` is safe.
- **B**: Keep `DoubleType` but spec explicitly requires `round(x, 2)` or `abs(a - b) < 0.01` before comparison. Test expected computed with the same rounding.
- **C** (recommended for money): Both — schema is Decimal AND the clarifications include a "float trap" teaching note.

Never leave the spec silent when currency / aggregated numerics feed into comparisons.

### Checklist summary table (workflow shortcut)

When designing problem N:

| # | Check | Quick test |
|---|---|---|
| R0 | Canonical solution actually run | Expected copied from real output, not a mental trace? |
| R0.5 | Mutation harness | ≥3 plausible wrong solutions, all caught? |
| R0.75 | Adversarial spec review | Fresh reviewer with only `problem.md` finds no forced question? |
| 1 | Test bites every step | Skip step → assert fail? (proven by R0.5) |
| 2 | Expected reconciled by enumeration | Every measured output row explained by the entity table? |
| 3 | Cross-problem interactions | Trace each problem's expected on shared data |
| 4 | Ambiguity audit | Where could reasonable people disagree? |
| 5 | ID semantics | Business ID for dedup, or intentional teaching point? |
| 6 | Edge cases (4Q ritual) | Empty / NULL aggregate / Join type / Boundary all tested? |
| 7 | Decoy alignment | Naive-enumeration mutation caught by wrong output (format-valid decoy present)? |
| 8 | Template alignment | 4-stage mapping OK? Ritual in Notion + asserts, not in notebook? Extension (warm-up) included? |
| 9 | Numeric precision | Money / aggregated numerics feed into ==? Decimal or explicit round in spec? |

A problem that fails any check is a **draft**, not a final. Either fix the check or document the intentional exclusion in the markdown.

## Problem Calibration (two independent axes)

DE problem difficulty has two dimensions that vary independently. Always tag problems on BOTH axes — a "Hard" label alone is ambiguous and is a common root cause of mis-calibrated DE interview prep (LeetCode-style "Hard" often differs from real DE-assessment "Hard" on the reading axis).

### Axis 1: Reading Load

Anchor: a Hard problem produces substantial reading load through *content volume* — multiple stakeholders, business rules with concrete bullet examples, and sample input data the reader must trace through to construct a mental model.

| Level | Target reading time | Characteristics |
|---|---|---|
| **Easy** | ~1 min | 1 paragraph or 2-3 bullet rules. No nested business context. Sample input/output fits on one screen. |
| **Medium** | ~3 min | 1-2 paragraphs of context + a few rules. Some business framing to internalize. Sample I/O shows edge cases. |
| **Hard** | ~5-7 min | Scenario paragraph + **≥3 named business rules**, each with its own prose + 3-4 bullet examples (including edge cases). Multiple input sources, each with both schema AND sample content. Reader must cross-reference rule examples with input sample data to build a mental table before coding. |

**Two-file structure (LeetCode-style split view):**

- `problem.md` — the full problem statement (scenario + rules + Task + Input + Output). Reader opens this in a left pane.
- `qK.ipynb` — the notebook. Cell-0 is a **short pointer** (title + calibration + target time + IO paths + focus tag). Cells 1-3 are setup / solution / tests.

This mimics LeetCode's split-pane UX. In JupyterLab or VSCode: split editor, `problem.md` on the left rendered as markdown, notebook on the right. No scrolling back and forth inside the notebook to re-read the spec.

**Canonical `problem.md` template (platform-style, applies to ALL difficulties; R:Hard adds more rule subsections):**

```
# Q{N} — {Problem name} [R:{level}, O:{level}] (target {N} min)

## Description
{Business context paragraph, then data-landscape paragraph(s), then computation
 semantics WOVEN INTO PROSE: output grain, derived-column definitions,
 inclusion/exclusion rules, boundary semantics (e.g., "exactly 30 minutes
 belongs to the same session"). FINAL paragraph = deliverable
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

Folder: `challenges/{mockN|dNN}/qK/input/`

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

Folder: `challenges/{mockN|dNN}/qK/output/`
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
 orphan keys) — LeetCode-style disclosure. Perf expectations if relevant.}
```

**Retired anti-pattern:** a separate `## Task` numbered-steps section and a trailing `**clarifications**` list. Both violate platform conventions — Task steps leak the solution recipe (e.g., "GroupBy X → count", "lag → cumsum"), and a clarifications dump means the problem statement was incomplete without a patch section. Every requirement lives in Description/Rules/Output where the reader parses it out themselves.

**Canonical notebook cell-0 pointer:**

```
# QK — {Problem name}

📖 **Problem:** `problem.md`

| | |
|---|---|
| Calibration | `[R:H, O:{level}]` |
| Target time | {N} min |
| Focus | {pattern being drilled — e.g., sessionization, top-N per group} |
| Input | `input/...` (list files/subfolders) |
| Output | `output/` (Parquet, partitioned by {key}) |
```

Cells 1-3: setup / solution scaffold / tests-DO-NOT-MODIFY. All spec content stays in `problem.md`.

**Setup cell must match the declared toolchain.** A pure-Python problem gets NO Spark session — pre-loading a tool the problem forbids is an affordance that invites the violation, and tests verify outputs, not toolchains, so nothing will catch it. The environment is part of the assessment surface: provide exactly what the real platform would provide, nothing more.

**Key structural rules:**
- **Requirements are woven into Description/Rules — never appended.** Ordering, return format, partitioning, derived-column formulas, inclusion/exclusion semantics all appear where the reader naturally encounters them. A separate "clarifications" dump means the statement failed.
- **The deliverable is a sentence, not a recipe.** State WHAT to produce and WHERE to write it. Never enumerate solution steps or name functions/algorithms (`to_date`, "GroupBy then count", "lag → cumsum") — deriving the approach IS the exam.
- **Ordering contract must be explicit and verifiable.** Either the description demands an exact order (single sorted file; test compares write order strictly) or says "no ordering requirement" (test re-sorts before comparing). Never demand a sort the test cannot physically verify (e.g., global order inside a partitioned dataset).
- **No off-topic terminology.** Don't mention concepts from other problems (e.g., "session" in a plain counting problem) — it misleads readers into over-engineering.
- Examples are **bullets, not prose-embedded** — easier to parse individually; reading load comes from quantity + cross-referencing.
- Each input source MUST have sample content (not just schema). See [Input Convention](#input-convention-folder-based-with-decoys).
- Sample IDs in inputs cross-reference scenario rule examples (e.g., if Rule 1 mentions `O8803 / refund_amount=NULL`, refunds.json sample must include that row).
- **Every schema column MUST have an explicit type.** `col: string` / `col: timestamp` / `col: double`, never bare `col1, col2, col3`. Implicit types leak decisions to the reader (e.g., `payment_ts` — timestamp or date?).
- **Money columns MUST use `decimal(p, 2)` OR the spec must state an explicit rounding rule.** `DoubleType` + `sum + ==` silently misclassifies via IEEE 754 accumulator drift (e.g., `$2508.06` summed once → `2508.0600000000004` → false negative on equality). Never leave precision handling silent when currency comparisons are involved.
- **No decoy listing, no Pre-Submit Ritual** in the notebook markdown. Those go to the paired Notion prep/retro page. The notebook is the assessment-realistic surface; decoys still exist physically in `input/` for the user to discover.

**Calibration trap:** the coach's default instinct for "Hard reading" is anchored to LeetCode-style problems, which is too light for real senior DE assessments. When in doubt, render the spec, count rule subsections + example bullets. <3 rule subsections each with bullet examples → not R:Hard.

### Axis 2: Operation Depth

Anchor: a Hard problem must require **the full pipeline from scratch** — read input file(s) → transform → write output file(s). If the user's solution is just an in-memory transform function (input is `createDataFrame`, output is a returned list), it is not O:Hard.

An "operation" is one discrete logical step:
- **SQL**: one clause that does meaningful work — a JOIN, WHERE predicate, GROUP BY, HAVING, window definition, CTE step, COALESCE wrap. (Selecting raw columns doesn't count.)
- **Python**: one transformation or check — filter, map, group, sort, regex extract, aggregate, dedup, validate.
- **PySpark**: one `.method()` call doing meaningful work — `filter`, `withColumn`, `groupBy.agg`, `join`, `Window` definition, `dropDuplicates`.

| Level | Operations count | Characteristics |
|---|---|---|
| **Easy** | 1-5 ops | Single-step transform or basic aggregation. One JOIN max. No nested logic. Input is still read from `input/` (Input Convention); returning an in-memory result is fine. |
| **Medium** | 5-10 ops | Multi-step linear pipeline. 1-2 JOINs, 1 window function, maybe one COALESCE. Edge case handling for nulls. Read from file is expected; final write optional. |
| **Hard** | 10-15 ops | **Full I/O lifecycle: read file(s) → transform → write file(s).** Complex business logic with conditional branches. Multiple JOINs or CTEs. Recursive CTE, multi-window, or multi-pass transforms. Edge cases for null/zero/empty/duplicate explicitly required. |

### The 3×3 Matrix — Why Both Axes Matter

| Reading \ Ops | Easy ops (1-5) | Medium ops (5-10) | Hard ops (10-15) |
|---|---|---|---|
| **Easy reading** (~1 min) | Quick warmup | LeetCode-style | Algorithm puzzle (rare in DE) |
| **Medium reading** (~3 min) | Brief scenario | **Standard DE problem** | Complex scenario |
| **Hard reading** (~5 min) | Wordy but simple (trap: over-engineering) | Realistic DE workload | **Target-assessment boss problem** |

**Calibration insight:** Prior LeetCode-style prep concentrated in the top-left and middle, leaving the bottom-right untrained. The real DE assessment lived in the bottom-right. When designing or selecting practice problems, weight toward the diagonal and below-diagonal cells.

### Tagging Convention

When creating or recording a problem, tag it `[R:level, O:level]`:
- `[R:Easy, O:Medium]` — short prompt, 5-10 operations
- `[R:Hard, O:Hard]` — long scenario, 10-15 operations
- `[R:Medium, O:Medium]` — the "default DE problem" shape

Track misses by tag to see if the failure mode is reading comprehension, operation execution, or both.
