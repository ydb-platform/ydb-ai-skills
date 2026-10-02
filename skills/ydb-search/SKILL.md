---
name: ydb-search
description: Designs YDB vector indexes, fulltext indexes, and hybrid search queries, including SDK examples for Python, Go, Java, C++, and JavaScript. Use for YDB semantic search, ANN or exact nearest neighbors, vector_kmeans_tree, Knn distance and similarity ranking, KMeansTreeSearchTopSize, fulltext_plain, fulltext_relevance, FulltextMatch, FulltextScore, BM25, tokenizers, n-grams, HybridRank, RRF, and search recall or index lifecycle problems. Covers index DDL, binary embedding parameters, batch writes, filtered search, ranking, and query troubleshooting. For general SDK usage or SQL execution use ydb-table; for finding documentation use ydb-docs. Does not cover YQL on YT or other search engines.
---

# YDB Search

Design search indexes and write vector, full-text, and hybrid queries for YDB row-oriented tables.

## Workflow

1. Identify the retrieval task: exact nearest neighbors, approximate vector search, lexical matching, BM25 ranking, or fusion of lexical and semantic results. Reuse the supplied schema, embedding model and dimension, metric, filters, and result limit; state assumptions where these are missing.
2. Establish the server version and relevant enabled features when available. Read [compatibility](references/compatibility.md) before relying on hybrid search, prefixed indexes, or non-integer full-text primary keys. A source checkout or documentation branch does not establish deployed availability.
3. Load only the relevant reference below. Produce matching DDL and parameterized SQL, distinguishing schema creation, initial data loading, index construction, and querying. Serialize application-provided FloatVectors on the client and bind the completed binary `String`; do not send `List<Float>` and convert it with `Knn::ToBinaryStringFloat` in SQL. Apply this to exact, indexed, and hybrid search, and to embedding fields in batch writes.
4. For diagnosis, compare the query with the index's columns, metric, readiness, and filter requirements. Use a non-executing explain when a target is available. Evaluate recall and latency with representative queries; compare ANN results with exact search on the same data and filters when practical.
5. Report the SQL, assumptions, applicable build/update limitations, and what was actually verified. Writing a query or skill does not require connecting to or changing a database.

## Load sources

| Task | Reference |
|---|---|
| Vector storage, exact/ANN queries, vector index DDL, coverage, filtering, recall, rebuilding | [Vector indexes](references/vector-indexes.md) |
| Text matching, BM25, analyzers, n-grams, filtered full-text indexes | [Full-text indexes](references/fulltext-indexes.md) |
| HybridRank, RRF/linear fusion, branch weights and candidate limits | [Hybrid search](references/hybrid-search.md); load the individual index references when changing their DDL |
| SDK setup, shared SQL files, parameter types, and operation order | [SDK workflow](references/sdk.md), plus only the relevant language page below |
| Search through the Python SDK | [Python](references/embed/python.md) |
| Search through the Go SDK | [Go](references/embed/go.md) |
| Search through the Java SDK | [Java](references/embed/java.md) |
| Search through the C++ SDK | [C++](references/embed/cpp.md) |
| Search through the JavaScript SDK | [JavaScript](references/embed/javascript.md) |
| Feature availability, documentation/source disagreements, source provenance | [Compatibility](references/compatibility.md) |

The SDK pages are focused on search and share executable SQL assets under `assets/queries/`. If installed, `ydb-table` covers general SDK usage and CLI execution, and `ydb-core` covers connection discovery. The examples can be used independently with the linked official SDK setup documentation.

## Gotchas

- Standalone vector and full-text queries select an index with `VIEW index_name`. A hybrid query reads the base table without `VIEW` and resolves branch indexes through `HybridRank`.
- Vectors are serialized binary `String` values. FloatVectors use little-endian float32 bytes followed by `0x01`. Pass that parameter directly to `Knn` functions, without `Knn::ToBinaryStringFloat` or `Untag` around it. Match stored and query vectors to the model, dimension, and index type; SQL-side conversion remains appropriate for vectors constructed or already stored as lists inside YDB.
- Build a vector index after loading representative data. An index built on an empty table has one cluster; later writes do not retrain the cluster tree. Writes during the build are not consistently captured.
- Standalone BM25 requires `fulltext_relevance` and the same `FulltextScore(...)` expression in `SELECT` and `WHERE ... > 0`. The hybrid rewrite supplies the branch access; do not copy this standalone `WHERE` requirement into a hybrid query.
- `HybridRank(...)` is the entire `ORDER BY` key. A parameterized outer `LIMIT` requires explicit candidate `Limits` for every branch. The inspected implementation also requires a single-column primary key.
- `BulkUpsert` is unavailable once these synchronous search indexes exist. Plan bulk initial loading before index creation; use supported SQL writes afterward.

## Content rules

Ground YDB syntax in the linked documentation and pinned implementation. Do not substitute PostgreSQL vector operators, HNSW settings, Elasticsearch query DSL, or an invented hybrid index type. Preserve the requested retrieval semantics: ANN is approximate, and fusion ranks the union of branch candidates. Tune candidate pools and vector probing separately.

Treat examples as query patterns, not measured capacity recommendations. State version uncertainty explicitly and use [compatibility](references/compatibility.md) to resolve stale documentation before claiming a feature is supported or unsupported.
