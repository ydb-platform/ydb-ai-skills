---
name: ydb-core
description: Entry point and router for YDB-related work. Orients an LLM about YDB — what it is, what surfaces it exposes, where to read upstream docs, which specialist skill to load for surface-specific questions. Covers SDK packages, connection strings and auth, local Docker, schema fundamentals, YDB CLI command discovery and scheme inspection, common integrations (ORMs, migration tools, Terraform), client-side balancing, and session lifecycle / resilience under rolling restart. Use when the user asks a general YDB question, mentions YDB without naming a specific surface (queries, topics, coordination), needs setup help, wants to inspect a database with YDB CLI, asks about balancing policies, end-to-end deadline propagation, caller cancellation, shared retry budgets, `BAD_SESSION` / `shutdownHint` / rolling restart, or when another YDB skill needs foundational context. Also triggers on `grpcs://` / `grpc://`, `ydb --help`, `ydb version`, `ydb config profile`, `ydb config info`, `ydb discovery`, `ydb scheme`, `balancers.RandomChoice`, `balancers.PreferNearestDC`, `ydb.WithBalancer`, `session-balancer`, and "getting started with YDB" prompts.
---

# YDB Core

Orientation + router for YDB. Always loaded when the skill fires.

## overview

YDB — open-source distributed SQL DBMS. Repo: https://github.com/ydb-platform/ydb. Docs: https://ydb.tech/docs/en/ (source in repo under `ydb/docs/` — read from there if the rendered site lags).

All four below live in one database namespace as schema objects — path-addressable (`/db/path/to/x`), listable via `ydb scheme ls`:

- **Table** — rows. SQL (dialect: YQL; say "SQL" in conversation).
- **Topic** — persistent ordered message stream; queue-like delivery to multiple subscribers. A Kafka-protocol endpoint is exposed so standard Kafka clients work — but the topic itself is a YDB schema object, not a separate service.
- **Coordination node** — holds semaphores / mutexes / leader-election primitives. Ephemeral semaphores are session-bound: session dies ⇒ lock silently released. Biggest pitfall.
- **Changefeed** — attached to a table, emits row changes into a topic. Not a webhook.

Don't invent concrete strings (env var names, CLI flags, method signatures, YQL built-ins, config keys). Either take from this file or fetch from docs. Extrapolating from PostgreSQL / MySQL / generic SQL is the #1 source of wrong YDB advice. If the linked page below doesn't answer, say so and quote the link.

For documentation lookup, start at https://ydb.tech/llms.txt. Follow its Russian or English index and select the requested product branch; use `main` if no version is specified. Search the index, read the relevant linked Markdown pages, preserve the version query parameter, and cite the pages actually read. `main` is not a guarantee of released behavior. If retrieval fails, state the limitation and try the section links below. This lookup procedure works without any additional skill; `ydb-docs` provides the standalone documentation-lookup workflow.

Where to read what:

- SQL / YQL syntax → https://ydb.tech/docs/en/yql/reference/
- Concepts (architecture, transactions, MVCC, data model) → https://ydb.tech/docs/en/concepts/
- Glossary → https://ydb.tech/docs/en/concepts/glossary
- SDK guides per language → https://ydb.tech/docs/en/reference/ydb-sdk/
- CLI → https://ydb.tech/docs/en/reference/ydb-cli/

## versioning

- Server: CalVer. Current stable at https://github.com/ydb-platform/ydb/releases.
- SDKs version independently per language. Don't assume SDK version tracks server version.

## surfaces

Router to specialist skills:

| Skill | When the question is about |
|---|---|
| `ydb-table` | writing SQL, schema design for query patterns, execution (SDK or CLI), optimization, `EXPLAIN`, secondary indexes, parameterization, SQL-to-YQL conversion |
| `ydb-search` | vector and full-text index design, nearest-neighbor search, BM25, hybrid search with `HybridRank`, search recall and index lifecycle |
| `ydb-topics` | producing/consuming YDB topics, the Kafka-compat endpoint, changefeed configuration on the producer side |
| `ydb-coordination` | distributed locks, semaphores, leader election |

Cluster operations (deployment beyond local, monitoring, backups, capacity) are out of scope of this repo.

## packages

SDKs, all official under https://github.com/ydb-platform/:

| Language | Repo | Install coord | Q | T | C |
|---|---|---|---|---|---|
| Go | ydb-go-sdk | `github.com/ydb-platform/ydb-go-sdk/v3` | ✅ | ✅ | ✅ |
| Python | ydb-python-sdk | PyPI `ydb` | ✅ | ✅ | ✅ |
| Java | ydb-java-sdk | Maven `tech.ydb:ydb-sdk-bom` + `ydb-sdk-query` / `ydb-sdk-topic` / `ydb-sdk-coordination` | ✅ | ✅ | ✅ |
| JS/TS | ydb-js-sdk | npm `@ydbjs/core`, `@ydbjs/query`, `@ydbjs/topic`, `@ydbjs/coordination` | ✅ | ✅ | ✅ |
| C++ | ydb-cpp-sdk | CMake `find_package(ydb-cpp-sdk)` / Debian `libydb-cpp-dev`; link `YDB-CPP-SDK::Driver` + `Query` / `Table` / `Topic` / `Coordination` | ✅ | ✅ | ✅ |

Q = queries, T = topics, C = coordination.

**JDBC driver** (separate from Java SDK): https://github.com/ydb-platform/ydb-jdbc-driver, Maven `tech.ydb.jdbc:ydb-jdbc-driver`. Gateway for JPA/Hibernate/Flyway/Liquibase.

**Kafka clients**: YDB does NOT ship a Kafka adapter package. Use standard Apache Kafka clients (`kafka-clients`, `franz-go`, `confluent-kafka-python`, `kafkajs`) against the YDB Kafka endpoint on port 9092. Docs: https://ydb.tech/docs/en/reference/kafka-api/.

**CLI** (`ydb` binary): install https://ydb.tech/docs/en/reference/ydb-cli/install. Connection and namespace subcommands covered here: `ydb config profile …`, `ydb config info`, `ydb discovery …`, `ydb scheme …`. Query execution (`ydb sql`) — route to the ydb-table skill.

## cli

Treat the installed CLI as a versioned interface whose syntax must be discovered at runtime:

1. Run `ydb version` and `ydb --help` before composing commands for a session.
2. Run `ydb <subcommand> --help` before first use of that command tree; use `-hh` when the regular help says more options are hidden.
3. Keep global connection options before the first subcommand. Preserve the endpoint, database, profile, certificate, and credential options supplied by the user; do not invent or silently replace them.
4. Prefer a non-interactive subcommand. Running `ydb` without a subcommand opens interactive mode; do that only when the user explicitly requests an interactive session.
5. Inspect namespace objects with `ydb scheme ls` and `ydb scheme describe`. Start at the narrowest known path; do not recursively enumerate the database root by default.
6. Route SQL construction, validation, and execution to `ydb-table`. Route an uncovered command tree to its upstream `--help` and documentation instead of extrapolating.

Apply execution gates by effect, not by the command's name:

- Treat `version`, help, `scheme ls`, `scheme describe`, and `ydb sql --explain` as read-only discovery. Do not assume that other commands under the same command tree are read-only.
- Before any mutating CLI operation—including SQL DDL/DML, `scheme mkdir`, `scheme rmdir`, permission changes, imports, and administrative commands—use a two-phase gate: first show the exact operation, target, effect, and a command without confirmation-bypass flags, then stop. Execute only after the user confirms that displayed operation in a subsequent turn; the initial request to mutate is not the execution confirmation.
- Do not include confirmation-bypass flags in the phase-one command, even if the initial request asks for them. After confirmation, include global `-y` / `--assume-yes` or command-specific flags such as `ydb scheme rmdir -f` / `--force` only if the user explicitly requested them; `-f` used by `ydb sql` to read query text is unrelated.
- During discovery or validation, run only help, version, describe/list, or non-executing explain commands. Never probe a mutating command by attempting it against a profile or endpoint.
- Treat `ydb admin` as high risk and outside this skill's operational scope. Its commands can damage a cluster and may require explicit global parameters even when another command would use a default profile; inspect `ydb admin --help` and request the missing target context rather than constructing a command from memory.

YDB CLI AI-mode implementation source: https://github.com/ydb-platform/ydb/blob/0c0d3f432c737269b0b91a2ec93cf76a8b76d00d/ydb/public/lib/ydb_cli/commands/interactive/ai/ai_model_handler.cpp. CLI command reference: https://ydb.tech/docs/en/reference/ydb-cli/commands.

## connecting

Connection string shape:

```
grpcs://<host>:2135/?database=/path/to/db
# or split form:
ydb -e grpcs://<host>:2135 -d /path/to/db ...
```

`grpcs://` — TLS, for anything shared or in production (default port 2135). `grpc://` — plaintext, only for local dev (the local Docker image exposes plaintext on port 2136). Suggesting `grpc://` for a hosted endpoint is broken advice.

Auth env vars (canonical reference: https://ydb.tech/docs/en/reference/ydb-sdk/auth; verified against `ydb-platform/ydb-go-sdk-auth-environ/env.go`):

- `YDB_SERVICE_ACCOUNT_KEY_FILE_CREDENTIALS` — path to a service-account JSON key file.
- `YDB_SERVICE_ACCOUNT_KEY_CREDENTIALS` — the key itself (raw content, not a path).
- `YDB_METADATA_CREDENTIALS` — cloud VM / serverless instance metadata service.
- `YDB_ACCESS_TOKEN_CREDENTIALS` — raw IAM/OAuth access token.
- `YDB_OAUTH2_KEY_FILE` — OAuth2 key file.
- `YDB_STATIC_CREDENTIALS_USER` + `YDB_STATIC_CREDENTIALS_PASSWORD` + `YDB_STATIC_CREDENTIALS_ENDPOINT` — static user/password auth.
- `YDB_ANONYMOUS_CREDENTIALS` — local Docker only. Value semantics differ per SDK; check the auth doc.

## balancing

Client-side balancer defaults, session lifecycle, `shutdownHint` / `BAD_SESSION` behaviour under rolling restart, and end-to-end deadline / cancellation budgets: `references/balancing.md`, `references/session-lifecycle.md`.

## local-deployment

Single-node docker (https://ydb.tech/docs/en/quickstart):

```
docker run -d --rm --name ydb-local -h localhost \
  --platform linux/amd64 \
  -p 2135:2135 -p 2136:2136 -p 8765:8765 -p 9092:9092 \
  -v $(pwd)/ydb_certs:/ydb_certs -v $(pwd)/ydb_data:/ydb_data \
  -e GRPC_TLS_PORT=2135 -e GRPC_PORT=2136 -e MON_PORT=8765 \
  -e YDB_KAFKA_PROXY_PORT=9092 \
  ydbplatform/local-ydb:latest
```

Ports: 2135 gRPCS, 2136 gRPC, 8765 UI/mon, 9092 Kafka-proxy. Connection: `grpc://localhost:2136/local` or `grpcs://localhost:2135/local` (database path is `/local`).

Multi-node dev: Kubernetes Operator (https://github.com/ydb-platform/ydb-kubernetes-operator) or Ansible (https://github.com/ydb-platform/ydb-ansible). No supported Docker Compose multi-node recipe — don't recommend that path.

## integrations

Official under https://github.com/ydb-platform/ unless noted.

- **Python**: SQLAlchemy dialect `ydb-sqlalchemy` (PyPI). URL scheme: `yql+ydb://localhost:2136/local`.
- **Go**: GORM driver `gorm-driver`; `golang-migrate` fork with a `ydb` driver.
- **JVM**: JDBC driver (see packages) is the gateway. `ydb-java-dialects` monorepo contains Hibernate 5/6, Spring Data JDBC, JOOQ, Liquibase, Flyway modules. Native ORM `yoj-project` for immutable entities.
- **Spark**: `ydb-spark-connector`.
- **Terraform**:
  - Schema objects (tables, indexes, changefeeds) inside a YDB database — `terraform-provider-ydb` (experimental).
  - Yandex Cloud Managed YDB provisioning — `yandex-cloud/terraform-provider-yandex` (`yandex_ydb_database_serverless` / `_dedicated` / `_iam_binding`, `yandex_ydb_table`).

Yandex Cloud Managed YDB uses the same engine and same open-source SDKs; only endpoint and IAM-based auth differ. Docs: https://yandex.cloud/en/docs/ydb/.

## schema-basics

Dominant LLM failure modes when generating YDB schemas:

- **Monotonic first-column PK → hot partition.** Common trigger: porting PostgreSQL `SERIAL` / `AUTO_INCREMENT` or a plain timestamp. First PK column determines partition; writes to a monotonic key concentrate on one tablet = one CPU. Use a hash prefix: `PRIMARY KEY (Digest::NumericHash(id), id)` for `id Uint64`. Signature: `Digest::NumericHash(Uint64{Flags:AutoMap}) -> Uint64` (https://ydb.tech/docs/en/yql/reference/udf/list/digest).
- **YDB has no `SERIAL` / `AUTO_INCREMENT` / `CREATE SEQUENCE`.** Don't emit those keywords in YQL — they'll fail. Use client-generated UUIDs or a hash-prefix + id-service design.
- **Partitioning is automatic, defaults need tuning for write-heavy tables.** `CREATE TABLE … WITH (…)` options: `AUTO_PARTITIONING_BY_LOAD`, `AUTO_PARTITIONING_BY_SIZE`, `AUTO_PARTITIONING_MIN_PARTITIONS_COUNT`, `AUTO_PARTITIONING_MAX_PARTITIONS_COUNT`, `AUTO_PARTITIONING_PARTITION_SIZE_MB`. Min count should be ≥ node count for write-heavy workloads.
- **Secondary indexes need the `VIEW IndexName` clause to be used on read.** Create: `ALTER TABLE t ADD INDEX idx_foo GLOBAL ON (foo)`. Read: `SELECT … FROM t VIEW idx_foo WHERE foo = …` (https://ydb.tech/docs/en/yql/reference/syntax/select/secondary_index).
- **YDB is NOT PostgreSQL.** JOIN semantics, DML behavior, transaction isolation, and built-in function names diverge in non-obvious places. Never extrapolate.

Authoritative: https://ydb.tech/docs/en/yql/reference/syntax/create_table and https://ydb.tech/docs/en/concepts/datamodel/table.

## Content rules

Route to a specialist skill (`ydb-table` / `ydb-topics` / `ydb-coordination`) when the question is clearly surface-specific. State uncertainty when this file doesn't cover the question — link the relevant doc page instead of improvising.
