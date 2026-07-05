# Batch vs Streaming — Concepts for the Verbal Rounds

這一檔是**口頭深潛 / system design 輪的彈藥**,不是 coding 練習 — timed coding screen 幾乎不考 streaming code(跑不了 Kafka、job 不終止、assert 驗不了 unbounded 資料)。但 senior DE 面試的口頭輪,batch/streaming tradeoff 是必考題;而且這些概念解釋了 batch 題裡資料怪象的**根因**,講得出根因是 senior signal。

## 光譜:Batch → Micro-batch → Streaming

| | Latency | 成本/複雜度 | 典型工具 |
|---|---|---|---|
| **Batch** | 小時~天 | 最低 | Spark batch, dbt, Airflow 排程 |
| **Micro-batch** | 分鐘 | 中 | Spark Structured Streaming(預設 mode)、每 N 分鐘的排程 batch |
| **Streaming (record-at-a-time)** | 亞秒~秒 | 最高 | Flink, Kafka Streams |

**Senior 開場白:** 選型由「這個數字晚多久到會造成業務損失」決定,不是由技術時髦度決定。大多數「我們要 streaming」的需求,追問下去是 hourly / 15-min micro-batch 就滿足 — streaming 是 latency-cost tradeoff,每往左移一格,運維複雜度(state 管理、重放、監控)跳一級。

> 面試被問「這條 pipeline 該 batch 還是 streaming?」— 先反問 freshness SLA 與下游用途(dashboard? 風控攔截?),再對映到光譜位置,最後補一句成本差異。直接跳答案是 junior 行為。

## Structured Streaming 心智模型

**「在一張 unbounded table 上跑 incremental query」** — API 跟 batch DataFrame 幾乎一樣:

```python
# batch
df = spark.read.json("input/")
out = df.groupBy("user_id").count()
out.write.parquet("out/")

# streaming — 同一段邏輯, read→readStream, write→writeStream
df = spark.readStream.schema(schema).json("input/")
out = df.groupBy("user_id").count()
q = (out.writeStream.outputMode("update")
        .option("checkpointLocation", "chk/")
        .trigger(processingTime="1 minute")
        .start())
```

引擎把「新到的資料」當作 table 的增量,每個 trigger 跑一次 incremental 計算。**這是學習成本低的原因:transform 層完全共用**,差異全在 source/sink/trigger/state 四件事。

> 面試被問「Spark Streaming 跟 batch 差在哪?」— 答 unbounded table 模型 + 四個差異點(source/sink/trigger/state),不要背 DStream 老 API(那是 Spark 1.x 時代)。

## Delivery Semantics — 為什麼資料天生有重複

- **At-most-once**: 可能掉資料,不重複(fire-and-forget)
- **At-least-once**: 不掉資料,**可能重複**(retry 直到 ack — 絕大多數 event pipeline 的實況)
- **Exactly-once**: 端到端不掉不重 — 需要 source 可重放 + sink 冪等/transactional 一起配合,單靠中間引擎做不到

**這解釋了 batch 題裡的資料怪象:** event 資料中「同 user 同 timestamp 同 type」的重複列,多半是 at-least-once retry 的痕跡 — 這就是為什麼:

1. **Dedup 需要 business-event id**(`event_id` / `idempotency_key`)才是定論;拿 `(user, ts, type)` 啟發式去重可能誤殺真實的並發事件
2. **Sink 要冪等** — 同一批資料重放兩次,結果要一樣(overwrite by partition、merge by key,而不是盲目 append)

> 面試被問「怎麼保證 exactly-once?」— 標準答:可重放的 source(Kafka offset / 檔案)+ checkpoint 記進度 + 冪等或 transactional 的 sink,三件缺一不可。再補一句「實務上常見做法是 at-least-once + 冪等 sink,效果等同」。

## Late Data 與 Watermark

事件的 **event time**(發生時間)跟 **processing time**(到達時間)永遠有差 — 手機離線補傳、上游 buffer flush、跨區網路。批次世界的症狀:每日檔案含有前一天的事件(「檔名不等於資料內容」);流式世界的問題:aggregation 要等多久才能「關窗」?

**Watermark = 「我最多等多晚的資料」的宣告:**

```python
(df.withWatermark("event_ts", "1 hour")           # 晚超過 1 小時的事件直接丟
   .groupBy(F.window("event_ts", "10 minutes"))   # tumbling window
   .count())
```

Window 種類對映你已會的 batch 概念:

- **Tumbling**(固定不重疊)= batch 的 `date_trunc` 分桶
- **Sliding**(固定會重疊)= batch 的 moving window
- **Session window**(gap 超過 N 就關窗)= 你的 sessionization 模板的即時版 — `F.session_window("event_ts", "30 minutes")` 一行等於整套 lag→gap→cumsum

> 面試被問「late data 怎麼處理?」— batch 答案:reprocess 窗口(每天重算最近 N 天)。streaming 答案:watermark + 允許遲到的量 tradeoff(等越久越準但 state 越大、輸出越晚)。兩個都講,說明你知道同一問題在兩個世界的解法。

## State、Checkpoint、Output Modes

- **Stateful 操作**(windowed agg、dedup、stream-stream join)要在 trigger 之間記住東西 — state store 存在 executor + checkpoint 到可靠儲存
- **Checkpoint** 記「讀到哪 + state」— job 掛掉重啟從 checkpoint 續跑,這是 exactly-once 的基石。**Checkpoint 綁定 query 邏輯**,改了 aggregation 邏輯通常不能沿用舊 checkpoint
- **Output modes**: `append`(只輸出新確定的列,搭 watermark)/ `update`(輸出有變化的列)/ `complete`(每次全量輸出,只適合小結果表)

## Trigger.AvailableNow — batch 與 streaming 的收斂點

```python
q = out.writeStream.trigger(availableNow=True).option("checkpointLocation", "chk/").start()
```

「把目前累積的新資料**一次處理完就停**」— 用 streaming 的 checkpoint/exactly-once 機制跑排程 batch。這是現代 **incremental batch** 的標準做法(取代自己手寫「記錄上次處理到哪個檔案」的邏輯)。

> 面試被問「每小時 ingest 新檔案、不重不漏,怎麼設計?」— 這題的現代答案就是 AvailableNow(或 Delta/lakehouse 的等效機制),比自製 high-water-mark table 乾淨。

## Lambda vs Kappa(一段講完)

- **Lambda**: batch 層(準確、慢)+ speed 層(即時、近似)雙軌,serving 層合併 — 準但要維護兩套邏輯
- **Kappa**: 只有 streaming 一軌,歷史重算靠 replay — 一套邏輯,但要求 source 可長期重放
- **實務現況**: lakehouse(Delta/Iceberg)+ incremental 處理讓兩者界線模糊 — 同一套 code,AvailableNow 跑排程、processingTime 跑近即時。面試講到這一層即可,別背教條。

## CDC(Change Data Capture,一段講完)

從 OLTP database 把變更(insert/update/delete)以事件流形式抽出(Debezium 讀 binlog → Kafka → lakehouse merge)。關鍵概念:每筆變更有 **op type + 主鍵 + before/after**,下游用 **merge/upsert** 重建表狀態;順序錯亂與重複靠主鍵 + LSN/ts 的「最後寫入勝」處理 — 又回到冪等與 dedup-by-key。

> 面試被問「怎麼把 MySQL 的表同步到 data lake?」— 全量快照 + CDC 增量 + 定期 compaction/merge,講出 delete 怎麼處理(tombstone/merge delete)是加分點。

## 一句總結(可以直接背)

「Batch 與 streaming 共用同一套語意問題 — 重複、遲到、順序、冪等;差別只是你在**檔案粒度**還是**事件粒度**面對它們。」能把 batch 題資料裡的重複列講成 at-least-once 的痕跡、把每日檔的跨日事件講成 late data,就是 senior 與 mid-level 的分界線。
