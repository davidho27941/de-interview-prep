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

### Aggregate NULL behavior comparison table

When aggregating after a LEFT JOIN, different functions behave differently on an "all-NULL group":

| Function | All-NULL group result | Needs COALESCE? |
|---|---|---|
| `F.count(col)` | **0** | ❌ No |
| `F.count('*')` | row count (including NULL rows) | Not suitable for counting "how many right-side rows exist" |
| `F.countDistinct(col)` | **0** | ❌ No |
| `F.sum(col)` | **NULL** | ✅ Required |
| `F.avg(col)` | **NULL** | ✅ Usually needed |
| `F.max/min(col)` | **NULL** | ✅ Depends on context |

**Reflex:** always wrap sum/avg/max/min in COALESCE. count doesn't need it (already returns 0).

(For the three-valued-logic trap of NULLs passing through a `when` chain, see the reconciliation shape in [joins.md](joins.md).)

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
F.to_date("event_ts")                       # timestamp → date (take the date part)
F.trunc("invoice_date", "month")            # date → first day of that month (standard for monthly-grain reports)
F.date_trunc("hour", "event_ts")            # timestamp → truncate to hour/minute (returns timestamp)
F.to_timestamp("ts_str", "yyyy-MM-dd HH:mm:ss")   # string → timestamp (explicit format)

# Duration in seconds — the standard idiom:
F.unix_timestamp("end_ts") - F.unix_timestamp("start_ts")

F.date_add("d", 7)  /  F.date_sub("d", 7)   # shift by days
F.months_between("d1", "d2")                # month difference (float — remember to floor/cast for cohort age)
F.year("d"), F.month("d"), F.dayofweek("d") # extract components
```

**Easily confused:** `trunc(col, "month")` takes a date and returns a date (start of month); `date_trunc("month", col)` takes a timestamp and returns a timestamp. Use the former for monthly-grain reports. **Don't use `datediff` for durations** (it only counts "how many calendar days were crossed" — two events on the same day return 0) — for seconds, subtract `unix_timestamp` values.

### `F.to_date()` means "take the date part", not "timestamps are equal"

```python
F.to_date(ts)   # take yyyy-MM-dd, truncating hours/minutes/seconds
```

`to_date(a) == to_date(b)` means "the same date (at any time)", **not "identical timestamps"**. Easy to misread in self-join conditions.

## Casts and ANSI mode (Spark 3 vs 4 behavior difference)

```python
F.col("amount_str").cast("double")
F.col("id").cast(IntegerType())
```

**Behavioral divergence — this is a version-sensitive trap:**

- **Legacy mode** (`spark.sql.ansi.enabled=false`, Spark 3.x default): a bad cast **silently becomes NULL** — `"abc".cast(int)` → NULL, division by zero → NULL. Errors get swallowed; you only discover the missing data downstream.
- **ANSI mode** (**Spark 4.x default ON**): bad casts / overflow / division by zero **throw immediately**. The same code "runs fine" on Spark 3 but blows up on Spark 4 — or the reverse: defensive patterns you practiced on Spark 4 never trigger in a Spark 3 environment.

```python
# Safe in both modes:
F.try_cast?  # Spark 3.5+ SQL has try_cast; in the DataFrame API use:
F.expr("try_cast(amount_str AS double)")      # bad values → NULL, consistent behavior in both modes
F.when(F.col("s").rlike(r"^\d+(\.\d+)?$"), F.col("s").cast("double"))  # validate before casting
```

**When asked in an interview "how do you handle converting a dirty string column to numbers", the senior answer:** first explain the behavior difference between the two modes, then give `try_cast` / validate-then-cast, and add "bad rows should be quarantined and reported, not silently dropped."
