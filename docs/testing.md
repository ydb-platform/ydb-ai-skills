# Testing skills

Response-quality cases are authored once, in
`skills/<skill>/evals/scenarios.json`. Activation cases live alongside them in
`activations.json`. These JSON files travel with the skills and are also
read by the public Promptfoo adapter. There are no generated eval copies to
refresh after an edit. See [the schemas](schemas.md) for fields and grading
semantics.

## What each run measures

| Run | Solver context | What it checks |
| --- | --- | --- |
| Preloaded matrix, `promptfooconfig.yaml` | Skill instructions and resources embedded in the prompt | Response quality on 66 text/planning scenarios; no tool execution |
| Bare comparison, `promptfooconfig.bare.yaml` | No preloaded skill material | A separate baseline for those same 66 scenarios |
| Selector matrix, `promptfooconfig.routing.yaml` | Skill descriptions only | Which single primary skill the model selects |
| Claude runtime, `promptfooconfig.agent.yaml` | Installed packages in an isolated temporary workspace | Actual Skill-tool selection and runtime-specific outcome checks |
| Offline Codex, `promptfooconfig.codex.yaml` | Installed packages in an isolated temporary workspace | 66 text/planning scenarios, with local skill reads and no network |
| Online Codex, `promptfooconfig.codex-online.yaml` | Installed packages with network retrieval enabled | The one live documentation-verification scenario |

The preloaded matrix is a useful upper-bound experiment, not a substitute for
runtime selection. The selector's single answer and the set of skills an agent
actually loads are different observations: an optional companion may be valid
even when it is not the primary selection. Keep activation results, response
quality, and deterministic outcome checks separate.

Sharing the case files does not make these environments identical. Compare
results only with the model, judge, context, case set, and runtime settings
recorded.

## Canonical cases and the Promptfoo adapter

Edit canonical JSON directly. [`tests/adapters/read-native-evals.cjs`](../tests/adapters/read-native-evals.cjs)
loads response scenarios into Promptfoo in memory, using each scenario's `prompt`
and `expectations`. `tests/runtime/scenario-checks.json` adds deterministic
assertions and metric labels keyed by `skill:name`; it contains no duplicate
prompts or quality rubrics. The mandatory rule-ID check is part of the native
whole rubric and is also checked deterministically through `additional_checks`;
this extra assertion must not replace the quality rubric. `tests/runtime/routing.json` identifies canonical
activation cases and their primary targets for the selector experiment.
Runtime fixtures in `tests/agent/` remain separate tests of agent behavior.

Most core/table quality rubrics keep alternatives, partial credit and explicit
failure conditions together in one expectation. These rubrics require an overall
score of at least 0.8 and no explicit failure condition, expressed as a binary
PASS or FAIL. Preserve the stated alternatives and partial-credit allowances;
do not turn every bullet into a separate mandatory criterion. An exact rule ID
is mandatory when the case explicitly requires it.

The three `ydb-docs` scenarios keep independent requirements in separate
expectations, all of which must pass. New scenarios should use clear PASS
criteria. The JSON contract has no numeric threshold field; any partial-credit
policy belongs in the expectation text.

## Review meaning before changing a failed case

Check the intended user outcome before changing either the skill or its test.
A lookup plan should give actionable URLs and selection steps without claiming
that retrieval happened. Actual verification should retrieve evidence or explain
why it could not be established. A network prohibition allows local file reads;
do not conflate local search with web search. Accept equivalent official sources
and paths when the request does not prescribe one exact route.

The docs quality suite separates two no-network lookup plans from one actual
source-verification task. Its activation suite requires docs for explicit lookup
requests and forbids it for unrelated products/tasks. General YDB tasks can use
docs as an optional companion and are evaluated for their primary target in the
separate selector matrix, not as forbidden docs activations.

The CLI quality suite checks proposed workflows and commands. It does not run
against a database or require an installed CLI. A correct plan includes discovery
through version/help, schema inspection where necessary, EXPLAIN before relevant
execution and confirmation for destructive changes. It must not invent the
schema or data. These cases do not certify the order of actual database calls.
Actual execution needs a separately prepared environment and grading of tool
calls and results.

When prompts, criteria, or the evaluated case set change, record that revision
and run a new baseline. Do not count a case removed for a semantic reason as a
newly passing case or compare the new percentage directly with the old one.

## Focused runs

Start with static validation and adapter tests; these do not use a model.
For a changed skill, run one relevant activation case before a response-quality
case if routing is uncertain. The `ydb-docs:lookup-offline` request is present
in both case types under ID `2133047914`, so they can be checked separately.
An activation check asks whether the skill loaded; a scenario asks whether the
answer meets the requirements. A run with an invalid judge verdict is an
evaluation error, not a reliable content FAIL.

Then run only the changed scenarios and a small selection of cross-skill
regressions. Reserve a full suite on one fixed agent/model for a release or CI
budget; do not start with the complete model matrix on a personal quota.
Without that full run, report which cases remain unverified.

## Deterministic checks first

These repository checks make no model calls and need only Python:

```bash
# Complete repository validation, also available as npm run validate.
python3 scripts/validate-skills.py

# Narrower checks for diagnosing eval data or coverage failures.
python3 scripts/validate-evals.py
python3 scripts/eval-coverage.py --check
```

`validate-evals.py` checks the canonical JSON contract: scenario and activation
fields, unique case IDs, positive and negative activation examples, and runtime
metadata references. It also rejects duplicate legacy response-case sources.
It validates test definitions without running an agent or judging an answer.

`validate-skills.py` is the full entry point. It checks package frontmatter,
resource links, rule prefixes, unfinished author markers, language boundaries,
and generated description freshness. It then invokes `validate-evals.py` and
`eval-coverage.py --check`. Coverage checks declared behavior mappings and rule
coverage against the canonical scenarios. Coverage measures the presence of
tests, not whether a model passes them.

### When the checks run

- `npm run validate` explicitly runs `validate-skills.py`, including the eval
  and coverage checks above. Either validator can also be run directly.
- `install.sh` runs `validate-skills.py` before copying or linking skills when
  both the validator and `python3` are available; a failure aborts installation.
- `npm run test:tools` and `npm run test:adapters` explicitly run the Python and
  JavaScript test suites for repository tooling. Validation does not run them.
- `npm run eval:codex`, `npm run eval:codex:online` and `npm run eval:claude` explicitly start model-backed
  runs. They do not run the static validators or tooling tests first.

This repository currently has no GitHub Actions workflow or build-system
target that invokes these checks on pull requests. The checks must be run
explicitly or through the installer; merely shipping the scripts does not
block a GitHub PR. Required status checks are configured separately in GitHub.

## Public runtime workspaces

`scripts/run-promptfoo.py` creates separate temporary solver and judge
workspaces outside the repository. It copies all three skill packages,
excluding `evals/`, test code, and grading answers, and exposes the packages
through `.agents/skills` and `.claude/skills`. It sets `YDB_EVAL_WORKSPACE`
and `YDB_EVAL_JUDGE_WORKSPACE` for the selected config, forwards Promptfoo
arguments, and cleans up the temporary directories after the run.

Use the npm wrappers below instead of invoking these runtime configs directly.
Do not run the solver from the repository root: it can otherwise read test
cases, expected outputs, grader material, or the repository's authoring
`CLAUDE.md`. Workspace separation reduces accidental leakage; the runtime's
tool and filesystem permissions still determine what the agent can access.

## Public API matrix

The preloaded matrix uses an OpenAI-compatible endpoint. Set the endpoint's
credentials explicitly; the default config uses OpenRouter:

```bash
export OPENROUTER_API_KEY="<token>"
# Optional endpoint override used by the main matrix:
export OPENROUTER_API_BASE_URL="https://openrouter.ai/api/v1"
npx promptfoo@latest eval -c promptfooconfig.yaml
npx promptfoo@latest view
```

Both HTTP matrices and offline Codex explicitly exclude
`ydb-docs:verify-source-chain`, which needs live retrieval tools. The loader
prints the excluded case; a 66-case result is not coverage of all 67 scenarios.
The opt-in online profile below runs the remaining case from the same canonical
JSON, without a duplicate test definition.

These are API-backed runs and can consume both solver and grader credits. Read
the selected config's provider and grading configuration before a large run.
The description-only routing matrix uses deterministic assertions rather than
an LLM judge, but its selector model still uses the configured API:

```bash
npx promptfoo@latest eval -c promptfooconfig.routing.yaml
```

For a focused run, limit both the provider and cases:

```bash
npx promptfoo@latest eval -c promptfooconfig.yaml \
  --filter-providers 'qwen' --filter-first-n 3 -j 1
```

Use `--filter-pattern` to match a case description. Run repeated uncached trials
when measuring stability; a single successful response is not evidence of a
reliable activation or safety boundary. Inspect failed responses and grader
reasoning before changing a test. A failing criterion may reveal either a skill
problem or ambiguity in the criterion.

## Local agent profiles

Install dependencies and run the repository checks first:

```bash
npm install
npm run validate
npm run test:tools
npm run test:adapters
```

The offline Codex config runs 66 canonical response-quality scenarios with separate Codex
app-server solver and judge sessions using the same authentication route. With the
local CLI configured for a personal login and no API-key override, it uses
that account; it does not silently fall back to an OpenRouter or another API
judge. Local runs can consume the account's usage allowance. The selected
model follows the local profile/config; record it when comparing results.

The profile starts the local Codex CLI's app-server with a read-only sandbox
and `on-request` approvals. Requests for additional command/file permissions
are declined. Each solver or judge turn has a three-minute timeout. Configured
runtime policies remain in force.

```bash
# One scenario first; arguments after -- are forwarded to Promptfoo.
npm run eval:codex -- --filter-first-n 1

# A selected scenario; use its name or description in the pattern.
npm run eval:codex -- --filter-pattern '^ydb-core:onboarding ·' \
  --no-share --output /tmp/ydb-onboarding.json

# Opt-in network retrieval for the one live documentation scenario.
npm run eval:codex:online

# Separate Claude Code activation/outcome fixtures, using its local SDK login.
npm run eval:claude -- --filter-first-n 1
```

The online profile enables network access and live web search for its solver;
the judge remains offline. Existing account and runtime access policies still
apply. An honest retrieval failure is a valid outcome where the rubric permits
it, but does not establish successful source-reading coverage.

The Codex judge checks the complete canonical expectations. Passing requires
the required expectations to pass. Different judge implementations can produce
different verdicts for the same prompt. Inspect the judge's reasons when a
response falls near the rubric's acceptance boundary.

Codex quality assertions receive the final answer together with the solver's
recorded actions and results. Exact-text assertions still examine only the final
answer, so text seen in a tool result cannot satisfy a required rule-ID mention.
Missing action metadata is an evaluation error, not evidence that no commands
were run. Tool evidence helps the judge assess retrieval claims; the CLI planning
suite still evaluates advice rather than a live execution experiment.

Quality PASS alone does not prove a skill was loaded. In a saved Promptfoo
JSON report, inspect `results.results[0].response.raw` (a JSON-encoded Codex
turn): a successful skill read must have `status: completed`, exit code `0`,
and the expected skill text in its command output. A failed read or runtime
configuration error must not be reported as a successful skill activation.

The Claude runtime suite uses the real Skill tool and checks activation apart
from final-answer outcomes. Its config restricts tools for the offline
fixtures. Codex has its own tool events and runtime contract; do not assume it
emits Claude's Skill-call signal.

API-backed model comparisons remain a separate explicit choice. A local solver
login is not automatically a credential for an unrelated API judge. Read the
selected configuration before choosing that route.

## Reporting results

Record the skill and case revision, installed packages, solver/judge identities,
runtime profile, repeat count, and failures. Separate structural validation,
coverage, activation, and response quality in the report. Inspect at least a
sample of passing explanations as well as failures: a generous judge can hide
a regression.

Ad-hoc results need not be committed. Keep a baseline snapshot only when it helps
a comparison, and label it with the evaluation setup.

[`matrix-baseline.md`](../matrix-baseline.md) uses a different case set and grading
setup; its percentages are not directly comparable with the current suite.
`scripts/grader-agreement.py` accepts only legacy single-rubric exports and
rejects the current canonical format. It cannot validate judge agreement for
this suite.

## See also

- [Authoring conventions](authoring.md)
- [Eval schemas](schemas.md)
- [Promptfoo documentation](https://www.promptfoo.dev/docs/intro)
- [Preloaded matrix configuration](../promptfooconfig.yaml)
