# Batch vs Streaming — Concepts for the Verbal Rounds

This file is **ammunition for verbal deep-dives / system design rounds**, not coding practice — timed coding screens almost never test streaming code (no Kafka to run, jobs don't terminate, asserts can't validate unbounded data). But in senior DE verbal rounds, the batch/streaming tradeoff is a guaranteed question; and these concepts explain the **root causes** of data oddities in batch problems — being able to articulate the root cause is a senior signal.

## Spectrum: Batch → Micro-batch → Streaming

| | Latency | Cost/Complexity | Typical tools |
|---|---|---|---|
| **Batch** | hours~days | lowest | Spark batch, dbt, Airflow schedules |
| **Micro-batch** | minutes | medium | Spark Structured Streaming (default mode), scheduled batch every N minutes |
| **Streaming (record-at-a-time)** | sub-second~seconds | highest | Flink, Kafka Streams |

**Senior opening line:** the choice is driven by "how late can this number arrive before the business loses money", not by technical fashion. Most "we need streaming" requests, when probed, are satisfied by hourly / 15-min micro-batch — streaming is a latency-cost tradeoff, and every step leftward on the spectrum jumps operational complexity (state management, replay, monitoring) up a level.

> When asked in an interview "should this pipeline be batch or streaming?" — first ask back about the freshness SLA and downstream use (dashboard? real-time fraud blocking?), then map to a position on the spectrum, and finish with a note on the cost difference. Jumping straight to an answer is junior behavior.

## Structured Streaming Mental Model

**"An incremental query running on an unbounded table"** — the API is nearly identical to a batch DataFrame:

```python
# batch
df = spark.read.json("input/")
out = df.groupBy("user_id").count()
out.write.parquet("out/")

# streaming — same logic, read→readStream, write→writeStream
df = spark.readStream.schema(schema).json("input/")
out = df.groupBy("user_id").count()
q = (out.writeStream.outputMode("update")
        .option("checkpointLocation", "chk/")
        .trigger(processingTime="1 minute")
        .start())
```

The engine treats "newly arrived data" as increments to the table, running an incremental computation on each trigger. **This is why the learning cost is low: the transform layer is fully shared** — all differences live in four things: source/sink/trigger/state.

> When asked in an interview "how does Spark Streaming differ from batch?" — answer with the unbounded table model + the four points of difference (source/sink/trigger/state); don't recite the old DStream API (that's Spark 1.x era).

## Delivery Semantics — Why Data Is Naturally Duplicated

- **At-most-once**: may lose data, never duplicates (fire-and-forget)
- **At-least-once**: never loses data, **may duplicate** (retry until ack — the reality of the vast majority of event pipelines)
- **Exactly-once**: end-to-end no loss, no duplicates — requires a replayable source + an idempotent/transactional sink working together; the engine in the middle can't do it alone

**This explains data oddities in batch problems:** duplicate rows with "same user, same timestamp, same type" in event data are usually traces of at-least-once retries — and this is why:

1. **Dedup requires a business-event id** (`event_id` / `idempotency_key`) to be definitive; heuristic dedup on `(user, ts, type)` can kill genuine concurrent events
2. **Sinks must be idempotent** — replaying the same batch twice must yield the same result (overwrite by partition, merge by key — not blind append)

> When asked in an interview "how do you guarantee exactly-once?" — the standard answer: a replayable source (Kafka offsets / files) + checkpoint recording progress + an idempotent or transactional sink; all three are required. Add: "in practice, the common approach is at-least-once + an idempotent sink, which is equivalent in effect."

## Late Data and Watermarks

An event's **event time** (when it happened) and **processing time** (when it arrived) always differ — offline phones re-uploading, upstream buffer flushes, cross-region networks. The batch-world symptom: daily files contain events from the previous day ("the filename does not equal the data content"); the streaming-world problem: how long should an aggregation wait before "closing the window"?

**Watermark = a declaration of "how late I'm willing to wait for data":**

```python
(df.withWatermark("event_ts", "1 hour")           # events more than 1 hour late are dropped
   .groupBy(F.window("event_ts", "10 minutes"))   # tumbling window
   .count())
```

Window types map to batch concepts you already know:

- **Tumbling** (fixed, non-overlapping) = batch's `date_trunc` bucketing
- **Sliding** (fixed, overlapping) = batch's moving window
- **Session window** (close when the gap exceeds N) = the real-time version of your sessionization template — one line of `F.session_window("event_ts", "30 minutes")` equals the whole lag→gap→cumsum routine

> When asked in an interview "how do you handle late data?" — batch answer: reprocess a window (recompute the last N days daily). Streaming answer: watermark + the lateness-allowance tradeoff (waiting longer is more accurate but grows state and delays output). Give both, showing you know how the same problem is solved in each world.

## State, Checkpoint, Output Modes

- **Stateful operations** (windowed agg, dedup, stream-stream join) must remember things between triggers — the state store lives on executors + checkpoints to reliable storage
- **Checkpoint** records "read position + state" — a crashed job restarts and resumes from the checkpoint; this is the foundation of exactly-once. **A checkpoint is bound to the query logic** — after changing the aggregation logic you usually can't reuse the old checkpoint
- **Output modes**: `append` (only emit newly finalized rows, paired with watermark) / `update` (emit changed rows) / `complete` (emit the full result every time — only suitable for small result tables)

## Trigger.AvailableNow — Where Batch and Streaming Converge

```python
q = out.writeStream.trigger(availableNow=True).option("checkpointLocation", "chk/").start()
```

"Process all the new data accumulated so far, **then stop**" — running scheduled batch with streaming's checkpoint/exactly-once machinery. This is the standard modern approach to **incremental batch** (replacing hand-rolled "record which file was processed last" logic).

> When asked in an interview "ingest new files hourly with no duplicates and no gaps — how do you design it?" — the modern answer to this is AvailableNow (or the Delta/lakehouse equivalent), cleaner than a home-made high-water-mark table.

## Lambda vs Kappa (one paragraph)

- **Lambda**: a batch layer (accurate, slow) + a speed layer (real-time, approximate) in parallel, merged at the serving layer — accurate but requires maintaining two sets of logic
- **Kappa**: streaming only; historical recomputation relies on replay — one set of logic, but requires a long-term replayable source
- **Practical reality**: lakehouse (Delta/Iceberg) + incremental processing has blurred the line — the same code runs on a schedule with AvailableNow and near-real-time with processingTime. In interviews, reaching this level is enough; don't recite dogma.

## CDC (Change Data Capture, one paragraph)

Extracting changes (insert/update/delete) from an OLTP database as an event stream (Debezium reads the binlog → Kafka → lakehouse merge). Key concepts: every change carries an **op type + primary key + before/after**; downstream rebuilds table state with **merge/upsert**; out-of-order and duplicate events are handled by primary key + LSN/ts "last write wins" — which brings us back to idempotency and dedup-by-key.

> When asked in an interview "how do you sync a MySQL table to a data lake?" — full snapshot + CDC increments + periodic compaction/merge; explaining how deletes are handled (tombstone/merge delete) is a bonus point.

## One-Sentence Summary (memorize verbatim)

"Batch and streaming share the same set of semantic problems — duplicates, lateness, ordering, idempotency; the only difference is whether you face them at **file granularity** or **event granularity**." Being able to explain duplicate rows in a batch problem's data as traces of at-least-once, and cross-day events in daily files as late data, is the line between senior and mid-level.
