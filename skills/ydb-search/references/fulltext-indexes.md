# Full-text indexes and BM25

Use `fulltext_plain` for matching/filtering and `fulltext_relevance` for BM25 scoring. Each index has one indexed text column (`String` or `Utf8`), optionally preceded by filter columns; `COVER` adds payload columns. These are synchronous indexes on row-oriented tables.

Sources: [full-text guide](https://ydb.tech/docs/en/dev/fulltext-indexes?version=v26.3), [DDL](https://ydb.tech/docs/en/yql/reference/syntax/create_table/fulltext_index?version=v26.3), [SELECT](https://ydb.tech/docs/en/yql/reference/syntax/select/fulltext_index?version=v26.3), and [built-ins](https://ydb.tech/docs/en/yql/reference/builtins/fulltext?version=v26.3).

**Release selection:** standalone full-text indexes are documented as enabled by default in **26.2.1.14**. The 26.2 guide requires a single `Uint64` primary key. Full-text filter columns and arbitrary-key support are described in 26.3 but are listed as disabled by default in 26.3.1.16 RC. Read [version compatibility](version-compatibility.md) before using these extensions or targeting 25.1–26.1.

## Runnable examples

Use the shared `documents` schema in [create-table.sql](../assets/queries/create-table.sql), load it with [upsert.sql](../assets/queries/upsert.sql), add the index with [add-fulltext-index.sql](../assets/queries/add-fulltext-index.sql), and rank results with [fulltext-search.sql](../assets/queries/fulltext-search.sql). These are the same table and data used by vector and hybrid search. The [SDK workflow](sdk.md) and one language page supply parameter binding and execution.

Unlike a k-means vector index, a full-text index can usefully be created before inserting documents. The shared walkthrough loads data first so it can support both search types with one setup sequence.

## Query shape and term semantics

The ranking file uses an identical `FulltextScore(...)` expression, including named options, in `SELECT` and `WHERE ... > 0`, then sorts `score DESC`. A `SELECT` alias is unavailable in `WHERE`; standalone relevance access requires the positive-score predicate and a `fulltext_relevance` index.

For a matching-only variation, use `fulltext_plain`, replace the scoring predicate with `FulltextMatch(body, $query_text)`, and remove the BM25 projection and sort. `FulltextMatch` can also use a relevance index.

Standalone full-text functions require explicit `VIEW`. One read supports one full-text predicate, combined with other filters using `AND`; SQL `OR`/`NOT` around full-text predicates and mixing `FulltextMatch` with `FulltextScore` in one `WHERE` are unsupported. Query-language term operators are a separate mechanism.

Only the first two function arguments are positional; optional settings use `value AS Name`. `Keywords` is the default matching mode and `And` the default term operator. The runnable ranking query explicitly selects `"Or" AS DefaultOperator`.

The 26.3 documentation specifies that, with `Or`, an optional `+` prefix marks that particular term as mandatory. Terms without `+` are optional, and `MinimumShouldMatch` counts only those optional terms (a number or percentage supplied as a string). The 26.2 docs describe `Or` and the threshold without that required-term extension; verify before assuming identical `+` behavior. With no `+`, the threshold applies to the supplied terms in both documented patterns. Preserve the query text; adding `+` changes its meaning. To require half the terms, add `"50%" AS MinimumShouldMatch` to both scoring expressions in the query.

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

The numbers above are examples. Length filtering discards tokens outside the range during indexing and search. Source: [analyzer parameters](https://ydb.tech/docs/en/yql/reference/syntax/create_table/fulltext_index?version=v26.3).

For substring matching, create a separate plain index over `body` with n-grams, for example `use_filter_ngram=true`, `filter_ngram_min_length=3`, and `filter_ngram_max_length=5`. Query through that index with `FulltextMatch(body, $pattern, "Wildcard" AS Mode)`, binding a pattern such as `%learn%`. Ordinary token indexing alone does not supply arbitrary substring search.

## String predicates, coverage, and short patterns

Through `VIEW`, string predicates can select candidates from the full-text index and then check the original text. The following extensions are verified in upstream `main`; confirm support on the target build before assuming they apply to 26.2/26.3. Sources: [predicate and fallback tests](https://github.com/ydb-platform/ydb/blob/04e081e623244fe86a09513a4123ffdbfcdba6c4/ydb/core/kqp/ut/indexes/fulltext/kqp_fulltext_search_ut.cpp#L1991) and [predicate recognition](https://github.com/ydb-platform/ydb/blob/04e081e623244fe86a09513a4123ffdbfcdba6c4/ydb/core/kqp/opt/logical/kqp_opt_log_indexes.cpp#L1728).

| Predicate on the indexed text column | Semantics |
|---|---|
| `body LIKE $pattern` | Case-sensitive `%` / `_` pattern |
| `body ILIKE $pattern` | Case-insensitive pattern; indexed access requires `use_filter_lowercase=true` |
| `body LIKE $pattern ESCAPE '!'` | `!%`, `!_`, and `!!` match literal `%`, `_`, and `!`; also supported with `ILIKE` |
| `body = $text` | Equality of the complete original value, not token membership |
| `StartsWith(body, $prefix)` | Literal prefix of the original value |
| `EndsWith(body, $suffix)` | Literal suffix of the original value |

Use n-grams for substring patterns. `StartsWith`/`EndsWith` arguments are literal strings, so `%` and `_` there are not wildcards. `ESCAPE` is SQL `LIKE`/`ILIKE` syntax; do not add it as an invented `FulltextMatch` option. Bind patterns as parameters and escape literal user input when building a `LIKE` pattern. See [SQL escape syntax](https://ydb.tech/docs/en/yql/reference/syntax/expressions?version=v26.3#check-match).

Setting `use_filter_lowercase=true` enables indexed `ILIKE`; it does not change `LIKE`, equality, or prefix/suffix predicates into case-insensitive comparisons of the original text. Without lowercase normalization, `ILIKE` alone cannot drive this index access and can be rejected through `VIEW`; it can still be a residual filter alongside a supported full-text predicate.

When the analyzer extracts no usable search terms, wildcard/string-predicate access can fall back to scanning the base table and checking the original text. For example, `%ab%` with minimum n-gram length 3 must not be assumed to return no matches or to be accelerated by the index. Primary-key bounds can narrow the fallback scan, and a filtered index still requires every prefix equality. An indexable pattern with no hits is different: it need not trigger a scan. Inspect explain and query statistics for the actual pattern; a small `LIMIT` does not guarantee a cheap scan. Source: [`NgramScanFallback` and `PrefixedNgramScanFallback`](https://github.com/ydb-platform/ydb/blob/04e081e623244fe86a09513a4123ffdbfcdba6c4/ydb/core/kqp/ut/indexes/fulltext/kqp_fulltext_search_ut.cpp#L3314).

`ON (body)` stores search terms, not an implicit copy of the original text. Add `COVER (body, title)` when the query needs the original body for projection or pattern verification as well as the title. Covering all needed columns can avoid base-table lookups for index candidates; it does not eliminate the no-terms scan fallback. Source: [n-gram index helper using `COVER (Text, Data)`](https://github.com/ydb-platform/ydb/blob/04e081e623244fe86a09513a4123ffdbfcdba6c4/ydb/core/kqp/ut/indexes/fulltext/kqp_fulltext_ut_common.cpp#L113). Verify the plan, including any document-ID mapping for arbitrary primary keys.

## Filtered search and writes

For tenant-scoped search using an index prefix, first verify the 26.3 filtered full-text capability is enabled, then extend the application schema and ingestion with a populated tenant column; it is absent from the shared demonstration schema. An index on `(tenant, body)` requires `tenant = $tenant` alongside the single full-text predicate. With more filter columns, constrain every one by equality; the text column is last and predicate order is unrestricted. Do not prescribe this prefix layout as a documented 26.2 feature.

Keep filter columns separate from the primary key in this variation. A prefix containing all primary-key columns is rejected; verify target support before using a prefix that overlaps only part of a composite key. Prefixed relevance indexes require support for filtered full-text indexes and the compact full-text implementation. Check that these capabilities are enabled on the target database.

Full-text indexes are maintained for `INSERT`, `UPSERT`, `REPLACE`, `UPDATE`, and `DELETE`; `BulkUpsert` on an indexed table is unsupported. Keep the shared single `Uint64` key for the documented 26.2 pattern. The 26.3 guide describes `Uint64`/`Int64`/`Uint32`/`Int32` keys supplying document IDs directly and, with arbitrary-key support enabled, other keys using `__ydb_row_id` and `__ydb_unique_row_id`. Omit the system column from writes; YDB populates it, and the unique index must remain while full-text indexes depend on it. For hybrid queries, also verify [primary-key compatibility](version-compatibility.md#limits-that-need-a-release-specific-answer) for the target hybrid implementation.

An `INSERT` earlier in the same explicit read-write transaction is visible to a subsequent `FulltextMatch` query through the index in that transaction; committing between the insert and read is not required. Keep both requests in the same transaction. Upstream `main` tests this for both compact and non-compact indexes: [`FulltextReadYourOwnWrite`](https://github.com/ydb-platform/ydb/blob/04e081e623244fe86a09513a4123ffdbfcdba6c4/ydb/core/kqp/ut/indexes/compact/kqp_fulltext_compact_ut.cpp#L1576). Verify this behavior on older target builds rather than inferring it from post-commit index maintenance alone.
