# PySpark Performance — Caching, Partitions, Shuffle, AQE, Skew

## Cache / Persist

```python
df.cache()              # keep in memory for re-use across actions
df.persist(StorageLevel.MEMORY_AND_DISK)
df.unpersist()          # release
```

**When to cache:** the same DataFrame is used in multiple downstream actions. Don't cache reflexively — it costs memory. **Cache vs checkpoint:** cache preserves lineage (recomputable on failure); `df.checkpoint()` truncates lineage and materializes to disk — only needed for very long iterative pipelines (repeated transforms in a loop) to prevent plan explosion.

## Repartition / Coalesce

```python
df.repartition(8)               # full shuffle, balanced — use before heavy ops
df.repartition("country")       # partition by column (still shuffles)
df.coalesce(1)                  # reduce partitions WITHOUT shuffle — for writing one file
```

`repartition(1)` and `coalesce(1)` are different — the former shuffles (slow but balanced), the latter merges existing partitions (fast but potentially unbalanced).

## Shuffle Fundamentals + AQE

- **`spark.sql.shuffle.partitions` defaults to 200** — the partition count after every groupBy/join. For small data, 200 micro-partitions are wasteful; for large data, 200 is too few. Classic interview question: "Why does my 5MB dataset produce 200 tasks after a groupBy?"
- **AQE (Adaptive Query Execution, on by default since Spark 3.2)** re-optimizes at runtime based on actual statistics:
  - Automatically coalesces overly small shuffle partitions (mitigating the point above)
  - Automatically converts sort-merge joins to broadcast joins (when runtime discovers one side is actually small)
  - Automatically splits skewed partitions (`skewJoin`)
- **Join strategy spectrum:** broadcast hash join (one side small) → sort-merge join (both sides large, the default) → shuffle hash join / broadcast nested loop (the fallback for non-equi joins — range joins often land here; see the SCD2 section in [joins.md](joins.md)).

## Reading explain()

```python
df.explain()                    # physical plan
df.explain("formatted")         # cleaner version
```

What to look for:

- **`Exchange`** = where a shuffle happens. Every Exchange in the plan is a full network redistribution — counting Exchanges is the first step in estimating job cost
- **`BroadcastHashJoin ... BuildRight/BuildLeft`** = which side gets broadcast (BuildRight = the right side). Broadcasting a large table will OOM
- **`PushedFilters: [...]`** (parquet scan) = whether predicate pushdown actually happened
- **`AQEShuffleRead`** = evidence that AQE intervened

## Skew

If one key has 90% of the rows, that one partition holds up the whole job. Symptom: in the Spark UI, one task runs for minutes while the others take milliseconds.

Mitigations (from simplest to most involved):
1. **Broadcast the other side** (skew only hurts in shuffle joins; broadcast avoids the shuffle)
2. **AQE skew join** (usually automatic in Spark 3.2+; confirm `spark.sql.adaptive.skewJoin.enabled`)
3. **Salting** — append a random suffix to the key to spread it out, then aggregate in two stages:

```python
# Stage 1: salted aggregation
salted = df.withColumn("salt", (F.rand() * 8).cast("int"))
partial = salted.groupBy("hot_key", "salt").agg(F.sum("x").alias("s"))
# Stage 2: de-salted final aggregation
final = partial.groupBy("hot_key").agg(F.sum("s"))
```

## Common Interview Performance Q&A

> "groupBy and Window can both compute aggregates — what's the difference?"

groupBy **collapses rows** (one row per group); Window **preserves rows** (each row is annotated with group statistics). To "compare each row against its group average" → Window does it in one step; groupBy requires a join back (one more shuffle).

> "How do you reduce shuffles?"

Broadcast small tables, filter/aggregate before joining (shrink the shuffled volume), repartition once and reuse the distribution across multiple operations on the same key, and use partition pruning on the read side to read less.

> "What do you do about a pile of small output files?"

`df.repartition("partition_key").write.partitionBy("partition_key")` — see the small files section in [io-formats.md](io-formats.md).
