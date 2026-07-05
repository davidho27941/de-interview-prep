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
# 等價: F.count(F.when(cond, 1)) — count 忽略 NULL, when 無 otherwise 時不符即 NULL
```

**Pivot 後補零** — `pivot` 產生的格子沒資料是 NULL 不是 0，counting 場景幾乎都要接 `fillna`:

```python
df.groupBy("merchant_id").pivot("status", ["matched", "unpaid"]).count() \
  .fillna(0, subset=["matched", "unpaid"])
# 給 pivot 明確的值清單: 少一次全表掃描, 且缺席類別仍會成為欄位
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

**排序契約與檔案佈局:**

- 需要「輸出照指定順序」→ `orderBy(...)` 後 `coalesce(1)` 寫**單一檔** — 單檔讀回會保留列順序,契約才驗得了
- Partitioned 輸出**沒有全域列順序**可言 — 讀回順序由 partition 目錄與檔案切分決定。spec 若寫 partitioned + sorted,那個 sort 是無法驗證的假契約
- `orderBy` 之後再 `repartition` 會毀掉排序(shuffle);順序永遠是 write 前最後一步

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

## Common Pitfalls

- `F.col("col").==(value)` — there is no `.==`. Use `==`. (Beginner trap.)
- Forgetting that transforms are lazy — adding a `.show()` to "test" each step is fine, but it re-executes the plan up to that point unless you cache.
- Mixing `df["col"]` references across two DataFrames after a join → ambiguous column error.
- Using Python `if`/`or` inside transforms — they execute once at plan time, not per row. Use `F.when` / `&` / `|`.
- Calling `.collect()` on a giant DataFrame — pulls everything to driver, OOMs.
- Treating `repartition(1)` and `coalesce(1)` as the same — `repartition` shuffles, `coalesce` doesn't (faster but can be unbalanced).
- Forgetting that `dropDuplicates()` with no args dedups on ALL columns; usually you want `dropDuplicates(["id"])` — and see the determinism warning in [window-sessionization.md](window-sessionization.md).
- **Sort order is never preserved** through `withColumn` / `filter` / `join` / `groupBy`. 題目要求 sort → 最後一定 explicit `.orderBy()`，不能假設「前面排過就 OK」。

## Minimal Run-Locally Setup

```bash
pip install pyspark
python -c "from pyspark.sql import SparkSession; SparkSession.builder.getOrCreate().createDataFrame([(1,)],['x']).show()"
```

If it prints a tiny table, you're set. Spark UI runs at `http://localhost:4040` during a session — useful to inspect stages and skew during practice.
