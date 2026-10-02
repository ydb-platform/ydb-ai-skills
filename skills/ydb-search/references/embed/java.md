# Search with the Java SDK

Read [the shared SDK workflow](../sdk.md) and copy its SQL assets to `queries/`. Use `tech.ydb:ydb-sdk-query` and a reusable `QueryClient`. The example uses Java 17 records. Sources: [recommended vector recipe](https://ydb.tech/docs/ru/recipes/ydb-sdk/vector-search?version=main&tabs=tool_java#search-by-vector) and [driver initialization](https://ydb.tech/docs/en/recipes/ydb-sdk/init).

```java
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

import tech.ydb.common.transaction.TxMode;
import tech.ydb.query.tools.QueryReader;
import tech.ydb.query.tools.SessionRetryContext;
import tech.ydb.table.query.Params;
import tech.ydb.table.result.ResultSetReader;
import tech.ydb.table.values.ListType;
import tech.ydb.table.values.PrimitiveType;
import tech.ydb.table.values.PrimitiveValue;
import tech.ydb.table.values.StructType;
import tech.ydb.table.values.Value;

public final class SearchExample {
    static final int DIMENSION = 3; // Match add-vector-index.sql.
    record Document(long id, String title, String body, float[] embedding) {}
    record Hit(long id, String title) {}

    static String sql(String name) throws IOException {
        return Files.readString(Path.of("queries", name));
    }

    static byte[] encodeVector(float[] vector) {
        if (vector.length != DIMENSION) {
            throw new IllegalArgumentException("Unexpected embedding dimension");
        }
        ByteBuffer data = ByteBuffer.allocate(4 * DIMENSION + 1)
                .order(ByteOrder.LITTLE_ENDIAN);
        for (float value : vector) data.putFloat(value);
        data.put((byte) 0x01);
        return data.array();
    }

    static void upsert(SessionRetryContext retry, List<Document> documents)
            throws IOException {
        if (documents.isEmpty()) return;
        StructType rowType = StructType.of(
                "id", PrimitiveType.Uint64, "title", PrimitiveType.Text,
                "body", PrimitiveType.Text, "embedding", PrimitiveType.Bytes);
        List<Value<?>> rows = new ArrayList<>();
        for (Document doc : documents) {
            rows.add(rowType.newValue(
                    "id", PrimitiveValue.newUint64(doc.id()),
                    "title", PrimitiveValue.newText(doc.title()),
                    "body", PrimitiveValue.newText(doc.body()),
                    "embedding", PrimitiveValue.newBytes(encodeVector(doc.embedding()))));
        }
        Params params = Params.of("$items", ListType.of(rowType).newValue(rows));
        String statement = sql("upsert.sql");
        retry.supplyResult(session -> QueryReader.readFrom(
                session.createQuery(statement, TxMode.SERIALIZABLE_RW, params)
        )).join().getValue();
    }

    static List<Hit> search(SessionRetryContext retry, String mode,
            String text, float[] vector, long limit) throws IOException {
        if (!Set.of("exact", "vector", "fulltext", "hybrid").contains(mode) || limit <= 0) {
            throw new IllegalArgumentException("Invalid search mode or limit");
        }
        Params params = Params.create().put("$limit", PrimitiveValue.newUint64(limit));
        if (!mode.equals("fulltext")) {
            params.put("$query_vector", PrimitiveValue.newBytes(encodeVector(vector)));
        }
        if (mode.equals("fulltext") || mode.equals("hybrid")) {
            params.put("$query_text", PrimitiveValue.newText(text));
        }
        String statement = sql(mode + "-search.sql");
        QueryReader reader = retry.supplyResult(session -> QueryReader.readFrom(
                session.createQuery(statement, TxMode.SNAPSHOT_RO, params)
        )).join().getValue();
        ResultSetReader rows = reader.getResultSet(0);
        List<Hit> hits = new ArrayList<>();
        while (rows.next()) {
            hits.add(new Hit(rows.getColumn("id").getUint64(),
                             rows.getColumn("title").getText()));
        }
        return hits;
    }
}
```

`PrimitiveValue.newBytes` binds YQL `String`; `newText` binds `Utf8`. Build parameters once, before entering retries. `QueryReader` consumes the stream inside `supplyResult`; build the returned list after the successful result, so retries cannot append duplicate hits. The shown `long` IDs/limits are nonnegative application values representable in signed 64 bits.

## Connection and invocation

Create an authenticated `GrpcTransport` using the application's configuration, then reuse a `QueryClient` and `SessionRetryContext`:

```java
import tech.ydb.query.QueryClient;

// transport is the application's configured GrpcTransport.
try (QueryClient client = QueryClient.newClient(transport).build()) {
    SessionRetryContext setup = SessionRetryContext.create(client).build();
    SessionRetryContext retry = SessionRetryContext.create(client)
            .idempotent(true).build();
    String create = SearchExample.sql("create-table.sql");
    setup.supplyResult(session -> QueryReader.readFrom(
            session.createQuery(create, TxMode.NONE, Params.empty())
    )).join().getValue();
    SearchExample.upsert(retry, List.of(
            new SearchExample.Document(1, "YDB", "distributed database", new float[]{1, 0, 0}),
            new SearchExample.Document(2, "Search", "vector search", new float[]{0, 1, 0}),
            new SearchExample.Document(3, "Queries", "database examples", new float[]{0.8f, 0.2f, 0})
    ));
    for (String file : List.of("add-vector-index.sql", "add-fulltext-index.sql")) {
        String ddl = SearchExample.sql(file);
        setup.supplyResult(session -> QueryReader.readFrom(
                session.createQuery(ddl, TxMode.NONE, Params.empty())
        )).join().getValue();
    }
    List<SearchExample.Hit> hits = SearchExample.search(
            retry, "hybrid", "database", new float[]{1, 0, 0}, 10);
}
```

For schema setup, use a separate retry context with its default idempotency settings and execute each DDL file with `TxMode.NONE` using the same `supplyResult(session -> QueryReader.readFrom(session.createQuery(...)))` form. The order is `create-table.sql`, `upsert(...)`, then the two index files. Check completion/status before searching. The read/write context above is explicitly idempotent for these SELECTs and deterministic UPSERTs; do not reuse that assumption for arbitrary application writes.

After setup, call `search(retry, "vector", "", queryVector, 10)`, `search(retry, "fulltext", "database", null, 10)`, or `search(retry, "hybrid", "database", queryVector, 10)`. Use `"exact"` for the baseline. The query vector comes from the same embedding model used for documents. In an existing service, propagate its remaining deadline through `ExecuteQuerySettings` and cancel the retry future when the request is cancelled; see the SDK timeout/retry documentation.
