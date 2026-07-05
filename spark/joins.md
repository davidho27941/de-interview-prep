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

### Reading broadcast direction in explain: BuildLeft / BuildRight

```
BroadcastHashJoin [...], Inner, BuildRight
```

`BuildRight` = the right side is broadcast; `BuildLeft` = the left side is broadcast. Broadcasting the **large side** OOMs the driver (only a small table fits in executor memory). Spark also auto-broadcasts tables < 10MB (tunable via `spark.sql.autoBroadcastJoinThreshold`; set `-1` to disable).

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
- **Interval semantics `[valid_from, valid_to)`** — right-open. An event exactly at the `valid_to` instant belongs to the **next** version. Use `>= from` + `< to`, not two `<=`.
- **`valid_to IS NULL` = current row** — forget the OR condition and every event falling in the current version fails to join.
- **Non-equi joins have no hash join available** → usually degrades to a broadcast nested loop join. Small dimension table (SCD tables usually are) → `F.broadcast(dim)` is the standard move; a large dimension table needs bucketing by key first, or a rewrite using the "union events with versions, then window" technique.
- **Each fact should match exactly ≤ 1 version** — after the join, verify once with `groupBy fact_id having count > 1` to catch dirty dimension data with overlapping intervals.
- Whether orphan facts (key missing from the dimension) are dropped or kept → check the spec; don't silently use inner.

## unionByName vs union (schema alignment)

```python
df_a.union(df_b)          # ❌ Concatenates by POSITION — data misaligns when column order differs, with no error!
df_a.unionByName(df_b)    # ✅ Concatenates by column NAME
df_a.unionByName(df_b, allowMissingColumns=True)   # Works even with different column sets; missing ones filled with NULL
```

**Trap:** `union` only checks the column *count*, not the names. Two DataFrames with different column order (select order, schema evolution) → data silently misaligns, and when the types happen to be compatible you don't even get an error. **Reflex: always use `unionByName` when merging multiple sources**; add `allowMissingColumns=True` when the schema evolves (monthly files gaining new columns).
