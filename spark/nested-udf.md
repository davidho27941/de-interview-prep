# PySpark Nested Types & UDF

## Nested Types (ArrayType / StructType / MapType)

### Schema structure

```python
from pyspark.sql.types import ArrayType, StructType, StructField, MapType

# ArrayType: a column containing a list
ArrayType(StringType())                    # a column that is a list of strings
ArrayType(IntegerType())                   # list of ints

# StructType: a column containing a nested object (like JSON)
StructType([
    StructField('user_id', StringType()),
    StructField('addr', StructType([        # nested struct
        StructField('city', StringType()),
        StructField('zip', StringType()),
    ])),
    StructField('tags', ArrayType(StringType())),    # array inside a struct
])

# MapType: a column containing a dict
MapType(StringType(), IntegerType())       # {str: int}
```

### Accessing nested struct fields

```python
df.select('user_id', F.col('addr.city'), F.col('addr.zip'))   # dot access
df.select('user_id', 'addr.*')                                # expand all struct fields
```

### explode: flatten an array into multiple rows

```python
# Suppose a user has tags = ['python', 'spark', 'sql']
# After explode: 3 rows — (user_id, 'python'), (user_id, 'spark'), (user_id, 'sql')

df.withColumn('tag', F.explode('tags'))
  .select('user_id', 'tag')

# posexplode: also get the array index
df.withColumn('idx_tag', F.posexplode('tags'))
# result has two columns: 'pos' and 'col'

# explode_outer: keeps the row when the array is NULL or empty (flattens to 1 row with NULL)
df.withColumn('tag', F.explode_outer('tags'))   # plain explode would drop empty-array rows
```

### The reverse: collect_list / collect_set

```python
# Combine multiple rows into an array
df.groupBy('user_id').agg(F.collect_list('tag').alias('tags'))
df.groupBy('user_id').agg(F.collect_set('tag').alias('unique_tags'))   # set deduplicates
```

⚠ `collect_list` element order is not guaranteed — when order matters, see the sort_array + struct trick in [window-sessionization.md](window-sessionization.md).

### Higher-order functions on arrays (Spark 3.0+)

Apply map / filter / aggregate to an array column **without explode**:

```python
# transform: apply a function to every element of the array
df.withColumn('upper_tags', F.transform('tags', lambda x: F.upper(x)))

# filter: filter array elements
df.withColumn('long_tags', F.filter('tags', lambda x: F.length(x) > 5))

# aggregate: accumulate over array elements
df.withColumn('total_amount',
    F.aggregate('amounts', F.lit(0.0), lambda acc, x: acc + x))

# exists: does any element match
df.withColumn('has_python', F.exists('tags', lambda x: x == 'python'))

# array_distinct / array_intersect / array_union / array_except
df.withColumn('unique', F.array_distinct('tags'))
```

**Reflex: if a higher-order function can do it, don't explode** (explode multiplies row count, making downstream processing more expensive).

### Parsing from a JSON string

```python
# You receive a string column whose content is JSON
df = spark.createDataFrame([('{"city":"Tokyo","zip":"100"}',)], ['addr_json'])

addr_schema = StructType([
    StructField('city', StringType()),
    StructField('zip', StringType()),
])

df.withColumn('addr', F.from_json('addr_json', addr_schema))
  .select('addr.city', 'addr.zip')

# The reverse: to_json
df.withColumn('addr_str', F.to_json(F.col('addr')))
```

### Map operations

```python
df.withColumn('city', F.col('attrs.city'))      # doesn't work — maps don't support dot access
df.withColumn('city', F.col('attrs')['city'])   # use brackets
df.withColumn('keys', F.map_keys('attrs'))
df.withColumn('values', F.map_values('attrs'))
df.withColumn('entries', F.map_entries('attrs'))   # array of structs
```

### Common scenarios

**1. Nested JSON parsing**

```python
# Each line of events.jsonl:
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
# flattened into a (user, ts, type) flat structure
```

**2. Pivot-style without pivot**

```python
# Want per-user counts for each event_type
# Traditional approach: pivot
df.groupBy('user').pivot('event_type').count()

# Alternative: array + map
df.groupBy('user').agg(
    F.map_from_entries(
        F.collect_list(F.struct('event_type', 'count'))
    ).alias('counts_by_type')
)
```

### Common interview question shapes

- "Given events.jsonl, extract each user's most recent purchase amount" → from_json / explode / window
- "Flatten a nested struct into flat columns" → `select('parent.*')` or multiple `col('a.b.c')`
- "Collect multiple rows into an array, then deduplicate" → groupBy + `collect_set`
- "Find array elements matching a condition" → `F.exists` / `F.filter`

---

## UDF (User-Defined Function)

### First principle: if a built-in can do it, **don't** use a UDF

Internally, a UDF makes Spark:
1. Serialize the Spark Column (JVM → Python)
2. Run row-by-row in the Python interpreter
3. Serialize results back (Python → JVM)

**Per-row serialization cost is 10-100x more than a built-in.**

```python
# ❌ Don't write this
@F.udf(returnType=DoubleType())
def double_it(x):
    return x * 2 if x else 0

df.withColumn('doubled', double_it('amount'))

# ✅ The built-in equivalent
df.withColumn('doubled', F.coalesce(F.col('amount') * 2, F.lit(0)))
```

**Reflex: before writing a UDF, search "pyspark functions <the operation you need>".** Nine times out of ten there's a built-in.

### Scenarios where a UDF is genuinely needed

1. **Complex business logic** that built-ins can't express (multi-step parsing, special hashing, etc.)
2. **Calling third-party Python libraries** (advanced regex, ML inference, charset detection, etc.)
3. **Non-serializable stateful operations** (rare)

### Basic UDF patterns

```python
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType

# Three ways to write one

# 1. Decorator
@udf(returnType=StringType())
def classify_amount(x):
    if x is None:
        return 'unknown'
    return 'high' if x > 1000 else 'low'

df.withColumn('tier', classify_amount('amount'))

# 2. Wrap directly
classify_udf = udf(lambda x: 'high' if x and x > 1000 else 'low', StringType())
df.withColumn('tier', classify_udf('amount'))

# 3. Omitting returnType defaults to StringType
@udf
def to_upper(s):
    return s.upper() if s else None
```

**Important:** UDFs do nothing magic with NULL — you must handle `if x is None` yourself. Built-ins are usually NULL-safe (NULL in, NULL out); UDFs give no such guarantee.

### Vectorized UDF (`@F.pandas_udf`)

**10-100x** better performance than a row-by-row UDF. Reason: each call processes a pandas Series (a batch of rows), not a single row.

```python
import pandas as pd
from pyspark.sql.functions import pandas_udf

@pandas_udf(DoubleType())
def normalize(amount: pd.Series) -> pd.Series:
    return (amount - amount.mean()) / amount.std()

df.withColumn('z_score', normalize('amount'))
```

**When to use:** math that requires numpy / pandas to express (common in ML feature engineering).

### UDF performance comparison (memorize)

```
built-in F.col(...) operations    → fastest (computed inside the JVM)
pandas_udf (vectorized)           → ~5-10x built-in
udf (row-by-row)                  → ~50-100x built-in
```

### Interviewers ask

> "Why are PySpark UDFs slow?"

**Correct answer:** Python ↔ JVM serialization cost (Py4J / Arrow). Every row crosses the boundary once.

> "Why is a Pandas UDF faster than a regular UDF?"

**Correct answer:** Arrow batches cross the boundary (one serialization per batch of rows) + pandas runs in C internally (unlike a Python loop).
