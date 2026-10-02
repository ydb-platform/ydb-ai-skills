# Search with the C++ SDK

Read [the shared SDK workflow](../sdk.md) and copy its SQL assets to `queries/`. Use `NYdb::NQuery::TQueryClient` from `ydb-cpp-sdk`. Sources: [recommended vector recipe](https://ydb.tech/docs/ru/recipes/ydb-sdk/vector-search?version=main&tabs=tool_cpp#search-by-vector), [driver initialization](https://ydb.tech/docs/en/recipes/ydb-sdk/init), and [SDK retries](https://ydb.tech/docs/en/recipes/ydb-sdk/retry).

The encoder below writes little-endian bytes explicitly. Its output does not depend on the host's byte order.

```cpp
#include <ydb-cpp-sdk/client/helpers/helpers.h>
#include <ydb-cpp-sdk/client/query/client.h>
#include <ydb-cpp-sdk/client/types/status/status.h>

#include <cstdint>
#include <cstring>
#include <fstream>
#include <iterator>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace Q = NYdb::NQuery;
constexpr std::size_t Dimension = 3; // Match add-vector-index.sql.
struct Document {
    std::uint64_t Id;
    std::string Title, Body;
    std::vector<float> Embedding;
};
struct Hit { std::uint64_t Id; std::string Title; };

std::string LoadSql(const std::string& name) {
    std::ifstream input("queries/" + name);
    if (!input) throw std::runtime_error("Cannot read SQL file: " + name);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

std::string EncodeVector(const std::vector<float>& vector) {
    static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559);
    if (vector.size() != Dimension) throw std::invalid_argument("Unexpected dimension");
    std::string bytes;
    bytes.reserve(4 * Dimension + 1);
    for (float value : vector) {
        std::uint32_t bits;
        std::memcpy(&bits, &value, sizeof(bits));
        for (unsigned shift = 0; shift < 32; shift += 8) {
            bytes.push_back(static_cast<char>((bits >> shift) & 0xff));
        }
    }
    bytes.push_back('\x01');
    return bytes;
}

void Upsert(Q::TQueryClient& client, const std::vector<Document>& documents) {
    if (documents.empty()) return;
    NYdb::TParamsBuilder builder;
    auto& items = builder.AddParam("$items");
    items.BeginList();
    for (const auto& doc : documents) {
        items.AddListItem().BeginStruct();
        items.AddMember("id").Uint64(doc.Id);
        items.AddMember("title").Utf8(doc.Title);
        items.AddMember("body").Utf8(doc.Body);
        items.AddMember("embedding").String(EncodeVector(doc.Embedding));
        items.EndStruct();
    }
    items.EndList().Build();
    const auto params = builder.Build();
    const auto sql = LoadSql("upsert.sql");
    NYdb::NStatusHelpers::ThrowOnError(client.RetryQuerySync(
        [&] (Q::TSession session) {
            return session.ExecuteQuery(sql,
                Q::TTxControl::BeginTx(Q::TTxSettings::SerializableRW()).CommitTx(),
                params).GetValueSync();
        }, NYdb::NRetry::TRetryOperationSettings().Idempotent(true)));
}

std::vector<Hit> Search(Q::TQueryClient& client, const std::string& mode,
        const std::string& text, const std::vector<float>& vector, std::uint64_t limit) {
    if (limit == 0 || (mode != "exact" && mode != "vector" &&
                      mode != "fulltext" && mode != "hybrid")) {
        throw std::invalid_argument("Invalid search mode or limit");
    }
    NYdb::TParamsBuilder builder;
    builder.AddParam("$limit").Uint64(limit).Build();
    if (mode != "fulltext") {
        builder.AddParam("$query_vector").String(EncodeVector(vector)).Build();
    }
    if (mode == "fulltext" || mode == "hybrid") {
        builder.AddParam("$query_text").Utf8(text).Build();
    }
    const auto params = builder.Build();
    const auto sql = LoadSql(mode + "-search.sql");
    std::vector<Hit> hits;
    NYdb::NStatusHelpers::ThrowOnError(client.RetryQuerySync(
        [&] (Q::TSession session) {
            auto result = session.ExecuteQuery(sql,
                Q::TTxControl::BeginTx(Q::TTxSettings::SnapshotRO()).CommitTx(),
                params).GetValueSync();
            if (result.IsSuccess()) {
                std::vector<Hit> attempt;
                auto parser = result.GetResultSetParser(0);
                while (parser.TryNextRow()) {
                    attempt.push_back({parser.ColumnParser("id").GetUint64(),
                                       parser.ColumnParser("title").GetUtf8()});
                }
                hits = std::move(attempt);
            }
            return result;
        }, NYdb::NRetry::TRetryOperationSettings().Idempotent(true)));
    return hits;
}
```

`.String(encoded)` binds the binary vector; `.Utf8(text)` binds text. Build a fresh result vector inside each successful retry attempt, then replace the outer collection. Appending directly to an outer vector inside a retried callback can duplicate results.

## Connection and invocation

The helper selects credentials from the application's configured environment. Reuse the driver and client for normal application requests:

```cpp
auto config = NYdb::CreateFromEnvironment(connectionString);
NYdb::TDriver driver(config);
Q::TQueryClient client(driver);

// Run this provisioning sequence once for a new demonstration table.
NYdb::NStatusHelpers::ThrowOnError(client.ExecuteQuery(
    LoadSql("create-table.sql"), Q::TTxControl::NoTx()).GetValueSync());
Upsert(client, {
    {1, "YDB", "distributed database", {1, 0, 0}},
    {2, "Search", "vector search", {0, 1, 0}},
    {3, "Queries", "database examples", {0.8f, 0.2f, 0}},
});
for (const auto* name : {"add-vector-index.sql", "add-fulltext-index.sql"}) {
    NYdb::NStatusHelpers::ThrowOnError(client.ExecuteQuery(
        LoadSql(name), Q::TTxControl::NoTx()).GetValueSync());
}
auto vectorHits = Search(client, "vector", "", {1, 0, 0}, 10);
auto textHits = Search(client, "fulltext", "database", {}, 10);
auto hybridHits = Search(client, "hybrid", "database", {1, 0, 0}, 10);
```

Use `exact` for the baseline. Replace the toy vectors with the embedding model's output. For production handlers, pass the caller's absolute deadline and remaining timeout into `TExecuteQuerySettings` and the shared retry budget/cancellation into `TRetryOperationSettings`; do not reset the budget for each retry. The standalone bounded-result example above focuses on parameter types and search execution.

API grounding: the YDB source under `ydb/public/sdk/cpp/include/ydb-cpp-sdk/client/` provides the `query`, `params`, `value`, `retry`, and `helpers` declarations used here.
