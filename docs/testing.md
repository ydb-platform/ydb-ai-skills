# Testing skills

Goal: build a **compatibility matrix** — for each `(provider, model)`, measure how well our installable skills work when loaded into a coding-agent-style system prompt. Identifies the minimum model per vendor family that still passes.

The tool is [promptfoo](https://www.promptfoo.dev). One declarative `promptfooconfig.yaml` at the repo root drives everything.

## What this tests

Every eval runs this shape:

- **System prompt:** the installable skills' content embedded into one system message. `ydb-core` is loaded as `SKILL.md` plus its `references/balancing.md`, `references/session-lifecycle.md`, `references/embed/go.md`, and `rules/embed/go.md`. `ydb-table` is loaded as `SKILL.md` plus its `references/cli.md`, `references/working-with-data.md`, `references/query-parameters.md`, `references/embed/java.md`, `references/embed/go.md`, `references/embed/cpp.md`, `rules/embed/java.md`, `rules/embed/go.md`, `rules/embed/cpp.md`, `references/embed/python.md`, and `rules/embed/python.md` — i.e. the full body of each skill, as if the agent had read every Load-Sources entry.
- **User prompt:** supplied by the test case (`tests/<skill>/<case>.yaml`).
- **Grader:** `anthropic/claude-haiku-4.5` judges each `llm-rubric` assertion against a criterion block written in plain English.

This approximates the *ceiling* per model — every loadable file is fully in context. A model that fails this can't work in a real runtime (Claude Code, Codex, Cursor, etc.) where the agent additionally has to decide which skill to load and which references to read.

`ydb-search` is loaded with its release compatibility, vector, full-text, hybrid, and SDK references, including all five language pages and the shared SQL assets. Its cases under `tests/ydb-search/` exercise early-release vector lifecycle limits, standalone full-text query shape, hybrid candidate limits, and 26.3 enablement/schema/prefix requirements. Run just these cases with `--filter-pattern 'Search ·'`; routing cases are in `tests/routing/18-*` through `21-*`. Source inspection and static validation do not substitute for running the model matrix or executing SQL against a matching server.

Runtime-specific behavior (how Claude Code chooses skills vs. how Codex does) is **not** tested here. That requires installing each runtime and running against it, which is a manual exercise — see the [known gap](#runtime-level-testing-known-gap) below.

## Setup

One-time:

```bash
export OPENROUTER_API_KEY="<token>"
```

The matrix uses `OPENROUTER_API_BASE_URL` from the environment, defaulting to
`https://openrouter.ai/api/v1` — see the header comment in [`promptfooconfig.yaml`](../promptfooconfig.yaml).

promptfoo runs via `npx` — no local install needed:

```bash
npx promptfoo@latest eval         # run all tests across all providers
npx promptfoo@latest view         # open the matrix in the browser
```

## Speed knobs

Default concurrency is set to **12** in each `promptfooconfig*.yaml` via
`evaluateOptions.maxConcurrency`. On a healthy OpenRouter key this
finishes the full matrix in roughly a third of the time of the
promptfoo default (4). If your key's monthly limit caps single-request
size or rate, lower concurrency to avoid clustered 402s:

```bash
npx promptfoo@latest eval -j 4    # CLI override for slower keys
```

Two providers benefit from extra config to avoid burning tokens on
internal reasoning:

- **Moonshot Kimi K2.6** — reasoning mode is on by default and consumes
  the whole `max_tokens` budget on thinking before emitting any
  visible answer. We set `reasoning: { enabled: false }` on this
  provider so the budget goes to the actual response.
- **Google Gemini 3.1 Pro (preview)** — same problem in principle, but
  the OpenRouter route to Gemini rejects `reasoning: { enabled: false }`
  with HTTP 400 ("Reasoning is mandatory for this endpoint"). Live
  with the thinking budget; `max_tokens: 2048` is just enough.

Other models on the matrix don't accept the `reasoning` parameter at
all and return HTTP 400 if you set it — do not blanket-apply it.

For a subset (faster iteration while writing a new skill or test):

```bash
# single provider (regex match on provider id)
npx promptfoo@latest eval --filter-providers 'qwen3-coder'

# single test (regex match on the test's `description` field)
npx promptfoo@latest eval --filter-pattern 'keyset pagination'

# first N tests only
npx promptfoo@latest eval --filter-first-n 3

# combine: one test on one provider
npx promptfoo@latest eval \
  --filter-pattern 'Cloud auth' \
  --filter-providers 'anthropic/claude-haiku-4.5'
```

Results are stored in `~/.promptfoo/` and rendered as a matrix: rows = models, columns = test cases, cells = pass/fail + grader reasoning.

## Adding a test

1. Copy an existing file under `tests/<skill>/` as a starting point — structure is `description`, `vars.user_prompt`, `assert`.
2. Write the `user_prompt` as a realistic user turn. Avoid toy examples — model size matters less on trivial prompts.
3. Write the `llm-rubric` criteria as bullet points the grader can check against the skill content. Every criterion should be something the grader can verify from the skill body alone. Do not introduce facts that aren't in any SKILL.md — the test would be impossible to pass on principle.
4. Run once with a cheap model and read the grader's reasoning. If the criteria are too loose (everything passes) or too strict (everything fails), tighten / relax them.
5. Commit once the rubric gives stable results across two runs.

Worked example — a minimal outcome test:

```yaml
description: Query · Keyset pagination in YQL + Go

vars:
  user_prompt: |
    Write a YQL query and the Go code to paginate a `users` table by
    `created_at` (Timestamp) and `id` (Uint64) — 50 rows per page.

assert:
  - type: llm-rubric
    value: |
      The response should:
      - Use keyset pagination: `WHERE (created_at, id) > ...`. Avoid `OFFSET`.
      - Bind values as typed parameters — no raw string interpolation.
      - Wrap the Go query in a session-retry scope (db.Query().Do(...)).
      Partial credit if pagination is correct but Go wrapper is missing.
```

## Adding a model

Edit `promptfooconfig.yaml`. Copy one of the existing provider rows:

```yaml
- id: openai:chat:<vendor>/<model-slug>
  label: <Human-friendly label>
  config: *openrouter
```

The `<vendor>/<model-slug>` must match what OpenRouter exposes. Check the live list at https://openrouter.ai/models.

## Reading the matrix

`npx promptfoo@latest view` opens an HTML matrix.

- **Green cell (pass)** — the grader judged the response to satisfy every criterion. Sanity-check by clicking the cell and reading the reasoning; occasionally the grader is too generous.
- **Red cell (fail)** — the grader flagged at least one criterion as unmet. Read the reasoning to see whether this is a genuine failure or a too-strict rubric.
- **Yellow / partial** — one or more criteria failed but others passed; the test opted into partial credit via the rubric wording.

Per-model summary: pass rate column on the right. This is what drives the "minimum model per family" decision.

## When to bump the model set

- A new major model ships and is available on `/openrouter`. Add a row, re-run.
- A model gets deprecated. Remove the row.
- A customer asks "does our skill work on model X?" and X is not in the matrix. Add it, commit the matrix run output to `matrix.md` (optional — see below).

## Committing matrix results

Not done by default. The matrix changes every time any skill or test changes, so committing full results would be noisy. For a committed A/B snapshot see [`matrix-baseline.md`](../matrix-baseline.md). Ad-hoc export: `npx promptfoo@latest eval --output matrix.md --format markdown`.

## Static validator

Independent of the promptfoo matrix, [`scripts/validate-skills.py`](../scripts/validate-skills.py) enforces structural invariants over `skills/` — SKILL.md frontmatter shape, no `TODO(author)` markers, language-agnostic top-level `references/` files, relative-link resolution, and that every `RULE-<PREFIX>-<NN>` ID uses a prefix registered in [`docs/authoring.md`](authoring.md). It runs as a pre-flight inside `install.sh` (failure aborts the install) and is also runnable standalone:

```bash
python3 scripts/validate-skills.py
```

Exit code 0 = all checks passed; 1 = at least one violation, printed to stderr with file path and reason. Use this before opening a PR to catch the cheap mistakes without burning a promptfoo run.

## Routing matrix

A second promptfoo config — `promptfooconfig.routing.yaml` — tests the
selector behavior instead of the ceiling. The system prompt contains only
each skill's `description:` field (extracted from `SKILL.md` frontmatter
by `scripts/extract-descriptions.py` into `tests/routing/descriptions.md`);
no skill body is loaded. The model is asked to reply with one token — the
slug of the skill that should fire, or `none`.

This approximates what Claude Code / Cursor / Codex do internally when they
decide which skill to load. It catches two failure modes the ceiling matrix
can't see:

- **False negatives** — `description:` is too narrow; valid requests don't
  trigger the skill at all.
- **False positives** — `description:` is too broad; the skill loads on
  unrelated requests (worse than not loading — the agent reads irrelevant
  context).

Run it the same way as the main matrix, with `-c`:

```bash
npx promptfoo@latest eval -c promptfooconfig.routing.yaml
```

Asserts are deterministic regex (no LLM grader) — cheap to re-run after
any `description:` edit. `scripts/validate-skills.py` calls
`extract-descriptions.py --check` and fails if `tests/routing/descriptions.md`
is stale relative to the SKILL.md frontmatter.

## Runtime-level testing (known gap)

This setup tests models. It does not test runtimes — Claude Code / Cursor / Windsurf / Codex / Gemini CLI each have their own skill-loading mechanics (description-first routing, varying system-prompt construction, different tool sets) that can change the outcome from what the matrix shows.

Runtime-level testing requires installing each runtime and running against it with the skill installed. That is manual today:

1. Install skills into the target runtime (`./install.sh --agent=<name>`).
2. Spin up the runtime with a target model.
3. Paste a prompt from `tests/` into the runtime's chat.
4. Eye-check the response.

A non-trivial runtime-testing harness would need per-runtime drivers (subprocess calls or embedded automation). Deferred.

## What is NOT included

- **CI workflow.** Promptfoo runs locally against an OpenAI-compatible endpoint. CI wiring would require that endpoint to be reachable from CI and an API key provisioned as a secret — out of scope right now.
- **Cost tracking.** The matrix runs every provider × every test. Use `--filter-providers` / `--filter-pattern` during iteration to keep the spend low.
- **Trigger-only tests.** The current layout always loads all installable skills. If you need to measure "does the model correctly pick ydb-table given only the descriptions?" — that's a second-stage rig, not built here.

## See also

- [promptfoo docs](https://www.promptfoo.dev/docs/intro) — the framework itself.
- [promptfoo OpenAI-compat provider](https://www.promptfoo.dev/docs/providers/openai/) — the provider type all our models use.
- [`promptfooconfig.yaml`](../promptfooconfig.yaml) — the matrix config.
- [`prompts/coding-agent.yaml`](../prompts/coding-agent.yaml) — the shared system prompt.
- [`docs/authoring.md`](authoring.md) — how to write a skill; conventions that tests check against.
