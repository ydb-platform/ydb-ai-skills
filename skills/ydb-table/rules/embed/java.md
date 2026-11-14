# Java SDK / JDBC / Hibernate / Spring Data — anti-patterns

Audit rules for application code talking to YDB via the Java stack. Each rule is self-contained: the surface skill must produce correct audit output on its own. Positive patterns are in `references/embed/java.md`, loaded directly from `SKILL.md`.

Use this structure for each rule-based item in the final review:

**<actual RULE-JV-NN> — <finding or preserved guardrail>**
- **Evidence:** what the supplied code/configuration establishes and what still needs verification.
- **Impact:** why the rule matters in this context.
- **Recommendation:** a concrete fix, or the conditions for safely changing an existing guardrail.

Replace the placeholder with the exact ID from the rule you apply. Keeping an existing guardrail or requesting missing context is not a confirmed defect; say so. Include the ID in the final review itself, and do not list unrelated rules merely to include an ID.

### RULE-JV-01: `findById` in a loop instead of `findAllById`

**Severity**: Medium

**What to look for**: calls to `findById(` inside `for` / `while` / `forEach` / `stream` blocks, or repeated `findById` calls against the same repository with different ids.

**Problem**: each `findById` is one round trip to YDB and one server-side query plan. On a single-server database (PostgreSQL, MySQL), N point reads amortize against a shared buffer cache and one connection. On YDB, rows are sharded across tablets that may live on different nodes — there is no shared locality to amortize against, and N point reads from the application travel N separate routes (network round trip + query planning + tablet lookup, every time). `findAllById(ids)` collapses the application-side cost into one round trip: the server resolves all ids against the tablet map once, dispatches reads to the owning tablets in parallel server-side, and returns a single response.

**Fix**:

```java
List<Token> tokens = repository.findAllById(ids);
```

**Source**: Spring Data Commons — `CrudRepository#findAllById(Iterable<ID>)` (returns all instances of the type with the given ids in a single call). <https://docs.spring.io/spring-data/commons/docs/current/api/org/springframework/data/repository/CrudRepository.html>.

### RULE-JV-02: JDBC batching not configured

**Severity**: High

**What to look for**: bulk writes without a positive `hibernate.jdbc.batch_size` (Spring Boot: `spring.jpa.properties.hibernate.jdbc.batch_size`).

**Problem**: JDBC batching is disabled by default. A positive batch size enables grouping; `hibernate.order_inserts` and `hibernate.order_updates` can improve grouping but are not prerequisites.

**Fix**: configure and measure a suitable batch size, for example:

```properties
spring.jpa.properties.hibernate.jdbc.batch_size=1000
```

Consider the ordering options and benchmark their effect. Check identifier generation: Hibernate disables insert batching for identity-generated identifiers.

**Source**: <https://docs.hibernate.org/orm/6.6/userguide/html_single/#batch>.

### RULE-JV-03: Per-entity saves without a shared transaction

**Severity**: High

**What to look for**: repeated repository `save()` calls without a surrounding transaction, or flushing after every entity. A loop inside one transaction with batching configured is not enough to establish this finding.

**Problem**: separate transactions or per-entity flushes prevent useful grouping. `saveAll()` itself loops over `save()`; replacing the loop alone does not create one SQL statement or fix batching inside an existing transaction.

**Fix**: group writes in one transaction with batching enabled. `saveAll(batch)` is a convenient transactional wrapper. For large imports, `flush()`/`clear()` can bound persistence-context memory, but neither commits the transaction. Chunking with flush/clear inside one outer `@Transactional` does not bound total transaction size. Separate committed transactions per chunk require explicit transaction boundaries and are appropriate only when partial completion is acceptable.

**Source**: <https://github.com/spring-projects/spring-data-jpa/blob/main/spring-data-jpa/src/main/java/org/springframework/data/jpa/repository/support/SimpleJpaRepository.java>; <https://docs.hibernate.org/orm/6.6/userguide/html_single/#batch>.

### RULE-JV-04: Spring `delete()` / `deleteAllById()` for bulk paths

**Severity**: High

**What to look for**: `repository.delete(` or `repository.deleteAllById(` in bulk-delete paths (loops, batch services). Anywhere a list of ids is being removed.

**Problem**: Spring Data JPA's `deleteAllById(Iterable<ID>)` calls `deleteById(id)` per id, and `deleteById` does `findById(id).ifPresent(this::delete);` — N `SELECT` + N `DELETE`. Strictly worse than naive `delete()`-in-loop. (Verified in `SimpleJpaRepository.deleteAllById` / `deleteById`, spring-data-jpa current source.)

**Fix**:

```java
repository.deleteAllByIdInBatch(ids);
```

JavaDoc: "Deletes the entities identified by the given ids using a single query. This kind of operation leaves JPAs first level cache and the database out of sync. Consider flushing the `EntityManager` before calling this method." Emits a single `DELETE … WHERE id IN (?, ?, …)` (verify via SQL logging — current ydb-java-dialects does not override this method).

**Source**: Spring Data JPA — `JpaRepository#deleteAllByIdInBatch(Iterable<ID>)`. <https://docs.spring.io/spring-data/jpa/docs/current/api/org/springframework/data/jpa/repository/JpaRepository.html>.

### RULE-JV-05: Removing JPA `@Version` without checking transaction boundaries

**Severity**: High

**What to look for**: proposals to remove `@Version` because YDB is serializable, especially when `merge()` or request payloads can carry state read in an earlier transaction. An entity declaration or frequent UPDATE traffic alone does not establish a defect.

**Problem**: YDB's `SerializableRW` isolation protects reads and writes within a database transaction; it does not detect that application-supplied state was derived from an earlier, completed transaction. JPA version checking can reject a stale detached entity at merge, flush, or commit. Removing it can allow a later transaction to overwrite an intervening update even when the database transactions execute serially.

**Fix**: preserve `@Version` while inspecting the actual isolation level, read/modify/write boundaries, detached entities, and any client-visible expected-version contract.

- Consider removal only when every database-dependent decision uses fresh reads inside the same `SerializableRW` transaction and the application needs no version check spanning transactions. Otherwise retain version checking or an equivalent atomic expected-version check.
- For a retryable YDB transaction abort such as `ABORTED`, retry the whole transaction, including reads and recomputation, with bounded backoff. After a Hibernate failure, roll back and start a new transaction with a fresh persistence context; do not retry only the failed UPDATE or flush in the failed context. Keep external effects safe from duplication and classify failures with an uncertain commit outcome separately.
- A stale-version conflict needs rejection or reconciliation according to application semantics. Do not bypass the check or repeatedly merge the same stale state. A fresh read and recomputation is an alternative only when that preserves the intended business operation.

Inspect generated SQL and measure the workload before claiming a performance benefit from removal; the annotation alone does not establish a full scan or a material bottleneck.

**Source**: [YDB transaction modes](https://ydb.tech/docs/en/concepts/transactions#serializable); [YDB status codes — ABORTED and UNDETERMINED](https://ydb.tech/docs/en/reference/ydb-sdk/ydb-status-codes); [Jakarta Persistence 3.1, §3.2.7.1 and §3.4.2](https://jakarta.ee/specifications/persistence/3.1/jakarta-persistence-spec-3.1.html); [Hibernate ORM 6.6, optimistic locking and §6.16 exception handling](https://docs.hibernate.org/orm/6.6/userguide/html_single/#locking-optimistic).

### RULE-JV-06: Ignoring retryable JDBC exceptions

**Severity**: Critical

**What to look for**: `catch (SQLException …)` blocks that log and continue, or that retry unconditionally without inspecting the subtype. Missing retry handling is a finding when the relevant call path/policy is supplied or its absence is stated. For an isolated method fragment, request verification of outer retry configuration rather than assume it is absent.

**Problem**: the `ydb-jdbc-driver` surfaces failures through the standard `java.sql` exception hierarchy, and the two categories the JDBC contract exposes want different handling:

- `SQLRecoverableException` — the YDB JDBC driver reports a retryable failure; retry within the budget without an idempotency gate for the database operation. For example, `ABORTED` (including `Transaction locks invalidated`) means the transaction was aborted: restart the entire transaction. Check external side effects separately before replaying application code.
- `SQLTransientException` — the server may have already committed before the failure surfaced. Retrying a non-idempotent statement (`INSERT`, decrement, transfer) risks double effect. Safe to retry only for idempotent operations: `UPSERT`, idempotency-key-protected writes, reads.

These are the two types JDBC consumers should branch on. Driver-internal subclasses exist but should not be referenced from application code — they are not part of the published contract and can change.

Catching the supertype `SQLException` (or `Exception`) and retrying both categories the same way violates the contract in one direction or the other.

Determine operation idempotency from key generation, statement semantics, and side effects. `repository.save()`, newly constructed entities, or a method name alone establish neither idempotency nor non-idempotency; a caller-supplied ID alone is also insufficient. If this context is missing, explain both retry policies conditionally.

**Fix**:

For a single autocommit statement in plain JDBC, classify the exception and treat transients as idempotency-gated:

```java
static final int MAX_RETRIES = 15;

void runWithRetry(Connection c, boolean idempotent, JdbcOp op) throws SQLException {
    for (int attempt = 0; ; attempt++) {
        try {
            op.run(c);
            return;
        } catch (SQLRecoverableException e) {
            if (attempt >= MAX_RETRIES) throw e;
        } catch (SQLTransientException e) {
            if (!idempotent || attempt >= MAX_RETRIES) throw e;
        }
    }
}
```

Spring path — `ydb-java-dialects` does not ship a retry annotation; hand-roll Spring Retry's `@Retryable` with the YDB exception buckets, or copy the meta-annotation pattern from the upstream example app (`ydb-java-examples/jdbc/ydb-token-app`). Note: retrying `SQLTransientException` for all annotated methods is only safe when those methods are themselves idempotent.

```java
@Retryable(
    retryFor = { SQLRecoverableException.class, SQLTransientException.class },
    maxAttempts = MAX_RETRIES,
    backoff = @Backoff(delay = 100, multiplier = 2.0, maxDelay = 5000, random = true)
)
@Transactional
public void insertBatch(List<Token> batch) {
    repository.saveAll(batch);
}
```

**Source**: `java.sql.SQLRecoverableException`, `SQLTransientException` — <https://docs.oracle.com/en/java/javase/21/docs/api/java.sql/java/sql/SQLException.html>. YDB transaction retry scope: [YDB status codes: ABORTED](https://ydb.tech/docs/en/reference/ydb-sdk/ydb-status-codes#400040-aborted). Example meta-annotation pattern: <https://github.com/ydb-platform/ydb-java-examples/tree/master/jdbc/ydb-token-app>.

### RULE-JV-07: Session retry context detached from caller cancellation or query deadline

**Severity**: High

**What to look for**: code using `SessionRetryContext.supplyResult(...)` or `.supplyStatus(...)` where the returned retry future is not cancelled when the caller goes away; or where an `ExecuteQuery` inside the retry callback has no `.withRequestTimeout(remainingBudget)`, uses a fixed timeout that can exceed the caller deadline, or receives a fresh full timeout on every retry.

**Problem**: an uncancelled `SessionRetryContext` can keep scheduling attempts after the caller no longer needs a result. An unbounded or freshly reset request timeout can also let the current `ExecuteQuery` outlive the caller's deadline.

**Fix**: retain the future returned by `SessionRetryContext` and cancel that outer future when the caller cancels. The retry context checks this cancellation before scheduling a retry and when its timer fires. Inside the retry callback, recompute the remaining duration from the original caller deadline and pass it to `.withRequestTimeout(...)`. Cancelling the retry future does not cancel an already running `ExecuteQuery`; its request timeout bounds that attempt. Cancelling the inner query future is normally unnecessary. Preserve the operation's idempotency and uncertain-result handling.

**Source**: <https://github.com/ydb-platform/ydb-java-sdk/blob/master/query/src/main/java/tech/ydb/query/tools/SessionRetryContext.java> — cancellation checks before retries; <https://github.com/ydb-platform/ydb-java-sdk/blob/master/query/src/main/java/tech/ydb/query/settings/ExecuteQuerySettings.java> and <https://github.com/ydb-platform/ydb-java-sdk/blob/master/query/src/main/java/tech/ydb/query/impl/SessionImpl.java> — request timeout mapping to the gRPC deadline.

### RULE-JV-08: Client FloatVector passed as `List<Float>` for server conversion

**Severity**: Medium

**What to look for**: application `float[]` values are bound as `List<Float>`, and the YQL query uses `Knn::ToBinaryStringFloat($embedding)` or converts an `AS_TABLE($items)` embedding member.

**Problem**: each coordinate is sent as a list element and converted on the server, although the vector can be sent as one binary `String` value.

**Fix**: serialize the vector on the client and include the [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) in the finding, pointing to its Java tab for the supported implementation. Bind it as YQL `String` and use it directly for storage or `Knn` distance functions. Explain that the YQL converter still applies to vectors created in YQL; other vector types require their own formats.

**Source**: <https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main> (Java recommended approach); <https://ydb.tech/docs/en/yql/reference/udf/list/knn#functions-convert>.
