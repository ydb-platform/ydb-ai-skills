# Full-text indexes and BM25

Use `fulltext_plain` for matching/filtering and `fulltext_relevance` for BM25 scoring. Each index has one indexed text column (`String` or `Utf8`), optionally preceded by filter columns; `COVER` adds payload columns. These are synchronous indexes on row-oriented tables.

Sources: [full-text guide](https://ydb.tech/docs/en/dev/fulltext-indexes?version=main), [DDL](https://ydb.tech/docs/en/yql/reference/syntax/create_table/fulltext_index?version=main), [SELECT](https://ydb.tech/docs/en/yql/reference/syntax/select/fulltext_index?version=main), and [built-ins](https://ydb.tech/docs/en/yql/reference/builtins/fulltext?version=main). See [compatibility](compatibility.md) before using prefixes or non-integer/composite primary keys.

## Create and rank

```yql
CREATE TABLE articles (
    id Uint64 NOT NULL,
    tenant Utf8,
    title Utf8,
    body Utf8,
    INDEX ft_idx GLOBAL USING fulltext_relevance
      ON (body) COVER (title)
      WITH (tokenizer=standard, use_filter_lowercase=true),
    PRIMARY KEY (id)
);
```

For an existing table, use the same index clause after `ALTER TABLE articles ADD INDEX ft_idx`. Unlike a k-means vector index, a full-text index can usefully be created before inserting documents.

```yql
DECLARE $query_text AS String;

SELECT id, title, FulltextScore(body, $query_text) AS relevance
FROM articles VIEW ft_idx
WHERE FulltextScore(body, $query_text) > 0
ORDER BY relevance DESC
LIMIT 10;
```

Use an identical scoring expression, including named options, in `SELECT` and `WHERE`; a `SELECT` alias is unavailable in `WHERE`. The standalone relevance access requires the `> 0` predicate. `FulltextScore` needs `fulltext_relevance`, while `FulltextMatch` can also use a plain index:

```yql
DECLARE $query_text AS String;

SELECT id, title
FROM articles VIEW ft_idx
WHERE FulltextMatch(body, $query_text)
LIMIT 20;
```

Standalone full-text functions require explicit `VIEW`. One read supports one full-text predicate, combined with other filters using `AND`; SQL `OR`/`NOT` around full-text predicates and mixing `FulltextMatch` with `FulltextScore` in one `WHERE` are unsupported. Query-language term operators are a separate mechanism.

## Query semantics and analyzers

Only the first two function arguments are positional; optional settings use `value AS Name`:

```yql
DECLARE $query_text AS String;

SELECT id
FROM articles VIEW ft_idx
WHERE FulltextMatch(body, $query_text,
                    "Keywords" AS Mode,
                    "Or" AS DefaultOperator,
                    "50%" AS MinimumShouldMatch)
LIMIT 20;
```

`Keywords` is the default mode and `And` the default term operator. With `Or`, `+term` is required, and `MinimumShouldMatch` counts only optional terms (a number or percentage supplied as a string). `Query` mode supports required/excluded terms and quoted phrases. `Wildcard` mode uses `%` and `_` and requires n-grams.

`FulltextScore` accepts `DefaultOperator`, `MinimumShouldMatch` (with `Or`), and numeric `K1`/`B` BM25 settings. Keep its options distinct from `FulltextMatch`'s `Mode`; do not infer that every matching option is also a scoring option.

Choose analyzer settings at index creation according to the desired matching:

| Requirement | Settings |
|---|---|
| Words split on whitespace/punctuation | `tokenizer=standard` |
| Whitespace splitting or whole-value tokens | `tokenizer=whitespace` or `tokenizer=keyword` |
| Case normalization | `use_filter_lowercase=true` |
| Stemming | `use_filter_snowball=true, language=english` (or the supported language required) |
| Token-length filtering | `use_filter_length=true, filter_length_min=2, filter_length_max=40` |
| Substrings within words | `use_filter_ngram=true` plus n-gram length bounds |
| Prefix completion | `use_filter_edge_ngram=true` plus n-gram length bounds |

The numbers above are examples. Length filtering discards tokens outside the range during indexing and search. Source: [analyzer parameters](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/docs/en/core/yql/reference/syntax/_includes/fulltext_index_parameters.md).

## Substrings

```yql
ALTER TABLE articles
  ADD INDEX ft_ngram_idx
  GLOBAL USING fulltext_plain
  ON (body)
  WITH (tokenizer=standard, use_filter_lowercase=true,
        use_filter_ngram=true,
        filter_ngram_min_length=3, filter_ngram_max_length=5);
```

```yql
DECLARE $pattern AS String;

SELECT id, title
FROM articles VIEW ft_ngram_idx
WHERE FulltextMatch(body, $pattern, "Wildcard" AS Mode)
LIMIT 20;
```

For example, bind `%learn%` as the pattern. `LIKE`/`ILIKE` on the indexed column through this `VIEW` can also use the n-gram index. Ordinary token indexing alone does not supply arbitrary substring search.

## Filtered search and writes

When the target supports full-text prefixes and compact relevance indexes, index `(tenant, body)` and constrain **every** filter column by equality:

```yql
ALTER TABLE articles
  ADD INDEX tenant_ft_idx
  GLOBAL USING fulltext_relevance
  ON (tenant, body)
  WITH (tokenizer=standard, use_filter_lowercase=true);
```

```yql
DECLARE $tenant AS Utf8;
DECLARE $query_text AS String;

SELECT id, title, FulltextScore(body, $query_text) AS relevance
FROM articles VIEW tenant_ft_idx
WHERE tenant = $tenant AND FulltextScore(body, $query_text) > 0
ORDER BY relevance DESC
LIMIT 10;
```

The text column is last, and equality predicates may be written in any order. Keep filter columns separate from the primary key in this pattern. The inspected schema validation prohibits a prefix containing all primary-key columns; its docs state the broader restriction that filter columns cannot be primary-key columns. Check the target if a prefix overlaps a composite key. Prefixed relevance indexes require both `EnableFulltextIndexPrefix` and the compact implementation selected by `EnableCompactFulltextIndex` in this snapshot; see [compatibility](compatibility.md).

Full-text indexes are maintained for `INSERT`, `UPSERT`, `REPLACE`, `UPDATE`, and `DELETE`; `BulkUpsert` on an indexed table is unsupported. A single `Uint64`/`Int64`/`Uint32`/`Int32` primary key supplies document IDs directly. With the row-ID feature enabled, other keys use the auto-managed `__ydb_row_id` column and `__ydb_unique_row_id` index. Omit the system column from writes; YDB populates it, and the unique index must remain while full-text indexes depend on it. Support for those keys in full-text search does not remove hybrid search's single-column key restriction.
