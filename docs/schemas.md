# Eval schemas

## Arcadia Skill Eval scenarios

Every installable skill keeps its Arcadia cases in
`skills/<skill>/evals/scenarios.json`. The file travels with the skill during
the GitHub-to-Arcadia sync.

```json
{
  "skill_name": "ydb-core",
  "description": "Optional suite description",
  "evals": [
    {
      "id": 123,
      "name": "stable-case-name",
      "category": "cli",
      "prompt": "The user's request",
      "expected_output": "A concise description of the correct outcome",
      "files": [],
      "expectations": [
        "One independently judgeable requirement",
        "Another independently judgeable requirement"
      ],
      "covers": "The skill behavior or source section covered by the case"
    }
  ]
}
```

Required suite fields:

- `skill_name` — exactly matches the skill directory and `SKILL.md` name.
- `evals` — a non-empty array of cases.

Required case fields:

- `id` — unique positive integer. The generator derives it from the skill and
  case names, so adding a case does not renumber existing cases.
- `name` — stable case name derived from the promptfoo YAML filename.
- `prompt` — complete request passed to the agent.
- `expected_output` — short description of a correct result.
- `files` — fixture files required by the case; empty for the current YDB
  response-quality scenarios.
- `expectations` — non-empty list of independently judgeable requirements.
- `covers` — human-readable behavior or skill section covered by the case.

`category` is optional and is used by the local runner's include/exclude
filters.

The editable sources in this repository are `tests/<skill>/*.yaml`. Regenerate
the Arcadia files after changing them:

```bash
python3 scripts/export-arcadia-evals.py
python3 scripts/export-arcadia-evals.py --check
```

Do not edit generated `scenarios.json` files directly. Keeping the promptfoo
and Arcadia forms generated from one source prevents the two suites from
drifting.

Arcadia also discovers the older `evals/evals.json` filename. New cases in
this repository use `scenarios.json`, which is the current scenario format in
`ai/artifacts/skills`.

## Arcadia Skill Eval activations

Routing is a separate deterministic contract. The editable source remains
`tests/routing/*.yaml`; generation creates one package-local view for each
skill:

```json
{
  "version": 1,
  "skill_name": "ydb-core",
  "cases": [
    {
      "id": 123,
      "prompt": "The user request",
      "should_activate": true,
      "note": "Why this is inside or outside the skill boundary"
    }
  ]
}
```

Each skill must have at least five positive and five negative cases. Sibling
requests are negatives: a `ydb-table` request must not activate `ydb-core`, and
vice versa. Generate or verify the files with:

```bash
python3 scripts/export-arcadia-activations.py
python3 scripts/export-arcadia-activations.py --check
```

## Coverage contract

`evals/coverage.json` defines the denominator for behavior coverage. Every
requirement has a stable ID, owner skill, risk weight, and one or more response
scenarios. `scripts/eval-coverage.py` verifies those references, explicit rule
coverage, duplicate rule IDs, and positive/negative activation balance:

```bash
python3 scripts/eval-coverage.py
python3 scripts/eval-coverage.py --check
```

Coverage measures which declared behaviors have tests. Model pass rate and
multi-trial stability are reported separately.
