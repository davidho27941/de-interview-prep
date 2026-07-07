# PySpark Core — Mental Model, Transforms, Aggregations, Output

## Mental Model

| Pandas / Python | PySpark |
|---|---|
| In-memory, eager | Distributed, **lazy** (transforms build a plan; actions execute) |
| One row at a time available | Think in columns — `F.col("x")`, not loops |
| `df.copy()` cheap | `df.cache()` deliberate — costs memory |
| Mutate in place | **Immutable** — every transform returns a new DataFrame |
| `for row in df.itertuples()` is normal | Iterating rows is an anti-pattern — push logic into transforms |

**Lazy evaluation trap:** `df.filter(...)` returns instantly because nothing runs. The work happens when you call an *action*: `.show()`, `.collect()`, `.count()`, `.write...()`, `.toPandas()`. A bug in your transform may only surface at the action.

## Imports You Always Need

```python
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType, DoubleType, DecimalType

spark = SparkSession.builder.appName("interview").getOrCreate()
```

Convention: `import functions as F`. Almost every column expression uses `F.something`.

## Reading Data (basics — full treatment in [io-formats.md](io-formats.md))

```python
df = spark.read.csv("path/", header=True, inferSchema=True)
df = spark.read.json("path/")
df = spark.read.parquet("path/")

# Better than inferSchema (one pass instead of two, no inference mistakes):
schema = StructType([
    StructField("user_id", IntegerType()),
    StructField("event_ts", TimestampType()),
    StructField("amount", DoubleType()),
])
df = spark.read.schema(schema).csv("path/", header=True)
```

For "given this data" problems:
```python
data = [(1, "alice", 100), (2, "bob", None)]
df = spark.createDataFrame(data, ["id", "name", "amount"])
```

## Column Expressions — Three Equivalent Forms

```python
df.filter(F.col("amount") > 100)
df.filter(df["amount"] > 100)
df.filter(df.amount > 100)
```

Pick one and stay consistent. `F.col("x")` works even when the column name is dynamic or contains spaces; the others can fail in those cases.

## Common Transforms

```python
df.select("id", "name", F.col("amount") * 1.1).alias("amount_plus_tax")

df.withColumn("status_flag", F.when(F.col("status") == "active", 1).otherwise(0))
df.withColumn("name_upper", F.upper(F.col("name")))
df.withColumnRenamed("old", "new")
df.drop("internal_col", "another")

df.filter((F.col("status") == "active") & (F.col("amount") > 0))   # & | ~ NOT and/or/not
df.filter(F.col("name").isNull())
df.filter(F.col("name").isNotNull())
df.filter(F.col("country").isin("US", "TW", "JP"))
df.filter(F.col("name").rlike(r"^A.*"))                            # regex match
```

**Gotcha:** Python `and`/`or` do NOT work on Spark columns. Use `&` `|` `~` with parentheses around each comparison.

## Aggregations

```python
df.groupBy("country").agg(
    F.count("*").alias("n_rows"),
    F.countDistinct("user_id").alias("n_users"),
    F.sum("amount").alias("revenue"),
    F.avg("amount").alias("avg_amount"),
    F.min("event_ts").alias("first_event"),
    F.max("event_ts").alias("last_event"),
)
```

**Null behavior:** `F.count("col")` ignores nulls; `F.count("*")` counts all rows. `F.sum`/`F.avg` ignore nulls. `F.countDistinct` ignores nulls. (Full NULL treatment: [null-money-dates.md](null-money-dates.md).)

**Conditional counting** (one groupBy, many filtered counts — the SQL `SUM(CASE WHEN ...)` idiom):

```python
df.groupBy("merchant_id").agg(
    F.sum(F.when(F.col("status") == "matched",  1).otherwise(0)).alias("matched_count"),
    F.sum(F.when(F.col("status") == "unpaid",   1).otherwise(0)).alias("unpaid_count"),
)
# Equivalent: F.count(F.when(cond, 1)) — count ignores NULL; when without otherwise yields NULL for non-matches
```

**Zero-filling after pivot** — cells produced by `pivot` with no data are NULL, not 0; counting scenarios almost always need a `fillna` right after:

```python
df.groupBy("merchant_id").pivot("status", ["matched", "unpaid"]).count() \
  .fillna(0, subset=["matched", "unpaid"])
# Give pivot an explicit value list: saves one full-table scan, and absent categories still become columns
```

## Spark SQL Bridge

When the logic is naturally SQL, use SQL:

```python
df.createOrReplaceTempView("events")
result = spark.sql("""
    SELECT user_id, COUNT(*) AS n, SUM(amount) AS total
    FROM events
    WHERE status = 'active'
    GROUP BY user_id
    HAVING SUM(amount) > 0
""")
```

Use DataFrame API when: composing programmatically, the transform list is generated, you want type safety in Scala.
Use SQL when: the logic mirrors what you'd write in SQL anyway, or you're comfortable in SQL and stressed.

These are interchangeable. Senior signal: picking the right one for clarity, not dogma.

## Output

```python
result.show(20, truncate=False)         # for debugging
result.collect()                        # list of Row objects — pulls to driver, danger on big data
result.toPandas()                       # pandas DataFrame — also pulls to driver

result.write.mode("overwrite").parquet("out/path")
result.write.mode("overwrite").partitionBy("date").parquet("out/path")
result.write.mode("append").csv("out/path", header=True)
```

`mode` options: `"overwrite"`, `"append"`, `"ignore"`, `"error"` (default).

**`overwrite` replaces the entire target DIRECTORY, not individual files.** Spark's mental model is "the path IS the dataset" — overwrite means *replace the old dataset at this path with the new one*, implemented as delete-directory-then-recreate. (File-level overwrite would be worse: a run writing 3 part-files over a previous run's 200 would leave 197 stale files mixed into the "new" dataset.) Consequences:

- **Sidecar files sharing the output directory** (a `metrics.txt`, a quarantine count) get wiped along with everything else. Discipline: **Spark writes first — let it raze the directory — sidecars second.** And when reading back, use an extension-precise glob (`out/*.parquet`) so the sidecar doesn't break the parquet reader; the two rules are the same cohabitation contract seen from both sides.
- **Partitioned overwrite has two modes, and the default bites:**

```python
# default (static): overwriting with ONLY June's data still razes the whole
# output/ — including every other month's partitions
df.write.mode("overwrite").partitionBy("month").parquet("out/")

# dynamic: only the partitions present in the incoming data are replaced
spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
```

Classic production incident: a daily job static-overwrites "today's partition" and silently deletes the entire history every night. Interview answer for "how do you safely re-run one day": dynamic partition overwrite, or a lakehouse table format's `replaceWhere` / MERGE.

**Ordering contract and file layout:**

- Need "output in a specified order" → `orderBy(...)` then `coalesce(1)` to write a **single file** — reading a single file back preserves row order, so the contract is actually verifiable
- Partitioned output has **no global row order** to speak of — read-back order is determined by partition directories and file splits. If a spec says partitioned + sorted, that sort is an unverifiable fake contract
- `repartition` after `orderBy` destroys the ordering (shuffle); ordering is always the last step before write

## DataFrame ↔ RDD

In modern Spark you almost never touch RDDs directly. If asked: `df.rdd` gives the underlying RDD; `spark.createDataFrame(rdd, schema)` goes the other way. If an interviewer pushes on RDD, they're probably testing whether you know DataFrame is the modern default — say so.

## Common Interview Question Shapes (routing index)

1. **Latest record per group** — Window + row_number → [window-sessionization.md](window-sessionization.md)
2. **Sessionization** — lag → gap → cumulative sum → [window-sessionization.md](window-sessionization.md)
3. **Dedup with tiebreaker** — deterministic window dedup → [window-sessionization.md](window-sessionization.md)
4. **Reconciliation / join-then-classify** — aggregate → LEFT join → coalesce → classify → [joins.md](joins.md)
5. **Point-in-time lookup (SCD2)** — range join on validity interval → [joins.md](joins.md)
6. **Pivot** — `groupBy().pivot().agg()` + fillna(0) (above)
7. **Read messy data** — explicit schema; PERMISSIVE/_corrupt_record → [io-formats.md](io-formats.md)
8. **Nested JSON flattening** — from_json / explode / higher-order fns → [nested-udf.md](nested-udf.md)
9. **Verbal round: batch vs streaming, exactly-once, late data** — concepts, not code → [batch-streaming-concepts.md](batch-streaming-concepts.md)

## Common Pitfalls

- `F.col("col").==(value)` — there is no `.==`. Use `==`. (Beginner trap.)
- Forgetting that transforms are lazy — adding a `.show()` to "test" each step is fine, but it re-executes the plan up to that point unless you cache.
- Mixing `df["col"]` references across two DataFrames after a join → ambiguous column error.
- Using Python `if`/`or` inside transforms — they execute once at plan time, not per row. Use `F.when` / `&` / `|`.
- Calling `.collect()` on a giant DataFrame — pulls everything to driver, OOMs.
- Treating `repartition(1)` and `coalesce(1)` as the same — `repartition` shuffles, `coalesce` doesn't (faster but can be unbalanced).
- Forgetting that `dropDuplicates()` with no args dedups on ALL columns; usually you want `dropDuplicates(["id"])` — and see the determinism warning in [window-sessionization.md](window-sessionization.md).
- **Sort order is never preserved** through `withColumn` / `filter` / `join` / `groupBy`. If the problem requires a sort → always end with an explicit `.orderBy()`; never assume "I sorted earlier so it's fine".

## Minimal Run-Locally Setup

```bash
pip install pyspark
python -c "from pyspark.sql import SparkSession; SparkSession.builder.getOrCreate().createDataFrame([(1,)],['x']).show()"
```

If it prints a tiny table, you're set. Spark UI runs at `http://localhost:4040` during a session — useful to inspect stages and skew during practice.
