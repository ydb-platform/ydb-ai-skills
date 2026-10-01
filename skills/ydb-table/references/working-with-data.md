# Working with data in YDB tables

How application code reads and writes YDB tables: which transaction mode applies, how to write many rows at once, and which API to pick when. Pair it with the `ydb-core` skill's schema fundamentals when that companion skill is installed.

## Terminology

YDB uses three terms that get conflated; pinning them down up front:

| Term                  | What it is                                                                                                                            | Transactional? |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | -------------- |
| **Transaction mode**  | The isolation contract for one logical unit of work: `SerializableRW` (default), `SnapshotRO`, `StaleRO`, `OnlineRO`.                 | by definition  |
| **Batch (writing)**   | Many rows packed into one YQL statement via `AS_TABLE($list)` + `UPSERT`. Runs inside whatever transaction mode the session opened.   | yes            |
| **Bulk upsert**       | A separate SDK / CLI / API call (`BulkUpsert`). Not YQL. Server splits the write into independent per-partition transactions.         | **no**         |

The choice between batch and bulk is a schema-shape and transactionality decision before it is a throughput decision; see [When to write which way](#when-to-write-which-way) below.

## Transaction modes

The Query Service supports four modes (<https://ydb.tech/docs/en/concepts/transactions>):

- **`SerializableRW`** — the default. Read-write, server-side serializable. YDB uses optimistic concurrency control: conflicting transactions are detected by the server at commit time and surface as a retryable `ABORTED` status with the message `Transaction locks invalidated`.
- **`SnapshotRO`** — read-only, sees a consistent snapshot. Does not coordinate with concurrent writers.
- **`StaleRO`** — read-only, reads from any replica; may return stale data.
- **`OnlineRO`** — read-only, reads from the leader.

### Implication: application-level optimistic locking is redundant

The Postgres / Read-Committed pattern of carrying a `version` column and emitting `UPDATE … WHERE … AND version = ?` to catch lost updates is unnecessary under `SerializableRW`: the server already detects the conflict and surfaces it as a retryable failure. The extra predicate adds work on every UPDATE and provides no additional safety — the correct response to a conflict is to retry the transaction, which the SDK retry helpers already do for `ABORTED`.

### Read-only loads

For purely read workloads, `SnapshotRO` is the right default — it reduces coordination cost with writers while still seeing a consistent view. Use `StaleRO` only when bounded staleness is acceptable in exchange for lower latency, and `OnlineRO` when you need to read from the leader (e.g., to observe the freshest committed state without participating in a read-write transaction).

Note: reads against column-oriented tables are restricted to `SerializableRW` and `SnapshotRO`; `StaleRO` and `OnlineRO` are not supported for column-oriented reads.

## Writing many rows: batch via `AS_TABLE`

```yql
DECLARE $items AS List<Struct<id: Uint64, value: Utf8>>;

UPSERT INTO t
SELECT id, value FROM AS_TABLE($items);
```

One query plan, one transaction, one round trip. Because the query is parameterized, the server's plan cache reuses the same plan across calls. The whole batch participates in the surrounding transaction — commits or rolls back atomically with the rest of the unit of work.

Sources: <https://ydb.tech/docs/en/yql/reference/syntax/select/from_as_table>, <https://ydb.tech/docs/en/yql/reference/syntax/upsert_into>.

## Writing many rows: bulk upsert (no transactions)

The SDK `BulkUpsert` API is faster than YQL `UPSERT` because it bypasses the transactional write path. That bypass costs three things — **each can disqualify the API outright, regardless of throughput**:

- **No transactions.** The upstream docs state plainly: "Since no transactionality is used, this approach has a much lower overhead than YQL queries." Each partition write is independent; there is no rollback, and partial visibility across partitions is the normal state during the call.
- **Not allowed on tables with synchronous secondary indexes.** Upstream warning: "The `BulkUpsert` method isn't supported for tables with synchronous secondary indexes." Asynchronous indexes are supported (added in a later server release; see the changelog).
- **Not allowed on tables with attached changefeeds.** Writes through bulk-upsert do not flow through the CDC path; on a table with a changefeed, the call is rejected. Verify against the current target table before recommending bulk-upsert in code that may run on CDC-enabled schemas.

If any of the three applies, fall back to `AS_TABLE`.

Sources: <https://ydb.tech/docs/en/dev/batch-upload>, <https://ydb.tech/docs/en/recipes/ydb-sdk/bulk-upsert>.

## When to write which way

`AS_TABLE` (batch in a transaction) — when the batch must commit or roll back atomically with the rest of the work, when the rows are read back in the same transaction, or when the target table carries synchronous secondary indexes or a changefeed. This is the default unless throughput pressure forces the other path.

`BulkUpsert` (non-transactional API) — for ingest or migrations: large initial loads, periodic refreshes, replays. Throughput is the constraint, transactionality is not required, and the target schema has no synchronous secondary index or changefeed attached.

## Reading many rows: long scans and resumable reads

A `SELECT` that returns "all matching rows" is one streaming RPC and one retry unit. A transient failure mid-stream restarts the call from the top — every already-streamed row is re-read. The cost of a partial failure scales with the size of the match, not the size of the failure.

The recipe is **keyset pagination by primary key**: an outer caller-side loop, each iteration reading one bounded batch. The query shape uses tuple comparison against the cursor:

```yql
SELECT ...
FROM t
WHERE (pk1, pk2, ...) > ($cur1, $cur2, ...)
ORDER BY pk1, pk2, ...
LIMIT $batch;
```

Field order in the tuple must match the primary key — otherwise the predicate is non-index-friendly and degenerates to a full scan. Terminate the outer loop when a page returns fewer than `$batch` rows.

Each batch is its own retry scope, so a transient failure replays only the current batch. Each batch is a key-ranged read, idempotent under the SDK's standard retry semantics; client-side memory in flight is bounded by `$batch`.

The cursor lives in caller-side memory by default. To resume after a process restart, persist it durably outside the process — for example, in a separate state table, a file, or a queue offset. The SDK has no built-in checkpoint API; checkpoints are application-level.

NULL in primary-key columns is discouraged: tuple comparison with NULL is undefined under the SQL standard, so the cursor predicate misbehaves.

`LIMIT $batch OFFSET $n` for large `$n` is the wrong shape — each page re-scans the rows skipped by `OFFSET`, so cost grows with page index. The recipe is keyset.

Source: <https://ydb.tech/docs/en/dev/paging>.

## Related

- The separate `ydb-core` skill's schema guidance covers how primary-key shape and partitioning determine batch-ingest efficiency and transaction-conflict locality.
