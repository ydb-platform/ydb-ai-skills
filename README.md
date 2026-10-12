# YDB AI Skills

AI coding agent skills for [YDB](https://ydb.tech) — for writing YQL, designing schemas, and reviewing Java application code against YDB. Skills auto-trigger based on context.

> **Status:** framework and scaffolding. Skill bodies are intentionally thin — content is migrated surface-by-surface, grounded in live YDB SDK source and upstream docs.

## What's Inside

| Skill                | Scope                                                                                                                                                 |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ydb-core**         | Entry point / router. YDB overview, auth and connection, schema basics, CLI discovery and scheme inspection. Baseline skill — auto-installed.     |
| **ydb-table**        | Writing YQL and executing it (SDK-embedded or with `ydb sql`). Optimization, schema design for query patterns, SQL-to-YQL conversion, audit.        |
| **ydb-docs** | Finds official documentation through `llms.txt`, with language and product-version selection. |

## Installation

### Local install (from cloned repo)

```bash
git clone https://github.com/ydb-platform/ydb-ai-skills.git
cd ydb-ai-skills

# Auto-detect agents in current project
./install.sh --detect

# Install for specific agent
./install.sh --agent=claude

# Install only ydb-table (ydb-core auto-included as baseline)
./install.sh --agent=claude --skills=ydb-table

# Install only ydb-table without the baseline
./install.sh --agent=claude --skills=ydb-table --no-core

# Install only the standalone documentation lookup skill
./install.sh --agent=claude --skills=ydb-docs --no-core

# Dry run — see what would be done
./install.sh --agent=claude --dry-run
```

### Remote install

```bash
# Auto-detect agents
curl -fsSL https://ai.ydb.sh | bash

# Specific agent
curl -fsSL https://ai.ydb.sh | bash -s -- --agent=cursor

# Multiple agents
curl -fsSL https://ai.ydb.sh | bash -s -- --agent=claude,copilot,gemini

# Global (user-level)
curl -fsSL https://ai.ydb.sh | bash -s -- --agent=claude --global

# All options
curl -fsSL https://ai.ydb.sh | bash -s -- --help
```

### Supported Agents

| Agent          | Project dir         | Global dir                 |
| -------------- | ------------------- | -------------------------- |
| Claude Code    | `.claude/skills/`   | `~/.claude/skills/`        |
| Cursor         | `.cursor/skills/`   | —                          |
| Windsurf       | `.windsurf/skills/` | —                          |
| GitHub Copilot | `.github/skills/`   | `~/.copilot/skills/`       |
| Codex CLI      | `.agents/skills/`   | `~/.codex/skills/`         |
| Roo Code       | `.roo/skills/`      | —                          |
| Gemini CLI     | `.gemini/skills/`   | `~/.gemini/skills/`        |
| Amp            | `.agents/skills/`   | `~/.config/agents/skills/` |
| Kiro           | `.kiro/skills/`     | —                          |
| Trae           | `.trae/skills/`     | —                          |
| Generic        | `.agents/skills/`   | `~/.agents/skills/`        |

## Usage

Skills trigger automatically from the user's phrasing. Examples of queries that route to each skill:

```
> What is YDB and how do I connect to it from Go?
  → ydb-core

> Find the official Russian documentation for YDB 26.1 transactions
  → ydb-docs

> Write a YQL query to paginate users by created_at
  → ydb-table

> Review this Java/Hibernate code that calls saveAll in a loop
  → ydb-table (audit mode)
```

For agents that don't auto-trigger skills, reference the skill name explicitly in the prompt.

## Repository Structure

```
skills/                          Surface-aligned skills (universal format)
  ydb-core/                      SKILL.md + references/ + rules/ + canonical eval JSON
  ydb-docs/                      SKILL.md + canonical eval JSON
  ydb-table/                     SKILL.md + references/ + rules/ + canonical eval JSON
promptfooconfig.yaml             Preloaded API compatibility matrix
promptfooconfig.codex.yaml       Local Codex solver and judge over canonical scenarios
promptfooconfig.agent.yaml       Claude Code runtime selection and outcome fixtures
tests/
  adapters/                     Read canonical evals into Promptfoo in memory
  runtime/                      Deterministic checks and routing metadata
  agent/                        Separate agent-runtime fixtures
agents/grader.md                 Reference grader prompt (from anthropics/skills)
docs/
  authoring.md                   How to write a skill — structure, conventions, review checklist
  testing.md                     How to run the compatibility matrix with promptfoo
  templates/                     Copy-paste skeletons for SKILL.md, references, rules
install.sh                       Universal installer
```

## Testing

Edit response-quality cases in `skills/<skill>/evals/scenarios.json` and
activation cases in the companion `activations.json`. These are the single
editable source for their prompts and criteria. The files travel with the
skill; the Promptfoo adapter reads them in memory without generating another
suite.

Start with checks that make no model calls:

```bash
npm install
npm run validate
npm run test:tools
npm run test:adapters
```

Run one quality case with the local Codex app-server and its existing login. The judge
uses the same Codex authentication route; no OpenRouter judge is added:

```bash
npm run eval:codex -- --filter-first-n 1

# Separate real-Claude runtime fixtures: activation and outcome checks
npm run eval:claude -- --filter-first-n 1
```

These commands create temporary solver and judge workspaces outside the repo,
copy the skill resources without evals or test answers, and clean up afterward.
They consume the selected account's model allowance. The preloaded multi-model
API matrix remains an explicit alternative with its own API credentials and
grading configuration.

Compare results only with the model, judge, and runtime settings recorded.
The 66 migrated rubrics preserve their original alternatives, partial
credit, and explicit failure conditions as complete expectations. The 63
explicit case-level 0.8 thresholds remain part of the textual acceptance
policy; the three documentation rubrics use a complete-criterion PASS verdict.
Historical numeric scores are not directly comparable with the new verdicts.

See [`docs/testing.md`](docs/testing.md) for runtime choices, focused runs,
static validation, current check wiring, and result interpretation, and [`docs/schemas.md`](docs/schemas.md)
for the JSON contract.

## Contributing

Read [`docs/authoring.md`](docs/authoring.md) before adding content. The short version: stay grounded in upstream YDB SDK source, don't invent rules from memory, one `RULE-<PREFIX>-<NN>` prefix per category claimed in the registry on first use, keep SKILL.md bodies short.

## License

Apache-2.0
