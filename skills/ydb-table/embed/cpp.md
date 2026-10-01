# Embedding YDB in C++ applications

## FloatVector parameters

For an application-provided `std::vector<float>`, follow the current recommended approach in the [YDB vector-search recipe](https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main) (C++ tab) to serialize it on the client. Declare the parameter or `AS_TABLE` member as YQL `String` and use it directly in storage or `Knn` distance functions. Avoid sending `List<Float>` for conversion with `Knn::ToBinaryStringFloat` in YQL on every request.

Source: <https://ydb.tech/docs/en/recipes/ydb-sdk/vector-search?version=main>.

Official SDK: **`ydb-cpp-sdk`** (<https://github.com/ydb-platform/ydb-cpp-sdk>), namespace `NYdb`, headers `#include <ydb-cpp-sdk/client/...>`.

- **`NYdb::NQuery::TQueryClient`** — Query Service (preferred): `ExecuteQuery`, `StreamExecuteQuery`, fused `TTxControl`. Transaction modes: <https://ydb.tech/docs/en/recipes/ydb-sdk/tx-control>.
- **`NYdb::NTable::TTableClient`** — Table Service: `ExecuteDataQuery`, `BulkUpsert`, `StreamExecuteScanQuery`, `ExecuteSchemeQuery`.
- One **`NYdb::TDriver`** per process; clients are cheap on top. C++20. Docs: <https://ydb.tech/docs/en/reference/ydb-sdk/>.

Connection details: <https://ydb.tech/docs/en/concepts/connect>. Production: `NYdb::CreateFromEnvironment(connectionString)` (`helpers/helpers.h`).

## Query pattern

`RetryQuerySync(lambda, TRetryOperationSettings)` — the **lambda is the retry unit**; the lambda receives `TSession session`. See <https://ydb.tech/docs/en/recipes/ydb-sdk/retry>. Second arg: `.Idempotent(true)` when replay-safe (reads, client-keyed UPSERT); omit for non-idempotent writes.

```cpp
ThrowOnError(client.RetryQuerySync(
    [] (TSession session) {
        auto p = TParamsBuilder().AddParam("$id").Uint64(42).Build().Build();
        return session.ExecuteQuery(
            "SELECT name FROM users WHERE id = $id",
            TTxControl::BeginTx(TTxSettings::SnapshotRO()).CommitTx(), p
        ).GetValueSync();
    },
    NYdb::NRetry::TRetryOperationSettings().Idempotent(true)));
```

Bind values with **`TParamsBuilder`** — never concatenate into YQL. Build results **inside** the lambda; assign outers only on success (see `rules/cpp.md` RULE-CPP-02).

## Transactions

Single statement: `TTxControl::BeginTx(TTxSettings::SerializableRW()).CommitTx()` on the query call. Multi-step: first query `BeginTx()` without `CommitTx`, later `TTxControl::Tx(tx).CommitTx()`. Modes: `references/working-with-data.md`, <https://ydb.tech/docs/en/recipes/ydb-sdk/tx-control>.

## Retries

Use SDK retriers — not outer `for` on `RetryQuerySync` (RULE-CPP-04) and not `sleep_for` + bare `ExecuteQuery` (RULE-CPP-05). Status classes: always-retry (`ABORTED`, `UNAVAILABLE`, `BAD_SESSION`); conditional with `.Idempotent(true)` (`UNDETERMINED`, `TRANSPORT_UNAVAILABLE`); non-retryable (`PRECONDITION_FAILED`, `SCHEME_ERROR`). Tune via `TRetryOperationSettings`. Source: <https://ydb.tech/docs/en/recipes/ydb-sdk/retry>, <https://ydb.tech/docs/en/reference/ydb-sdk/ydb-status-codes>.

## Request deadline and cancellation

Pass the caller's absolute deadline to the request, its remaining time to retry orchestration, and its `std::stop_token` to the retry settings:

```cpp
auto retrySettings = NYdb::NRetry::TRetryOperationSettings()
    .MaxTimeout(remainingBudget)
    .CancellationToken(requestStop)
    .Idempotent(true);

auto settings = NYdb::NQuery::TExecuteQuerySettings()
    .Deadline(callerDeadline)
    .ClientTimeout(remainingBudget)
    .RetrySettings(retrySettings);

auto result = client.ExecuteQuery(query, txControl, params, settings).GetValueSync();
```

`Deadline` preserves the caller's absolute boundary even if dispatch is delayed; `MaxTimeout` caps the whole retry orchestration; `ClientTimeout` supplies the per-RPC cap. Compute relative limits from the caller's *remaining* budget rather than resetting a fixed duration for each attempt. The SDK applies the earlier of `Deadline` and `ClientTimeout` to the RPC.

`CancellationToken` stops retry orchestration, including before an attempt or during backoff, but it does **not** cancel an already running RPC. `CLIENT_CANCELLED` may replace a successful result and does not imply rollback. Keep `ClientTimeout` and the operation's idempotency semantics even when a stop token is present.

Source: <https://github.com/ydb-platform/ydb/blob/main/ydb/public/sdk/cpp/include/ydb-cpp-sdk/client/retry/retry.h> — released `TRetryOperationSettings::CancellationToken` contract; <https://github.com/ydb-platform/ydb/blob/main/ydb/public/sdk/cpp/include/ydb-cpp-sdk/client/types/request_settings.h> and <https://github.com/ydb-platform/ydb/blob/main/ydb/public/sdk/cpp/src/client/impl/internal/rpc_request_settings/settings.h> — absolute request deadline and its combination with `ClientTimeout`; <https://ydb.tech/docs/en/dev/timeouts> — operation, transport, and cancel-after timeout layers.

## Large reads & streams

- **`ExecuteDataQuery`**: check `TResultSet::Truncated()` or paginate / use `StreamExecuteScanQuery` (RULE-CPP-01).
- **`StreamExecuteQuery`**: wrap with `RetryQuerySync`; `ReadNext()` parts. Retrier replay can re-emit rows — dedupe side effects. RULE-CPP-09; see <https://ydb.tech/docs/en/dev/example-app/example-cpp#stream-query>.

```cpp
ThrowOnError(client.RetryQuerySync(
    [] (TSession session) -> TStatus {
        auto stream = session.StreamExecuteQuery(
            "SELECT id FROM events", TTxControl::NoTx()).GetValueSync();
        if (!stream.IsSuccess()) {
            return stream;
        }
        // ReadNext loop — side effects must be idempotent per key
        return TStatus(EStatus::SUCCESS, NYdb::NIssue::TIssues());
    }));
```

## Bulk upsert

`TTableClient::BulkUpsert` via `RetryOperationSync` — non-transactional, UPSERT-keyed, `.Idempotent(true)` conventional. See <https://ydb.tech/docs/en/dev/batch-upload> and `references/working-with-data.md`.
