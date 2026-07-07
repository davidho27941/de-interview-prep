# PySpark IO — File Formats, Readers, Path Traps, Write Layout

## Trade-off comparison

| Format | Schema | Compression | Predicate pushdown | Schema evolution | Use case |
|---|---|---|---|---|---|
| **CSV** | None; needs inferSchema or explicit | Weak (text) | None | Painful | External exchange, log files |
| **JSON** (multi-line) | Nested, one object per file | Weak | None | Medium | API responses, config |
| **JSONL** (one per line) | Nested, one object per line | Weak | None | Medium | Event logs, streaming output |
| **Parquet** | Self-describing schema | Strong (columnar + compression) | Strong | Good | Analytics default, big data |
| **ORC** | Self-describing schema | Strong | Strong | Good | Hive environments |
| **Delta** | Parquet + transaction log | Strong | Strong + ACID | Excellent | Modern lakehouse |

**Reflex:** Use Parquet for internal data. CSV / JSON only when exchanging with external parties or receiving from an API.

## Reading JSON

```python
# Multi-line (whole file is one JSON object or array)
df = spark.read.option('multiLine', 'true').json('input/config.json')

# JSON Lines (one JSON object per line) — the default
df = spark.read.json('input/events.jsonl')

# Explicit schema is twice as fast as inferSchema (no second scan)
schema = StructType([
    StructField('user_id', StringType()),
    StructField('events', ArrayType(StructType([
        StructField('ts', TimestampType()),
        StructField('type', StringType()),
    ]))),
])
df = spark.read.schema(schema).json('input/events.jsonl')
```

## Parsing JSON from a string column

A CSV has a column whose value is a JSON string; parse it into a struct:

```python
event_schema = StructType([
    StructField('type', StringType()),
    StructField('amount', DoubleType()),
])

df.withColumn('parsed', F.from_json('event_json_str', event_schema))
  .select('user_id', F.col('parsed.type'), F.col('parsed.amount'))
```

Reverse direction: `F.to_json(struct_col)` writes a struct back to a JSON string. (Full set of nested operations: [nested-udf.md](nested-udf.md))

## Parquet read/write

```python
# Write
df.write.mode('overwrite').parquet('out/path')

# Partition by column
df.write.partitionBy('year', 'month').parquet('out/path')
# Writes out/path/year=2026/month=06/part-*.parquet

# Read (automatic schema discovery)
df = spark.read.parquet('out/path')

# Predicate pushdown — Spark pushes the filter down automatically, scanning only the needed partitions
df.filter(F.col('year') == 2026).filter(F.col('month') == 6)  # only reads year=2026/month=06/
```

## Schema evolution

New data has an extra column that old data lacks:

```python
# Merge schemas across multiple writes (handles added columns automatically)
df = spark.read.option('mergeSchema', 'true').parquet('out/path')

# Inconsistent schemas fail on write; you must be explicit
df.write.option('mergeSchema', 'true').mode('append').parquet('out/path')
```

## Malformed rows (dirty-data read modes)

```python
# Three modes:
spark.read.option("mode", "PERMISSIVE")      # Default: set bad rows' fields to NULL, continue
spark.read.option("mode", "DROPMALFORMED")   # Drop bad rows outright
spark.read.option("mode", "FAILFAST")        # Throw immediately on a bad row

# PERMISSIVE + capture the raw text of bad rows (CSV/JSON):
schema_with_corrupt = StructType([
    StructField("user_id", StringType()),
    StructField("amount", DoubleType()),
    StructField("_corrupt_record", StringType()),   # raw text of bad rows lands in this column
])
df = spark.read.schema(schema_with_corrupt).json("input/").cache()   # cache is REQUIRED — see below
bad = df.filter(F.col("_corrupt_record").isNotNull())   # isolate bad rows for reporting/landing
```

**The `.cache()` is not optional.** `_corrupt_record` is populated as a *side effect of trying to parse the other columns*. A query that references only the corrupt column would let column pruning skip parsing entirely — a semantic contradiction — so Spark 3+ rejects it outright with `[UNSUPPORTED_FEATURE.QUERY_ONLY_CORRUPT_RECORD_COLUMN]`. Caching materializes the full parse first; subsequent queries hit the cache instead of the pruned reader.

Two more traps on the same line:
- NULL checks are `isNotNull()` / `isNull()` — never `!= "NULL"` (that compares against the *string* "NULL") and never `!= None` (three-valued logic: `NULL != x` is NULL, so the filter silently returns nothing).
- The `_corrupt_record` field in your schema must be nullable (`True`).

**Senior stance:** production ingest uses PERMISSIVE + `_corrupt_record` to route bad rows to a quarantine path, rather than DROPMALFORMED silently swallowing them — "how much was dropped, and what" must be answerable.

## Common pitfalls when reading

- **CSV with `header=True` still defaults to an all-String schema**; you need `inferSchema=True` or an explicit schema
- **JSON time fields** should use `TimestampType()`, not string — otherwise sorting is a lexical sort
- **Never enable `multiLine` on JSONL** — `multiLine=True` is for "whole file is one JSON object"; enable it on JSONL and each file gets treated as one broken JSON, with permissive mode producing one all-NULL row per file. Symptoms: count equals the number of files, columns all NULL, `isin` filters match nothing
- **Compatibility between the Spark version writing Parquet and the one reading it** — usually fine, but verify across major versions
- **Decimal precision** can be lost during CSV → Parquet conversion; financial use requires an explicit schema (see [null-money-dates.md](null-money-dates.md))

## Path and reader API traps

```python
# json/csv/text accept str, list, even RDD[str]
spark.read.json(["a.jsonl", "b.jsonl"])          # OK

# parquet/orc are varargs — passing a list blows up:
spark.read.parquet(files)                         # ClassCastException: ArrayList → String
spark.read.parquet(*files)                        # OK (unpack)

# Universal fix: both accept a glob string directly; don't glob into a list yourself
spark.read.parquet("input/invoices/*.parquet")
spark.read.json("input/events/events-*.jsonl")
```

- **Use exact-extension globs to filter out stray files** — folders often mix in `.bak`, `_SUCCESS`, `.DS_Store`, `README.md`. Patterns like `*.parquet` / `events-*.jsonl` naturally exclude them; `spark.read.parquet("dir/")` reading the whole directory swallows everything.
- **`F.input_file_name()`** lets you trace, after reading, which file each row came from — use it to debug stray-file contamination, or when you need to filter based on filename information.
- **Glob paths trigger one harmless WARN**: `FileStreamSink ... FileNotFoundException` — before reading, Spark checks whether the path is a streaming sink's metadata directory; a glob is not a real path, so it throws and falls back. Pure log noise, results are correct; if it bothers you, `setLogLevel('ERROR')`.
- **Filename does not equal data content** — a daily file is not guaranteed to contain only that day's events (upstream spillover is very common). Always derive dates from columns, never from filenames.

## The small-files problem (senior awareness on the write side)

`partitionBy` can write one file per partition value × per task — a high-cardinality column (like `user_id`) as partition key explodes into millions of small files; metadata crushes listing and reads slow down.

```python
# Pick a low-cardinality column as partition key (date / country / status)
df.write.partitionBy("date").parquet("out/")

# Cap rows per file (prevents any single file from getting too large)
df.write.option("maxRecordsPerFile", 1_000_000).parquet("out/")

# Reshuffle data by partition key before writing, so each partition value converges to a few files:
df.repartition("date").write.partitionBy("date").parquet("out/")
```

**Rule of thumb:** partition key cardinality ≈ tens to thousands; target file size ~128MB–1GB. When asked in an interview "what do you do about a pile of small output files" → repartition by partition key before write.
