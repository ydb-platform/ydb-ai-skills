---
name: ydb-table
description: "Write, explain, and audit YDB table queries, schemas, and data access. Use for YQL pagination, primary keys and partitioning, query parameters, `ydb sql`, SQL-to-YQL conversion, and reviews of Java JDBC/Hibernate/Spring Data configuration or write patterns, Go query/transaction handlers, and C++ query/retry code. Includes caller deadline and cancellation propagation in query code and Python FloatVector parameter encoding. Use ydb-core for connection/authentication, SDK selection, or general client policy without a query/code audit. YQL on YT alone is outside this skill."
---

# YDB Table

Writing YQL against YDB tables, designing schemas to back those queries, and auditing application code that runs them.

## Workflow

1. **Classify the task.** Write a new query or schema, execute SQL with YDB CLI, audit existing code, convert from another SQL dialect, or read an `EXPLAIN`.
2. **Load sources** per the table below before drafting YQL or reviewing code. For an audit, read the matching language rules and match the findings to the supplied code.
3. **Do the work.** Report each matched audit finding as **rule ID — problem — why it matters — fix**. Use the actual `RULE-JV-NN`, `RULE-GO-NN`, `RULE-CPP-NN`, or `RULE-PY-NN` from the loaded rule; the ID lets the user trace the finding to its rationale. C++ findings use the format in [C++ rules](rules/cpp.md).

## Load sources

| Task                                                | Files to consult                                                                          |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Executing or explaining SQL with YDB CLI            | [references/cli.md](references/cli.md); activate `ydb-core` separately for connection context                                       |
| Parameter binding, CLI value encoding, `DECLARE` syntax and compatibility | [references/query-parameters.md](references/query-parameters.md)                                             |
| Reads, writes, transaction modes, batch vs bulk     | [references/working-with-data.md](references/working-with-data.md)                                                         |
| Writing Java application code against YDB           | [embed/java.md](embed/java.md)                                                                |
| Auditing Java application code against YDB          | [rules/java.md](rules/java.md)                                                                     |
| Writing Go application code against YDB             | [embed/go.md](embed/go.md)                                                                  |
| Auditing Go application code against YDB            | [rules/go.md](rules/go.md)                                                                       |
| Writing C++ application code against YDB            | [embed/cpp.md](embed/cpp.md)                                                                 |
| Auditing C++ application code against YDB           | [rules/cpp.md](rules/cpp.md)                                                                      |
| Writing Python FloatVector parameters                | [embed/python.md](embed/python.md)                                                              |
| Auditing Python FloatVector parameters               | [rules/python.md](rules/python.md)                                                                   |
| Schema design — primary key shape, partitioning     | [references/working-with-data.md](references/working-with-data.md); activate `ydb-core` for schema fundamentals                                                      |
| Converting serial/auto-increment keys to YDB         | [references/working-with-data.md](references/working-with-data.md#serial-columns-and-sql-conversion) |
| YQL syntax, built-in functions, pragmas             | <https://ydb.tech/docs/en/yql/reference/> — do not reproduce the spec from memory         |

## Content rules

- Always parameterize: bind values through the SDK's typed parameter API (e.g. `ydb.ParamsBuilder()` in Go, `TParamsBuilder` in C++, `PreparedStatement` in JDBC), do not concatenate them into the query text. Plan-cache reuse depends on it; concatenated literals miss the cache. `DECLARE` only describes parameter types and never replaces binding; load [references/query-parameters.md](references/query-parameters.md) before deciding whether to emit it.
- For CLI parameter answers, inspect `ydb sql -hh` before using advanced input flags and show that discovery command when the user asks for a command without allowing execution. Specify `--input-format` explicitly for every input file; do not omit `json` merely because it is the default.
- For every agent or CI non-TTY parameter file, emit `--input-file - < path`; never emit a named `--input-file path`. A named path is only for an interactive terminal or an explicitly allocated PTY. Keep query text in `-s` or `-f` when stdin carries parameters.
- For application-provided `FloatVector` embeddings, follow the current [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) to serialize on the client and bind binary YQL `String`; flag `List<Float>` parameters converted by `Knn::ToBinaryStringFloat` in YQL. This does not apply to vectors constructed in YQL or to `Int8Vector`, `Uint8Vector`, and `BitVector`; see [references/query-parameters.md](references/query-parameters.md).
- Prefer the Query Service over the deprecated Table Service for new code.
- Propagate the caller's deadline and cancellation through one shared budget covering session acquisition, retries, the RPC, and result draining. Load the matching language reference before suggesting concrete APIs; cancellation is not proof that a write rolled back.
- When converting from another SQL dialect, check the target YDB version and explain differences in primary-key distribution, JOIN behavior, and built-in functions. YDB v26.1 documents [Serial types](https://ydb.tech/docs/en/yql/reference/types/serial?version=v26.1) for primary-key columns; distinguish their availability from the hot-partition risk of a monotonic key, and do not transplant PostgreSQL/MySQL sequence syntax without verification.
- Don't fabricate YQL syntax, built-in names, or SDK symbols. If the loaded sources don't cover the question, link the relevant page under <https://ydb.tech/docs/en/yql/reference/> and state the uncertainty.
