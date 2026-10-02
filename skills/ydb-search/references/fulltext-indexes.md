# Full-text indexes and BM25

Use `fulltext_plain` for matching/filtering and `fulltext_relevance` for BM25 scoring. Each index has one indexed text column (`String` or `Utf8`), optionally preceded by filter columns; `COVER` adds payload columns. These are synchronous indexes on row-oriented tables.

Sources: [full-text guide](https://ydb.tech/docs/en/dev/fulltext-indexes?version=main), [DDL](https://ydb.tech/docs/en/yql/reference/syntax/create_table/fulltext_index?version=main), [SELECT](https://ydb.tech/docs/en/yql/reference/syntax/select/fulltext_index?version=main), and [built-ins](https://ydb.tech/docs/en/yql/reference/builtins/fulltext?version=main). See [compatibility](compatibility.md) before using prefixes or non-integer/composite primary keys.

## Runnable examples

Use the shared `documents` schema in [create-table.sql](../assets/queries/create-table.sql), load it with [upsert.sql](../assets/queries/upsert.sql), add the index with [add-fulltext-index.sql](../assets/queries/add-fulltext-index.sql), and rank results with [fulltext-search.sql](../assets/queries/fulltext-search.sql). These are the same table and data used by vector and hybrid search. The [SDK workflow](sdk.md) and one language page supply parameter binding and execution.

Unlike a k-means vector index, a full-text index can usefully be created before inserting documents. The shared walkthrough loads data first so it can support both search types with one setup sequence.

## Query shape and term semantics

The ranking file uses an identical `FulltextScore(...)` expression, including named options, in `SELECT` and `WHERE ... > 0`, then sorts `score DESC`. A `SELECT` alias is unavailable in `WHERE`; standalone relevance access requires the positive-score predicate and a `fulltext_relevance` index.

For a matching-only variation, use `fulltext_plain`, replace the scoring predicate with `FulltextMatch(body, $query_text)`, and remove the BM25 projection and sort. `FulltextMatch` can also use a relevance index.

Standalone full-text functions require explicit `VIEW`. One read supports one full-text predicate, combined with other filters using `AND`; SQL `OR`/`NOT` around full-text predicates and mixing `FulltextMatch` with `FulltextScore` in one `WHERE` are unsupported. Query-language term operators are a separate mechanism.

Only the first two function arguments are positional; optional settings use `value AS Name`. `Keywords` is the default matching mode and `And` the default term operator. The runnable ranking query explicitly selects `"Or" AS DefaultOperator`.

With `Or`, an optional `+` prefix marks that particular term as mandatory. Terms without `+` are optional, and `MinimumShouldMatch` counts only those optional terms (a number or percentage supplied as a string). If no term has `+`, all terms are optional and the threshold applies to all of them. Preserve the supplied query text; adding `+` changes which documents match. To require half the optional terms, add `"50%" AS MinimumShouldMatch` to both scoring expressions in the query.

`FulltextMatch` also supports `"Query" AS Mode` for required/excluded terms and quoted phrases, and `"Wildcard" AS Mode` for `%`/`_` patterns backed by n-grams. `FulltextScore` accepts `DefaultOperator`, `MinimumShouldMatch` (with `Or`), and numeric `K1`/`B` BM25 settings. Keep its options distinct from the matching function's `Mode`.

## Analyzer variations

Adapt the settings in [add-fulltext-index.sql](../assets/queries/add-fulltext-index.sql) at index creation according to the desired matching:

| Requirement | Settings |
|---|---|
| Words split on whitespace/punctuation | `tokenizer=standard` |
| Whitespace splitting or whole-value tokens | `tokenizer=whitespace` or `tokenizer=keyword` |
| Case normalization | `use_filter_lowercase=true` |
| Stemming | `use_filter_snowball=true, language=english` (or the supported language required) |
| Token-length filtering | `use_filter_length=true, filter_length_min=2, filter_length_max=40` |
| Substrings within words | `use_filter_ngram=true` plus n-gram length bounds |
| Prefix completion | `use_filter_edge_ngram=true` plus n-gram length bounds |

The numbers above are examples. Length filtering discards tokens outside the range during indexing and search. Source: [analyzer parameters](https://ydb.tech/docs/en/yql/reference/syntax/create_table/fulltext_index?version=main).

For substring matching, create a separate plain index over `body` with n-grams, for example `use_filter_ngram=true`, `filter_ngram_min_length=3`, and `filter_ngram_max_length=5`. Query through that index with `FulltextMatch(body, $pattern, "Wildcard" AS Mode)`, binding a pattern such as `%learn%`. `LIKE`/`ILIKE` on the indexed column through its `VIEW` can also use the n-gram index. Ordinary token indexing alone does not supply arbitrary substring search.

## Filtered search and writes

For tenant-scoped search, first extend the application schema and ingestion with a populated tenant column; it is absent from the shared demonstration schema. An index on `(tenant, body)` requires `tenant = $tenant` alongside the single full-text predicate. With more filter columns, constrain every one by equality; the text column is last and predicate order is unrestricted.

Keep filter columns separate from the primary key in this variation. The inspected schema validation prohibits a prefix containing all primary-key columns; older docs state the broader restriction that filter columns cannot be primary-key columns. Check the target if a prefix overlaps a composite key. Prefixed relevance indexes require support for filtered full-text indexes and the compact full-text implementation; their default availability by branch is in [compatibility](compatibility.md).

Full-text indexes are maintained for `INSERT`, `UPSERT`, `REPLACE`, `UPDATE`, and `DELETE`; `BulkUpsert` on an indexed table is unsupported. A single `Uint64`/`Int64`/`Uint32`/`Int32` primary key supplies document IDs directly. With the row-ID feature enabled, other keys use the auto-managed `__ydb_row_id` column and `__ydb_unique_row_id` index. Omit the system column from writes; YDB populates it, and the unique index must remain while full-text indexes depend on it. Support for those keys in full-text search does not remove hybrid search's single-column key restriction.
