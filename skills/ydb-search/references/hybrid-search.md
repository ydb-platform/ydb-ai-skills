# Hybrid search with HybridRank

Hybrid search fuses candidate rankings from existing indexes on one table. For lexical plus semantic retrieval, use `fulltext_relevance` on the text and `vector_kmeans_tree` on the embedding. There is no separate hybrid index type.

Sources: [hybrid guide](https://ydb.tech/docs/en/dev/hybrid-search?version=main) and [HybridRank syntax](https://ydb.tech/docs/en/yql/reference/syntax/select/hybrid_search?version=main). The inspected implementation requires a single-column primary key; see [compatibility](compatibility.md) for feature defaults and branch-specific prefix rules.

## Runnable example

Use the shared `documents` table from [create-table.sql](../assets/queries/create-table.sql), load data with [upsert.sql](../assets/queries/upsert.sql), then execute [add-vector-index.sql](../assets/queries/add-vector-index.sql) and [add-fulltext-index.sql](../assets/queries/add-fulltext-index.sql). Both indexes must be ready before running [hybrid-search.sql](../assets/queries/hybrid-search.sql). The [SDK workflow](sdk.md) and one language page provide the execution path.

The shared index uses three-dimensional float vectors. When adapting it to the embedding model, follow [vector index settings](vector-indexes.md#index-settings-and-recall) and build after loading representative data. If bulk loading is needed, finish it before adding either synchronous index. Coordinate writes during vector construction if build consistency is required.

## Query shape

The query reads the base table without `VIEW`. Each scoring argument resolves a ready matching index from its column and, for vector branches, its metric. `HybridRank(...)` must be the entire `ORDER BY` key: do not add another sort key, negate it, or wrap it in an expression. The rewrite ranks larger fused contributions first.

Bind the user's search text and the model's embedding of that same query. The vector parameter is a completed binary `String`, used directly by `Knn`; follow [client encoding](vector-indexes.md#store-and-load-embeddings). The hybrid rewrite constructs full-text branch access internally, so the standalone `WHERE FulltextScore(...) > 0` requirement does not belong in this query. Documents found by only one branch can still appear in the result.

## Fusion and candidate tuning

The runnable query names `ft_idx` and `vec_idx` explicitly and gives them candidate limits of 100 and 200 respectively. These are tuning examples. Tuple entries correspond to scoring-argument order, with exactly one entry per branch. To favor the vector branch under the default RRF fusion, add `(1.0, 2.0) AS Weights` after the scoring arguments.

| Option | Meaning |
|---|---|
| `Mode` | `"rrf"` (default) or `"linear"` |
| `Weights` | One numeric weight per branch; defaults to 1 each |
| `K` | RRF constant, default 60.0; branch contribution is `weight / (K + rank)` with 1-based rank |
| `Normalize` | Linear mode only; defaults to true, normalizing branch scores before weighted fusion |
| `Indexes` | One explicit index name per branch; resolves ambiguous matching indexes |
| `Limits` | One positive integer literal per branch; candidate counts before fusion |

Without explicit `Limits`, the pool size defaults to the literal outer `LIMIT` multiplied by `HybridSearchFactor` (default 10). The runnable query supplies `Limits` so its final `$limit` can be a parameter. `KMeansTreeSearchTopSize` controls vector clusters explored, `Limits` controls candidates retained, and outer `LIMIT` controls returned rows. Size candidate pools for the requested count and filtering, then measure relevance and latency.

RRF compares positions, avoiding raw BM25/vector score scale differences. Linear fusion normalizes scores by default and accounts for distance versus similarity direction. Tune it against relevance data instead of summing raw BM25 and distance values in an ordinary sort expression.

Two or more scoring branches are supported, including additional vector columns with their own indexes. Optional `RankLambda` receives `Dict<Int64, Int64>` (zero-based branch number to 1-based rank); `ScoreLambda` receives `Dict<Int64, Double>` of raw scores. Missing branches have no entry. A custom lambda must handle missing values and return a numeric score where larger is better; raw distances need the appropriate direction. Choose at most one lambda, and do not combine it with `Mode`, `Weights`, `K`, or `Normalize`.

## Filtered variations and diagnosis

If the application extends the schema with tenant data, preserve its `WHERE tenant = $tenant` predicate. General predicates are reapplied after candidate lookup, so small pools can leave fewer rows than requested. Increasing pools may help; measure the result and do not promise exact filtered top-k from ANN.

On the inspected main revision, both full-text and vector indexes require equality on every prefix column. For example, `(tenant, region, embedding)` requires both `tenant = $tenant` and `region = $region`; a leading subset is insufficient. Predicates under SQL `OR` do not establish those equalities. The older stable-26-3-1 behavior and feature defaults are documented in [compatibility](compatibility.md). Prefixed relevance indexes also require compact full-text indexes.

When a query fails, inspect:

- Server support and the effective `EnableHybridSearch` setting.
- A single-column primary key; standalone full-text support for composite keys does not remove this hybrid restriction.
- Both indexes ready, correct scored columns, compatible vector metric, and `fulltext_relevance` for BM25.
- Ambiguous matches resolved with `Indexes`, and tuple lengths matching the number of branches.
- Explicit `Limits` with a parameterized outer limit, and the unwrapped `HybridRank` sort key.
- Prefix equalities and feature availability. Preserve the requested tenant scope when correcting the query.

Use non-executing explain to inspect the target plan, then evaluate retrieval quality separately.
