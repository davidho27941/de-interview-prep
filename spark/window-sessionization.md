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

**Direction gotcha:** `orderBy` in a window defaults to ASC. Spec verbs map to direction — 「最新/最多/最高/latest/most/highest」→ `F.col(x).desc()`;「最早/最少/oldest」→ default ASC. Circle the verb while reading the spec, pick the direction before writing the window.

## Window ranking trio: rank vs dense_rank vs row_number

當你想「每 partition 取 top N」時，這三個的差別**會直接決定你 filter 後留下幾 row**：

| Function | 同值（tie）時 | filter rn==1 後 | 用途 |
|---|---|---|---|
| `F.rank()` | 同 rank（有 gap）：1,1,3 | **多 row 通過** | 想保留 ties |
| `F.dense_rank()` | 同 rank（無 gap）：1,1,2 | **多 row 通過** | 想保留 ties，連號計算 |
| **`F.row_number()`** | **強制連續編號** 1,2,3 | **每 partition 必定 1 row** | **「top 1 per group」的標準解** |

**反射：** 看到「每 X 取一個」→ `row_number()`。看到「每 X 取所有並列冠軍」→ `rank()` / `dense_rank()`。

```python
# 標準「每 country 取最活躍 user」
w = Window.partitionBy('country').orderBy(F.col('cnt').desc(), F.col('user_id'))
df.withColumn('rn', F.row_number().over(w)).filter(F.col('rn') == 1)
# ↑ 換成 rank() 或 dense_rank() 在有 tie 時會 leak 多 row
```

## Deduplication — deterministic vs arbitrary

```python
# ❌ 非決定性: dropDuplicates 保留「任意」一列 — 每次跑、每種 partition 佈局可能不同
df.dropDuplicates(["order_id"])

# ✅ 決定性: Window + row_number + 明確 tiebreaker
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
# ⚠ collect_list 的元素順序「不保證」— shuffle 後的到達順序, 每次可能不同
```

需要「按時間順序的事件序列」時,兩個決定性做法:

```python
# 法 1: struct 排序後再取欄位 (推薦)
df.groupBy("user_id").agg(
    F.sort_array(F.collect_list(F.struct("event_ts", "event_type"))).alias("seq")
).withColumn("event_seq", F.col("seq.event_type"))

# 法 2: 先在 window 內排好再 collect (依賴實作細節, 法 1 更穩)
```

面試題「輸出每個 user 的事件路徑 (view→cart→purchase)」→ 沒排序的 collect_list 會間歇性錯,小資料還常常「剛好對」— 典型的 flaky 正確性陷阱。

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
