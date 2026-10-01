---
name: ydb-table
description: "Use only for YDB table and data-access work: writing or auditing YQL; designing tables and primary keys; reading `EXPLAIN`; executing parameterized `ydb sql`; converting PostgreSQL/MySQL SQL and schemas to YDB; BulkUpsert and batched writes; and reviewing Java, Go, C++, or Python application code that executes YDB queries or transactions. Triggers include YQL (`SELECT`, `UPSERT`, `DECLARE`, `AS_TABLE`, `Knn::ToBinaryStringFloat`, `FloatVector`, `CREATE TABLE`, `ALTER TABLE`), `ydb sql`, `--explain`, `--param`, YDB SDK query/transaction types, ydb-java-sdk, ydb-jdbc-driver, Hibernate or Spring Data JPA with YDB, `ydb-go-sdk/v3`, `ydb-cpp-sdk`, and `ydb.QuerySessionPool`. For Python, cover FloatVector parameter encoding and YQL/schema/transaction modes; for C#, cover only YQL, schema, and transaction modes and refer SDK details upstream."
---

# YDB Table

Writing YQL against YDB tables, designing schemas to back those queries, and auditing application code that runs them.

## Workflow

1. **Classify the task.** Write a new query or schema, execute SQL with YDB CLI, audit existing code, convert from another SQL dialect, or read an `EXPLAIN`.
2. **Load sources** per the table below.
3. **Do the work.** When auditing, cite `RULE-JV-NN`, `RULE-GO-NN`, `RULE-CPP-NN`, or `RULE-PY-NN`. C++ audits: never empty, never rule-ID-only — use the 4-part format in `rules/cpp.md` (ID + diagnosis in sentence 1, then trigger, failure mode, fix).

## Load sources

| Task                                                | Files to consult                                                                          |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Executing or explaining SQL with YDB CLI            | `references/cli.md`; activate `ydb-core` separately for connection context                                       |
| Parameter binding, CLI value encoding, `DECLARE` syntax and compatibility | `references/query-parameters.md`                                             |
| Reads, writes, transaction modes, batch vs bulk     | `references/working-with-data.md`                                                         |
| Writing Java application code against YDB           | `embed/java.md`                                                                |
| Auditing Java application code against YDB          | `rules/java.md`                                                                     |
| Writing Go application code against YDB             | `embed/go.md`                                                                  |
| Auditing Go application code against YDB            | `rules/go.md`                                                                       |
| Writing C++ application code against YDB            | `embed/cpp.md`                                                                 |
| Auditing C++ application code against YDB           | `rules/cpp.md`                                                                      |
| Writing Python FloatVector parameters                | `embed/python.md`                                                              |
| Auditing Python FloatVector parameters               | `rules/python.md`                                                                   |
| Schema design — primary key shape, partitioning     | `references/working-with-data.md`; activate `ydb-core` for schema fundamentals                                                      |
| YQL syntax, built-in functions, pragmas             | <https://ydb.tech/docs/en/yql/reference/> — do not reproduce the spec from memory         |

## Content rules

- Always parameterize: bind values through the SDK's typed parameter API (e.g. `ydb.ParamsBuilder()` in Go, `TParamsBuilder` in C++, `PreparedStatement` in JDBC), do not concatenate them into the query text. Plan-cache reuse depends on it; concatenated literals miss the cache. `DECLARE` only describes parameter types and never replaces binding; load `references/query-parameters.md` before deciding whether to emit it.
- For CLI parameter answers, inspect `ydb sql -hh` before using advanced input flags and show that discovery command when the user asks for a command without allowing execution. Specify `--input-format` explicitly for every input file; do not omit `json` merely because it is the default.
- For every agent or CI non-TTY parameter file, emit `--input-file - < path`; never emit a named `--input-file path`. A named path is only for an interactive terminal or an explicitly allocated PTY. Keep query text in `-s` or `-f` when stdin carries parameters.
- For application-provided `FloatVector` embeddings, follow the current [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) to serialize on the client and bind binary YQL `String`; flag `List<Float>` parameters converted by `Knn::ToBinaryStringFloat` in YQL. This does not apply to vectors constructed in YQL or to `Int8Vector`, `Uint8Vector`, and `BitVector`; see `references/query-parameters.md`.
- Prefer the Query Service over the deprecated Table Service for new code.
- Propagate the caller's deadline and cancellation through one shared budget covering session acquisition, retries, the RPC, and result draining. Load the matching language reference before suggesting concrete APIs; cancellation is not proof that a write rolled back.
- When converting from another SQL dialect, surface where YDB diverges — primary keys are partition keys, no `SERIAL` / `AUTO_INCREMENT`, JOIN behavior and built-in function names differ — rather than producing code that happens to parse.
- Don't fabricate YQL syntax, built-in names, or SDK symbols. If the loaded sources don't cover the question, link the relevant page under <https://ydb.tech/docs/en/yql/reference/> and state the uncertainty.
