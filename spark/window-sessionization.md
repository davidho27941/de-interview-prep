# PySpark Windows — Ranking, Dedup, Sessionization

## Window Functions

```python
w = Window.partitionBy("user_id").orderBy("event_ts")

df.withColumn("row_n", F.row_number().over(w))
df.withColumn("rank", F.rank().over(w))                          # gaps after ties
df.withColumn("dense_rank", F.dense_rank().over(w))              # no gaps
df.withColumn("prev_amount", F.lag("amount", 1).over(w))
df.withColumn("next_amount", F.lead("amount", 1).over(w))

# Running totals — define frame explicitly
w_running = Window.partitionBy("user_id").orderBy("event_ts").rowsBetween(Window.unboundedPreceding, Window.currentRow)
df.withColumn("cum_amount", F.sum("amount").over(w_running))

# Latest record per group (very common)
w_latest = Window.partitionBy("user_id").orderBy(F.col("event_ts").desc())
df.withColumn("rn", F.row_number().over(w_latest)).filter(F.col("rn") == 1).drop("rn")
```

**Frame gotcha:** the default frame for an unordered window is the entire partition, but for an *ordered* window with an aggregate (sum/avg/etc.) the default frame is `unboundedPreceding → currentRow` — which is the running total, often surprising people who wanted the partition total. Be explicit with `rowsBetween` / `rangeBetween` when it matters.

**Direction gotcha:** `orderBy` in a window defaults to ASC. Spec verbs map to direction — "latest/most/highest" → `F.col(x).desc()`; "earliest/fewest/oldest" → default ASC. Circle the verb while reading the spec, pick the direction before writing the window.

## Window ranking trio: rank vs dense_rank vs row_number

When you want "top N per partition", the difference between these three **directly determines how many rows survive your filter**:

| Function | On ties | After filter rn==1 | Use case |
|---|---|---|---|
| `F.rank()` | Same rank (with gaps): 1,1,3 | **Multiple rows pass** | Keep ties |
| `F.dense_rank()` | Same rank (no gaps): 1,1,2 | **Multiple rows pass** | Keep ties, consecutive numbering |
| **`F.row_number()`** | **Forced consecutive numbering** 1,2,3 | **Exactly 1 row per partition** | **The standard solution for "top 1 per group"** |

**Reflex:** See "pick one per X" → `row_number()`. See "pick all tied winners per X" → `rank()` / `dense_rank()`.

```python
# The standard "most active user per country"
w = Window.partitionBy('country').orderBy(F.col('cnt').desc(), F.col('user_id'))
df.withColumn('rn', F.row_number().over(w)).filter(F.col('rn') == 1)
# ↑ Swapping in rank() or dense_rank() leaks multiple rows when there are ties
```

## Deduplication — deterministic vs arbitrary

```python
# ❌ Non-deterministic: dropDuplicates keeps an "arbitrary" row — may differ per run and per partition layout
df.dropDuplicates(["order_id"])

# ✅ Deterministic: Window + row_number + explicit tiebreaker
w = Window.partitionBy("order_id").orderBy(F.col("updated_at").desc(), F.col("source_file"))
deduped = (df.withColumn("rn", F.row_number().over(w))
             .filter(F.col("rn") == 1)
             .drop("rn"))
```

**When each is right:**
- `dropDuplicates(cols)` — rows are **exact duplicates** on every column you care about; which copy survives doesn't matter.
- Window dedup — rows differ (timestamps, versions, sources) and the spec implies a rule ("keep the latest"). `dropDuplicates` here is a silent correctness bug that tests may not catch on small data.

**Semantic check before ANY dedup:** is there a real business-event id (`order_id`, `idempotency_key`)? Dedup on one is definitive. Dedup on `(user, ts, amount)` heuristics can delete legitimate concurrent transactions — call the assumption out.

## collect_list / collect_set ordering

```python
df.groupBy("user_id").agg(F.collect_list("event_type"))
# ⚠ collect_list element order is NOT guaranteed — arrival order after shuffle, may differ every run
```

When you need "the event sequence in time order", two deterministic approaches:

```python
# Approach 1: sort structs, then extract the field (recommended)
df.groupBy("user_id").agg(
    F.sort_array(F.collect_list(F.struct("event_ts", "event_type"))).alias("seq")
).withColumn("event_seq", F.col("seq.event_type"))

# Approach 2: sort within a window first, then collect (relies on implementation details; approach 1 is more robust)
```

Interview question "output each user's event path (view→cart→purchase)" → an unsorted collect_list fails intermittently, and on small data it often happens to look right — a classic flaky correctness trap.

## Sessionization Template (worth memorizing)

**Step 1 — tag events with a session id** (`lag → gap → cumulative sum`):

```python
w = Window.partitionBy("user_id").orderBy("event_ts")
GAP_SEC = 30 * 60

tagged = (df
    .withColumn("prev_ts", F.lag("event_ts").over(w))
    .withColumn("gap_sec", F.unix_timestamp("event_ts") - F.unix_timestamp("prev_ts"))
    .withColumn("new_session", (F.col("gap_sec").isNull() | (F.col("gap_sec") > GAP_SEC)).cast("int"))
    .withColumn("session_id",
        F.sum("new_session").over(w.rowsBetween(Window.unboundedPreceding, Window.currentRow)))
)
```

**Step 2 — aggregate to one row per session** (the usual deliverable):

```python
sessions = (tagged
    .groupBy("user_id", "session_id")
    .agg(F.min("event_ts").alias("start_ts"),
         F.max("event_ts").alias("end_ts"),
         F.count("*").alias("event_count"))
    .withColumn("duration_sec",
        F.unix_timestamp("end_ts") - F.unix_timestamp("start_ts"))
)
```

This is the Spark version of the gaps-and-islands SQL pattern. It shows up in many DE assessments — memorize the shape, then adapt.

**Traps in this template:**

- **Boundary operator ↔ spec verb.** "more than 30 minutes" → `>`; "30 minutes or more" → `>=`. Data often contains an exactly-at-boundary gap specifically to catch the wrong operator.
- **First event per user:** `lag` returns NULL → the `isNull()` term makes it a new session, and the cumulative sum then starts at **1**. If the spec wants 0-based ids, subtract 1 explicitly.
- **Sessions can cross midnight.** Derive a session's date from `start_ts` (`F.to_date(F.min("event_ts"))`), never from the per-event date or the source filename.
- **Duplicate timestamps** (client double-fire) are ties in the window order — gap is 0, same session, both events count. Don't dedup unless the spec says so.
- **Single-event sessions** have `duration_sec = 0`, not NULL.
- The cumulative sum needs the explicit `rowsBetween(unboundedPreceding, currentRow)` frame if you build the window separately from the ordered one.
