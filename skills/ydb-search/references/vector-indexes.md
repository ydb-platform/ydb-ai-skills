# Vector indexes and nearest-neighbor search

Use `vector_kmeans_tree` for approximate nearest neighbors (ANN). Exact search evaluates distances across the eligible rows and is useful for small datasets and recall baselines. Both use `Knn` functions over binary `String` embeddings.

Sources: [vector guide](https://ydb.tech/docs/en/dev/vector-indexes?version=v26.3), [index DDL](https://ydb.tech/docs/en/yql/reference/syntax/create_table/vector_index?version=v26.3), [indexed SELECT](https://ydb.tech/docs/en/yql/reference/syntax/select/vector_index?version=v26.3), and [Knn functions and encoding](https://ydb.tech/docs/en/yql/reference/udf/list/knn?version=v26.3).

For YDB 25.1–26.3, select matching versioned pages and read the [release notes and limitations](version-compatibility.md) before choosing update behavior or advanced index options. In particular, do not apply the later incremental-maintenance behavior to 25.1 without verification.

## Runnable examples

Use the SQL files in [assets/queries](../assets/queries) and one SDK language page selected in `SKILL.md`. The shared [SDK workflow](sdk.md) describes operation order and parameter types. All examples use the `documents` table with `id`, `title`, `body`, and a three-dimensional `embedding`.

| Step | SQL file |
|---|---|
| Create the shared table | [create-table.sql](../assets/queries/create-table.sql) |
| Load documents with encoded embeddings | [upsert.sql](../assets/queries/upsert.sql) |
| Build the index after loading representative data | [add-vector-index.sql](../assets/queries/add-vector-index.sql) |
| Query through `VIEW vec_idx` | [vector-search.sql](../assets/queries/vector-search.sql) |
| Compare against exact search | [exact-search.sql](../assets/queries/exact-search.sql) |

## Store and load embeddings

Compute embeddings outside YDB with the same model for documents and queries. Serialize application-provided FloatVectors on the client and bind the completed bytes as YQL `String`. A FloatVector contains little-endian float32 coordinates followed by `0x01`: dimension `D` occupies `4 * D + 1` bytes.

Use that binary parameter directly in `Knn::CosineDistance(embedding, $query_vector)` or the corresponding similarity function. Sending `List<Float>` and converting it with `Knn::ToBinaryStringFloat`/`Untag` in SQL adds list serialization, element transfer/parsing, and server conversion. This recommendation applies to exact, indexed, and hybrid search, as well as every `embedding: String` member in the batch passed to [upsert.sql](../assets/queries/upsert.sql). See the [recommended SDK recipe](https://ydb.tech/docs/ru/recipes/ydb-sdk/vector-search?version=v26.3#search-by-vector).

When refactoring, retain the application interface, stored column format, and search semantics. Verify byte equality with the UDF representation, read back a stored vector, and check exact and indexed search. Measure performance on representative requests; a transfer benchmark does not establish a fixed speedup for complete ANN queries.

For vectors constructed inside SQL or list values already stored in YDB, server conversion remains appropriate: persist `Untag(Knn::ToBinaryStringFloat($vector), "FloatVector")` because the UDF returns a tagged value while the column stores `String`. This exception does not apply to a list supplied by the client. `Knn` comparisons return `NULL` for incompatible formats or lengths.

The shared example uses `float`; the release DDL pages also document `uint8` and `int8`. Other formats, including `bit`, `float16`, and `bfloat16`, need target-specific confirmation rather than an assumption of uniform support across 25.1–26.3; see [encoding compatibility](version-compatibility.md#limits-that-need-a-release-specific-answer). Do not reject a format independently verified on the target. Each type has its own encoding; the float32 layout above applies only to `FloatVector`.

## Index settings and recall

The runnable [index definition](../assets/queries/add-vector-index.sql) uses `vector_dimension=3`, `clusters=2`, and `levels=1`. For a production model that emits 768-dimensional vectors, `vector_dimension=768` and a measured choice such as `clusters=128` are deployment-specific settings to tune on representative data.

`COVER (embedding, title)` includes the actual vector needed for final distance sorting as well as the projected title. Without covering the vector, the engine still needs base-table reads even if other output columns are covered.

Choose one of `distance` or `similarity`, matching the query:

| Index setting | Standalone sort |
|---|---|
| `distance=cosine` or `similarity=cosine` | `Knn::CosineDistance(...) ASC` or `Knn::CosineSimilarity(...) DESC` |
| `distance=euclidean` | `Knn::EuclideanDistance(...) ASC` |
| `distance=manhattan` | `Knn::ManhattanDistance(...) ASC` |
| `similarity=inner_product` | `Knn::InnerProductSimilarity(...) DESC` |

Dimensions may be 1–16384, `clusters` 2–2048, and `levels` 1–16. The documented bounds also require `clusters ** levels <= 1073741824` and `vector_dimension * clusters <= 4194304`. Type and dimension can be inferred from a populated table, but explicit settings make the embedding contract clear. Source: [vector index parameters](https://ydb.tech/docs/en/yql/reference/syntax/create_table/vector_index?version=v26.3).

`KMeansTreeSearchTopSize` controls clusters probed at each tree level, independently of the result `LIMIT`. Set it explicitly, as in [vector-search.sql](../assets/queries/vector-search.sql). Increasing it generally trades latency for recall. `overlap_clusters` is a build-time setting that places vectors in multiple leaf clusters, increasing index size; it is explicitly described in the [25.4.1.15 release notes](https://ydb.tech/docs/en/changelog-server.md?version=v25.4#25-4-1-15). Verify earlier builds before adding it.

Measure recall@k against [exact-search.sql](../assets/queries/exact-search.sql) with the same data, metric, and filters, and account for the cost of that scan. Tune probing and cluster settings using recall and latency together; a small result limit does not by itself ensure a cheap query.

## Scoped-search variation

If the application adds and populates a tenant/category column, put it before the vector column in the index, for example `ON (tenant, embedding)`, and bind `tenant = $tenant` in the query through that index. The shared demonstration schema has no `tenant` column; extend the schema and ingestion together before using this variation.

For multiple categories, partial prefixes, or additional filters, verify support and the actual plan on the target database. Hybrid search has its own [prefix requirements](hybrid-search.md#filtered-variations-and-diagnosis).

## Lifecycle and verification

- Load representative data before building. Building on an empty table produces one cluster and no useful search acceleration.
- In the documented update path for 25.3–26.3, completed indexes assign new/modified rows to existing clusters; they do not retrain centroids. The 25.1 pages warn that indexes do not track later changes, and the 25.2 pages disagree about updates; see [version compatibility](version-compatibility.md). When updates are supported, distribution changes can reduce recall and unbalance query work. Build a replacement when needed, then switch indexes using the documented [index rename/replacement operation](https://ydb.tech/docs/en/reference/ydb-cli/commands/secondary_index?version=v26.3#rename).
- Concurrent writes during construction are not consistently reflected in the built vector index. If the application needs a fully consistent build, coordinate a write pause for its duration; writes are not paused automatically.
- Use `BulkUpsert` before creating synchronous indexes and supported SQL writes afterward; first verify indexed-write support on early targets. Tables with vector indexes do not support TTL. See [bulk loading](https://ydb.tech/docs/en/dev/batch-upload?version=v26.3).
- A non-executing explain should show access to the requested index rather than an unintended base-table scan. Base-table lookups can still be appropriate when the index does not cover needed columns. Exact search intentionally scans; label it accordingly.
