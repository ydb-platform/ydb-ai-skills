# Balancing and sessions in Go (`ydb-go-sdk/v3`)

Principles: `references/balancing.md`, `references/session-lifecycle.md`. YQL execution and transaction patterns live in the ydb-table skill.

## Default balancer

```go
db, err := ydb.Open(ctx, os.Getenv("YDB_CONNECTION_STRING"))
```

No `ydb.WithBalancer(...)` ⇒ `balancers.Default()` = `balancers.RandomChoice()`. Source: `ydb-go-sdk/balancers/balancers.go`.

Explicit equivalent (when other options accompany it):

```go
db, err := ydb.Open(ctx, connStr, ydb.WithBalancer(balancers.RandomChoice()))
```

## Prefer-DC variants

`balancers.PreferLocalDC(...)` — marked `// Deprecated: use PreferNearestDC instead`. Both have the same semantics.
`balancers.PreferNearestDC(...)`, `balancers.PreferLocalDCWithFallback(...)` — same family.

## Run every operation through `Do` / `DoTx`

```go
err := db.Query().Do(ctx, func(ctx context.Context, s query.Session) error {
    res, err := s.Query(ctx,
        `SELECT name FROM users WHERE id = $id;`,
        query.WithParameters(ydb.ParamsBuilder().Param("$id").Uint64(42).Build()),
    )
    if err != nil { return err }
    defer func() { _ = res.Close(ctx) }()
    // process inside the closure; assign to outer vars only on the success path
    return nil
}, query.WithIdempotent())
```

`query.WithIdempotent()` declares the closure safe to replay on conditional failures (transport drops, session loss). Omit on non-idempotent writes (counter increment, unkeyed `INSERT`); make those idempotent first (client-generated id, dedup table) before opting in.

Canonical: `ydb-go-sdk/examples/basic/native/query/series.go`.

## Server-side balancer is automatic

SDK attaches `session-balancer` capability header per request (`ydb-go-sdk/internal/meta/headers.go: HintSessionBalancer = "session-balancer"`). No application config — but requires using `Do`/`DoTx`, not a stored `Session`.
