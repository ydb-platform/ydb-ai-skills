# YDB AI Skills

AI coding agent skills for [YDB](https://ydb.tech) — for writing YQL, designing schemas, and reviewing Java application code against YDB. Skills auto-trigger based on context.

> **Status:** framework and scaffolding. Skill bodies are intentionally thin — content is migrated surface-by-surface, grounded in live YDB SDK source and upstream docs.

## What's Inside

| Skill                | Scope                                                                                                                                                 |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ydb-core**         | Entry point / router. YDB overview, auth and connection, schema basics, CLI discovery and scheme inspection. Baseline skill — auto-installed.     |
| **ydb-table**        | Writing YQL and executing it (SDK-embedded or with `ydb sql`). Optimization, schema design for query patterns, SQL-to-YQL conversion, audit.        |
| **ydb-search**       | Vector and full-text indexes, BM25, `HybridRank`, release compatibility for 25.1–26.3, recall tuning, index lifecycle, and search examples for Python, Go, Java, C++, and JavaScript SDKs. |
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

# Install search guidance (ydb-core auto-included)
./install.sh --agent=codex --skills=ydb-search

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

> Create YDB vector and full-text indexes and combine their rankings with HybridRank
  → ydb-search

> Review this Java/Hibernate code that calls saveAll in a loop
  → ydb-table (audit mode)
```

For agents that don't auto-trigger skills, reference the skill name explicitly in the prompt.

## Repository Structure

```
skills/                          Surface-aligned skills (universal format)
  ydb-core/SKILL.md              Single-file router — overview, auth, schema basics, CLI discovery
  ydb-table/                     SKILL.md + references/ + rules/
  ydb-search/                    Search references + SDK examples in references/embed/ + shared SQL assets
  ydb-docs/SKILL.md               Standalone documentation lookup via llms.txt
promptfooconfig.yaml             Compatibility matrix config — provider list, test discovery
prompts/coding-agent.yaml        Shared system prompt for all tests
tests/                           Test cases per skill (YAML, one per file)
agents/grader.md                 Reference grader prompt (from anthropics/skills)
docs/
  authoring.md                   How to write a skill — structure, conventions, review checklist
  testing.md                     How to run the compatibility matrix with promptfoo
  templates/                     Copy-paste skeletons for SKILL.md, references, rules
install.sh                       Universal installer
```

## Testing

A compatibility matrix built with [promptfoo](https://www.promptfoo.dev). Each `(provider, model)` pair runs every test; the grader scores each result via `llm-rubric`. Identifies the minimum model per vendor family that still works.

Quick run:

```bash
export OPENROUTER_API_BASE_URL="..."
export OPENROUTER_API_KEY="..."
npx promptfoo@latest eval
npx promptfoo@latest view
```

All providers route through one OpenAI-compatible endpoint. Default model set skews toward enterprise-deployed open-source (Qwen, DeepSeek, Mistral, Llama, GLM, Kimi) with one baseline per major cloud vendor (Anthropic, Google, OpenAI, xAI).

Details — adding tests, adding models, reading the matrix, known gaps — in [`docs/testing.md`](docs/testing.md).

## Contributing

Read [`docs/authoring.md`](docs/authoring.md) before adding content. The short version: stay grounded in upstream YDB SDK source, don't invent rules from memory, one `RULE-<PREFIX>-<NN>` prefix per category claimed in the registry on first use, keep SKILL.md bodies short.

## License

Apache-2.0
