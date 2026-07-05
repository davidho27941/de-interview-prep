# PySpark IO — File Formats, Readers, Path Traps, Write Layout

## Trade-off 對照

| 格式 | Schema | 壓縮 | Predicate pushdown | Schema evolution | 用途 |
|---|---|---|---|---|---|
| **CSV** | 無，要 inferSchema 或顯式 | 弱（文字） | 無 | 麻煩 | 跟外部交換、log file |
| **JSON** (multi-line) | 嵌套，每檔一個物件 | 弱 | 無 | 中等 | API response、config |
| **JSONL** (one per line) | 嵌套，每行一個物件 | 弱 | 無 | 中等 | event log、streaming output |
| **Parquet** | 自帶 schema | 強（柱狀+壓縮） | 強 | 好 | analytics 預設、大資料 |
| **ORC** | 自帶 schema | 強 | 強 | 好 | Hive 環境 |
| **Delta** | Parquet + transaction log | 強 | 強 + ACID | 極好 | modern lakehouse |

**反射：** 內部資料用 Parquet。給外部 / 來自 API 才用 CSV / JSON。

## JSON 讀取

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

## 從 string column parse JSON

CSV 內有一個欄位 value 是 JSON string，要 parse 成 struct：

```python
event_schema = StructType([
    StructField('type', StringType()),
    StructField('amount', DoubleType()),
])

df.withColumn('parsed', F.from_json('event_json_str', event_schema))
  .select('user_id', F.col('parsed.type'), F.col('parsed.amount'))
```

反向：`F.to_json(struct_col)` 把 struct 寫回 JSON string。（Nested 操作全集：[nested-udf.md](nested-udf.md)）

## Parquet 讀寫

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

## Schema 演進

新資料多了一個欄位，舊資料沒有：

```python
# 合併多次 write 的 schema（自動處理新增 column）
df = spark.read.option('mergeSchema', 'true').parquet('out/path')

# 寫入時 schema 不一致會 fail，要明示
df.write.option('mergeSchema', 'true').mode('append').parquet('out/path')
```

## Malformed rows（髒資料讀取模式）

```python
# 三種 mode:
spark.read.option("mode", "PERMISSIVE")      # 預設: 壞列欄位設 NULL, 繼續
spark.read.option("mode", "DROPMALFORMED")   # 壞列直接丟
spark.read.option("mode", "FAILFAST")        # 壞列立刻拋錯

# PERMISSIVE + 捕捉壞列原文 (CSV/JSON):
schema_with_corrupt = StructType([
    StructField("user_id", StringType()),
    StructField("amount", DoubleType()),
    StructField("_corrupt_record", StringType()),   # 壞列的原始文字會進這欄
])
df = spark.read.schema(schema_with_corrupt).json("input/")
bad = df.filter(F.col("_corrupt_record").isNotNull())   # 壞列隔離出來報告/落地
```

**Senior 姿態:** production ingest 用 PERMISSIVE + `_corrupt_record` 把壞列導去 quarantine 路徑，而不是 DROPMALFORMED 無聲吞掉 — 「掉了多少、掉了什麼」必須可回答。

## Reading 常見坑

- **CSV 跟 `header=True` 預設 schema 全 String**，需要 `inferSchema=True` 或顯式 schema
- **JSON 時間欄位**用 `TimestampType()` 而不是 string，否則排序時是 lexical sort
- **JSONL 千萬別開 `multiLine`** — `multiLine=True` 是給「整檔一個 JSON 物件」用的；對 JSONL 開了它，每個檔會被當成一個壞掉的 JSON，permissive 模式產出每檔一列全 NULL。症狀：count 等於檔案數、欄位全 NULL、`isin` 過濾抓不到任何東西
- **Parquet 寫 Spark 跟讀 Spark 版本相容性** — 通常 ok，但跨大版本要驗
- **Decimal precision** 在 CSV → Parquet 轉換時可能掉精度，金融用要顯式 schema（見 [null-money-dates.md](null-money-dates.md)）

## Path 與 reader API 陷阱

```python
# json/csv/text 接受 str、list、甚至 RDD[str]
spark.read.json(["a.jsonl", "b.jsonl"])          # OK

# parquet/orc 是 varargs — 傳 list 會炸:
spark.read.parquet(files)                         # ClassCastException: ArrayList → String
spark.read.parquet(*files)                        # OK (unpack)

# 通用解法: 兩邊都直接吃 glob string, 別自己先 glob 成 list
spark.read.parquet("input/invoices/*.parquet")
spark.read.json("input/events/events-*.jsonl")
```

- **用「精確 extension」的 glob 過濾雜檔** — 資料夾常混著 `.bak`、`_SUCCESS`、`.DS_Store`、`README.md`。`*.parquet` / `events-*.jsonl` 這種 pattern 天然排除它們；`spark.read.parquet("dir/")` 整目錄讀會全吞。
- **`F.input_file_name()`** 可以在讀入後追查每列來自哪個檔 — debug 雜檔混入、或需要以檔名資訊過濾時用。
- **Glob path 會觸發一條無害 WARN**：`FileStreamSink ... FileNotFoundException` — Spark 讀檔前先檢查該路徑是否為 streaming sink 的 metadata 目錄，glob 不是真實路徑所以拋錯再 fallback。純 log 噪音，結果正確；嫌吵就 `setLogLevel('ERROR')`。
- **檔名不等於資料內容** — 每日檔不保證只含當日事件（上游 spillover 很常見）。日期永遠從欄位推，不從檔名推。

## Small files 問題（write 端的 senior 意識）

`partitionBy` 的每個 partition 值 × 每個 task 都可能各寫一檔 — 高基數欄位（如 `user_id`）當 partition key 會爆出百萬小檔，metadata 壓垮 listing、讀取變慢。

```python
# partition key 選低基數欄位 (date / country / status)
df.write.partitionBy("date").parquet("out/")

# 控制單檔列數上限（防單檔過大）
df.write.option("maxRecordsPerFile", 1_000_000).parquet("out/")

# 寫前先把資料按 partition key 重排, 每個 partition 值收斂到少數檔:
df.repartition("date").write.partitionBy("date").parquet("out/")
```

**Rule of thumb:** partition key 基數 ≈ 幾十到幾千；單檔目標 ~128MB–1GB。面試被問「輸出一堆小檔怎麼辦」→ repartition by partition key before write。
