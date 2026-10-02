# Search with the JavaScript SDK

Read [the shared SDK workflow](../sdk.md) and copy its SQL assets to `queries/`. Install `@ydbjs/core`, `@ydbjs/query`, and `@ydbjs/value`. Sources: [recommended vector recipe](https://ydb.tech/docs/ru/recipes/ydb-sdk/vector-search?tabs=tool_javascript#search-by-vector) and [SDK initialization](https://ydb.tech/docs/en/recipes/ydb-sdk/init).

The `@ydbjs/query` client accepts a trusted SQL string as well as a tagged template. `.parameter()` binds an explicitly typed value and supplies its `DECLARE`; use the shared SQL files without adding duplicate declarations. Application values do not pass through `unsafe()`.

```javascript
import { readFileSync } from 'node:fs'
import { Driver } from '@ydbjs/core'
import { query } from '@ydbjs/query'
import { fromJs } from '@ydbjs/value'
import { Bytes, Text, Uint64 } from '@ydbjs/value/primitive'

const DIMENSION = 3 // Match add-vector-index.sql and the embedding model.
const modes = new Set(['exact', 'vector', 'fulltext', 'hybrid'])
const loadSql = name => readFileSync(`queries/${name}`, 'utf8')

function encodeVector(vector) {
  if (vector.length !== DIMENSION) throw new Error('Unexpected embedding dimension')
  const bytes = new Uint8Array(DIMENSION * 4 + 1)
  const view = new DataView(bytes.buffer)
  vector.forEach((value, i) => view.setFloat32(i * 4, value, true))
  bytes[bytes.length - 1] = 0x01
  return bytes
}

async function upsertDocuments(sql, documents, signal) {
  if (documents.length === 0) return
  const items = documents.map(doc => ({
    id: new Uint64(BigInt(doc.id)),
    title: new Text(doc.title),
    body: new Text(doc.body),
    embedding: new Bytes(encodeVector(doc.embedding)),
  }))
  await sql(loadSql('upsert.sql'))
    .parameter('items', fromJs(items))
    .idempotent(true)
    .signal(signal)
}

async function search(sql, mode, { vector, text = '', limit = 10n, signal }) {
  if (!modes.has(mode) || BigInt(limit) <= 0n) throw new Error('Invalid mode or limit')
  let request = sql(loadSql(`${mode}-search.sql`))
    .parameter('limit', new Uint64(BigInt(limit)))
    .idempotent(true)
    .signal(signal)
  if (mode !== 'fulltext') {
    request = request.parameter('query_vector', new Bytes(encodeVector(vector)))
  }
  if (mode === 'fulltext' || mode === 'hybrid') {
    request = request.parameter('query_text', new Text(text))
  }
  const [rows] = await request
  return rows.map(({ id, title }) => ({ id, title }))
}
```

`Bytes` maps to YQL `String`, `Text` to `Utf8`, and `Uint64` accepts `bigint`. Pass IDs as `bigint` or decimal strings if they can exceed the exact integer range of a JavaScript `number`. `fromJs(items)` retains the explicit value types inside the list of structs; the empty-batch guard avoids inferring a row type from an empty array.

## Connection and invocation

Use your application's existing credential provider in `driverOptions`, following the initialization recipe. Reuse one driver and query client:

```javascript
async function runExample(connectionString, driverOptions, signal) {
  const driver = new Driver(connectionString, driverOptions)
  const sql = query(driver)
  try {
    await driver.ready()
    await sql(loadSql('create-table.sql')).signal(signal)
    await upsertDocuments(sql, [
      { id: 1n, title: 'YDB', body: 'distributed database', embedding: [1, 0, 0] },
      { id: 2n, title: 'Search', body: 'vector and fulltext search', embedding: [0, 1, 0] },
      { id: 3n, title: 'Queries', body: 'database examples', embedding: [0.8, 0.2, 0] },
    ], signal)
    await sql(loadSql('add-vector-index.sql')).signal(signal)
    await sql(loadSql('add-fulltext-index.sql')).signal(signal)

    const options = { text: 'database', vector: [1, 0, 0], limit: 10n, signal }
    for (const mode of ['vector', 'fulltext', 'hybrid']) {
      console.log(mode, await search(sql, mode, options))
    }
  } finally {
    await sql[Symbol.asyncDispose]()
    driver.close()
  }
}
```

Provision only a new demo table with this sequence; existing applications run schema migrations separately. The caller supplies an `AbortSignal` covering the operation; propagate its cancellation/deadline. Replace the toy vectors with model output, and use `exact` for the baseline. Query failures reject the awaited promise; handle them at the request boundary.

API grounding: `ydb-js-sdk` source under `packages/query/src/` defines string queries, `.parameter()`, `.idempotent()`, `.signal()`, and asynchronous client disposal; `packages/value/src/` defines the primitive wrappers and `fromJs` conversion. These details supplement the vector recipe's tagged-template examples.
