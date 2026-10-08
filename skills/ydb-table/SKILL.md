---
name: ydb-table
description: Writing and auditing code that runs YQL against YDB tables. Use when the user writes a query, designs a table or primary key, reads an `EXPLAIN`, executes SQL with `ydb sql`, passes typed YDB query parameters or JSON/CSV/TSV/raw parameter files, or asks to review Java (ydb-java-sdk, ydb-jdbc-driver, Hibernate, Spring Data JPA), Go (`ydb-go-sdk/v3`), or C++ (`ydb-cpp-sdk`) application code that talks to YDB, or Python (`ydb.QuerySessionPool`) FloatVector parameter code. Triggers on `ydb sql`, `--explain`, `--explain-analyze`, `--param`, `--input-file`, `--input-format`, `--input-framing`, `--input-param-name`, `--input-batch`, Arrow/CSV/TSV parameter-file questions, YQL keywords (`UPSERT`, `SELECT`, `DECLARE`, `AS_TABLE`, `Knn::ToBinaryStringFloat`, `FloatVector`, `VIEW <index>`, `CREATE TABLE`, `ALTER TABLE`, `EXPLAIN`, `Serial`, `SmallSerial`, `BigSerial`), on the `BulkUpsert` SDK API, on JDBC / Hibernate / Spring symbols (`JpaRepository`, `findAllById`, `saveAll`, `deleteAllByIdInBatch`, `hibernate.jdbc.batch_size`, `@Version`, `@Retryable`, `SQLRecoverableException`, `SQLTransientException`, `ExecuteQuerySettings.withRequestTimeout`, `SessionRetryContext`, `SessionRetryContext.supplyResult`), on `ydb-go-sdk/v3` symbols (`ydb.Open`, `db.Query().Do`, `db.Query().DoTx`, `db.Table().Do`, `query.WithIdempotent`, `query.WithCommit`, `query.WithStatsMode`, `query.Stats`, `query.StatsModeBasic`, `result.Close`, `context.WithTimeout`, `context.Background`, `ydb.WithLazyTx`, `ydb.ParamsBuilder`, `s.BeginTransaction`, `table.TxControl`, `table.BeginTx`, `BulkUpsertDataRows`, `sugar.Embedding`, `balancers.PreferLocalDC`, `balancers.PreferNearestDC`), on `ydb-cpp-sdk` symbols (`#include <ydb-cpp-sdk/client/`, `NYdb::TDriver`, `TDriverConfig`, `NYdb::NQuery::TQueryClient`, `NYdb::NTable::TTableClient`, `RetryQuerySync`, `RetryOperationSync`, `TRetryOperationSettings`, `TRetryOperationSettings::CancellationToken`, `ClientTimeout`, `TDeadline`, `Deadline`, `MaxTimeout`, `TParamsBuilder`, `TTxControl`, `TValueBuilder`, `TResultSetParser`, `StreamExecuteQuery`, `BulkUpsert`, `ExecuteSchemeQuery`, `CreateFromEnvironment`, `GetValueSync`, `find_package(ydb-cpp-sdk`, `YDB-CPP-SDK::`), on flaky empty/zero query stats right after `Query` returns, on YDB transaction-mode names (`SerializableRW`, `SnapshotRO`), and on PostgreSQL / MySQL → YDB conversion prompts. For Python, this skill covers FloatVector parameter encoding and YQL / schema / transaction modes; other Python SDK behavior and C# SDK specifics remain outside this skill — point at upstream docs.
---

# YDB Table

Writing YQL against YDB tables, designing schemas to back those queries, and auditing application code that runs them.

## Workflow

1. **Classify the task.** Write a new query or schema, execute SQL with YDB CLI, audit existing code, convert from another SQL dialect, or read an `EXPLAIN`.
2. **Load sources** per the table below.
3. **Do the work.** When auditing, cite `RULE-JV-NN`, `RULE-GO-NN`, `RULE-CPP-NN`, or `RULE-PY-NN`. C++ audits: never empty, never rule-ID-only — use the 4-part format in `rules/embed/cpp.md` (ID + diagnosis in sentence 1, then trigger, failure mode, fix).

## Load sources

| Task                                                | Files to consult                                                                          |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Executing or explaining SQL with YDB CLI            | `references/cli.md` and `../ydb-core/SKILL.md#cli`                                       |
| Parameter binding, CLI value encoding, `DECLARE` syntax and compatibility | `references/query-parameters.md`                                             |
| Reads, writes, transaction modes, batch vs bulk     | `references/working-with-data.md`                                                         |
| Writing Java application code against YDB           | `references/embed/java.md`                                                                |
| Auditing Java application code against YDB          | `rules/embed/java.md`                                                                     |
| Writing Go application code against YDB             | `references/embed/go.md`                                                                  |
| Auditing Go application code against YDB            | `rules/embed/go.md`                                                                       |
| Writing C++ application code against YDB            | `references/embed/cpp.md`                                                                 |
| Auditing C++ application code against YDB           | `rules/embed/cpp.md`                                                                      |
| Writing Python FloatVector parameters                | `references/embed/python.md`                                                              |
| Auditing Python FloatVector parameters               | `rules/embed/python.md`                                                                   |
| Schema design — primary key shape, partitioning     | `../ydb-core/SKILL.md#schema-basics`                                                      |
| YQL syntax, built-in functions, pragmas             | <https://ydb.tech/docs/en/yql/reference/> — do not reproduce the spec from memory         |

## Content rules

- Always parameterize: bind values through the SDK's typed parameter API (e.g. `ydb.ParamsBuilder()` in Go, `TParamsBuilder` in C++, `PreparedStatement` in JDBC), do not concatenate them into the query text. Plan-cache reuse depends on it; concatenated literals miss the cache. `DECLARE` only describes parameter types and never replaces binding; load `references/query-parameters.md` before deciding whether to emit it.
- For CLI parameter answers, inspect `ydb sql -hh` before using advanced input flags and show that discovery command when the user asks for a command without allowing execution. Specify `--input-format` explicitly for every input file; do not omit `json` merely because it is the default.
- For every agent or CI non-TTY parameter file, emit `--input-file - < path`; never emit a named `--input-file path`. A named path is only for an interactive terminal or an explicitly allocated PTY. Keep query text in `-s` or `-f` when stdin carries parameters.
- For application-provided `FloatVector` embeddings, follow the current [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) to serialize on the client and bind binary YQL `String`; flag `List<Float>` parameters converted by `Knn::ToBinaryStringFloat` in YQL. This does not apply to vectors constructed in YQL or to `Int8Vector`, `Uint8Vector`, and `BitVector`; see `references/query-parameters.md`.
- Prefer the Query Service over the deprecated Table Service for new code.
- Propagate the caller's deadline and cancellation through one shared budget covering session acquisition, retries, the RPC, and result draining. Load the matching language reference before suggesting concrete APIs; cancellation is not proof that a write rolled back.
- When converting PostgreSQL schemas with generated integer IDs, determine the target YDB server version and load the single version/feature matrix in `../ydb-core/SKILL.md#schema-basics` before choosing a type. If the version is unknown, ask for it or give explicitly conditioned paths. When serial support is absent or disabled for a PostgreSQL integer ID, use a client-generated numeric `Int64` and supply it explicitly. Preserve signedness for ordinary integer columns: PostgreSQL `BIGINT` maps to YDB `Int64`, not `Uint64`. `ALTER TABLE ... ADD COLUMN ... Serial` and `AUTO_INCREMENT` are unsupported. Also surface other YDB differences such as primary-key partitioning, JOIN behavior, and built-in function names rather than producing code that merely parses.
- Don't fabricate YQL syntax, built-in names, or SDK symbols. If the loaded sources don't cover the question, link the relevant page under <https://ydb.tech/docs/en/yql/reference/> and state the uncertainty.
