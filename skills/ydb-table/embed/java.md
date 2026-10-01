# Embedding YDB in Java applications

## FloatVector parameters

For an application-provided `float[]`, follow the current recommended approach in the [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) (Java tab) to serialize it on the client. Declare the YQL parameter or `AS_TABLE` member as `String`, then use it directly for storage or `Knn` distance functions. Avoid `List<Float>` plus server-side `Knn::ToBinaryStringFloat` for client data.

Source: <https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main> (Java recommended approach).

## Stack

YDB Java app code typically layers as: **ydb-java-sdk** → **ydb-jdbc-driver** → **Hibernate** → **Spring Data JPA**. Most application code uses the JDBC driver as the entry point. Connection-string format and authentication environment variables: see <https://ydb.tech/docs/en/concepts/connect>. Setup and connection examples: <https://github.com/ydb-platform/ydb-jdbc-driver>. Worked Spring Data JDBC / JPA / Flyway / jOOQ / Liquibase examples: <https://github.com/ydb-platform/ydb-java-examples/tree/master/jdbc>.

## Bulk operations

Canonical pattern for reading, inserting, and deleting batches via Spring Data JPA + Hibernate over YDB:

```java
@Service
public class TokenService {
    private final TokenRepository repository;

    @Transactional
    public List<Token> readMany(List<Long> ids) {
        return repository.findAllById(ids);
    }

    @Transactional
    public void writeMany(List<Token> tokens) {
        repository.saveAll(tokens);
    }

    @Transactional
    public void deleteMany(List<Long> ids) {
        repository.deleteAllByIdInBatch(ids);
    }
}
```

`application.properties`:

```properties
spring.jpa.properties.hibernate.jdbc.batch_size=1000
spring.jpa.properties.hibernate.order_inserts=true
spring.jpa.properties.hibernate.order_updates=true
```

Why: each method issues one statement instead of N. Batches form only when `batch_size` is set *and* statements are ordered — without `order_inserts` / `order_updates`, the session can't group like statements together. `deleteAllByIdInBatch` is the only delete variant that emits a single `DELETE … WHERE id IN (?, ?, …)`; `deleteAllById` does a SELECT per id before deleting.

For the underlying YDB-level mechanisms (`AS_TABLE`, `BulkUpsert`), see `references/working-with-data.md`.

## Retries

The `ydb-jdbc-driver` classifies retryability through the standard `java.sql` exception hierarchy. Concrete subtypes (see `tech.ydb.jdbc.exception` in the driver):

- `YdbRetryableException extends SQLRecoverableException` — base retryable statuses (e.g. `ABORTED`). Safe to retry for any operation.
- `YdbUnavailbaleException extends SQLTransientConnectionException` — `TRANSPORT_UNAVAILABLE`. Retry only for idempotent operations: the server may have committed before the connection died.
- `YdbConditionallyRetryableException extends SQLTransientException` — other transient statuses including `TIMEOUT`. Retry only for idempotent operations.

So in plain JDBC: catch `SQLRecoverableException` unconditionally; catch `SQLTransientException` (and its `SQLTransientConnectionException` subtype) only when the call is idempotent.

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

Failsafe library form, taken from the official jdbc-driver example
(<https://github.com/ydb-platform/ydb-java-examples/blob/master/jdbc/failsafe-example/src/main/java/tech/ydb/jdbc/failsafe/Main.java>):

```java
private static final RetryPolicy<?> DEFAULT_POLICY = RetryPolicy.builder()
        .handle(SQLRecoverableException.class)
        .withBackoff(100, 1000, ChronoUnit.MILLIS, 2)
        .withMaxDuration(Duration.ofSeconds(5))
        .build();

private static final RetryPolicy<?> IDEMPOTENT_POLICY = RetryPolicy.builder()
        .handle(SQLRecoverableException.class, SQLTransientException.class)
        .withBackoff(100, 1000, ChronoUnit.MILLIS, 2)
        .withMaxDuration(Duration.ofSeconds(5))
        .build();
```

Spring path — `ydb-java-dialects` does not currently ship a retry annotation. The official example app
(<https://github.com/ydb-platform/ydb-java-examples/tree/master/jdbc/ydb-token-app>) defines a thin
meta-annotation over Spring Retry that you can copy or adapt:

```java
@Target({ ElementType.METHOD, ElementType.TYPE })
@Retention(RetentionPolicy.RUNTIME)
@Retryable(
        retryFor = { SQLRecoverableException.class, SQLTransientException.class },
        maxAttempts = MAX_RETRIES,
        backoff = @Backoff(delay = 100, multiplier = 2.0, maxDelay = 5000, random = true)
)
public @interface YdbRetryable { /* AliasFor passthroughs */ }
```

Applied to a transactional service method:

```java
@YdbRetryable
@Transactional
public void loadData(int firstID, int lastID) {
    List<Token> batch = new ArrayList<>();
    for (int id = firstID; id < lastID; id++) {
        batch.add(new Token("user_" + id));
    }
    tokenRepo.saveAll(batch);
}
```

Note that this annotation in the example app retries `SQLTransientException` for *all* annotated methods, which is only safe because every annotated operation there is idempotent. In your own code, restrict the non-`SQLRecoverableException` catch to methods you know are idempotent.

## Native Query SDK deadline and retry cancellation

For `tech.ydb:ydb-sdk-query`, bound every `ExecuteQuery` attempt with the caller's remaining budget. If `SessionRetryContext` owns retries, cancel the future returned by the retry context when the caller no longer needs the result:

```java
Duration initialBudget = Duration.between(Instant.now(), callerDeadline);
// Reject the request before building the retry context if initialBudget <= 0.
SessionRetryContext retryContext = SessionRetryContext.create(client)
        .sessionCreationTimeout(initialBudget)
        .maxRetries(3)
        .idempotent(true)
        .build();

CompletableFuture<Result<QueryInfo>> operation = retryContext.supplyResult(session -> {
    Duration remainingBudget = Duration.between(Instant.now(), callerDeadline);
    // Return a deadline-expired result without dispatching if remainingBudget <= 0.
    ExecuteQuerySettings settings = ExecuteQuerySettings.newBuilder()
            .withRequestTimeout(remainingBudget)
            .build();

    return session.createQuery(query, TxMode.SNAPSHOT_RO, params, settings)
            .execute(this::onPart);
});

requestCancelled.thenRun(() -> operation.cancel(false));
```

`withRequestTimeout` becomes the transport deadline for the current query attempt. Recompute it from the original caller deadline inside the retry callback; giving every attempt a fresh full duration silently multiplies the request budget.

The `operation` future belongs to `SessionRetryContext`. The retry context checks `promise.isCancelled()` before scheduling a retry and again when the retry timer fires, so this outer future is the cancellation handle for retry orchestration. Cancelling it does **not** cancel an already running `ExecuteQuery`; the request timeout remains responsible for bounding that attempt. Do not add cancellation of the inner `ExecuteQuery` future to this pattern: it is normally unnecessary and is not a substitute for cancelling the outer retry future.

Source: <https://github.com/ydb-platform/ydb-java-sdk/blob/master/query/src/main/java/tech/ydb/query/tools/SessionRetryContext.java> — cancellation checks before subsequent retries; <https://github.com/ydb-platform/ydb-java-sdk/blob/master/query/src/main/java/tech/ydb/query/settings/ExecuteQuerySettings.java> and <https://github.com/ydb-platform/ydb-java-sdk/blob/master/query/src/main/java/tech/ydb/query/impl/SessionImpl.java> — request timeout mapping to the gRPC deadline.

## Transactions

YDB Query Service defaults to `SerializableRW`. Conflicting transactions are detected by the server and surface as retryable `SQLRecoverableException` (`ABORTED`). For the full mode list and the consequence for application-level optimistic locking, see `references/working-with-data.md`.

## Connection

See <https://ydb.tech/docs/en/concepts/connect>.
