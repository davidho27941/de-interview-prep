# PySpark Joins — Types, Broadcast, Reconciliation Shape, SCD2, Union

## Join Types

```python
df_a.join(df_b, on="user_id", how="inner")
df_a.join(df_b, on=["user_id", "date"], how="left")
df_a.join(df_b, df_a.user_id == df_b.id, how="left")    # different column names

# Semi/anti — keep/exclude rows in df_a based on existence in df_b
df_a.join(df_b, on="user_id", how="left_semi")          # rows in a that match b
df_a.join(df_b, on="user_id", how="left_anti")          # rows in a with no match in b
```

**Ambiguous column trap:** after `join`, both sides' join columns may exist. Always alias before joining or use the `on="col"` form (which collapses to one column).

**Row-multiplication trap:** joining a one-to-many relation *before* aggregating multiplies the "one" side's rows — a later `sum` double-counts. Aggregate the many side first (see the reconciliation shape below), or verify with counts before/after the join.

## Broadcast

```python
# Broadcast hint — for small-to-large joins (small side fits in memory)
df_large.join(F.broadcast(df_small), on="user_id", how="left")
```

When to broadcast: small side is < ~10MB. Senior signal: knowing when shuffle cost dominates and broadcast avoids it.

### 讀 explain 的 broadcast 方向: BuildLeft / BuildRight

```
BroadcastHashJoin [...], Inner, BuildRight
```

`BuildRight` = right side 被 broadcast；`BuildLeft` = left side 被 broadcast。Broadcast **大邊**會 OOM driver（小表才能塞進 executor memory）。Spark 也會自動 broadcast < 10MB 的表（`spark.sql.autoBroadcastJoinThreshold` 可調，設 `-1` 關閉）。

## The aggregate → LEFT join → classify shape (reconciliation problems)

"Sum the child records per parent, compare against the parent's own amount, classify" — invoices vs payments, orders vs shipments, plans vs actuals. The shape:

```python
paid = payments.groupBy("invoice_id").agg(F.sum("amount").alias("paid_total"))

classified = (invoices
    .join(paid, "invoice_id", "left")                      # LEFT — parents with no children must survive
    .withColumn("paid_total",                              # join-produced NULL → 0 BEFORE comparing
        F.coalesce(F.col("paid_total"), F.lit(0).cast("decimal(12,2)")))
    .withColumn("status",
        F.when(F.col("paid_total") == F.col("amount"), "matched")
         .when(F.col("paid_total") >  F.col("amount"), "overpaid")
         .when(F.col("paid_total") >  0,               "underpaid")
         .when(F.col("paid_total") == 0,               "unpaid")
         .otherwise("unclassified"))                       # defensive — should never fire
)
```

**The three-valued-logic trap this guards against:** an INNER join silently drops no-child parents; a LEFT join without the `coalesce` leaves `paid_total = NULL`, and NULL fails EVERY `when` condition — the row gets a NULL status and silently vanishes from any `status == "x"` aggregation. Two separate mistakes, same symptom: missing rows.

Three disciplines, always together:
1. **LEFT join** when zero-child parents are part of the answer.
2. **`coalesce` to a typed zero** immediately after the join (`F.lit(0).cast(...)` matching the column type — mixing int literals with Decimal columns invites type surprises).
3. **`.otherwise("unclassified")`** at the end of every classification chain — a visible "should not happen" beats a silent NULL. If it appears in output, you missed a case.

One more naming discipline: the label strings produced here are compared *as strings* downstream (`F.when(status == "overpaid", ...)`). A one-character mismatch (`over_paid` vs `overpaid`) produces silent zeros, not an error. Define the labels once, reuse the constant.

## Point-in-time lookup — SCD2 / range join

Dimension tables often keep history as validity intervals (SCD Type 2): one row per `(key, valid_from, valid_to)`, `valid_to = NULL` meaning current. To attribute a fact row to the dimension version **in effect at the fact's timestamp**:

```python
joined = (facts.alias("f")
    .join(dim.alias("d"),
          (F.col("f.user_id") == F.col("d.user_id")) &
          (F.col("f.event_ts") >= F.col("d.valid_from")) &
          ((F.col("f.event_ts") < F.col("d.valid_to")) | F.col("d.valid_to").isNull()),
          "left")
)
```

**Traps:**
- **Interval semantics `[valid_from, valid_to)`** — 右開。事件恰好在 `valid_to` 的瞬間屬於**下一個**版本。用 `>= from` + `< to`,不是兩個 `<=`。
- **`valid_to IS NULL` = current row** — 忘了 OR 條件,所有落在 current 版本的事件都 join 不到。
- **Non-equi join 沒有 hash join 可用** → 通常退化成 broadcast nested loop join。維度表小(SCD 表通常小)→ `F.broadcast(dim)` 是標配;維度表大就要先按 key bucketing 或改寫成「事件與版本 union 後開窗」的技巧。
- **每筆 fact 應恰好對到 ≤1 個版本** — join 後 `groupBy fact_id having count > 1` 驗一次,抓出重疊 interval 的髒維度資料。
- Orphan facts(維度裡沒這個 key)是 drop 還是保留 → 看 spec,别默默用 inner。

## unionByName vs union（schema 對齊）

```python
df_a.union(df_b)          # ❌ 按「位置」拼 — 欄位順序不同時資料錯位, 不報錯!
df_a.unionByName(df_b)    # ✅ 按「欄名」拼
df_a.unionByName(df_b, allowMissingColumns=True)   # 欄位集合不同也行, 缺的補 NULL
```

**Trap:** `union` 只檢查欄位「數量」,不檢查名字。兩個 DataFrame 欄位順序不同(select 順序、schema 演進)→ 資料靜靜錯位,型別剛好相容時連錯都不報。**反射: 多來源合併一律 `unionByName`**;schema 會演進的(月度檔多了新欄位)再加 `allowMissingColumns=True`。
