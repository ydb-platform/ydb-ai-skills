# Go SDK (`ydb-go-sdk/v3`) — anti-patterns

Audit rules for application code talking to YDB through the Go SDK. Each rule is self-contained: the surface skill must produce correct audit output on its own.

### RULE-GO-01: Reading "all matching rows" through Table Service without pagination

**Severity**: Critical

**What to look for**: `s.Execute(ctx, ..., "SELECT ...")` inside `db.Table().Do(...)` where the read is **intended to exhaust a result set** — an unbounded `SELECT` (no `WHERE` key match), a `SELECT ... WHERE billed = false` / `WHERE created_at > $cutoff` over an unbounded range, anything followed by a code-side `for ... res.NextRow()` that processes the full match — and there is no outer keyset-pagination loop wrapping the `Do` call. A bounded point read (`WHERE id = $id LIMIT 1`) or a small explicit `LIMIT N` where the caller cannot accept more than N rows by construction is not the target. `s.StreamExecuteScanQuery(...)` is *not* a target either — per ydb.tech, scan queries return a gRPC stream with no row-count cap and are the legitimate Table Service path for exhausting large result sets. Also flag any `ydb.WithIgnoreTruncated` on the driver — that option silences the v3 `s.Execute` truncation error and restores v2-style silent truncation, which is what the rule exists to prevent.

**Problem**: Table Service `s.Execute` caps the result at 1000 rows by default; in v3 the cap surfaces as a non-retryable error. The architectural problem is that code written assuming "one `s.Execute` returns everything matching" is wrong by construction: it works in dev with small data, errors out in production once the match crosses the cap, and the common reflex — pass `ydb.WithIgnoreTruncated` to "fix" the error — restores v2-style silent truncation where the call returns `err == nil` with the first 1000 rows of the match and everything beyond the cap dropped on the floor; downstream code under-bills / under-processes without any signal. The cap is a design constraint, not a knob.

**Fix** — pick one of two structural paths; both are valid:

- **Switch to Query Service streaming**: rewrite the read through `db.Query().Do(ctx, func(ctx, s query.Session) error { res, err := s.Query(ctx, sql, query.WithParameters(...)); ... })`. The Query Service streams the result set without the 1000-row cap, so a code-side `for` over `res.ResultSets(...) / .Rows(...)` exhausts the full match in one call.
- **Keyset-paginate through whichever surface you're already on**: wrap the call in an outer `for` loop with a cursor predicate and `ORDER BY` over the table's primary key, terminate when a page returns zero rows.

`ydb.WithIgnoreTruncated` is not a fix — it silences the signal without addressing the structural problem.

**Source**: `ydb-platform/ydb-go-sdk/MIGRATION_v2_v3.md` — section "About truncated result" documents the 1000-row default and the v3 non-retryable-error behavior. <https://github.com/ydb-platform/ydb-go-sdk/blob/master/MIGRATION_v2_v3.md>.

### RULE-GO-02: External state mutation from inside the `Do`/`DoTx` retry closure

**Severity**: High

**What to look for**: mutations of state outside the `db.Query().Do(...)` / `db.Table().Do(...)` / `DoTx(...)` lambda *while the closure is still running* — `append(outerSlice, row)` mid-iteration, `outerMap[k] = v` after each row, `outerResult, err = s.Execute(...)` capturing a per-attempt handle, an external side effect like a charge / RPC / log emission called from inside the closure body. The single allowed pattern is the final `outerVar = local` assignment on the success path, immediately before the closure returns `nil` — that one is what the Fix prescribes and must not be flagged.

**Problem**: the `Do`/`DoTx` closure is the unit of work — SDK invokes it again on every retryable error (transaction conflict, network transient, session loss). All data processing must happen *inside* the closure. Mutations to external state survive across attempts and produce wrong values: `append` to an outer slice duplicates on retry, an outer `Result` reference may end up holding a stream from a failed attempt, an outer map accumulates entries from partial reads. The closure crosses only one thing back: the success/failure decision. A value the caller needs is built atomically inside on the successful attempt and assigned to the outer variable only at the end, after the closure body has reached that line cleanly.

**Fix**: build the result inside the closure as a per-attempt local; assign to the outer variable only on the path that returns `nil`. The closure owns all data processing; only the success decision crosses the boundary.

**Source**: `ydb-platform/ydb-go-sdk` — `Do`/`DoTx` retry contract in <https://github.com/ydb-platform/ydb-go-sdk/blob/master/query/client.go> (godocs on `Do` / `DoTx`) and the retry loop in <https://github.com/ydb-platform/ydb-go-sdk/blob/master/retry/retry.go>.

### RULE-GO-03: Missing `WithIdempotent` on `Do`/`DoTx`

**Severity**: High

**What to look for**: a mismatch between the closure's idempotency and the option in either direction.

- **Missing flag on safe-to-replay work**: `db.Query().Do(...)` / `db.Table().Do(...)` / `DoTx(...)` whose closure body is replay-safe (a read; an `UPSERT` keyed on a value the caller already has — externally-generated id, idempotency key; a write guarded by such a key) but no `query.WithIdempotent()` / `table.WithIdempotent()` in the options list. Fix: add the option.
- **Flag set on non-idempotent work**: `Do` / `DoTx` carrying `WithIdempotent()` while the closure performs a non-idempotent write (counter increment, money transfer, raw `INSERT` of a generated row). Fix: remove the option *and* rework the write to be idempotent (introduce a client-generated request id, an idempotency-key guard) before opting back in — never the option alone, because the underlying write would still be unsafe on replay.

**Problem**: the SDK classifies failures into three buckets (`retry/mode.go:MustRetry`): non-retryable (never retried), unconditionally-retryable (always retried), and **conditionally-retryable** (retried only when the developer has declared the work idempotent). The third bucket holds transport-class failures — connection drop, gRPC reset, session loss after the request was sent — where the server may have already committed the write before the failure reached the client. Replay is safe for an idempotent write (`UPSERT` keyed on an externally-generated id, idempotency-key-guarded insert) and unsafe for a non-idempotent one (counter increment, decrement, transfer, raw `INSERT` of a generated row). The SDK cannot tell which from the API surface — only the developer knows. `WithIdempotent()` is the contract: *"I declare this closure safe to replay on conditional failures."* Setting it on a non-idempotent write causes double effect; omitting it on an idempotent write makes the program propagate transport errors it could have absorbed.

**Fix**: add `query.WithIdempotent()` (or `table.WithIdempotent()`) to the `Do`/`DoTx` call when the inner work is idempotent — `UPSERT` keyed on a client-generated id, idempotency-key-guarded writes, reads. For a non-idempotent write (counter increment, transfer), the flag must *not* be set; the fix there is to make the write idempotent first — usually with a client-generated request id — and only then opt in.

**Source**: `ydb-platform/ydb-go-sdk/retry/mode.go` — `MustRetry(isOperationIdempotent bool)` returns `isOperationIdempotent` for `TypeConditionallyRetryable` errors and `true` otherwise. <https://github.com/ydb-platform/ydb-go-sdk/blob/master/retry/mode.go>.

### RULE-GO-04: `for` loop wrapping `db.Query().Do(...)` / `db.Table().Do(...)`

**Severity**: High

**What to look for**: an outer `for` / `for { ... }` / `for i := 0; i < N; i++` block whose body calls `db.Query().Do(ctx, ...)` or `db.Table().Do(ctx, ...)` and decides whether to repeat based on the returned error.

**Problem**: `Do`/`DoTx` already retries the closure internally with classified backoff (`retry/retry.go`, `retry/mode.go`). An outer loop multiplies the backoff schedule, re-runs work on non-retryable errors the SDK has correctly decided not to retry, and silently inflates the retry budget the caller thinks they configured.

**Fix**: remove the outer loop. If the goal is "retry forever on a specific class", express it through `WithIdempotent` / retry options on the `Do` call, not by wrapping.

**Source**: `ydb-platform/ydb-go-sdk/retry/retry.go` — `Retry` / `Do` / `DoTx` implement the retry loop internally with classified backoff. <https://github.com/ydb-platform/ydb-go-sdk/blob/master/retry/retry.go>.

### RULE-GO-05: Custom retrier with `time.Sleep` wrapping YDB calls

**Severity**: High

**What to look for**: `for` loop with explicit `time.Sleep(...)` between attempts, calling any YDB-facing method inside — session methods (`s.Execute`, `s.Query`, `s.BeginTransaction`), client-level methods (`db.Table().CreateSession`, `db.Table().Do`, `db.Query().Do`, `db.Query().DoTx`), or arbitrary user functions that themselves call into the SDK.

**Problem**: a hand-rolled retrier replays every non-nil error indiscriminately. Non-retryable failures (`PRECONDITION_FAILED`, schema mismatch) burn the retry budget on errors that will never recover, and conditionally-retryable failures (transport drops where the server may have committed) get retried with no idempotency gate, which can double-apply a non-idempotent write. The SDK retrier classifies via `retry/mode.go` `MustRetry(isOperationIdempotent bool)` and only retries the conditional bucket when `WithIdempotent` is set; backoff with jitter and session-pool integration come from the same path.

**Fix**: delete the custom loop and use the SDK retrier (`db.Query().Do`, `db.Table().Do`, `retry.Retry` from `retry/`); express tuning (max attempts, backoff envelope) through its options rather than in caller-side `for`/`Sleep` code.

**Source**: `ydb-platform/ydb-go-sdk` — retry classification in <https://github.com/ydb-platform/ydb-go-sdk/blob/master/retry/mode.go>; retry loop and backoff in <https://github.com/ydb-platform/ydb-go-sdk/blob/master/retry/retry.go> and <https://github.com/ydb-platform/ydb-go-sdk/blob/master/retry/backoff.go>.

### RULE-GO-06: Nested `Do` / `DoTx` call

**Severity**: Critical

**What to look for**: a `db.Query().Do(...)` or `db.Table().Do(...)` (or `DoTx`) appearing inside another `Do`/`DoTx` lambda. Any "retrier inside a retrier" shape.

**Problem**: the inner `Do` checks out an independent session from the pool — under load this races for pool slots and can starve the caller, and under retry it multiplies attempts combinatorially with the outer scope. The pool and retry budget were sized for one scope, not two nested ones.

**Fix**: pass the active handle through the call chain instead of opening a new retry scope. Helpers called from inside a `Do(ctx, ...)` lambda must accept `query.Session` / `table.Session` and use it directly; helpers called from inside a `DoTx(ctx, ...)` lambda must accept the transaction actor (`query.TxActor` for Query Service, the `table.Transaction` handle for Table Service) so their work runs in the same transaction — passing a fresh `Session` from inside a `DoTx` would step outside the transaction the closure is trying to preserve.

**Source**: `ydb-platform/ydb-go-sdk/retry/retry.go` — `Do` pool checkout semantics. <https://github.com/ydb-platform/ydb-go-sdk/blob/master/retry/retry.go>.

### RULE-GO-07: Non-parametrized YQL — `fmt.Sprintf` / string concat into query text

**Severity**: Critical

**What to look for**: `fmt.Sprintf` building a query string, `"SELECT ... " + variable` concatenation, `text/template` rendering of a query body. Anything where caller values appear inside the YQL literal rather than as bound parameters.

**Problem**: two failure modes the SDK's parameter API closes at once. SQL injection — caller values become YQL syntax when concatenated. Per-call query-plan miss — the server's plan cache is keyed on query text, so every distinct rendered string forces a fresh plan compilation.

**Fix**: bind values through `ydb.ParamsBuilder().Param("$name").<Type>(value).Build()` and pass them via `query.WithParameters(...)` (or `table.NewQueryParameters(...)` for Table Service).

**Source**: `ydb-platform/ydb-go-sdk` — `ParamsBuilder` in <https://github.com/ydb-platform/ydb-go-sdk/blob/master/params_builder.go>; `query.WithParameters` in <https://github.com/ydb-platform/ydb-go-sdk/blob/master/query/execute_options.go>. YQL parameters reference: <https://ydb.tech/docs/en/yql/reference/syntax/declare>.

### RULE-GO-08: `PreferLocalDC` / `PreferNearestDC` balancer in production

**Severity**: High

**What to look for**: `ydb.WithBalancer(balancers.PreferLocalDC(...))` or `ydb.WithBalancer(balancers.PreferNearestDC(...))` (the rename — `PreferLocalDC` is marked `// Deprecated`, but `PreferNearestDC` has the same effect) in driver construction.

**Problem**: prefer-DC balancers concentrate all client traffic on nodes in the chosen "local" / "nearest" datacenter, turning the cluster's other DCs into idle hot-standbys and the chosen DC into a saturation bottleneck. Cross-DC latency savings on individual requests are dwarfed by the throughput cliff once the chosen DC's nodes saturate.

**Fix**: drop the `WithBalancer(...)` option (or pass `balancers.RandomChoice()` explicitly — that's what `balancers.Default()` returns). `RandomChoice` picks an endpoint at random per request and spreads load evenly across every available node in the cluster.

**Source**: `ydb-platform/ydb-go-sdk/balancers/balancers.go` — `PreferLocalDC` is marked `// Deprecated: use PreferNearestDC instead`; both have the same balancing semantics. <https://github.com/ydb-platform/ydb-go-sdk/blob/master/balancers/balancers.go>.

### RULE-GO-09: Transaction begin as a separate RPC

**Severity**: Medium

YDB supports two transaction styles. *Interactive* — the developer writes `begin` and `commit` calls. *Non-interactive* — the SDK manages the transaction inside `DoTx`; the developer influences it via options.

**What to look for**:

- *Interactive*: `s.BeginTransaction(ctx, ...)` or `s.Begin(ctx, ...)` returning a `tx` handle, followed by `tx.Exec(...)` / `tx.Query(...)` (Query Service) or `tx.Execute(...)` (Table Service).
- *Non-interactive*: `db.Query().DoTx(...)` (or `db.Table().DoTx(...)`) on a driver opened without `ydb.WithLazyTx(true)`.

**Problem**: the explicit begin is a standalone RPC that does no work — it just opens the transaction. Fusing it into the first query's RPC removes one round-trip per transaction. On a high-frequency OLTP path that's a measurable share of total latency and load.

**Fix**:

- *Interactive*: drop the standalone `s.BeginTransaction(...)` and let the begin ride on the first query.
  - Table Service: the first call is `tx, result, err := s.Execute(ctx, table.TxControl(table.BeginTx(table.WithSerializableReadWrite())), firstQuery, params)` — `txControl` is the positional second argument; the returned `tx` is then used for subsequent `tx.Execute(...)` calls within the transaction (single-shot autocommit also exists: add `table.CommitTx()` to the same `TxControl` if the transaction has just one statement).
  - Query Service: `s.Query(ctx, firstQuery, query.WithTxControl(tx.NewControl(tx.BeginTx(tx.WithSerializableReadWrite()))), query.WithParameters(...))`.
- *Non-interactive*: open the driver with `ydb.WithLazyTx(true)` (or pass `query.WithLazyTx(true)` as a per-call `DoTxOption`). `DoTx` then defers begin to the first query inside the closure.

**Source**: `Session.Execute(ctx, *TransactionControl, sql, *params.Params, ...)` returns `(Transaction, Result, error)` — <https://github.com/ydb-platform/ydb-go-sdk/blob/master/table/table.go>. Canonical multi-statement form: <https://github.com/ydb-platform/ydb-go-sdk/blob/master/table/example_test.go> (`Example_lazyTransaction`). `ydb.WithLazyTx` driver option: <https://github.com/ydb-platform/ydb-go-sdk/blob/master/options.go>; per-call `query.WithLazyTx`: <https://github.com/ydb-platform/ydb-go-sdk/blob/master/query/client.go>.

### RULE-GO-10: Transaction commit as a separate RPC

**Severity**: Medium

Same interactive / non-interactive split as RULE-GO-09, applied to the commit side.

**What to look for**:

- *Interactive*: `tx.Commit(ctx)` / `tx.CommitTx(ctx)` called as a separate statement after the last `tx.Exec(...)` / `tx.Query(...)` (Query Service) or `tx.Execute(...)` (Table Service).
- *Non-interactive*: `db.Query().DoTx(ctx, func(...) { ...; return nil })` where the last write inside the closure does not carry `query.WithCommit()`. `DoTx` will commit on return-nil, but as its own RPC.
- *Doubly wrong*: an explicit `tx.CommitTx(ctx)` call **inside** a `DoTx` closure. `DoTx` already commits on return-nil per `query/client.go:DoTx` godoc; the explicit call is both redundant and a separate RPC.

**Problem**: an explicit commit is a standalone RPC that does no work — it just terminates the transaction. Fusing it into the last query's RPC removes one round-trip per transaction. The doubly-wrong case adds redundant work on top: `DoTx` would have committed on return-nil anyway, so the explicit call is both useless and an extra round-trip.

**Fix**: fuse the commit into the last query's RPC.

- Query Service: pass `query.WithCommit()` as an `ExecuteOption` to the last `tx.Exec(...)` / `tx.Query(...)` of the closure.
- Table Service (multi-statement interactive transaction): pass `options.WithCommit()` (from `github.com/ydb-platform/ydb-go-sdk/v3/table/options`) as an `ExecuteDataQueryOption` to the last `tx.Execute(ctx, sql, params, options.WithCommit())` — the commit flag rides on that RPC and the transaction terminates without a separate `tx.CommitTx`. For a single-statement Table Service transaction, fold both begin and commit into one `s.Execute(ctx, table.TxControl(table.BeginTx(...), table.CommitTx()), sql, params)`.

For the doubly-wrong case (explicit `tx.CommitTx` inside a `DoTx` closure), also delete the call — `DoTx` handles commit on return-nil.

**Source**: `query.WithCommit() ExecuteOption` — <https://github.com/ydb-platform/ydb-go-sdk/blob/master/query/execute_options.go>; `DoTx` godoc *"If op TxOperation returns nil - transaction will be committed"* — <https://github.com/ydb-platform/ydb-go-sdk/blob/master/query/client.go>. Table Service `options.WithCommit() ExecuteDataQueryOption` — <https://github.com/ydb-platform/ydb-go-sdk/blob/master/table/options/options.go>; canonical multi-statement usage in <https://github.com/ydb-platform/ydb-go-sdk/blob/master/table/example_test.go> (`Example_lazyTransaction`) and <https://github.com/ydb-platform/ydb-go-sdk/blob/master/tests/integration/table_tx_lazy_test.go>.

### RULE-GO-11: Assuming `query.Stats` is final before stream drain

**Severity**: High

**What to look for**: `query.WithStatsMode(...)` (any mode: `StatsModeBasic`, `StatsModeFull`, etc.) on a streaming `Query` / `Exec` / `transaction.Query` call, where the captured `query.Stats` value is consumed as if final (returned, logged, converted, or used in control flow) **before** the corresponding `query.Result` is fully drained.

Concrete signals:

- `s.Query(..., query.WithStatsMode(..., func(s query.Stats) { stats = s }))` followed on the next lines by `return convert(stats)`, `logStats(stats)`, or any decision based on `stats`, with only `defer res.Close(ctx)` later (or no `Close` at all). `defer` runs at function return; it does **not** drain the stream before the lines between `Query` and `return`.
- Helpers that return a stats-derived value right after `Query` while the result stream is still open.
- Table Service analogue: reading stats from `result.Result` before `res.Close()` / before full stream drain.

**Problem**: `ExecuteQuery` is a gRPC stream. `WithStatsMode` registers a callback that the SDK may invoke on **each** stream part as parts arrive. Query rows may appear in early parts while stats-bearing parts arrive later. Control returns to caller code before the stream is exhausted, so the captured `query.Stats` snapshot at that moment may be `nil` or partial.

Reading stats immediately after `Query` returns can therefore produce **nil or incomplete** stats even when the server operation succeeded. This causes flaky observability, unstable diagnostics, and incorrect logic when downstream code assumes stats are final.

This is independent of how `Close` is scheduled (`defer` vs direct call): the invariant is that **no consumer should trust stats until stream drain completes**.

**Fix**: drain the result synchronously, then read stats.

```go
var stats query.Stats

res, err := s.Query(ctx, sql,
    query.WithStatsMode(query.StatsModeBasic, func(x query.Stats) {
        stats = x
    }),
)
if err != nil {
    return err
}
if err := res.Close(ctx); err != nil {
    return err
}
// Safe to use stats here.
```

For reusable helpers, keep a strict shape: run `Query` → drain (`Close` or full iteration) → return/use captured stats. Do not consume stats in the code path between `Query` and drain completion.

If the call also iterates rows, draining by iteration to EOF is valid; stats may be consumed only after that iteration finishes. Calling `Close` after iteration remains a safe finalizer.

**Source**: `ydb-go-sdk/v3` query result stream — stats callback from `internal/query/result.go` `nextPart` when `part.GetExecStats() != nil`; drain loop in `(*streamResult).Close`. Query stats API: <https://github.com/ydb-platform/ydb-go-sdk/blob/master/query/execute_options.go> (`WithStatsMode`).

### RULE-GO-12: YDB work detached from the caller deadline or cancellation

**Severity**: High

**What to look for**: a request handler receives `ctx` / `requestCtx` but passes `context.Background()` or `context.TODO()` to `db.Query().Do`, `db.Table().Do`, `s.Query`, `s.Execute`, or result `Close`; a fresh `context.WithTimeout(context.Background(), ...)`; a new full timeout created inside a `Do` / `DoTx` callback; or SDK calls inside the callback that use an outer context instead of the callback's context.

**Problem**: detached work survives caller disconnect and deadline expiry, continuing to wait for a session, back off, retry, execute, or drain a stream while the caller has gone away. Resetting the full timeout inside every retry attempt multiplies the intended latency budget. Cancellation is best-effort and does not prove that an already-sent write was rolled back, so losing the caller context also makes uncertain results harder to handle safely.

**Fix**: derive one bounded context from the caller (`opCtx, cancel := context.WithTimeout(requestCtx, maxYDBDuration)`), `defer cancel()`, and pass `opCtx` to `Do` / `DoTx`. Inside its callback, use the callback-provided context for every session, transaction, and result-stream call. Keep `WithIdempotent` aligned with replay safety because cancellation does not change whether a write can be retried.

**Source**: <https://github.com/ydb-platform/ydb-go-sdk/blob/master/query/example_test.go> — `Do` supplies the context used by `s.Query`; <https://pkg.go.dev/context#WithTimeout> — derived contexts inherit parent cancellation and deadlines.

### RULE-GO-13: Client FloatVector passed as `List<Float>` for server conversion

**Severity**: Medium

**What to look for**: a Go slice holding an application-provided embedding is bound as `List<Float>`, while the YQL query calls `Knn::ToBinaryStringFloat($embedding)` or converts an `embedding` member of `AS_TABLE($items)` before a vector search or write.

**Problem**: the SDK sends individual list elements and YDB converts them to the binary FloatVector format on every call, although the client can send that format directly as one `String` value.

**Fix**: follow the current recommended approach in the [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) (Go tab) to serialize the vector on the client. Bind it as YQL `String` and use it directly in the `Knn` distance function or stored column. Keep `Knn::ToBinaryStringFloat` when the vector is constructed in YQL; other vector types require their own formats.

**Source**: <https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main>.
