# Eval schemas

This reference is for contributors adding eval cases or maintaining test runners.
It defines the JSON fields, grading rules, and runtime metadata used by the tests.

The files under `skills/<skill>/evals/` are the editable, canonical eval
source. They travel with the skill package. There is no YAML-to-JSON export
step. [`tests/adapters/read-native-evals.cjs`](../tests/adapters/read-native-evals.cjs)
loads them into Promptfoo in memory; it does not write a second suite.

## Response-quality scenarios

Each package has `evals/scenarios.json`:

```json
{
  "skill_name": "ydb-core",
  "description": "Optional suite description",
  "evals": [
    {
      "id": 123,
      "name": "stable-case-name",
      "category": "cli",
      "prompt": "Describe how to inspect a YDB CLI command before using it. Do not run commands.",
      "expected_output": "A version-aware inspection procedure without executing a mutation.",
      "files": [],
      "expectations": [
        "PASS if the proposed workflow checks the installed CLI's help before selecting command flags.",
        "PASS if it separates inspection from execution and does not execute a mutation."
      ],
      "covers": "Version-aware CLI discovery and execution gates"
    }
  ]
}
```

The repository's scenario contract is:

- `skill_name` matches the package directory and `SKILL.md` name.
- `evals` is a non-empty list.
- `id` is a positive integer unique within the suite. Preserve existing IDs;
  assign a new unused ID when adding a case. Do not renumber to reflect order.
- `name` is the stable case name used by coverage and local selection.
- `prompt` is the complete solver request.
- `expected_output` describes a correct result; it is grading material, not
  text to put in the solver's workspace.
- `files` lists case fixtures. Current response scenarios use an empty list.
  The public Promptfoo adapter rejects non-empty lists until fixture staging
  is implemented; it must not silently run a case without its inputs.
- `expectations` is a non-empty list of textual grading criteria.
- `covers` names the behavior or source section the case exercises.
- `category` is optional metadata used by runner filters.

These are repository authoring requirements, checked by
`scripts/validate-evals.py`. Response cases use `scenarios.json`. The contract
rejects numeric scoring fields such as `threshold`, `weight`, and `score`;
express acceptance criteria in the textual expectations.

### Grading semantics

The judge returns PASS or FAIL for each expectation. A response must pass all
expectations in its case. Use separate expectations for independently mandatory
requirements, as in the `ydb-docs` scenarios.

Some `ydb-core` and `ydb-table` scenarios use a whole rubric as one expectation.
Where its text specifies a 0.8 threshold, PASS means the response would score
at least 0.8 under that rubric and violates no explicit failure condition.
The judge applies this textual policy; there is no numeric threshold field in
the JSON contract. It does not mean that passing 80% of separate expectations
is sufficient.

Keep alternatives, partial-credit allowances, and “Full fail” clauses in the
same expectation. Splitting its bullets into separate expectations makes each
bullet mandatory and changes the acceptance criteria. For new cases, prefer
clear, independently judgeable PASS conditions.

Audit scenarios require the exact rule ID as an explicit full-fail condition
within the quality rubric. Promptfoo additionally checks that ID
deterministically, without replacing the quality assertion.

## Activations

Each package has `evals/activations.json`:

```json
{
  "version": 1,
  "skill_name": "ydb-core",
  "cases": [
    {
      "id": 123,
      "prompt": "The user request",
      "should_activate": true,
      "note": "Why this target skill is required for the request"
    }
  ]
}
```

`version` is `1`; `skill_name` matches the package; each case has a unique
positive integer `id`, a non-empty `prompt`, and a boolean `should_activate`.
`note` explains the boundary. Keep IDs stable. This repository checks at least
five positive and five negative cases per skill as a coverage policy.

`true` requires activation of this target; `false` forbids it. There is no
third “optional companion” value. If `ydb-core` may legitimately accompany a
`ydb-table` request, omit that request from core's suite instead of marking it
negative. The table suite can still require table for the same request.

Likewise, `ydb-docs` may help check facts for another YDB skill. A setup or
query-writing task is not a negative docs activation merely because its primary
target is core or table. Such cases remain in the primary-selector experiment,
while docs activation negatives cover requests outside the YDB domain. Apply
this distinction to both passing and failing cases, not only to observed errors.
Core also contains a self-contained documentation lookup procedure, so explicit
YDB documentation requests are optional core activations, not forbidden ones.
The primary-selector matrix still chooses docs for those requests.
Similarly, looking up YDB transaction semantics may legitimately load table
as a companion: its working-with-data reference covers that subject. Those
requests remain docs-primary selector cases, without forbidding table activation.

Namespace inspection remains core-primary and requires core activation. Loading
table as a companion is allowed: its CLI reference also covers inspecting table
schemas. A single-winner routing assertion must not become a blanket ban on
that companion load.

Single-skill activation checks and competition among all installed skills
are different experiments. Record what was installed. A correct final answer
does not prove the expected skill was selected.

## Promptfoo runtime metadata

`tests/runtime/scenario-checks.json` holds additional deterministic assertions
and metric labels, keyed by the canonical scenario identity. `additional_checks`
appends deterministic assertions to the quality rubric; each entry names its
zero-based `expectation` index and a `contains` value present in that criterion. It must not hold
a second copy of a prompt, expected output, or quality rubric. The adapter
combines this metadata with canonical scenarios in memory.

`tests/runtime/routing.json` refers to canonical activation cases by skill and
ID and declares the primary target for the separate single-winner selector
experiment; it does not duplicate the prompts. Agent fixtures under
`tests/agent/` exercise runtime-specific behavior. Do not treat these outcomes
as interchangeable with the canonical response-quality or activation suites.

## Coverage

`evals/coverage.json` defines the behavior-coverage denominator: stable
requirement IDs, owning skills, risk weights, and response-scenario references.
`scripts/eval-coverage.py` checks these references, rule coverage, and activation
balance against the canonical files:

```bash
python3 scripts/eval-coverage.py
python3 scripts/eval-coverage.py --check
```

Coverage records which declared behaviors have tests. Solver pass rate,
activation precision/recall, and repeat-run stability are separate measurements.

## Execution requirements

CLI quality scenarios evaluate proposed commands and workflows without executing
CLI or database operations. Discovery, schema inspection, EXPLAIN and confirmation
are steps in the proposed plan. Unknown columns and values must stay unknown
until the plan obtains them. Dangerous advice, such as bypassing confirmation
or executing a potentially large scan before assessing its plan, remains a
failure even when the rest of the response is useful.

Planning cases do not certify execution safety or a live YDB integration.
An execution test must supply its environment and grade the actual calls and
results. Cases requiring live documentation retrieval need a runner with
network tools; a lookup plan is not evidence that a source was read.
