# Source provenance and compatibility

The search guidance was checked against `ydb-platform/ydb` **main at [`169565ba`](https://github.com/ydb-platform/ydb/tree/169565bacd19165e6c2c6d5432db89f11b422189)** on 2026-10-02. The original supplied checkout, [`4cdb81ee`](https://github.com/ydb-platform/ydb/tree/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7), is a **stable-26-3-1** snapshot. It is not main, and several defaults and query restrictions differ. Local paths below are relative to the source repository; the installed skill does not require the author's filesystem path.

For a specified server version, consult that version's documentation and implementation. Otherwise give the grounded query pattern with explicit availability assumptions. When documentation and source disagree, describe the difference and check the target; do not infer a release introduction from source presence or a test fixture.

## Branch differences that affect generated SQL

| Topic | stable-26-3-1 at `4cdb81ee` | main at `169565ba` |
|---|---|---|
| Hybrid prefix equalities | Full-text requires every prefix column; vector accepts a nonempty contiguous leading prefix | Both full-text and vector require **every** prefix column; a leading subset is rejected |
| `TTableServiceConfig.EnableHybridSearch` | Proto default `false` | Proto default `true` |
| `EnableFulltextIndexPrefix` | Proto default `false` | Proto default `true` |
| `EnableCompactFulltextIndex` | Proto default `false` | Proto default `true` |
| `EnableFulltextIndexRowId` | Proto default `false` | Proto default `true` |

Main therefore enables those four features by default unless the cluster overrides them. Do not carry stable-branch defaults into an answer about main. For an unknown target, establish the server revision and effective configuration. Feature verification is not an instruction to change cluster configuration.

For hybrid SQL, bind every prefix column unless the requested version has been verified to accept a partial prefix. For example, `ON (Region, Category, Embedding)` needs both `Region = $region` and `Category = $category` on main. The older `UsesLeadingSubPrefixWithPkInVectorIndex` test became `RejectsLeadingSubPrefixWithPkInVectorIndex` on main; it must not be used as evidence that current main accepts a leading subset.

## Other source and documentation differences

- `GetKMeansTreeSearchTopSize` uses 4 with overlapping clusters, 10 otherwise in both inspected snapshots; the older bundled docs say 1. Set the pragma explicitly.
- Both inspected hybrid implementations require a single-column primary key. Standalone full-text row-ID support does not remove this restriction.
- Prefixed `fulltext_relevance` requires the compact implementation and prefix support. These features default on in the inspected main revision.
- Schema validation rejects a full-text prefix containing all primary-key columns; the older docs prohibit any overlap. Keep filter columns outside the key in the examples and inspect target support before using partial overlap with a composite key.
- `vector_type="bit"` works in both snapshots: `OrderByCosineLevel1WithBitQuantization` creates the index and queries it. The older Knn documentation's blanket prohibition is stale. Main additionally has `HalfVectorIndex` coverage for `float16` and `bfloat16`; do not treat the older docs' `float`/`uint8`/`int8` list as exhaustive.

## Evidence map

- Vector documentation: `ydb/docs/en/core/dev/vector-indexes.md`, `ydb/docs/en/core/yql/reference/syntax/{create_table,select}/vector_index.md`, `ydb/docs/en/core/yql/reference/udf/list/knn.md`, and `ydb/docs/en/core/recipes/ydb-sdk/vector-search.md`.
- Full-text documentation: `ydb/docs/en/core/dev/fulltext-indexes.md`, `ydb/docs/en/core/yql/reference/syntax/{create_table,select}/fulltext_index.md`, and `ydb/docs/en/core/yql/reference/builtins/fulltext.md`.
- Hybrid documentation: `ydb/docs/en/core/dev/hybrid-search.md` and `ydb/docs/en/core/yql/reference/syntax/select/hybrid_search.md`.
- [Main optimizer](https://github.com/ydb-platform/ydb/blob/169565bacd19165e6c2c6d5432db89f11b422189/ydb/core/kqp/opt/logical/kqp_opt_log_indexes.cpp): search for `GetKMeansTreeSearchTopSize`, `KqpRewriteHybridRankTopSort`, `extractPrefixColumns`, `single-column primary key`, and `branchLimit`.
- [Main hybrid tests](https://github.com/ydb-platform/ydb/blob/169565bacd19165e6c2c6d5432db89f11b422189/ydb/core/kqp/ut/indexes/hybrid/kqp_hybrid_search_ut.cpp): `UsesPrefixedVectorIndex`, `RejectsLeadingSubPrefixWithPkInVectorIndex`, `UsesPrefixedCompactFulltextIndexWithPlainVectorIndex`, `RejectsPartiallyBoundMultiColumnPrefixes`, `ParameterizedLimitWithExplicitLimits`, `AppliesWherePredicate`, and `DisabledByFlag`.
- `EnableHybridSearch`: [main configuration](https://github.com/ydb-platform/ydb/blob/169565bacd19165e6c2c6d5432db89f11b422189/ydb/core/protos/table_service_config.proto) and [stable-26-3-1 configuration](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/protos/table_service_config.proto).
- Full-text flags: [main definitions](https://github.com/ydb-platform/ydb/blob/169565bacd19165e6c2c6d5432db89f11b422189/ydb/core/protos/feature_flags.proto) and [stable-26-3-1 definitions](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/protos/feature_flags.proto).
- [Main vector tests](https://github.com/ydb-platform/ydb/blob/169565bacd19165e6c2c6d5432db89f11b422189/ydb/core/kqp/ut/indexes/vector/kqp_indexes_vector_ut.cpp): `OrderByCosineLevel1WithBitQuantization`, `HalfVectorIndex`. [Stable bit-index test](https://github.com/ydb-platform/ydb/blob/4cdb81ee6e8a3949acb6d6fb56eff0399d207eb7/ydb/core/kqp/ut/indexes/vector/kqp_indexes_vector_ut.cpp): `OrderByCosineLevel1WithBitQuantization`.
- [Main full-text query tests](https://github.com/ydb-platform/ydb/blob/169565bacd19165e6c2c6d5432db89f11b422189/ydb/core/kqp/ut/indexes/fulltext/kqp_fulltext_search_ut.cpp): `FulltextScore` with `"or" AS DefaultOperator` and `"50%" AS MinimumShouldMatch`, including query terms without `+`.
- [Main index schema validation](https://github.com/ydb-platform/ydb/blob/169565bacd19165e6c2c6d5432db89f11b422189/ydb/core/tx/schemeshard/index/index_utils.h): `Only compact prefixed fulltext indexes with relevance are supported` and `index prefix must not contain all primary key columns`.

For updated documentation, start at [YDB's documentation index](https://ydb.tech/llms.txt), preserve the requested product version when following links, and read the actual feature pages. If the requested version cannot be retrieved, state that limitation rather than presenting `main` as verified released behavior.
