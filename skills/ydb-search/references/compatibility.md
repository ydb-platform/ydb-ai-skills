# Source provenance and compatibility

This skill was grounded in the supplied `ydb-platform/ydb` checkout at commit [`4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7`](https://github.com/ydb-platform/ydb/tree/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7), inspected on 2026-10-02. Local paths below are relative to that repository root; the installed skill does not require the author's filesystem path. Online `main` documentation can advance independently of this snapshot and of a deployed server.

For a specified server version, consult that version's documentation and implementation. Otherwise give the grounded query pattern with explicit availability assumptions. When documentation and source disagree, describe the difference and check the target; do not infer a release introduction from source presence or a test fixture.

## Differences that affect generated SQL

| Topic | Evidence in this checkout | Consequence |
|---|---|---|
| Vector probing default | `GetKMeansTreeSearchTopSize` uses 4 with overlapping clusters, 10 otherwise; bundled vector docs still say 1 | Set `PRAGMA ydb.KMeansTreeSearchTopSize` explicitly; do not teach 1 as a universal current default |
| Hybrid prefixes | Bundled hybrid docs say prefixed vector indexes are unsupported; `KqpRewriteHybridRankTopSort` and tests support them with equality bindings | Verify target support; full-text needs all prefix columns, vector needs a nonempty contiguous leading prefix |
| Hybrid primary key | The optimizer rejects `KeyColumnNames.size() != 1` | Require a single-column key for this implementation |
| Hybrid availability | `TTableServiceConfig.EnableHybridSearch` has proto default false; comments/tests describe or enable a different default | Check effective server configuration; do not assume the feature is enabled |
| Full-text prefixes and row IDs | `EnableFulltextIndexPrefix` and `EnableFulltextIndexRowId` have proto defaults false; tests enable them | Verify effective flags before recommending prefixes or non-integer/composite keys |
| Prefixed BM25 | Schema validation rejects the old prefixed relevance implementation; tests enable `EnableCompactFulltextIndex` (proto default false) | Prefixed `fulltext_relevance` requires compact indexes as well as prefix support in this snapshot |
| Full-text prefixes overlapping the primary key | Docs prohibit any overlap; schema validation rejects prefixes containing all primary-key columns | Keep filter columns outside the key in the portable examples; inspect target support before using partial overlap with a composite key |

Proto defaults describe this snapshot, not every cluster's effective settings. Feature verification is not an instruction to change cluster configuration.

## Evidence map

- Vector documentation: `ydb/docs/en/core/dev/vector-indexes.md`, `ydb/docs/en/core/yql/reference/syntax/{create_table,select}/vector_index.md`, `ydb/docs/en/core/yql/reference/udf/list/knn.md`, and `ydb/docs/en/core/recipes/ydb-sdk/vector-search.md`.
- Full-text documentation: `ydb/docs/en/core/dev/fulltext-indexes.md`, `ydb/docs/en/core/yql/reference/syntax/{create_table,select}/fulltext_index.md`, and `ydb/docs/en/core/yql/reference/builtins/fulltext.md`.
- Hybrid documentation: `ydb/docs/en/core/dev/hybrid-search.md` and `ydb/docs/en/core/yql/reference/syntax/select/hybrid_search.md`.
- [Optimizer](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/kqp/opt/logical/kqp_opt_log_indexes.cpp): search for `GetKMeansTreeSearchTopSize`, `KqpRewriteHybridRankTopSort`, `extractPrefixColumns`, `single-column primary key`, and `branchLimit`.
- [Hybrid tests](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/kqp/ut/indexes/hybrid/kqp_hybrid_search_ut.cpp): `UsesPrefixedVectorIndex`, `UsesLeadingSubPrefixWithPkInVectorIndex`, `UsesPrefixedCompactFulltextIndexWithPlainVectorIndex`, `RejectsPartiallyBoundMultiColumnPrefixes`, `ParameterizedLimitWithExplicitLimits`, `AppliesWherePredicate`, and `DisabledByFlag`.
- [Table service configuration](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/protos/table_service_config.proto): `EnableHybridSearch`.
- [Feature flags](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/protos/feature_flags.proto): `EnableVectorIndex`, `EnableFulltextIndex`, `EnableCompactFulltextIndex`, `EnableFulltextIndexPrefix`, and `EnableFulltextIndexRowId`.
- [Full-text schema tests](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/tx/schemeshard/ut_index/ut_fulltext_index.cpp): `CreateTablePrefixDisabled`, `CreateTableRowIdDisabled`.
- [Row-ID enforcement](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/tx/schemeshard/index/index_utils.cpp): `EnableFulltextIndexRowId`.
- [Index schema validation](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/tx/schemeshard/index/index_utils.h): `Only compact prefixed fulltext indexes with relevance are supported` and `index prefix must not contain all primary key columns`.

For updated documentation, start at [YDB's documentation index](https://ydb.tech/llms.txt), preserve the requested product version when following links, and read the actual feature pages. If the requested version cannot be retrieved, state that limitation rather than presenting `main` as verified released behavior.
