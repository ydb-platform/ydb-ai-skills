# Search with the Python SDK

Read [the shared SDK workflow](../sdk.md) and copy its SQL assets to `queries/`. Install `ydb`; use the Query Service `QuerySessionPool`. Sources: [recommended SDK recipe](https://ydb.tech/docs/ru/recipes/ydb-sdk/vector-search?tabs=tool_python#search-by-vector) and [driver initialization](https://ydb.tech/docs/en/recipes/ydb-sdk/init).

## Encoding, writes, and reads

```python
from pathlib import Path
import struct
import ydb

DIMENSION = 3  # Match add-vector-index.sql and the embedding model.
MODES = {"exact", "vector", "fulltext", "hybrid"}


def load_sql(name: str) -> str:
    return (Path("queries") / name).read_text(encoding="utf-8")


def encode_vector(vector: list[float]) -> bytes:
    if len(vector) != DIMENSION:
        raise ValueError("Unexpected embedding dimension")
    return struct.pack(f"<{DIMENSION}f", *vector) + b"\x01"


def upsert_documents(pool: ydb.QuerySessionPool, documents: list[dict]) -> None:
    if not documents:
        return
    row_type = (
        ydb.StructType()
        .add_member("id", ydb.PrimitiveType.Uint64)
        .add_member("title", ydb.PrimitiveType.Utf8)
        .add_member("body", ydb.PrimitiveType.Utf8)
        .add_member("embedding", ydb.PrimitiveType.String)
    )
    rows = [
        {"id": doc["id"], "title": doc["title"], "body": doc["body"],
         "embedding": encode_vector(doc["embedding"])}
        for doc in documents
    ]
    pool.execute_with_retries(
        load_sql("upsert.sql"),
        {"$items": (rows, ydb.ListType(row_type))},
        retry_settings=ydb.RetrySettings(idempotent=True),
    )


def search(pool: ydb.QuerySessionPool, mode: str, *,
           vector: list[float] | None = None, text: str = "",
           limit: int = 10) -> list[dict]:
    if mode not in MODES or limit <= 0:
        raise ValueError("Invalid search mode or limit")
    parameters = {"$limit": (limit, ydb.PrimitiveType.Uint64)}
    if mode != "fulltext":
        if vector is None:
            raise ValueError("This mode requires a query embedding")
        parameters["$query_vector"] = (encode_vector(vector), ydb.PrimitiveType.String)
    if mode in {"fulltext", "hybrid"}:
        parameters["$query_text"] = (text, ydb.PrimitiveType.Utf8)
    result_sets = pool.execute_with_retries(
        load_sql(f"{mode}-search.sql"), parameters,
        retry_settings=ydb.RetrySettings(idempotent=True),
    )
    return [{"id": row["id"], "title": row["title"]}
            for result_set in result_sets for row in result_set.rows]
```

`bytes` bound as `ydb.PrimitiveType.String` is the binary vector; `Utf8` is used for text. The batch has `embedding: String`, and the helper leaves the caller's document objects unchanged. `execute_with_retries` consumes the result stream and raises on failure; do not wrap it in another retry loop.

## Connection and invocation

Use the application's endpoint, database, and credential provider. For environment-based authentication:

```python
import os

with ydb.Driver(
    endpoint=os.environ["YDB_ENDPOINT"],
    database=os.environ["YDB_DATABASE"],
    credentials=ydb.credentials_from_env_variables(),
) as driver:
    driver.wait(5, fail_fast=True)
    with ydb.QuerySessionPool(driver) as pool:
        # Provision once for a new demo table; use migrations in an existing app.
        pool.execute_with_retries(load_sql("create-table.sql"))
        upsert_documents(pool, [
            {"id": 1, "title": "YDB", "body": "distributed database",
             "embedding": [1.0, 0.0, 0.0]},
            {"id": 2, "title": "Search", "body": "vector and fulltext search",
             "embedding": [0.0, 1.0, 0.0]},
            {"id": 3, "title": "Queries", "body": "database query examples",
             "embedding": [0.8, 0.2, 0.0]},
        ])
        pool.execute_with_retries(load_sql("add-vector-index.sql"))
        pool.execute_with_retries(load_sql("add-fulltext-index.sql"))

        print(search(pool, "vector", vector=[1.0, 0.0, 0.0]))
        print(search(pool, "fulltext", text="database"))
        print(search(pool, "hybrid", text="database", vector=[1.0, 0.0, 0.0]))
```

The vectors above are illustrative. In an application, the query vector is the model's embedding of the supplied search text. For an exact baseline, call `search(pool, "exact", vector=...)`.

For asyncio, use `ydb.aio.Driver` and `ydb.aio.QuerySessionPool`, await readiness and `execute_with_retries`, and retain the same encoder and typed parameters. The [SDK recipe](https://ydb.tech/docs/ru/recipes/ydb-sdk/vector-search?tabs=tool_python#search-by-vector) supplies the async variant. Propagate the application's timeouts when adapting these synchronous examples to request handlers.
