# Project guide for coding agents

This repository, **ydb-ai-skills**, ships AI coding agent skills for [YDB](https://ydb.tech). The skills auto-trigger inside Claude Code / Cursor / Codex / etc. and route the agent toward grounded YDB material instead of letting it generalize from training memory. Skill bodies are deliberately small; details land in `references/` (positive patterns) and `rules/` (anti-patterns with `RULE-<PREFIX>-<NN>` IDs).

When you, the coding agent, work in this repo: the rules below are non-negotiable. Project-specific conventions on top of them live in [`docs/authoring.md`](docs/authoring.md) — read it before adding or restructuring skill content.

## Cardinal rule: no invention

Every factual claim about YDB, an SDK, a driver, or a framework must be grounded in upstream source before it lands on disk. The failure mode this repo exists to fight is precisely a model confidently inventing YDB-shaped statements that don't hold (PostgreSQL-style `SERIAL`, fabricated YQL built-ins, non-existent SDK method names, plan claims that aren't true).

Acceptable verification sources:

- **YDB docs**: <https://ydb.tech/docs/en/>. Fetch with WebFetch when you need a specific section.
- **YDB GitHub orgs**: prefer `gh api repos/ydb-platform/<repo>/contents/<path>` (returns content directly) or `gh search code --repo ydb-platform/<repo>` over WebFetch for code lookups. Relevant repos include `ydb`, `ydb-jdbc-driver`, `ydb-java-sdk`, `ydb-java-dialects`, `ydb-java-examples`, `ydb-go-sdk`, `ydb-python-sdk`, `ydb-cpp-sdk`, `ydb-dotnet-sdk`, `ydb-js-sdk`.
- **Standard external references** when an SDK delegates to a framework: Hibernate user guide, Spring Data JPA reference, Jakarta Persistence spec, JDK JavaDoc. Use the version-pinned canonical URL and verify it returns HTTP 200 before citing.

If a claim cannot be grounded in any of the above:

- Soften the wording until what remains is grounded ("non-index-friendly predicate" instead of "FullScan", if FullScan can't be confirmed).
- Or drop the item from the change set and add a follow-up note to the user.

Never ship a sharper claim than the verification supports. "Sounds plausible" is not verification.

## Where things live

```
skills/
  ydb-core/SKILL.md             single-file router; stable anchor sections (#connecting, #schema-basics, ...)
  ydb-table/                    Table surface — YQL, schema, query execution
    SKILL.md
    references/                 language-agnostic YDB-level guidance
      working-with-data.md      reads, writes, and transaction modes
    embed/                      per-language positive SDK / driver patterns
      <lang>.md
    rules/                      RULE-<PREFIX>-<NN> anti-patterns
      <lang>.md
  ydb-topics/, ydb-coordination/  same shape as ydb-table
docs/
  authoring.md                  full content conventions, prefix registry
  templates/                    copy-paste skeletons (SKILL.md.tmpl, reference.md.tmpl, rule.md.tmpl)
```

## Conventions you must respect

- **Content buckets do not mix.** `references/` holds language-agnostic positive guidance, `embed/` holds language-specific positive patterns, and `rules/` holds audit anti-patterns with `RULE-<PREFIX>-<NN>`, severity, signals, problem, and fix. Positive guidance has no rule IDs or severity labels.
- **`rules/` files are self-contained.** No cross-skill links from `rules/`. The user may install one surface skill without the others; rules must still produce correct audit output. `references/` and `embed/` may link to files inside the same skill package. Do not use relative links that escape the package; refer to a companion skill by slug or link official external documentation.
- **YDB-level files stay language-agnostic.** Top-level `references/*.md` (e.g. `working-with-data.md`) and any cross-cutting references must not mention JDBC / Hibernate / Spring / Java / Python / Go / .NET / C++ tokens. Per-language guidance goes in `embed/<lang>.md` and `rules/<lang>.md`. Verify with `grep -iE 'jdbc|hibernate|spring|java|jpa|python|golang|\.net|dotnet|csharp'` before committing.
- **Prefix registry.** New rule prefixes must be registered in the table in `docs/authoring.md` on first use. Never reuse an ID or renumber after merge. Currently allocated: `JV` (Java SDK / JDBC / Hibernate / Spring Data), `GO` (Go SDK application APIs), `CGO` (Go core driver), `CPP` (C++ SDK), and `PY` (Python SDK).
- **Skill `description:` matches shipped content, not aspirations.** The selector triggers on what's in `description:`. If you list `ydb-go-sdk` in the triggers but the skill has no grounded Go content, the skill will fire on Go code and have nothing useful to load — worse than not firing. Update the description when content lands, not before.

## Git workflow

- **Branch for any non-trivial change.** `main` is protected. Trivial typo / formatting fixes on `main` are acceptable; new rules, references, SKILL.md edits, or anything spanning >1 file goes on a feature branch and ships via PR.
- **Stage explicit paths.** This repo can have long-running dirty worktrees from parallel work. Never `git add -A` or `git add .` — name each file path you mean to commit.
- **Commit messages descriptive.** Look at recent `git log` for tone — a one-line subject framed as "scope: action" plus a body when it isn't obvious from the diff. Don't amend pushed commits, don't `--no-verify`.

## Before you start a non-trivial change

If the change has architectural shape (new skill, new surface, restructuring SKILL.md routing, adding multiple related rules), pause and talk to the user about the approach before writing. A short discussion catches scope and grounding problems while they're still cheap to fix.

For routine additions — one new rule, one new reference file, a wording tweak — just do it, with the verification step from the cardinal rule.

## Useful pointers

- Full content conventions and prefix registry: [`docs/authoring.md`](docs/authoring.md).
- Templates for new files: [`docs/templates/`](docs/templates/).
- Testing harness: [`docs/testing.md`](docs/testing.md).
