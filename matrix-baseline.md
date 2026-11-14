# Matrix baseline — 2026-11-13 (Haiku grader)

Snapshot of the A/B compatibility matrix for the YDB skills.

Future edits to skills should be compared against this — a meaningful change should move
cells from `REDUNDANT` / `INSUFFICIENT` toward `SKILL_WORKS` without regressing
`SKILL_WORKS` cells.

> **Snapshot scope (2026-11-13).** Same grader (`anthropic/claude-haiku-4.5`).
> **11 providers × 66 tests = 726 cells** per side, with 0 transport or grading errors.
> This HTTP profile checks answers and lookup plans; source retrieval and
> skill activation are checked separately.

## How to run

```bash
export OPENROUTER_API_KEY="..."
# Optional OpenRouter-compatible gateway: set OPENROUTER_API_BASE_URL.
npx promptfoo@0.125.1 eval --no-cache -j 4                               # skill loaded
npx promptfoo@0.125.1 eval -c promptfooconfig.bare.yaml --no-cache -j 4   # bare control
python3 scripts/ab-compare.py --skill <skill-eval-id> --bare <bare-eval-id>
```

- **11 providers** × **66 tests** = 726 cells per side.
- Skill side: 655 pass, 71 fail, 0 errors.
- Bare side: 71 pass, 655 fail, 0 errors.
- Grader: `anthropic/claude-haiku-4.5`, temperature 0, `max_tokens: 1024`.
- Reasoning disabled on DeepSeek and Qwen. Other reasoning models use low effort;
  Kimi and Ministral keep the provider default. Output caps are 2048 or 8192 tokens.
  See [`docs/testing.md`](docs/testing.md#speed-knobs).

## Provider mix

- **Frontier** (2): Anthropic Opus 5.5, OpenAI GPT-6.1 Sol.
- **Efficient / open weights** (6): Google Gemini 3.8 Flash, DeepSeek V4 Pro 0813,
  Moonshot Kimi K2.7 Code, Qwen3.8 Flash, Z.ai GLM 5.3, MiniMax M3.1 Flash.
- **Small** (3): OpenAI gpt-oss-20b, Mistral Ministral 3 14B, Qwen3.8 27B.

When iterating on skill content, the Small tier provides a cheaper first check:

```bash
npx promptfoo@0.125.1 eval --filter-providers 'Small'
```

## How to read it

Each cell is one (provider, test) pair, classified by comparing the main matrix
verdict against the bare-control verdict:

| Quadrant       | skill | bare | Meaning                                      |
|----------------|-------|------|----------------------------------------------|
| `SKILL_WORKS`  | PASS  | FAIL | The skill earned the answer. **Keep.**       |
| `REDUNDANT`    | PASS  | PASS | The model already knew. Candidate for trim.  |
| `INSUFFICIENT` | FAIL  | FAIL | Skill text isn't enough — investigate.       |
| `SKILL_HARMS`  | FAIL  | PASS | Skill confused the model. Investigate.       |

## Snapshot

```
grader: anthropic/claude-haiku-4.5

──────────────────────────────────────────────────────────────────────────────
Headline (cells across all providers × tests)
──────────────────────────────────────────────────────────────────────────────
  + SKILL_WORKS       584  ( 80.4%)
  . REDUNDANT          71  (  9.8%)
  x INSUFFICIENT       71  (  9.8%)
  ! SKILL_HARMS         0  (  0.0%)
  ? ERROR               0  (  0.0%)

──────────────────────────────────────────────────────────────────────────────
Per-test (aggregated across providers)
──────────────────────────────────────────────────────────────────────────────
  TEST                                                    works  redu insuf harms
  C++ audit · Custom Sleep retrier around YDB calls (RULE    11     0     0     0
  C++ audit · DDL (ExecuteSchemeQuery) inside RetryOperat    11     0     0     0
  C++ audit · Explicit BeginTransaction when fused TTxCon    11     0     0     0
  C++ audit · External state mutation in retry lambda (RU    11     0     0     0
  C++ audit · INSERT INTO inside .Idempotent(true) retry     11     0     0     0
  C++ audit · Missing Idempotent on RetryQuerySync (RULE-    10     0     1     0
  C++ audit · Non-parametrized YQL via std::format (RULE-    11     0     0     0
  C++ audit · Outer for loop around RetryQuerySync (RULE-    10     0     1     0
  C++ audit · StreamExecuteQuery without duplicate handli    10     0     1     0
  C++ audit · TDriver constructed per request instead of     11     0     0     0
  C++ audit · Unbounded Table read without pagination (RU    11     0     0     0
  C++ audit · caller stop and deadline omitted from retri    11     0     0     0
  C++ audit · client FloatVector list converted in YQL (R     4     0     7     0
  Core CLI · Discover syntax and preserve connection cont     8     2     1     0
  Core CLI · Gate recursive scheme mutation by effect         6     2     3     0
  Core CLI · Prefer a scoped non-interactive command          6     3     2     0
  Core CLI · Refuse to invent a high-risk admin command       4     6     1     0
  Core · Client-side balancing and prefer-nearest-DC boun     2     9     0     0
  Core · Cloud auth without hardcoded credentials             7     3     1     0
  Core · Local Docker + Python quickstart                    10     1     0     0
  Core · Onboarding — 3-minute YDB intro for a newcomer       6     3     2     0
  Core · Preserve one end-to-end deadline budget              0    11     0     0
  Core · Select official SDK and integration packages wit     9     1     1     0
  Documentation · Default branch and retrieval fallback      11     0     0     0
  Documentation · Offline lookup plan preserves language     10     0     1     0
  Go audit · Custom retrier with time.Sleep (RULE-GO-05)     11     0     0     0
  Go audit · Explicit BeginTransaction before first query    10     0     1     0
  Go audit · External state mutation from Do retry closur    11     0     0     0
  Go audit · Interactive Table Service `tx.CommitTx` as a    10     0     1     0
  Go audit · Missing WithIdempotent on Do (RULE-GO-03)       10     0     1     0
  Go audit · Nested Do call (RULE-GO-06)                     10     0     1     0
  Go audit · Non-interactive DoTx auto-commit without `qu     9     0     2     0
  Go audit · Non-interactive DoTx without `ydb.WithLazyTx    10     0     1     0
  Go audit · Non-parametrized YQL via fmt.Sprintf (RULE-G    10     0     1     0
  Go audit · PreferLocalDC / PreferNearestDC balancer (RU    11     0     0     0
  Go audit · PreferNearestDC balancer (RULE-GO-08, curren    11     0     0     0
  Go audit · Reading all matching rows through Table Serv    11     0     0     0
  Go audit · Separate Commit after last query (RULE-GO-10     9     0     2     0
  Go audit · Stats consumed before stream drain (RULE-GO-    11     0     0     0
  Go audit · `ydb.WithIgnoreTruncated` masking Table Serv    11     0     0     0
  Go audit · client FloatVector list converted in YQL (RU     6     0     5     0
  Go audit · detached caller context loses deadline and c    11     0     0     0
  Go audit · for-loop wrapping Do (RULE-GO-04)                8     0     3     0
  Go core audit · Long-lived application-owned session (R     2     0     9     0
  Java audit · JDBC batching not configured (RULE-JV-02)     11     0     0     0
  Java audit · JPA @Version over YDB (RULE-JV-05)            11     0     0     0
  Java audit · Spring save() in a loop (RULE-JV-03)           7     2     2     0
  Java audit · client FloatVector list converted in YQL (     7     0     4     0
  Java audit · deleteAllById on bulk path (RULE-JV-04)       11     0     0     0
  Java audit · detached SessionRetryContext and reset que    10     0     1     0
  Java audit · findById in a loop (RULE-JV-01)               11     0     0     0
  Java audit · ignoring retryable JDBC exceptions (RULE-J    11     0     0     0
  Python audit · client FloatVector list converted in YQL    11     0     0     0
  Query parameters · DECLARE remains required by YDB CLI      8     3     0     0
  Query parameters · Optional DECLARE and unquoted type s     4     7     0     0
  Query · Converting PostgreSQL SERIAL to YQL                 8     1     2     0
  Query · Keyset pagination in YQL + Go                      11     0     0     0
  Query · Primary-key design for IoT events (monotonic-PK     5     0     6     0
  RULE-JV-03 — per-entity saves outside a shared transact    10     0     1     0
  Table CLI · Encode typed YDB parameters in JSON            10     0     1     0
  Table CLI · Explain a complex query before execution        9     2     0     0
  Table CLI · Explain-analyze is real execution               4     7     0     0
  Table CLI · Handle CSV, TSV, and Arrow parameter files      9     1     1     0
  Table CLI · Inspect schema and values before filtering      9     0     2     0
  Table writes · BulkUpsert eligibility and transactional     9     1     1     0
  Table writes · Transactional batch with AS_TABLE            4     6     1     0

──────────────────────────────────────────────────────────────────────────────
SKILL_HARMS + INSUFFICIENT cells
──────────────────────────────────────────────────────────────────────────────
  HARMS (0)
  INSUFFICIENT (71)
  openai/gpt-oss-20b                    ydb-core/cli-admin-safety
  mistralai/ministral-14b-2512          ydb-core/cli-command-discovery
  mistralai/ministral-14b-2512          ydb-core/cli-noninteractive
  openai/gpt-oss-20b                    ydb-core/cli-noninteractive
  mistralai/ministral-14b-2512          ydb-core/cli-scheme-mutation-safety
  openai/gpt-oss-20b                    ydb-core/cli-scheme-mutation-safety
  qwen/qwen3.8-flash                    ydb-core/cli-scheme-mutation-safety
  mistralai/ministral-14b-2512          ydb-core/cloud-auth
  deepseek/deepseek-v4-pro-0813         ydb-core/go-rule-cgo-01-long-lived-session
  minimax/minimax-m3.1-flash            ydb-core/go-rule-cgo-01-long-lived-session
  mistralai/ministral-14b-2512          ydb-core/go-rule-cgo-01-long-lived-session
  moonshotai/kimi-k2.7-code             ydb-core/go-rule-cgo-01-long-lived-session
  openai/gpt-6.1-sol                    ydb-core/go-rule-cgo-01-long-lived-session
  openai/gpt-oss-20b                    ydb-core/go-rule-cgo-01-long-lived-session
  qwen/qwen3.8-27b                      ydb-core/go-rule-cgo-01-long-lived-session
  qwen/qwen3.8-flash                    ydb-core/go-rule-cgo-01-long-lived-session
  z-ai/glm-5.3                          ydb-core/go-rule-cgo-01-long-lived-session
  mistralai/ministral-14b-2512          ydb-core/onboarding
  openai/gpt-oss-20b                    ydb-core/onboarding
  mistralai/ministral-14b-2512          ydb-core/package-integration-selection
  openai/gpt-oss-20b                    ydb-docs/lookup-offline
  mistralai/ministral-14b-2512          ydb-table/batch-as-table
  mistralai/ministral-14b-2512          ydb-table/bulk-upsert-boundaries
  openai/gpt-oss-20b                    ydb-table/cli-file-parameter-formats
  mistralai/ministral-14b-2512          ydb-table/cli-safe-exploration
  openai/gpt-oss-20b                    ydb-table/cli-safe-exploration
  mistralai/ministral-14b-2512          ydb-table/cli-typed-parameters
  openai/gpt-oss-20b                    ydb-table/cpp-rule-cpp-03-missing-idempotent
  openai/gpt-oss-20b                    ydb-table/cpp-rule-cpp-04-outer-retry-loop
  openai/gpt-oss-20b                    ydb-table/cpp-rule-cpp-09-stream-duplicates
  deepseek/deepseek-v4-pro-0813         ydb-table/cpp-rule-cpp-13-client-floatvector
  google/gemini-3.8-flash               ydb-table/cpp-rule-cpp-13-client-floatvector
  mistralai/ministral-14b-2512          ydb-table/cpp-rule-cpp-13-client-floatvector
  openai/gpt-6.1-sol                    ydb-table/cpp-rule-cpp-13-client-floatvector
  openai/gpt-oss-20b                    ydb-table/cpp-rule-cpp-13-client-floatvector
  qwen/qwen3.8-27b                      ydb-table/cpp-rule-cpp-13-client-floatvector
  qwen/qwen3.8-flash                    ydb-table/cpp-rule-cpp-13-client-floatvector
  openai/gpt-oss-20b                    ydb-table/go-rule-go-03-missing-idempotent
  mistralai/ministral-14b-2512          ydb-table/go-rule-go-04-outer-loop-around-do
  openai/gpt-oss-20b                    ydb-table/go-rule-go-04-outer-loop-around-do
  qwen/qwen3.8-27b                      ydb-table/go-rule-go-04-outer-loop-around-do
  openai/gpt-oss-20b                    ydb-table/go-rule-go-06-nested-do
  openai/gpt-oss-20b                    ydb-table/go-rule-go-07-non-parametrized
  openai/gpt-oss-20b                    ydb-table/go-rule-go-09-explicit-begin
  openai/gpt-oss-20b                    ydb-table/go-rule-go-09b-dotx-without-lazytx
  mistralai/ministral-14b-2512          ydb-table/go-rule-go-10-separate-commit
  openai/gpt-oss-20b                    ydb-table/go-rule-go-10-separate-commit
  mistralai/ministral-14b-2512          ydb-table/go-rule-go-10b-interactive-table-commit
  mistralai/ministral-14b-2512          ydb-table/go-rule-go-10c-dotx-missing-withcommit
  openai/gpt-oss-20b                    ydb-table/go-rule-go-10c-dotx-missing-withcommit
  google/gemini-3.8-flash               ydb-table/go-rule-go-13-client-floatvector
  mistralai/ministral-14b-2512          ydb-table/go-rule-go-13-client-floatvector
  moonshotai/kimi-k2.7-code             ydb-table/go-rule-go-13-client-floatvector
  openai/gpt-oss-20b                    ydb-table/go-rule-go-13-client-floatvector
  qwen/qwen3.8-flash                    ydb-table/go-rule-go-13-client-floatvector
  mistralai/ministral-14b-2512          ydb-table/java-rule-jv-03-save-in-loop
  moonshotai/kimi-k2.7-code             ydb-table/java-rule-jv-03-save-in-loop
  openai/gpt-oss-20b                    ydb-table/java-rule-jv-03-save-without-transaction
  mistralai/ministral-14b-2512          ydb-table/java-rule-jv-07-detached-session-retry-context
  google/gemini-3.8-flash               ydb-table/java-rule-jv-08-client-floatvector
  mistralai/ministral-14b-2512          ydb-table/java-rule-jv-08-client-floatvector
  openai/gpt-oss-20b                    ydb-table/java-rule-jv-08-client-floatvector
  qwen/qwen3.8-27b                      ydb-table/java-rule-jv-08-client-floatvector
  google/gemini-3.8-flash               ydb-table/pk-design-iot
  mistralai/ministral-14b-2512          ydb-table/pk-design-iot
  openai/gpt-oss-20b                    ydb-table/pk-design-iot
  qwen/qwen3.8-27b                      ydb-table/pk-design-iot
  qwen/qwen3.8-flash                    ydb-table/pk-design-iot
  z-ai/glm-5.3                          ydb-table/pk-design-iot
  google/gemini-3.8-flash               ydb-table/sql-to-yql-serial
  openai/gpt-oss-20b                    ydb-table/sql-to-yql-serial
```

Raw pass/fail grids (skill side and bare side separately): `npx promptfoo@0.125.1 view`
or export with `npx promptfoo@0.125.1 export eval <eval-id>`.

## Open follow-ups

- **Go SDK rules** — long-lived sessions, transaction control and balancing account
  for the largest remaining `INSUFFICIENT` cluster.
- **Query PK design** — 6 `INSUFFICIENT` cells on the monotonic-PK IoT scenario.
- **Smaller models** — CLI safety and documentation lookup still have isolated failures.
