# PySpark Patterns Reference

Focused on what shows up in DE coding assessments: DataFrame API, SQL bridge, window functions, performance basics, common gotchas.

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
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType, DoubleType

spark = SparkSession.builder.appName("interview").getOrCreate()
```

Convention: `import functions as F`. Almost every column expression uses `F.something`.

## Reading Data

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

For interview Q4-style "given this data" problems:
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

**Null behavior:** `F.count("col")` ignores nulls; `F.count("*")` counts all rows. `F.sum`/`F.avg` ignore nulls. `F.countDistinct` ignores nulls.

## File Formats Deep Dive

### Trade-off 對照

| 格式 | Schema | 壓縮 | Predicate pushdown | Schema evolution | 用途 |
|---|---|---|---|---|---|
| **CSV** | 無，要 inferSchema 或顯式 | 弱（文字） | 無 | 麻煩 | 跟外部交換、log file |
| **JSON** (multi-line) | 嵌套，每檔一個物件 | 弱 | 無 | 中等 | API response、config |
| **JSONL** (one per line) | 嵌套，每行一個物件 | 弱 | 無 | 中等 | event log、streaming output |
| **Parquet** | 自帶 schema | 強（柱狀+壓縮） | 強 | 好 | analytics 預設、大資料 |
| **ORC** | 自帶 schema | 強 | 強 | 好 | Hive 環境 |
| **Delta** | Parquet + transaction log | 強 | 強 + ACID | 極好 | modern lakehouse |

**反射：** 內部資料用 Parquet。給外部 / 來自 API 才用 CSV / JSON。

### JSON 讀取

```python
# Multi-line (整檔一個 JSON 物件 or array)
df = spark.read.option('multiLine', 'true').json('input/config.json')

# JSON Lines (每行一個 JSON 物件) — 預設
df = spark.read.json('input/events.jsonl')

# 顯式 schema 比 inferSchema 快兩倍（不用掃兩次）
schema = StructType([
    StructField('user_id', StringType()),
    StructField('events', ArrayType(StructType([
        StructField('ts', TimestampType()),
        StructField('type', StringType()),
    ]))),
])
df = spark.read.schema(schema).json('input/events.jsonl')
```

### 從 string column parse JSON

CSV 內有一個欄位 value 是 JSON string，要 parse 成 struct：

```python
from pyspark.sql.functions import from_json

event_schema = StructType([
    StructField('type', StringType()),
    StructField('amount', DoubleType()),
])

df.withColumn('parsed', F.from_json('event_json_str', event_schema))
  .select('user_id', F.col('parsed.type'), F.col('parsed.amount'))
```

反向：`F.to_json(struct_col)` 把 struct 寫回 JSON string。

### Parquet 讀寫

```python
# 寫
df.write.mode('overwrite').parquet('out/path')

# Partition by column
df.write.partitionBy('year', 'month').parquet('out/path')
# 寫出 out/path/year=2026/month=06/part-*.parquet

# 讀（自動 schema discovery）
df = spark.read.parquet('out/path')

# Predicate pushdown — Spark 自動把 filter 推進去，只掃需要的 partition
df.filter(F.col('year') == 2026).filter(F.col('month') == 6)  # 只讀 year=2026/month=06/
```

### Schema 演進

新資料多了一個欄位，舊資料沒有：

```python
# 合併多次 write 的 schema（自動處理新增 column）
df = spark.read.option('mergeSchema', 'true').parquet('out/path')

# 寫入時 schema 不一致會 fail，要明示
df.write.option('mergeSchema', 'true').mode('append').parquet('out/path')
```

### Reading 常見坑

- **CSV 跟 `header=True` 預設 schema 全 String**，需要 `inferSchema=True` 或顯式 schema
- **JSON 時間欄位**用 `TimestampType()` 而不是 string，否則排序時是 lexical sort
- **Parquet 寫 Spark 跟讀 Spark 版本相容性** — 通常 ok，但跨大版本要驗
- **Decimal precision** 在 CSV → Parquet 轉換時可能掉精度，金融用要顯式 schema

---

## UDF (User-Defined Function)

### 第一原則：能用 built-in 就**別用** UDF

UDF 在 Spark 內部會：
1. 把 Spark Column 序列化（JVM → Python）
2. 在 Python interpreter 跑 row-by-row
3. 結果序列化回去（Python → JVM）

**單筆 serialization cost 比 built-in 多 10-100x。**

```python
# ❌ 別這樣寫
@F.udf(returnType=DoubleType())
def double_it(x):
    return x * 2 if x else 0

df.withColumn('doubled', double_it('amount'))

# ✅ Built-in 跟它一樣
df.withColumn('doubled', F.coalesce(F.col('amount') * 2, F.lit(0)))
```

**反射：寫 UDF 前先 google「pyspark functions <你要的操作>」**。九成情況有 built-in。

### 真的需要 UDF 的場景

1. **複雜業務邏輯** built-in 表達不出來（multi-step parsing、特殊 hash 等）
2. **呼叫第三方 Python 函式庫**（regex 進階、ML 推論、charset detection 等）
3. **不可序列化的 stateful 操作**（rare）

### UDF 基本寫法

```python
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

# 三種寫法

# 1. Decorator
@udf(returnType=StringType())
def classify_amount(x):
    if x is None:
        return 'unknown'
    return 'high' if x > 1000 else 'low'

df.withColumn('tier', classify_amount('amount'))

# 2. 直接包
classify_udf = udf(lambda x: 'high' if x and x > 1000 else 'low', StringType())
df.withColumn('tier', classify_udf('amount'))

# 3. 不指定 returnType 預設 StringType
@udf
def to_upper(s):
    return s.upper() if s else None
```

**重要：** UDF 對 NULL 不 magic — 你要自己 `if x is None`。built-in 通常 NULL-safe（NULL 進 NULL 出），UDF 沒這保證。

### Vectorized UDF (`@F.pandas_udf`)

效能比 row-by-row UDF 好 **10-100x**。原因：每次處理一個 pandas Series（一批 row），不是單 row。

```python
import pandas as pd
from pyspark.sql.functions import pandas_udf

@pandas_udf(DoubleType())
def normalize(amount: pd.Series) -> pd.Series:
    return (amount - amount.mean()) / amount.std()

df.withColumn('z_score', normalize('amount'))
```

**何時用：** 需要 numpy / pandas 才能寫的數學運算（ML feature engineering 常用）。

### UDF 性能對照（記住）

```
built-in F.col(...) operations    → 最快（JVM 內運算）
pandas_udf (vectorized)           → ~5-10x built-in
udf (row-by-row)                  → ~50-100x built-in
```

### 面試會問

> 「為什麼 PySpark UDF 慢？」

**正解：** Python ↔ JVM 序列化成本（Py4J / Arrow）。每 row 都跨界一次。

> 「Pandas UDF 為什麼比一般 UDF 快？」

**正解：** Arrow batch 跨界（一批 row 一次序列化）+ pandas 內部用 C 跑（不像 Python loop）。

---

## NULL Handling (common DE-assessment gap — make it reflexive)

```python
df.fillna(0, subset=["amount"])              # numeric default
df.fillna("unknown", subset=["country"])
df.fillna({"amount": 0, "country": "unknown"})

df.na.drop(subset=["user_id"])               # drop rows where user_id is null
df.na.drop(how="any")                        # drop if ANY column is null
df.na.drop(how="all")                        # drop only if ALL columns null

# Equivalent of SQL COALESCE — first non-null wins
df.withColumn("preferred_email", F.coalesce(F.col("work_email"), F.col("personal_email")))

# Conditional: like SQL CASE WHEN
df.withColumn("tier", F.when(F.col("amount") > 1000, "gold")
                       .when(F.col("amount") > 100, "silver")
                       .otherwise("bronze"))
```

**Pre-submit reflex (Spark version of the 4-question check):**
- Any `sum/avg/count` used downstream — what does it do for an empty group?
- Any join — did unmatched rows turn into nulls that propagate into later math?
- Any column expression doing arithmetic — wrap with `F.coalesce(..., F.lit(0))` if a null is meaningful as zero.

## Joins

```python
df_a.join(df_b, on="user_id", how="inner")
df_a.join(df_b, on=["user_id", "date"], how="left")
df_a.join(df_b, df_a.user_id == df_b.id, how="left")    # different column names

# Semi/anti — keep/exclude rows in df_a based on existence in df_b
df_a.join(df_b, on="user_id", how="left_semi")          # rows in a that match b
df_a.join(df_b, on="user_id", how="left_anti")          # rows in a with no match in b
```

**Ambiguous column trap:** after `join`, both sides' join columns may exist. Always alias before joining or use the `on="col"` form (which collapses to one column).

```python
# Broadcast hint — for small-to-large joins (small side fits in memory)
df_large.join(F.broadcast(df_small), on="user_id", how="left")
```

When to broadcast: small side is < ~10MB. Senior signal: knowing when shuffle cost dominates and broadcast avoids it.

## Common Subtle Gotchas

### Window ranking trio: rank vs dense_rank vs row_number

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

### Aggregate NULL behavior 對照表

LEFT JOIN 後做 aggregate，不同 function 對「全 NULL group」的行為不同：

| Function | 全 NULL group 結果 | 需要 COALESCE? |
|---|---|---|
| `F.count(col)` | **0** | ❌ 不需要 |
| `F.count('*')` | row 數（含 NULL row） | 不適合算「有幾筆 right 資料」|
| `F.countDistinct(col)` | **0** | ❌ 不需要 |
| `F.sum(col)` | **NULL** | ✅ 必須 |
| `F.avg(col)` | **NULL** | ✅ 通常需要 |
| `F.max/min(col)` | **NULL** | ✅ 視情境 |

**反射：** sum/avg/max/min 永遠 wrap COALESCE。count 不用（已經回 0）。

### Sort order 不會被保留

Spark 任何 transform 後（`withColumn`, `filter`, `join`, `groupBy`）都**不承諾保留 sort order**。

```python
df.orderBy('x').withColumn(...).filter(...)   # 順序可能已不在
```

**反射：** 題目要求 sort → 最後一定 explicit `.orderBy()` / `.sort()`，**不能假設「前面排過就 OK」**。

### `F.to_date()` 是「取日期部分」不是「ts 相等」

```python
F.to_date(ts)   # 取 yyyy-MM-dd，截掉時/分/秒
```

`to_date(a) == to_date(b)` 代表「同一個日期（任何時間）」，**不是「ts 一模一樣」**。容易在 self-join 條件中誤讀。

### Broadcast 方向: BuildLeft / BuildRight

```
BroadcastHashJoin [...], Inner, BuildRight
```

`BuildRight` = right side 被 broadcast；`BuildLeft` = left side 被 broadcast。Broadcast **大邊**會 OOM driver（小表才能塞進 executor memory）。

`F.broadcast(small_df)` 用來顯式 hint。Spark 也會自動 broadcast < 10MB 的表（threshold 可調）。

### 跨題測資交互風險

設計多題共用 data 時，**某題故意埋的 quirk（dup pair / orphan row / null amount）會在別題以非預期方式影響 expected**。每題寫 expected 前要過一遍：「這份 quirk 對我這題的影響是？」

例：dedup test 故意埋一對「同 user / 同 ts / 同 type」的 duplicate row。但在「count per-user per-day」這類聚合題裡，這對 duplicate 會被算成 2 筆 → 該題 expected 也得反映兩筆。

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

## Performance Basics (interview-level)

```python
df.cache()              # keep in memory for re-use across actions
df.persist(StorageLevel.MEMORY_AND_DISK)
df.unpersist()          # release

df.repartition(8)               # full shuffle, balanced — use before heavy ops
df.repartition("country")       # partition by column (still shuffles)
df.coalesce(1)                  # reduce partitions WITHOUT shuffle — for writing one file

df.explain()                    # show physical plan
df.explain("formatted")         # cleaner version
```

**When to cache:** the same DataFrame is used in multiple downstream actions. Don't cache reflexively — it costs memory.

**Skew awareness:** if one key has 90% of the rows, that one partition holds up the whole job. Mitigations: salting (add random suffix to key, aggregate twice), broadcast the other side, increase partitions.

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

## DataFrame ↔ RDD

In modern Spark you almost never touch RDDs directly. If asked: `df.rdd` gives the underlying RDD; `spark.createDataFrame(rdd, schema)` goes the other way. If an interviewer pushes on RDD, they're probably testing whether you know DataFrame is the modern default — say so.

## Common Interview Question Shapes

1. **Latest record per group** — Window + row_number + filter (template above)
2. **Sessionization** — events within 30 min are one session; mark gaps with `lag()`, cumulative sum the boolean
3. **Dedup with tiebreaker** — `dropDuplicates(["id"])` is order-undefined; for a specific tiebreaker use Window + row_number
4. **Join then aggregate** — make sure the join doesn't multiply rows before you sum
5. **Pivot** — `df.groupBy("country").pivot("month").agg(F.sum("amount"))`
6. **Read messy data** — explicit schema beats inferSchema; handle bad rows with `PERMISSIVE` / `DROPMALFORMED` / `FAILFAST` mode on reader options

## Nested Types (ArrayType / StructType / MapType)

### Schema 結構

```python
from pyspark.sql.types import ArrayType, StructType, StructField, MapType

# ArrayType: 一個 column 內是 list
ArrayType(StringType())                    # 一個 column 是 list of strings
ArrayType(IntegerType())                   # list of ints

# StructType: 一個 column 內是 nested object（如 JSON）
StructType([
    StructField('user_id', StringType()),
    StructField('addr', StructType([        # 嵌套 struct
        StructField('city', StringType()),
        StructField('zip', StringType()),
    ])),
    StructField('tags', ArrayType(StringType())),    # struct 內的 array
])

# MapType: 一個 column 內是 dict
MapType(StringType(), IntegerType())       # {str: int}
```

### 存取 nested struct field

```python
df.select('user_id', F.col('addr.city'), F.col('addr.zip'))   # 點存取
df.select('user_id', 'addr.*')                                # 展開 struct 所有 field
```

### explode：把 array 攤平成多 row

```python
# 假設一個 user 有 tags = ['python', 'spark', 'sql']
# explode 後變 3 row：(user_id, 'python'), (user_id, 'spark'), (user_id, 'sql')

df.withColumn('tag', F.explode('tags'))
  .select('user_id', 'tag')

# posexplode：同時拿到 array index
df.withColumn('idx_tag', F.posexplode('tags'))
# 結果有 'pos' 跟 'col' 兩個 column

# explode_outer：array 為 NULL 或空時，仍保留 row（攤成 1 row with NULL）
df.withColumn('tag', F.explode_outer('tags'))   # 如果 explode 會丟空 array row
```

### 反向：collect_list / collect_set

```python
# 把多 row 合成 array
df.groupBy('user_id').agg(F.collect_list('tag').alias('tags'))
df.groupBy('user_id').agg(F.collect_set('tag').alias('unique_tags'))   # set 去重
```

### Higher-order functions on arrays（Spark 3.0+）

對 array column 做 map / filter / aggregate，**不用 explode**：

```python
# transform: 對 array 每個元素套用 function
df.withColumn('upper_tags', F.transform('tags', lambda x: F.upper(x)))

# filter: 過濾 array 元素
df.withColumn('long_tags', F.filter('tags', lambda x: F.length(x) > 5))

# aggregate: array 元素累計
df.withColumn('total_amount',
    F.aggregate('amounts', F.lit(0.0), lambda acc, x: acc + x))

# exists: 是否有任何元素符合
df.withColumn('has_python', F.exists('tags', lambda x: x == 'python'))

# array_distinct / array_intersect / array_union / array_except
df.withColumn('unique', F.array_distinct('tags'))
```

**反射：能用 higher-order function 不要 explode**（explode 會增 row 數，下游處理更貴）。

### 從 JSON string parse

```python
# 收到 string column，內容是 JSON
df = spark.createDataFrame([('{"city":"Tokyo","zip":"100"}',)], ['addr_json'])

addr_schema = StructType([
    StructField('city', StringType()),
    StructField('zip', StringType()),
])

df.withColumn('addr', F.from_json('addr_json', addr_schema))
  .select('addr.city', 'addr.zip')

# 反向：to_json
df.withColumn('addr_str', F.to_json(F.col('addr')))
```

### Map operations

```python
df.withColumn('city', F.col('attrs.city'))   # 不行，map 不能點存取
df.withColumn('city', F.col('attrs')['city'])   # 用 bracket
df.withColumn('keys', F.map_keys('attrs'))
df.withColumn('values', F.map_values('attrs'))
df.withColumn('entries', F.map_entries('attrs'))   # array of structs
```

### 常見場景

**1. Nested JSON parsing**

```python
# events.jsonl 每行：
# {"user": "u1", "actions": [{"ts": "2026-01-01", "type": "click"}, ...]}

schema = StructType([
    StructField('user', StringType()),
    StructField('actions', ArrayType(StructType([
        StructField('ts', TimestampType()),
        StructField('type', StringType()),
    ]))),
])

df = (spark.read.schema(schema).json('events.jsonl')
      .select('user', F.explode('actions').alias('action'))
      .select('user', 'action.ts', 'action.type'))
# 展平成 (user, ts, type) flat structure
```

**2. Pivot-style 不用 pivot**

```python
# 想算 per-user 各種 event_type count
# 傳統做法：pivot
df.groupBy('user').pivot('event_type').count()

# Alternative：array + map
df.groupBy('user').agg(
    F.map_from_entries(
        F.collect_list(F.struct('event_type', 'count'))
    ).alias('counts_by_type')
)
```

### 面試常見題型

- 「給 events.jsonl，提取每個 user 的最近一次 purchase 金額」→ from_json / explode / window
- 「展平 nested struct 到 flat columns」→ `select('parent.*')` 或多次 `col('a.b.c')`
- 「把多 row 收進 array 再去重」→ groupBy + `collect_set`
- 「array 內找符合條件的元素」→ `F.exists` / `F.filter`

---

## Sessionization Template (worth memorizing)

```python
w = Window.partitionBy("user_id").orderBy("event_ts")
GAP_MIN = 30

sessions = (df
    .withColumn("prev_ts", F.lag("event_ts").over(w))
    .withColumn("gap_min", (F.col("event_ts").cast("long") - F.col("prev_ts").cast("long")) / 60)
    .withColumn("new_session", (F.col("gap_min").isNull() | (F.col("gap_min") > GAP_MIN)).cast("int"))
    .withColumn("session_id", F.sum("new_session").over(w))
)
```

This pattern (lag → gap detector → cumulative sum as session id) shows up in many DE assessments. It's the Spark version of the gaps-and-islands SQL pattern.

## Common Pitfalls

- `F.col("col").==(value)` — there is no `.==`. Use `==`. (Beginner trap.)
- Forgetting that transforms are lazy — adding a `.show()` to "test" each step is fine, but it re-executes the plan up to that point unless you cache.
- Mixing `df["col"]` references across two DataFrames after a join → ambiguous column error.
- Using Python `if`/`or` inside transforms — they execute once at plan time, not per row. Use `F.when` / `&` / `|`.
- Calling `.collect()` on a giant DataFrame — pulls everything to driver, OOMs.
- Treating `repartition(1)` and `coalesce(1)` as the same — `repartition` shuffles, `coalesce` doesn't (faster but can be unbalanced).
- Forgetting that `dropDuplicates()` with no args dedups on ALL columns; usually you want `dropDuplicates(["id"])`.

## Minimal Run-Locally Setup

```bash
pip install pyspark
python -c "from pyspark.sql import SparkSession; SparkSession.builder.getOrCreate().createDataFrame([(1,)],['x']).show()"
```

If it prints a tiny table, you're set. Spark UI runs at `http://localhost:4040` during a session — useful to inspect stages and skew during practice.
