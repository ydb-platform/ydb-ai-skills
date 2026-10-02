# Vector indexes and nearest-neighbor search

Use `vector_kmeans_tree` for approximate nearest neighbors (ANN). Exact search evaluates distances across the eligible rows and is useful for small datasets and recall baselines. Both use `Knn` functions over binary `String` embeddings.

Sources: [vector guide](https://ydb.tech/docs/en/dev/vector-indexes?version=main), [index DDL](https://ydb.tech/docs/en/yql/reference/syntax/create_table/vector_index?version=main), [indexed SELECT](https://ydb.tech/docs/en/yql/reference/syntax/select/vector_index?version=main), and [Knn functions and encoding](https://ydb.tech/docs/en/yql/reference/udf/list/knn?version=main). See [compatibility](compatibility.md) for the inspected source revision and differences from its docs.

## Store and load embeddings

```yql
CREATE TABLE documents (
    id Uint64 NOT NULL,
    tenant Utf8,
    title Utf8,
    body Utf8,
    embedding String,
    PRIMARY KEY (id)
);
```

Compute embeddings outside YDB with the same model for documents and queries. For application input, serialize on the client and bind `String`; the [SDK recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) gives the serialization patterns. A `FloatVector` contains little-endian float32 coordinates followed by one byte `0x01`: dimension `D` occupies `4 * D + 1` bytes. Preserve binary bytes through parameter binding.

Bind the serialized embedding for writes as well as queries:

```yql
DECLARE $id AS Uint64;
DECLARE $embedding AS String;

UPSERT INTO documents (id, embedding)
VALUES ($id, $embedding);
```

For vectors constructed inside SQL, persist `Untag(Knn::ToBinaryStringFloat($vector), "FloatVector")`: the conversion UDF returns a tagged value, while the column stores `String`. `Knn` comparisons return `NULL` for incompatible formats or lengths. Indexable vector types are `float`, `uint8`, and `int8`; `BitVector` is supported by conversion/comparison functions but not by vector indexes.

## Build after initial loading

Given a representative dataset of **768-dimensional float vectors** already loaded into `documents`:

```yql
ALTER TABLE documents
  ADD INDEX vec_idx
  GLOBAL USING vector_kmeans_tree
  ON (embedding)
  COVER (embedding, title)
  WITH (
    distance=cosine,
    vector_type="float",
    vector_dimension=768,
    clusters=128,
    levels=2,
    overlap_clusters=3
  );
```

The cluster values are an example to tune against data size and distribution. `COVER (embedding, title)` includes the actual vector needed for final distance sorting as well as the projected title. Without covering the vector, the engine still needs base-table reads even if other output columns are covered.

Choose one of `distance` or `similarity`, matching the query:

| Index setting | Standalone sort |
|---|---|
| `distance=cosine` or `similarity=cosine` | `Knn::CosineDistance(...) ASC` or `Knn::CosineSimilarity(...) DESC` |
| `distance=euclidean` | `Knn::EuclideanDistance(...) ASC` |
| `distance=manhattan` | `Knn::ManhattanDistance(...) ASC` |
| `similarity=inner_product` | `Knn::InnerProductSimilarity(...) DESC` |

Dimensions may be 1–16384, `clusters` 2–2048, and `levels` 1–16. The documented bounds also require `clusters ** levels <= 1073741824` and `vector_dimension * clusters <= 4194304`. Type and dimension can be inferred from a populated table, but explicit settings make the embedding contract clear. Source: [parameter definitions](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/docs/en/core/yql/reference/syntax/_includes/vector_index_parameters.md).

## Query and tune

```yql
PRAGMA ydb.KMeansTreeSearchTopSize = "10";
DECLARE $query_vector AS String;

SELECT id, title,
       Knn::CosineDistance(embedding, $query_vector) AS distance
FROM documents VIEW vec_idx
ORDER BY distance ASC
LIMIT 10;
```

Bind an encoded 768-dimensional vector to `$query_vector`. For an exact baseline, use the same query without `VIEW vec_idx`; it computes distances over the eligible base-table rows. Keep the same filters and metric for recall comparisons, and account for the cost of that scan.

`KMeansTreeSearchTopSize` controls clusters probed at each tree level; it is independent of the result `LIMIT`. Set it explicitly. Increasing it generally trades latency for recall. `overlap_clusters` is a build-time setting that places vectors in multiple leaf clusters, increasing index size. Measure recall@k against exact top-k and latency before choosing these values; a small result limit does not by itself ensure a cheap query.

For tenant/category search, put filter columns before the vector column:

```yql
ALTER TABLE documents
  ADD INDEX tenant_vec_idx
  GLOBAL USING vector_kmeans_tree
  ON (tenant, embedding)
  COVER (embedding, title)
  WITH (distance=cosine, vector_type="float", vector_dimension=768);
```

```yql
PRAGMA ydb.KMeansTreeSearchTopSize = "10";
DECLARE $tenant AS Utf8;
DECLARE $query_vector AS String;

SELECT id, title
FROM documents VIEW tenant_vec_idx
WHERE tenant = $tenant
ORDER BY Knn::CosineDistance(embedding, $query_vector)
LIMIT 10;
```

This binds the index prefix directly. When using multiple categories, a partial prefix, or additional filters, verify support and the actual plan for the target version; do not transfer standalone vector filtering rules to `HybridRank` without checking its stricter prefix extraction.

## Lifecycle and verification

- Load representative data before building. Building on an empty table produces one cluster and no useful search acceleration.
- Completed indexes assign new/modified rows to existing clusters; they do not retrain centroids. Distribution changes can reduce recall and unbalance query work. Build a replacement index when measurements justify it, then switch indexes using the documented [index rename/replacement operation](https://ydb.tech/docs/en/reference/ydb-cli/commands/secondary_index?version=main#rename).
- Concurrent writes during vector index construction are not consistently reflected in the built index. If the application needs a fully consistent build, coordinate a write pause for its duration; writes are not paused automatically.
- Use `BulkUpsert` before creating synchronous indexes and SQL `INSERT`/`UPSERT` afterward. The inspected implementation also rejects TTL on a table with a vector index. Sources: [bulk loading](https://ydb.tech/docs/en/dev/batch-upload?version=main), [VectorIndexNoBulkUpsert and TTL tests](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/kqp/ut/indexes/vector/kqp_indexes_vector_ut.cpp).
- A non-executing explain should show access to the requested index rather than an unintended base-table scan. Base-table lookups can still be appropriate when the index does not cover needed columns. Exact search intentionally scans; label it accordingly.
