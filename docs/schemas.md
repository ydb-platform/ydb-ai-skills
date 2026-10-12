# Eval schemas

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
      "prompt": "Explain how to inspect a YDB CLI command before using it.",
      "expected_output": "A version-aware inspection procedure without executing a mutation.",
      "files": [],
      "expectations": [
        "PASS if the response inspects the installed CLI's help before selecting command flags.",
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

### Preserving the migrated rubrics

The unchanged migrated `ydb-core` and `ydb-table` rubrics remain whole expectations,
preceded by an explicit binary-verdict policy. Their original case-level
threshold was 0.8: PASS means the response would score at least 0.8 under that
rubric and violates no explicit failure condition; otherwise FAIL.

The three `ydb-docs` cases instead use separate expectations for their
independent requirements. Their prompts and criteria were reviewed semantically
to distinguish a lookup plan from actual source verification; they are no
longer a verbatim copy of the initial export. Each requirement must pass.
Do not wrap their bullet lists in a
single numbered expectation: in a local pilot the judge treated the nested
bullets as extra expectation IDs and returned an invalid verdict.

The documentation YAML cases had no case-level threshold. The original
matrix's shared judge allowed partial credit; the initial JSON-export PR
also tightened that shared judge. Requiring every documentation expectation
to pass is an explicit acceptance policy, not an equivalent reproduction of
the original numeric grading.

There is no numeric threshold option in this JSON contract. Alternatives, partial-credit
allowances, and “Full fail” clauses remain inside that same expectation.
Splitting those bullets into independent requirements would make optional
details mandatory and change the test.

Audit scenarios keep the mandatory exact rule ID in the same whole
expectation as their quality rubric, as an explicit full-fail condition. This
preserves the former conjunction of quality and exact-ID checks while avoiding
a second, redundant expectation that the local judge repeatedly omitted.
Promptfoo additionally checks the same ID deterministically, without replacing
the quality assertion. New cases should normally use clear PASS conditions
rather than copying the historical scoring policy.

The judge implementation and installed skill context can differ between
runners. Historical Promptfoo scores and current binary pass rates are therefore
not directly comparable; record a new baseline when comparing runtimes.

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

The Java batching cases `java-rule-jv-02-batch-size-unset` and
`java-rule-jv-03-save-in-loop` were corrected against Hibernate and Spring Data
sources: batching is disabled by default, ordering is optional, and a save loop
inside an existing transaction does not inherently defeat batching. The companion
`java-rule-jv-03-save-without-transaction` covers the actual transaction-boundary
problem. These are intentional semantic corrections, not equivalent formatting
changes.

The primary-key scenario rejects function expressions inside `PRIMARY KEY`:
a hash prefix is a stored column, populated on writes and supplied on keyed
reads. Its partition minimum is relative to node count; the prompt gives no
numeric node count or guarantee that the id-service produces monotonic ids.
The serial-conversion scenario requires YQL's separate primary-key clause;
a high-write redesign is optional for a request asking only for direct syntax
conversion. These corrections are grounded in the official YDB schema docs.
Two activation requests were clarified without naming a skill: the query is
explicitly for YDB, and the Go audit includes the code instead of referring to
a handler absent from the test workspace.
The Java save-loop boundary case expresses its two existing requirements
separately: batching within the supplied transaction, and the actual saveAll()
implementation. This makes a partial explanation visible as a missing criterion
instead of allowing a broad summary verdict to overlook it.
