# PySpark Performance — Caching, Partitions, Shuffle, AQE, Skew

## Cache / Persist

```python
df.cache()              # keep in memory for re-use across actions
df.persist(StorageLevel.MEMORY_AND_DISK)
df.unpersist()          # release
```

**When to cache:** the same DataFrame is used in multiple downstream actions. Don't cache reflexively — it costs memory. **Cache vs checkpoint:** cache 保留 lineage(失敗可重算);`df.checkpoint()` 截斷 lineage 落地到 disk — 超長 iterative pipeline(loop 內反覆 transform)才需要,防 plan 爆炸。

## Repartition / Coalesce

```python
df.repartition(8)               # full shuffle, balanced — use before heavy ops
df.repartition("country")       # partition by column (still shuffles)
df.coalesce(1)                  # reduce partitions WITHOUT shuffle — for writing one file
```

`repartition(1)` 與 `coalesce(1)` 不同 — 前者 shuffle(慢但均衡),後者合併現有 partition(快但可能不均)。

## Shuffle 基本盤 + AQE

- **`spark.sql.shuffle.partitions` 預設 200** — 每次 groupBy/join 後的 partition 數。小資料 200 個微 partition 是浪費;大資料 200 個又太少。經典面試題:「為什麼我 5MB 的資料 groupBy 之後有 200 個 task?」
- **AQE (Adaptive Query Execution, Spark 3.2+ 預設開)** 在 runtime 依實際統計重新優化:
  - 自動 coalesce 過小的 shuffle partitions(緩解上面那條)
  - 自動把 sort-merge join 轉 broadcast join(當 runtime 發現一邊其實很小)
  - 自動拆 skewed partition(`skewJoin`)
- **Join 策略光譜:** broadcast hash join(一邊小)→ sort-merge join(兩邊大,預設)→ shuffle hash join / broadcast nested loop(non-equi join 的退路 — range join 常落在這,見 [joins.md](joins.md) SCD2 節)。

## 讀 explain()

```python
df.explain()                    # physical plan
df.explain("formatted")         # cleaner version
```

看什麼:

- **`Exchange`** = shuffle 發生的位置。plan 裡每個 Exchange 都是一次全網路重分佈 — 數 Exchange 個數是估 job 成本的第一步
- **`BroadcastHashJoin ... BuildRight/BuildLeft`** = 哪一邊被 broadcast(BuildRight = 右邊)。Broadcast 大表會 OOM
- **`PushedFilters: [...]`**(parquet scan)= predicate pushdown 有沒有真的推下去
- **`AQEShuffleRead`** = AQE 介入過的痕跡

## Skew

If one key has 90% of the rows, that one partition holds up the whole job. 症狀: Spark UI 裡一個 task 跑分鐘級、其他毫秒級。

Mitigations(由簡到繁):
1. **Broadcast the other side**(skew 只在 shuffle join 有害;broadcast 免 shuffle)
2. **AQE skew join**(Spark 3.2+ 通常自動;確認 `spark.sql.adaptive.skewJoin.enabled`)
3. **Salting** — key 加隨機後綴打散,兩段式聚合:

```python
# Stage 1: 加鹽聚合
salted = df.withColumn("salt", (F.rand() * 8).cast("int"))
partial = salted.groupBy("hot_key", "salt").agg(F.sum("x").alias("s"))
# Stage 2: 去鹽總聚合
final = partial.groupBy("hot_key").agg(F.sum("s"))
```

## 面試常見性能問答

> 「groupBy 跟 Window 都能算聚合,差在哪?」

groupBy **收斂列數**(每 group 一列);Window **保留列數**(每列附上 group 統計)。要「每列跟它的 group 平均比較」→ Window 一步;groupBy 要再 join 回去(多一次 shuffle)。

> 「怎麼減少 shuffle?」

Broadcast 小表、先 filter/aggregate 再 join(縮小 shuffle 的量)、同 key 的多次操作間 repartition 一次重用分佈、讀取端用 partition pruning 少讀。

> 「輸出一堆小檔怎麼辦?」

`df.repartition("partition_key").write.partitionBy("partition_key")` — 見 [io-formats.md](io-formats.md) small files 節。
