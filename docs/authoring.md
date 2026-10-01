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
  references/    # OPTIONAL — language-agnostic driver/transport patterns
  embed/         # OPTIONAL — language-specific positive patterns
  rules/         # OPTIONAL — driver/transport anti-patterns
  evals/
    scenarios.json
    activations.json
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

Progressive disclosure is intentionally off for `ydb-core` itself: the SKILL.md body must remain in context whenever the skill triggers (body budget: ≤500 lines). The optional `references/` and `rules/` subdirs are loaded on demand the same way they are in surface skills, and they exist for driver/transport patterns whose surface is `ydb.Open(...)` rather than any one application API — balancing, session lifecycle, retry. Application-layer rules (query execution, transactions, schema) stay in the relevant surface skill (`ydb-table`, etc.). Every skill package must validate independently; refer to companion skills by slug instead of linking outside the package.

### Surface skills — split by authoring vs audit

```
skills/ydb-<surface>/
  SKILL.md
  references/    # language-agnostic positive patterns
  embed/         # language-specific positive SDK / driver patterns
  rules/         # what to catch (RULE-<PREFIX>-NN anti-patterns)
  evals/
    scenarios.json
    activations.json
```

Workflow inside `SKILL.md` loads **one** tree or the other based on task type (author vs audit), saving tokens when only one mode is needed. Body budget: ≤150 lines.

### `references/` and `embed/` content

`references/` contains language-agnostic YDB guidance. `embed/<lang>.md`
contains language-specific SDK or driver patterns.

- Short doc excerpt (what the feature is, with a link to upstream YDB docs).
- Positive-pattern snippet(s).
- One or two sentences explaining *why* this is the canonical pattern.
- **No rule IDs**, no severity labels — these files are for authoring, not auditing.

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

### References and package boundaries

Relative Markdown links must stay inside the current skill package. A
`references/` or `embed/` file may link to another file in the same package.
To direct the runtime to another installed skill, name its slug in prose; for
product facts, prefer an official external documentation URL. Arcadia Skill
Eval rejects resource links that escape the package and warns about
reference-to-reference chains, so important resources must be linked directly
from `SKILL.md`.

## Rule ID scheme

Rule IDs have the shape `RULE-<PREFIX>-<NN>`. Prefixes are **not pre-allocated**. When adding the first rule in a new category, choose a short uppercase prefix, register it in the table below, and increment `NN` sequentially thereafter. Renumbering after merge is forbidden.

### Prefix registry

<!-- Contributors: append a row below when claiming a new prefix. Keep ordered by first use. -->

| Prefix | Scope | First used in |
|--------|-------|---------------|
| JV | Java SDK / JDBC / Hibernate / Spring Data anti-patterns | skills/ydb-table/rules/java.md |
| GO | Go SDK (`ydb-go-sdk/v3`) — driver, sessions, query/table services, retry, transactions | skills/ydb-table/rules/go.md |
| CGO | Go SDK core driver, balancing, and session-lifecycle anti-patterns | skills/ydb-core/rules/go.md |
| CPP | C++ SDK (`ydb-cpp-sdk`) — query/table clients, retry, transactions, parameterization | skills/ydb-table/rules/cpp.md |
| PY | Python SDK (`ydb`) — query parameters and vector encoding | skills/ydb-table/rules/python.md |

### Severity labels

- **Critical** — data loss, correctness bug, or security issue. Ships only with explicit override.
- **High** — performance cliff or runaway resource cost likely to bite under production load.
- **Medium** — suboptimal but functional.
- **Low** — style or hygiene.

More precise definitions evolve alongside real rules. Don't invent cutoffs up front.

## Frontmatter

Required fields: `name`, `description`. Nothing else.

- `name` — kebab-case matching the directory.
- `description` — a selector-facing scope statement. State the closed positive scope first (for example, `Use only for ...`) and include grounded trigger phrases for the intended requests. Avoid listing detailed negative keywords: semantic selectors can match those words and overtrigger. Measure both recall and false activation with activation evals. See [`skill-creator`, "Write the SKILL.md"](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md#write-the-skillmd).

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

Write response-quality cases as promptfoo YAML under `tests/<skill>/`. The
Arcadia-compatible `skills/<skill>/evals/scenarios.json` is generated from
those files and travels with the skill during sync. Its schema is documented
in [`docs/schemas.md`](schemas.md).

After adding or changing a case, regenerate and check the Arcadia form:

```bash
python3 scripts/export-arcadia-evals.py
python3 scripts/export-arcadia-evals.py --check
```

Do not edit `scenarios.json` directly. Follow this authoring workflow:

1. Write prompts first. Leave `expectations` empty.
2. Run once to observe behavior.
3. Draft `expectations` based on what the model actually did, not what you imagined it would do.

See [`docs/testing.md`](testing.md) for how to run evals.

## Review checklist (use before PR)

1. `name:` is kebab-case, matches the directory.
2. `description:` states a closed positive scope and uses specific triggers grounded in SDK/CLI/docs.
3. No `version:` or other non-spec frontmatter fields.
4. Body ≤150 lines (surface skills) / ≤500 lines (`ydb-core`).
5. No cross-references from `rules/` to any other skill.
6. `references/` cross-references use relative paths and point only to `ydb-core` anchor sections.
7. All `RULE-<PREFIX>-<NN>` IDs use a prefix listed in the registry above.
8. Any trigger phrase or API name in `description:` can be found by grep in the upstream SDK source.

## See also

- [`docs/schemas.md`](schemas.md) — Arcadia `scenarios.json` shape used by this repository.
- [`docs/testing.md`](testing.md) — how to run the promptfoo compatibility matrix.
- [Upstream `skill-creator` SKILL.md](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md) — general skill-authoring principles.
