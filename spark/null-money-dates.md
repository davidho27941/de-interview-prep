# PySpark Types — NULL, Money (Decimal), Dates, Casts

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

（NULL 穿過 `when` 鏈的三值邏輯陷阱 → 見 [joins.md](joins.md) 的 reconciliation shape。）

## Money Arithmetic (DecimalType — make it reflexive)

IEEE 754 doubles cannot represent most 2-decimal amounts exactly. Individually the error is invisible; **summed, it surfaces**: a `sum()` over amounts totalling $2508.06 can return `2508.0600000000004`, and a `paid_total == invoice_amount` comparison then misclassifies a perfectly matched invoice. No exception, no warning — just a wrong label.

```python
from pyspark.sql.types import DecimalType

MONEY = DecimalType(12, 2)   # 12 total digits, 2 after the point

# JSON/CSV: force Decimal at read time (inferSchema gives you double)
schema = StructType([
    StructField("invoice_id", StringType()),
    StructField("amount",     MONEY),
])

# Parquet: whatever was written; check with printSchema() — don't assume

# Zero literals must be typed to match, or the comparison type-promotes oddly:
F.coalesce(F.col("paid_total"), F.lit(0).cast(MONEY))

# Explicit rounding — only if the pipeline is stuck with doubles:
F.round(F.col("amount"), 2)
```

**Reflex:** money that flows through `sum` into an equality/inequality → `DecimalType` end-to-end. If the source is genuinely double (messy API), round to a declared precision *before* every comparison, and say so in comments. On the Python side the same rule holds: `decimal.Decimal(str(x))`, never `Decimal(float_val)` (which re-imports the float noise).

## Date/Time Toolbox

```python
F.to_date("event_ts")                       # timestamp → date (取日期部分)
F.trunc("invoice_date", "month")            # date → 該月第一天 (月報 grain 的標配)
F.date_trunc("hour", "event_ts")            # timestamp → 截到小時/分 (回傳 timestamp)
F.to_timestamp("ts_str", "yyyy-MM-dd HH:mm:ss")   # string → timestamp (格式明示)

# Duration in seconds — the standard idiom:
F.unix_timestamp("end_ts") - F.unix_timestamp("start_ts")

F.date_add("d", 7)  /  F.date_sub("d", 7)   # 平移天數
F.months_between("d1", "d2")                # 月差 (float — cohort age 記得 floor/cast)
F.year("d"), F.month("d"), F.dayofweek("d") # 拆欄位
```

**易混:** `trunc(col, "month")` 吃 date 回 date(月初);`date_trunc("month", col)` 吃 timestamp 回 timestamp。月度 grain 報表用前者。**Duration 不要用 `datediff`**(它只算「跨了幾個日曆日」,同日兩事件回 0)— 秒數用 `unix_timestamp` 相減。

### `F.to_date()` 是「取日期部分」不是「ts 相等」

```python
F.to_date(ts)   # 取 yyyy-MM-dd，截掉時/分/秒
```

`to_date(a) == to_date(b)` 代表「同一個日期（任何時間）」，**不是「ts 一模一樣」**。容易在 self-join 條件中誤讀。

## Casts 與 ANSI mode（Spark 3 vs 4 行為差異）

```python
F.col("amount_str").cast("double")
F.col("id").cast(IntegerType())
```

**行為分歧 — 這是版本敏感的坑:**

- **傳統模式**(`spark.sql.ansi.enabled=false`, Spark 3.x 預設): 壞 cast **無聲變 NULL** — `"abc".cast(int)` → NULL,除以零 → NULL。錯誤被吞,downstream 才發現資料缺了。
- **ANSI 模式**(**Spark 4.x 預設 ON**): 壞 cast / 溢位 / 除以零 **直接拋錯**。同一份 code 在 Spark 3 「跑得過」、在 Spark 4 炸掉 — 或反過來,你在 Spark 4 練的防禦寫法到了 Spark 3 環境不會觸發。

```python
# 兩邊都安全的寫法:
F.try_cast?  # Spark 3.5+ SQL 有 try_cast; DataFrame API 用:
F.expr("try_cast(amount_str AS double)")      # 壞值 → NULL, 兩種模式行為一致
F.when(F.col("s").rlike(r"^\d+(\.\d+)?$"), F.col("s").cast("double"))  # 先驗再 cast
```

**面試被問「髒字串欄位轉數字怎麼處理」的 senior 答法:** 先講兩種模式的行為差異,再給 `try_cast` / 驗證後 cast,並補「壞列要隔離回報,不是無聲丟棄」。
