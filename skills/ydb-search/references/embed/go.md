# Search with the Go SDK

Read [the shared SDK workflow](../sdk.md) and copy its SQL assets to `queries/`. Use `ydb-go-sdk/v3` and its Query Service client. Sources: [vector-search recipe](https://ydb.tech/docs/ru/recipes/ydb-sdk/vector-search?version=main&tabs=tool_go#search-by-vector) and [initialization](https://ydb.tech/docs/en/recipes/ydb-sdk/init).

The helper takes the caller's context. Give it a deadline at the request boundary; the SDK retry scope uses the same context and budget.

```go
package search

import (
    "context"
    "encoding/binary"
    "errors"
    "fmt"
    "io"
    "math"
    "os"

    "github.com/ydb-platform/ydb-go-sdk/v3"
    "github.com/ydb-platform/ydb-go-sdk/v3/query"
    "github.com/ydb-platform/ydb-go-sdk/v3/types"
)

const dimension = 3 // Match add-vector-index.sql and the embedding model.

type Document struct {
    ID uint64
    Title, Body string
    Embedding []float32
}
type Hit struct { ID uint64; Title string }

func loadSQL(name string) (string, error) {
    data, err := os.ReadFile("queries/" + name)
    return string(data), err
}

func encodeVector(vector []float32) ([]byte, error) {
    if len(vector) != dimension { return nil, fmt.Errorf("unexpected embedding dimension") }
    data := make([]byte, 4*dimension+1)
    for i, v := range vector {
        binary.LittleEndian.PutUint32(data[4*i:], math.Float32bits(v))
    }
    data[len(data)-1] = 0x01
    return data, nil
}

func Upsert(ctx context.Context, db *ydb.Driver, documents []Document) error {
    if len(documents) == 0 { return nil }
    sql, err := loadSQL("upsert.sql")
    if err != nil { return err }
    rows := make([]types.Value, 0, len(documents))
    for _, doc := range documents {
        encoded, err := encodeVector(doc.Embedding)
        if err != nil { return err }
        rows = append(rows, types.StructValue(
            types.StructFieldValue("id", types.Uint64Value(doc.ID)),
            types.StructFieldValue("title", types.UTF8Value(doc.Title)),
            types.StructFieldValue("body", types.UTF8Value(doc.Body)),
            types.StructFieldValue("embedding", types.BytesValue(encoded)),
        ))
    }
    params := ydb.ParamsBuilder().Param("$items").
        BeginList().AddItems(rows...).EndList().Build()
    return db.Query().Do(ctx, func(ctx context.Context, session query.Session) error {
        return session.Exec(ctx, sql, query.WithParameters(params))
    }, query.WithIdempotent())
}

func Search(ctx context.Context, db *ydb.Driver, mode, text string,
    vector []float32, limit uint64) ([]Hit, error) {
    if limit == 0 { return nil, fmt.Errorf("limit must be positive") }
    switch mode {
    case "exact", "vector", "fulltext", "hybrid":
    default: return nil, fmt.Errorf("unknown search mode")
    }
    sql, err := loadSQL(mode + "-search.sql")
    if err != nil { return nil, err }
    builder := ydb.ParamsBuilder().Param("$limit").Uint64(limit)
    if mode != "fulltext" {
        encoded, err := encodeVector(vector)
        if err != nil { return nil, err }
        builder = builder.Param("$query_vector").Bytes(encoded)
    }
    if mode == "fulltext" || mode == "hybrid" {
        builder = builder.Param("$query_text").Text(text)
    }
    params := builder.Build()
    var hits []Hit
    err = db.Query().Do(ctx, func(ctx context.Context, session query.Session) error {
        result, err := session.Query(ctx, sql, query.WithParameters(params))
        if err != nil { return err }
        defer func() { _ = result.Close(ctx) }()
        var attempt []Hit
        for {
            set, err := result.NextResultSet(ctx)
            if errors.Is(err, io.EOF) { break }
            if err != nil { return err }
            for {
                row, err := set.NextRow(ctx)
                if errors.Is(err, io.EOF) { break }
                if err != nil { return err }
                var hit Hit
                if err := row.ScanNamed(query.Named("id", &hit.ID),
                    query.Named("title", &hit.Title)); err != nil { return err }
                attempt = append(attempt, hit)
            }
        }
        if err := result.Close(ctx); err != nil { return err }
        hits = attempt // Publish only a completely read successful attempt.
        return nil
    }, query.WithIdempotent())
    if err != nil { return nil, err }
    return hits, nil
}
```

`.Bytes(encoded)` and `types.BytesValue(encoded)` bind YQL `String`; `.Text(text)` binds `Utf8`. The list builder's result must be retained: use the returned builder when adding a conditional parameter. Stream errors other than `io.EOF` propagate to the SDK retry scope; partial rows from a failed attempt are discarded.

## Connection and invocation

Open `db` once with `ydb.Open(ctx, connectionString, driverOptions...)`, supplying the application's credential options from the initialization recipe. Close it at shutdown with `db.Close(ctx)`. For a new demo table, execute each DDL file separately with `db.Query().Exec(ctx, sql)` after checking `loadSQL` errors. Run `Upsert` between table creation and index construction.

Example application calls, with every returned error handled by the caller:

```go
documents := []Document{
    {ID: 1, Title: "YDB", Body: "distributed database", Embedding: []float32{1, 0, 0}},
    {ID: 2, Title: "Search", Body: "vector search", Embedding: []float32{0, 1, 0}},
    {ID: 3, Title: "Queries", Body: "database examples", Embedding: []float32{0.8, 0.2, 0}},
}
if err := Upsert(ctx, db, documents); err != nil { return err }
// Build both indexes here, after initial data loading, following sdk.md.
hits, err := Search(ctx, db, "hybrid", "database", []float32{1, 0, 0}, 10)
if err != nil { return err }
// Consume hits in ranked order. Use "vector", "fulltext", or "exact" for other modes.
_ = hits
```

API grounding: `ydb-go-sdk` source under `query/` defines `Do`, `Session.Exec`, `Session.Query`, and `WithIdempotent`; `internal/query/result/` defines `NextResultSet`/`NextRow`; `internal/params/` defines typed parameter builders. These patterns also avoid the vector recipe's simplified loops that stop on any error without distinguishing end-of-stream.
