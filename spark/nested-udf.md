# PySpark Nested Types & UDF

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

⚠ `collect_list` 元素順序不保證 — 需要順序時見 [window-sessionization.md](window-sessionization.md) 的 sort_array + struct 技巧。

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
df.withColumn('city', F.col('attrs.city'))      # 不行，map 不能點存取
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

**反射：寫 UDF 前先查「pyspark functions <你要的操作>」**。九成情況有 built-in。

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
