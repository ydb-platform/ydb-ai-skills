# Embedding YDB in Go applications

## FloatVector parameters

For an application-provided vector, follow the current recommended approach in the [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) (Go tab) to serialize it on the client. Bind the result as YQL `String` and use it directly in `Knn` distance functions or store it in a `String` column. Avoid a `List<Float>` parameter followed by `Knn::ToBinaryStringFloat` in YQL; that conversion is useful for vectors constructed in YQL.

Source: <https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main>.

## Stack

The only YDB Go SDK is **`github.com/ydb-platform/ydb-go-sdk/v3`**. The same package exposes two surfaces:

- a **native** API with the modern Query Service (`db.Query().Do/DoTx(...)`) and the legacy Table Service (`db.Table().Do/DoTx(...)`),
- a **`database/sql`** driver registered as `"ydb"` (blank-import `_ "github.com/ydb-platform/ydb-go-sdk/v3"`) for code that needs the stdlib interface.

Default new code to the native Query Service. The Table Service is in legacy mode and has a 1000-row default result cap (surfaced as an error on `s.Execute` in v3 by default, restored to v2-style silent truncation if `ydb.WithIgnoreTruncated` is set on the driver — see <https://github.com/ydb-platform/ydb-go-sdk/blob/master/MIGRATION_v2_v3.md>). Connection-string format and authentication environment variables: see <https://ydb.tech/docs/en/concepts/connect>. Worked examples for both surfaces: <https://github.com/ydb-platform/ydb-go-sdk/tree/master/examples>. `database/sql` specifics: <https://github.com/ydb-platform/ydb-go-sdk/blob/master/SQL.md>.

## Query execution

Canonical native-API pattern — open the driver once with `ydb.Open(...)`, then run all work inside a `db.Query().Do(...)` closure. The closure is the retry unit: the SDK invokes it again on every retryable error.

```go
db, err := ydb.Open(ctx, "grpc://localhost:2136/local")
if err != nil { return err }
defer db.Close(ctx)

err = db.Query().Do(ctx, func(ctx context.Context, s query.Session) error {
    res, err := s.Query(ctx,
        `SELECT name FROM users WHERE id = $id;`,
        query.WithParameters(ydb.ParamsBuilder().
            Param("$id").Uint64(42).Build()),
    )
    if err != nil { return err }
    defer func() { _ = res.Close(ctx) }()
    // iterate result sets / rows, build the value inside the closure
    return nil
}, query.WithIdempotent())
```

Three load-bearing pieces:

- **`query.WithIdempotent()`** declares the closure safe to replay on *conditionally* retryable failures (connection drop, gRPC reset, session loss). Set on reads and on writes keyed by a client-generated id; do not set on a non-idempotent write such as a counter increment.
- **`query.WithParameters(ydb.ParamsBuilder()...)`** binds values rather than concatenating them. Closes SQL injection and per-distinct-text plan-cache churn.
- **All data processing happens inside the closure.** Assign to outer variables only on the success path — the line that returns `nil`. Anything assigned earlier survives across retry attempts and produces wrong values.

Source: <https://github.com/ydb-platform/ydb-go-sdk> README "Example Usage".

`ParamsBuilder` is a value builder: each `.Param(...).Uint64(...)`, `.Timestamp(...)`, or other typed setter returns the updated builder. When adding parameters conditionally, assign that result back to the variable; discarding it leaves the new parameter out of `Build()`. Chaining typed setters also preserves the result. Source: [builder](https://github.com/ydb-platform/ydb-go-sdk/blob/master/internal/params/builder.go) and [typed setters](https://github.com/ydb-platform/ydb-go-sdk/blob/master/internal/params/parameters.go).

## Request deadline and cancellation

Derive the YDB operation context from the caller's context. `context.WithTimeout` keeps an earlier parent deadline, so the same budget covers pool/session acquisition, retry backoff, every attempt, the RPC, and stream draining. Inside `Do` / `DoTx`, use the context passed to the callback; it is the SDK's per-attempt context.

```go
func loadUser(requestCtx context.Context, db *ydb.Driver, id uint64) error {
    opCtx, cancel := context.WithTimeout(requestCtx, maxYDBDuration)
    defer cancel()

    return db.Query().Do(opCtx, func(ctx context.Context, s query.Session) error {
        res, err := s.Query(ctx,
            `SELECT name FROM users WHERE id = $id`,
            query.WithParameters(ydb.ParamsBuilder().
                Param("$id").Uint64(id).Build()),
        )
        if err != nil { return err }
        return res.Close(ctx)
    }, query.WithIdempotent())
}
```

Do not replace `requestCtx` with `context.Background()` / `context.TODO()`, and do not create a new full timeout inside the retry callback: both detach or reset the caller's budget. Context cancellation stops the client work best-effort; it does not prove that an already-sent write was rolled back, so the idempotency contract still applies.

Source: <https://github.com/ydb-platform/ydb-go-sdk/blob/master/query/example_test.go> — the `Do` callback uses its context for `s.Query`; <https://pkg.go.dev/context#WithTimeout> — derived contexts inherit parent cancellation and deadlines.

## Query stats (`WithStatsMode`)

`query.WithStatsMode(mode, callback)` attaches a per-query stats handler. The handler may run **more than once** as the SDK receives stream parts. Stats-bearing parts are not guaranteed to arrive first; row data can arrive earlier, and the final stats snapshot may appear only after additional `Recv` calls while draining.

Canonical shape: `Query` → drain the `query.Result` (`Close` or full iteration) → read `query.Stats`.

- Prefer **`res.Close(ctx)` before reading stats** when there is little or no row iteration.
- When iterating rows, finish iteration first and then read stats.

```go
var stats query.Stats

res, err := s.Query(ctx, q,
    query.WithStatsMode(query.StatsModeBasic, func(s query.Stats) { stats = s }),
)
if err != nil { return err }
if err := res.Close(ctx); err != nil { return err }
// use stats after drain
```

Source: `internal/query/result.go` — stats callback in `nextPart`, drain in `Close`.

## Transactions

YDB has two transaction styles, and `ydb-go-sdk/v3` supports both:

- **Non-interactive** (default for new code) — the SDK manages the transaction inside `db.Query().DoTx(ctx, func(ctx, tx query.TxActor) error { ... })`. Per the upstream `query/client.go` godoc: *"If op TxOperation returns nil — transaction will be committed"*. Open the driver with `ydb.WithLazyTx(true)` so the begin is deferred onto the first query, and pass `query.WithCommit()` to the last write so the commit rides on its RPC — zero standalone begin/commit round-trips.
- **Interactive** — the developer writes the begin and commit explicitly. Same fusing, two shapes depending on statement count:
  - *Multi-statement*: first call is `tx, result, err := s.Execute(ctx, table.TxControl(table.BeginTx(table.WithSerializableReadWrite())), firstQuery, params)` — `txControl` is `s.Execute`'s positional second argument and the begin rides on this RPC. Subsequent calls use the returned `tx` handle. The last call uses `tx.Execute(ctx, lastQuery, params, options.WithCommit())` (where `options` is `github.com/ydb-platform/ydb-go-sdk/v3/table/options`) — the commit rides on the final write's RPC. Canonical form: `table/example_test.go` `Example_lazyTransaction` in upstream.
  - *Single-statement*: combine begin and commit on the only `s.Execute`: `s.Execute(ctx, table.TxControl(table.BeginTx(table.WithSerializableReadWrite()), table.CommitTx()), sql, params)` — one RPC carries begin + write + commit. Canonical form: `examples/ttl/series.go`.
  - *Query Service* equivalent: `s.Query(ctx, sql, query.WithTxControl(...), query.WithCommit())` — txControl and commit are `ExecuteOption`s on `s.Query(...)`.

Worked non-interactive example: <https://github.com/ydb-platform/ydb-go-sdk/blob/master/examples/transaction/query/main.go>.

For the transaction-mode list (`SerializableRW`, `SnapshotRO`, `StaleRO`, `OnlineRO`) and the consequence for application-level optimistic locking, see `references/working-with-data.md`.

## Retries

`Do` / `DoTx` retry the closure internally; there is no need for an outer `for` loop or a `time.Sleep`-based retrier in caller code. The SDK classifies the error through `retry/mode.go` `MustRetry(isOperationIdempotent bool)`:

- **Non-retryable** — propagated to the caller (`PRECONDITION_FAILED`, schema mismatch, bad parameters).
- **Unconditionally retryable** — always retried regardless of idempotency (`ABORTED`, `OVERLOADED`).
- **Conditionally retryable** — retried only when `WithIdempotent` was passed (transport drops, session loss, timeouts).

Backoff and jitter are built in; configure via retry options on the `Do` / `DoTx` call, not by wrapping.

Source: <https://github.com/ydb-platform/ydb-go-sdk/blob/master/retry/mode.go>.

## Long scans / resumable reads

One `s.Query(ctx, "SELECT ... FROM big_table WHERE <wide predicate>")` inside a single `Do` closure is one retry unit — a transient failure mid-stream replays the whole read. Cut the read into keyset-paginated batches: caller-side cursor over the primary key, each iteration is its own `Do`. See `references/working-with-data.md` → "Reading many rows" for the YDB-level recipe and the tuple-order / NULL / `OFFSET` caveats.

For a non-null composite primary key `(created_at, id)`, carry **both** fields in the cursor and compare them in that order. A timestamp alone cannot distinguish rows sharing the same timestamp. The first page has no cursor predicate; do not substitute a fabricated minimum key. Separate pages are separate transactions, not one shared snapshot.

```go
type rowKey struct {
    CreatedAt time.Time
    ID        uint64
}

var after *rowKey
const batch = uint64(1000)
for {
    var page []rowKey
    err := db.Query().Do(ctx, func(ctx context.Context, s query.Session) error {
        params := ydb.ParamsBuilder().Param("$batch").Uint64(batch)
        q := "SELECT created_at, id FROM events"
        if after != nil {
            params = params.Param("$created_at").Timestamp(after.CreatedAt)
            params = params.Param("$id").Uint64(after.ID)
            q += " WHERE (created_at, id) > ($created_at, $id)"
        }
        q += " ORDER BY created_at, id LIMIT $batch"
        res, err := s.Query(ctx, q, query.WithParameters(params.Build()))
        if err != nil { return err }
        defer func() { _ = res.Close(ctx) }()
        var local []rowKey
        for rs, err := range res.ResultSets(ctx) {
            if err != nil { return err }
            for row, err := range rs.Rows(ctx) {
                if err != nil { return err }
                var key rowKey
                if err := row.Scan(&key.CreatedAt, &key.ID); err != nil { return err }
                local = append(local, key)
            }
        }
        if err := res.Close(ctx); err != nil { return err }
        page = local // publish only after this attempt has drained successfully
        return nil
    }, query.WithIdempotent())
    if err != nil { return err }
    if len(page) == 0 { break }
    // process page
    last := page[len(page)-1]
    after = &last
    if uint64(len(page)) < batch { break }
}
```

`local` is rebuilt inside each retry attempt. Publish it to `page` only after the stream is drained without error. Keep the complete cursor in caller memory and persist it externally if reads must resume after process restarts.

Sources: [SDK pagination example](https://github.com/ydb-platform/ydb-go-sdk/blob/master/examples/pagination/cities.go), [YDB pagination](https://ydb.tech/docs/en/dev/paging), and the typed parameter builder linked above.

## Bulk upsert

Use `db.Table().BulkUpsert(ctx, tablePath, rows)` for non-transactional ingest:

```go
err := db.Table().BulkUpsert(ctx,
    path.Join(db.Name(), "events"),
    table.BulkUpsertDataRows(types.ListValue(values...)),
)
```

For when the bulk API is the right call versus `AS_TABLE` inside a transaction — and when it is forbidden (synchronous secondary indexes, attached changefeeds) — see `references/working-with-data.md`.

Source: <https://github.com/ydb-platform/ydb-go-sdk/blob/master/examples/opensource_night2024/main.go>.

## Connection

See <https://ydb.tech/docs/en/concepts/connect>.
