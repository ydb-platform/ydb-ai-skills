---
name: ydb-table
description: "Open and read this SKILL.md file before answering requests to write, explain, execute or review SQL/YQL queries or query-oriented schemas for the YDB database, or to audit YDB code/configuration in Go, C++ or Java/JDBC/ORM (including driver initialization and balancing), or Python FloatVector parameter handling. This includes short syntax questions, parameters, transactions, EXPLAIN and SQL migration to YDB. Otherwise do not activate or open this skill, even to check applicability. YQL on YT/YTsaurus is outside scope. General YDB introductions/comparisons, local setup, connection/authentication, SDK selection and shared client policy belong to ydb-core; SDK code/configuration reviews may also use core for shared driver/session policy. Standalone official-documentation lookup belongs to ydb-docs. SQL/YQL review applies in any host language. For audits, read the matching language rules; Python covers FloatVector only."
---

# YDB Table

Writing YQL against YDB tables, designing schemas to back those queries, and auditing application code that runs them.

SQL/YQL query and schema work applies regardless of the application's host language. Language-specific SDK/ORM audits cover Go, C++ and Java/JDBC/ORM; Python coverage is limited to FloatVector parameter handling. Other SDK-specific audits, including C#/JS/TS and other Python features, are outside the maintained rule set. For those tasks, use official SDK documentation and state the coverage limit.

## Workflow

1. **Classify the task.** Write a new query or schema, execute SQL with YDB CLI, audit existing code, convert from another SQL dialect, or read an `EXPLAIN`.
2. **Load sources** per the table below before drafting YQL or reviewing code. A request to check existing SDK code or configuration within the supported scope is an audit. Read the matching language rules before evaluating it, even when the question is short or the API looks familiar. For other SDKs, distinguish SQL/YQL findings from SDK-specific claims; do not look for a language rule file that is not listed below. Resolve the language rule links in the table from this skill's directory. The same-named file in `ydb-core` provides additional client-policy checks and does not replace table's audit rules.
3. **Do the work.** Report each matched audit finding as **rule ID — problem — why it matters — fix**. Use the actual `RULE-JV-NN`, `RULE-GO-NN`, `RULE-CPP-NN`, or `RULE-PY-NN` from the loaded rule; the ID lets the user trace the finding to its rationale. Check the rule's preconditions against the supplied code before assigning a finding or severity. Keep optional style improvements separate from defects and required fixes; when surrounding configuration or code is missing, state what needs verification rather than treating it as absent. Before sending an audit, check that every rule-based finding names its ID in the answer and gives a concrete correction; do not cite a rule whose preconditions are not established. C++ findings use the format in [C++ rules](rules/embed/cpp.md).

## Load sources

| Task                                                | Files to consult                                                                          |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Executing or explaining SQL with YDB CLI            | [references/cli.md](references/cli.md); activate `ydb-core` separately for connection context                                       |
| Parameter binding, CLI value encoding, `DECLARE` syntax and compatibility | [references/query-parameters.md](references/query-parameters.md)                                             |
| Reads, writes, transaction modes, batch vs bulk     | [references/working-with-data.md](references/working-with-data.md)                                                         |
| Writing Java application code against YDB           | [references/embed/java.md](references/embed/java.md)                                                                |
| Auditing Java application code against YDB          | [ydb-table/rules/embed/java.md](rules/embed/java.md)                                                                     |
| Writing Go application code against YDB             | [references/embed/go.md](references/embed/go.md)                                                                  |
| Auditing Go application code against YDB            | [ydb-table/rules/embed/go.md](rules/embed/go.md)                                                                       |
| Writing C++ application code against YDB            | [references/embed/cpp.md](references/embed/cpp.md)                                                                 |
| Auditing C++ application code against YDB           | [ydb-table/rules/embed/cpp.md](rules/embed/cpp.md)                                                                      |
| Writing Python FloatVector parameters                | [references/embed/python.md](references/embed/python.md)                                                              |
| Auditing Python FloatVector parameters               | [ydb-table/rules/embed/python.md](rules/embed/python.md)                                                                   |
| Schema design — primary key shape, partitioning     | [references/working-with-data.md](references/working-with-data.md); activate `ydb-core` for schema fundamentals                                                      |
| Converting serial/auto-increment keys to YDB         | [references/working-with-data.md](references/working-with-data.md#serial-columns-and-sql-conversion) |
| YQL syntax, built-in functions, pragmas             | <https://ydb.tech/docs/en/yql/reference/> — do not reproduce the spec from memory         |

## Content rules

- For SQL/YQL through YDB CLI, use `ydb sql`; use `ydb sql --explain` for a non-executing plan. This applies to commands launched by scripts and subprocess wrappers as well as commands shown to a user. Do not introduce the deprecated query entry points `ydb table query execute`, `ydb table query explain`, `ydb yql`, or `ydb scripting yql` into new workflows. Discuss them only to explain migration or a verified compatibility constraint; see [CLI guidance](references/cli.md).
- Always parameterize: bind values through the SDK's typed parameter API (e.g. `ydb.ParamsBuilder()` in Go, `TParamsBuilder` in C++, `PreparedStatement` in JDBC), do not concatenate them into the query text. Plan-cache reuse depends on it; concatenated literals miss the cache. `DECLARE` only describes parameter types and never replaces binding; load [references/query-parameters.md](references/query-parameters.md) before deciding whether to emit it.
- For CLI parameter answers, inspect `ydb sql -hh` before using advanced input flags and show that discovery command when the user asks for a command without allowing execution. Specify `--input-format` explicitly for every input file; do not omit `json` merely because it is the default.
- For every agent or CI non-TTY parameter file, emit `--input-file - < path`; never emit a named `--input-file path`. A named path is only for an interactive terminal or an explicitly allocated PTY. Keep query text in `-s` or `-f` when stdin carries parameters.
- For application-provided `FloatVector` embeddings, follow the current [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) to serialize on the client and bind binary YQL `String`; flag `List<Float>` parameters converted by `Knn::ToBinaryStringFloat` in YQL. This does not apply to vectors constructed in YQL or to `Int8Vector`, `Uint8Vector`, and `BitVector`; see [references/query-parameters.md](references/query-parameters.md).
- Use Query Service for SQL/query execution whenever it supports the required functionality, especially for new code. When reviewing existing Table Service code, recommend migration to Query Service where equivalent functionality is available. A targeted fix to the existing Table Service implementation may be useful for compatibility, but do not present it as the default for new users. Choose Table Service only for required functionality not available through Query Service and explain that constraint.
- Propagate the caller's deadline and cancellation through one shared budget covering session acquisition, retries, the RPC, and result draining. Load the matching language reference when available; otherwise verify concrete APIs in official SDK documentation. Cancellation is not proof that a write rolled back.
- When converting from another SQL dialect, check the target YDB version and explain differences in primary-key distribution, JOIN behavior, and built-in functions. For [Serial columns](references/working-with-data.md#serial-columns-and-sql-conversion), verify support in that version; if it is unknown, make availability conditional. Distinguish support from the hot-partition risk of a monotonic key, and do not transplant PostgreSQL/MySQL sequence syntax without verification.
- Don't fabricate YQL syntax, built-in names, or SDK symbols. If the loaded sources don't cover the question, link the relevant page under <https://ydb.tech/docs/en/yql/reference/> and state the uncertainty.
