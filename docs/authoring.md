# Authoring skills for this repo

This file documents the conventions unique to `ydb-platform/ydb-ai-skills`. General-purpose skill authoring guidance lives upstream at [`anthropics/skills/skills/skill-creator/SKILL.md`](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) — read that first, then apply the rules below on top.

## Taxonomy

Skills are decomposed **by YDB surface**, not by developer medium (code vs SQL vs config):

| Skill | Surface |
|-------|---------|
| `ydb-core` | Entry point / router. Covers YDB overview, connection + auth, schema basics, CLI discovery and scheme inspection. For models unfamiliar with YDB or prone to hallucination. |
| `ydb-table` | Writing YQL and executing it — in SDK code, from CLI (`ydb sql`), or directly. |
| `ydb-topics` | Pub/sub API + native Kafka adapter. |
| `ydb-coordination` | Distributed locks, semaphores, leader election. |

`ydb-docs` is a standalone documentation-discovery utility, not a new YDB surface. It routes explicit documentation lookup to the official `llms.txt` indexes; implementation and audit tasks remain with the surface skills. The core skill also carries a short, self-contained lookup procedure.

`ydb-ops` (cluster operations) is deferred as a separate future skill.

### Surface-boundary decision principle

Content lives in the surface skill whose API it is called on. When a method or concept spans surfaces, it is documented in both with short cross-references — not duplicated in full. Specific placements are decided case-by-case when authoring content, against live SDK source and upstream YDB documentation. No pre-filled routing table — don't invent one.

## Skill file layout

### `ydb-core` — primary SKILL.md plus optional driver-level subdirs

```
skills/ydb-core/
  SKILL.md
  references/    # OPTIONAL — driver/transport patterns (balancing, sessions)
  rules/         # OPTIONAL — driver/transport anti-patterns
  evals/evals.json
```

The body of `SKILL.md` carries stable section anchors so other skills can deep-link to it:

- `## overview` — what YDB is + the "don't invent, read docs" behavioral rule + doc map
- `## versioning` — server + SDK release cadence
- `## surfaces` — router to `ydb-table`, `ydb-topics`, `ydb-coordination`
- `## packages` — SDK repos, install coordinates, CLI, JDBC
- `## cli` — version-aware command discovery, connection context, inspection, and execution gates
- `## connecting` — connection strings, auth env vars, CLI profile
- `## balancing` — pointer to `references/balancing.md` + `references/session-lifecycle.md`
- `## local-deployment` — Docker / Kubernetes / Ansible
- `## integrations` — ORMs, migration tools, Terraform, Spark, EF Core
- `## schema-basics` — LLM failure modes on YDB schemas with concrete fixes

Progressive disclosure is intentionally off for `ydb-core` itself: the SKILL.md body must remain in context whenever the skill triggers (body budget: ≤500 lines). The optional `references/` and `rules/` subdirs are loaded on demand the same way they are in surface skills, and they exist for driver/transport patterns whose surface is `ydb.Open(...)` rather than any one application API — balancing, session lifecycle, retry. Application-layer rules (query execution, transactions, schema) stay in the relevant surface skill (`ydb-table`, etc.); cross-link only from `references/`, not `rules/`.

### Surface skills — split by authoring vs audit

```
skills/ydb-<surface>/
  SKILL.md
  references/    # how to write correctly (positive patterns + short doc excerpts)
  rules/         # what to catch (RULE-<PREFIX>-NN anti-patterns)
  evals/evals.json
```

Workflow inside `SKILL.md` loads **one** tree or the other based on task type (author vs audit), saving tokens when only one mode is needed. Body budget: ≤150 lines.

### `references/` content

- Short doc excerpt (what the feature is, with a link to upstream YDB docs).
- Positive-pattern snippet(s).
- One or two sentences explaining *why* this is the canonical pattern.
- **No rule IDs**, no severity labels — references are for authoring, not auditing.

### `rules/` content — template

```
### RULE-<PREFIX>-<NN>: <title>
**Severity**: Critical | High | Medium | Low
**What to look for**: <grep-friendly signals>
**Problem**: <1–3 lines>
**Fix**: <1–2 sentences naming the corrective API call(s), OR a short corrected snippet>
**Source**: <upstream file URL(s) backing the claim>
```

`Fix` may be prose-only when the prose itself names every corrective API the auditor needs (e.g. `query.WithIdempotent()`, `table.TxControl(table.BeginTx(...))`). Reach for a snippet when the fix turns on a non-obvious composition of calls or a config-file shape that prose can't capture (the Java rules' Hibernate `application.properties` block, JPA annotations, Spring meta-annotations). The Go rules ship prose-only after laptop A/B confirmed that adding code blocks did not improve audit quality on smaller models — verify the same on any new surface before going prose-only.

Rules must be self-contained — a surface skill installed without `ydb-core` must still produce correct audit output for its own rules. Do not cross-reference `ydb-core` from `rules/`.

### Cross-references (from `references/` only)

A `references/` file may link into `ydb-core/SKILL.md` by anchor:

```
See ../ydb-core/SKILL.md#schema-basics for partitioning fundamentals.
```

Relative paths only. One level of indirection.

## Rule ID scheme

Rule IDs have the shape `RULE-<PREFIX>-<NN>`. Prefixes are **not pre-allocated**. When adding the first rule in a new category, choose a short uppercase prefix, register it in the table below, and increment `NN` sequentially thereafter. Renumbering after merge is forbidden.

### Prefix registry

<!-- Contributors: append a row below when claiming a new prefix. Keep ordered by first use. -->

| Prefix | Scope | First used in |
|--------|-------|---------------|
| JV | Java SDK / JDBC / Hibernate / Spring Data anti-patterns | skills/ydb-table/rules/embed/java.md |
| GO | Go SDK (`ydb-go-sdk/v3`) — driver, sessions, query/table services, retry, transactions | skills/ydb-table/rules/embed/go.md |
| CPP | C++ SDK (`ydb-cpp-sdk`) — query/table clients, retry, transactions, parameterization | skills/ydb-table/rules/embed/cpp.md |
| PY | Python SDK (`ydb`) — query parameters and vector encoding | skills/ydb-table/rules/embed/python.md |

### Severity labels

- **Critical** — data loss, correctness bug, or security issue. Ships only with explicit override.
- **High** — performance cliff or runaway resource cost likely to bite under production load.
- **Medium** — suboptimal but functional.
- **Low** — style or hygiene.

More precise definitions evolve alongside real rules. Don't invent cutoffs up front.

## Frontmatter

Required fields: `name`, `description`. Nothing else.

- `name` — kebab-case matching the directory.
- `description` — **third person**, in the style that Claude's skill selector expects. Include both what the skill does **and** specific trigger phrases that grab the right user intent. Upstream calls this "pushy" phrasing and documents it as the counter to Claude's tendency to undertrigger — see [`skill-creator`, "Write the SKILL.md"](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md#write-the-skillmd).

Do not add `version:`, `compatibility:` (unless you really mean it), or other fields — they are not part of the Agent Skills spec and get ignored or, worse, cause confusion in other runtimes.

## SKILL.md body shape

Copy from `docs/templates/SKILL.md.tmpl`. The expected sections:

1. **Tagline** — one sentence.
2. **Workflow** — numbered: identify task → load sources → do the work → report.
3. **Load-sources matrix** — surface skills only; selects `references/` vs `rules/` vs both based on task.
4. **Gotchas** — 4–6 real traps. Upstream: *"the most valuable content in any skill is the Gotchas section."*
5. **Content rules** — prose with *why*, no all-caps `NEVER`/`ALWAYS`. Cover: no fabrication, cite rule IDs when auditing, prefer stating uncertainty over guessing.

Do not include a `## Test Fixtures` section or any other pointer to deleted directories.

## Descriptions — what to put in the trigger string

Grounded triggers only. When writing `description:`, list concrete SDK symbol names (imports, classes, methods), YQL keywords, CLI flags that actually exist in the upstream source. Do not invent plausible-looking trigger phrases from training-data memory; verify against:

- The YDB SDK repositories for the language in question (`ydb-go-sdk`, `ydb-python-sdk`, `ydb-java-sdk`, `ydb-cpp-sdk`, `Ydb.Sdk`).
- The YDB CLI's `--help` output.
- Upstream docs at https://ydb.tech/docs.

A trigger phrase without a corresponding grep hit in upstream code is a bug.

## Evals

One `evals/evals.json` per skill. Schema in [`docs/schemas.md`](schemas.md) (ported verbatim from upstream). Follow the upstream workflow:

1. Write prompts first. Leave `expectations` empty.
2. Run once to observe behavior.
3. Draft `expectations` based on what the model actually did, not what you imagined it would do.

See [`docs/testing.md`](testing.md) for how to run evals.

## Review checklist (use before PR)

1. `name:` is kebab-case, matches the directory.
2. `description:` is third-person, specific, grounded in real symbols from SDK/CLI/docs.
3. No `version:` or other non-spec frontmatter fields.
4. Body ≤150 lines (surface skills) / ≤500 lines (`ydb-core`).
5. No cross-references from `rules/` to any other skill.
6. `references/` cross-references use relative paths and point only to `ydb-core` anchor sections.
7. All `RULE-<PREFIX>-<NN>` IDs use a prefix listed in the registry above.
8. Any trigger phrase or API name in `description:` can be found by grep in the upstream SDK source.

## See also

- [`docs/schemas.md`](schemas.md) — canonical JSON shapes for `evals.json`, `grading.json`, `benchmark.json`.
- [`docs/testing.md`](testing.md) — how to run the promptfoo compatibility matrix.
- [Upstream `skill-creator` SKILL.md](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) — general skill-authoring principles.

## Public ydb-docs export

`skills/ydb-docs/SKILL.md` is the complete, standalone skill for public open-source YDB documentation at `ydb.tech`. Keep its language and product-version discovery instructions in this file.

Downstream packages can import this file as an OSS reference alongside separately maintained deployment instructions. Consumers should resolve the source revision to a full commit SHA, copy the file without rewriting it, and record its content hash. Changes to downstream instructions belong in their owning repository; this public skill remains usable independently.
