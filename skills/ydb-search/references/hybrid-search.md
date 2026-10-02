# Hybrid search with HybridRank

Hybrid search fuses candidate rankings from existing indexes on one table. For lexical plus semantic retrieval, use `fulltext_relevance` on the text and `vector_kmeans_tree` on the embedding. There is no separate hybrid index type.

Sources: [hybrid guide](https://ydb.tech/docs/en/dev/hybrid-search?version=main) and [HybridRank syntax](https://ydb.tech/docs/en/yql/reference/syntax/select/hybrid_search?version=main). Read [compatibility](compatibility.md) for implementation evidence and differences from stable-26-3-1. The inspected main implementation requires a single-column primary key and enables hybrid search by default unless the cluster overrides the setting.

## Prepare the table and indexes

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

Load representative documents and encoded embeddings **before building the vector index**. The following example assumes 768-dimensional float embeddings. If using bulk loading, finish it before adding either synchronous index. Coordinate writes during vector construction if build consistency is required.

```yql
ALTER TABLE documents
  ADD INDEX ft_idx GLOBAL USING fulltext_relevance
  ON (body)
  WITH (tokenizer=standard, use_filter_lowercase=true);

ALTER TABLE documents
  ADD INDEX vec_idx GLOBAL USING vector_kmeans_tree
  ON (embedding) COVER (embedding, title)
  WITH (distance=cosine, vector_type="float", vector_dimension=768,
        clusters=128, levels=2, overlap_clusters=3);
```

Wait for both indexes to be ready before querying. Adjust the example dimension and tree settings to the dataset; see [vector indexes](vector-indexes.md) and [full-text indexes](fulltext-indexes.md) when changing their definitions.

## Query the base table

```yql
PRAGMA ydb.KMeansTreeSearchTopSize = "10";
DECLARE $query_text AS String;
DECLARE $query_vector AS String;

SELECT id, title
FROM documents
ORDER BY HybridRank(
    FulltextScore(body, $query_text),
    Knn::CosineDistance(embedding, $query_vector))
LIMIT 10;
```

Bind the user's search text and the client-computed binary embedding of that query. For FloatVectors, bind the completed little-endian float32 bytes with the trailing `0x01` marker as `$query_vector AS String`; do not send `List<Float>` or wrap this parameter in `Knn::ToBinaryStringFloat`/`Untag`. See [client encoding and batch writes](vector-indexes.md#store-and-load-embeddings). Use the same embedding model as the stored documents. The `HybridRank` call is the entire sort key; follow this form without adding another sort key, negating it, or wrapping it in an expression. The rewrite ranks larger fused contributions first.

Read the base table **without `VIEW`**. Each branch resolves a ready matching index from its scored column and, for vector branches, its metric. The rewrite constructs the full-text branch internally: the standalone `WHERE FulltextScore(...) > 0` requirement does not belong in this query. Documents found by only one branch can still appear in the fused result.

## Weights, candidate counts, and parameterized limits

```yql
PRAGMA ydb.KMeansTreeSearchTopSize = "10";
DECLARE $query_text AS String;
DECLARE $query_vector AS String;
DECLARE $limit AS Uint64;

SELECT id, title
FROM documents
ORDER BY HybridRank(
    FulltextScore(body, $query_text),
    Knn::CosineDistance(embedding, $query_vector),
    "rrf" AS Mode,
    (1.0, 2.0) AS Weights,
    ("ft_idx", "vec_idx") AS Indexes,
    (100, 200) AS Limits)
LIMIT $limit;
```

Tuple entries correspond to branch argument order: here text gets weight 1 and 100 candidates; vector gets weight 2 and 200. The pools are tuning examples, not a promise of recall. Keep them large enough for the requested result count and filtering, and measure relevance and latency.

| Option | Meaning |
|---|---|
| `Mode` | `"rrf"` (default) or `"linear"` |
| `Weights` | One numeric weight per branch; defaults to 1 each |
| `K` | RRF constant, default 60.0; branch contribution is `weight / (K + rank)` with 1-based rank |
| `Normalize` | Linear mode only; defaults to true, normalizing branch scores before weighted fusion |
| `Indexes` | One explicit index name per branch; resolves ambiguous matching indexes |
| `Limits` | One positive integer literal per branch; candidate counts before fusion |

Without explicit `Limits`, the pool size defaults to the literal outer `LIMIT` multiplied by `HybridSearchFactor` (default 10). A parameterized outer `LIMIT` therefore requires explicit `Limits`. `KMeansTreeSearchTopSize` controls vector clusters explored, `Limits` controls branch candidates retained, and outer `LIMIT` controls returned rows.

RRF compares positions, avoiding raw BM25/vector score scale differences. Linear fusion normalizes scores by default and accounts for distance versus similarity direction. Tune it against relevance data instead of summing raw BM25 and distance values in an ordinary `ORDER BY`.

Two or more scoring branches are supported, including additional vector columns with their own indexes. Optional `RankLambda` receives `Dict<Int64, Int64>` (zero-based branch number to 1-based rank); `ScoreLambda` receives `Dict<Int64, Double>` of raw scores. Missing branches have no entry. A custom lambda must handle missing values and return a numeric score where larger is better; raw distances need the appropriate direction. Choose at most one lambda, and do not combine it with `Mode`, `Weights`, `K`, or `Normalize`.

## Filters and diagnosis

For a tenant filter, preserve `WHERE tenant = $tenant`. General predicates are reapplied after candidate lookup, so a small candidate pool can leave fewer than the requested number of rows. Increasing pools may help; measure the result and do not promise exact filtered top-k from ANN.

On the inspected main revision, **both** prefixed full-text and prefixed vector indexes require equality on **every** prefix column. A leading subset is insufficient: `(Region, Category, Embedding)` with only `WHERE Region = $region` is rejected; also bind `Category = $category`. Predicates under SQL `OR` do not establish those equalities. Full-text `(tenant, body)` and vector `(tenant, embedding)` with `WHERE tenant = $tenant` and explicit `Indexes` bind both prefixes fully. The older stable-26-3-1 snapshot accepted a leading subset for vector branches; use [compatibility](compatibility.md) to keep that historical behavior out of SQL for main.

Prefixed relevance indexes require `EnableFulltextIndexPrefix` and the compact implementation selected by `EnableCompactFulltextIndex`. Both, as well as `EnableHybridSearch`, default to true on the inspected main revision; an effective cluster override can disable them.

When a query fails, inspect:

- Server support and `TableServiceConfig.EnableHybridSearch`.
- A single-column primary key; the inspected hybrid rewrite rejects composite keys even where standalone full-text indexing accepts them.
- Both indexes ready, correct scored columns, compatible vector metric, and `fulltext_relevance` for BM25.
- Ambiguous matches resolved with `Indexes`, and tuple lengths matching the number of branches.
- Explicit `Limits` with a parameterized outer limit, and the unwrapped `HybridRank` sort key.
- Prefix equalities and feature availability. Do not change a tenant-scoped request into an unfiltered search to make it compile.

Use non-executing explain to inspect the target plan, then evaluate retrieval quality separately. Implementation checks and query examples are backed by the main hybrid query tests; see [compatibility](compatibility.md) for their source locations.
