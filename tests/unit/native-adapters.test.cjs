'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadScenarios } = require('../adapters/read-native-evals.cjs');
const { loadRouting } = require('../adapters/read-routing.cjs');

test('every native expectation has a Promptfoo assertion; prompts contain no rubrics', () => {
  const tests = loadScenarios();
  const skillsRoot = path.resolve(__dirname, '../../skills');
  const expectedCount = fs.readdirSync(skillsRoot).reduce((count, skill) => {
    const file = path.join(skillsRoot, skill, 'evals/scenarios.json');
    return count + (fs.existsSync(file) ? JSON.parse(fs.readFileSync(file)).evals.length : 0);
  }, 0);
  assert.equal(tests.length, expectedCount);
  for (const item of tests) {
    assert.deepEqual(Object.keys(item.vars), ['user_prompt']);
    assert.ok(item.assert.length);
    for (const check of item.assert.filter(check => check.type === 'llm-rubric')) {
      assert.equal(check.threshold, 1);
    }
  }
  const deadline = tests.find(item => item.metadata.caseName === 'deadline-budget');
  assert.ok(deadline.assert[0].value.includes('context.Background()'));
  const pagination = tests.find(item => item.metadata.caseName === 'keyset-pagination');
  assert.ok(pagination.assert[0].value.includes('Partial credit'));
  const audit = tests.find(item => item.metadata.caseName === 'cpp-rule-cpp-02-closure-mutation');
  assert.equal(audit.assert[0].type, 'llm-rubric');
  assert.ok(audit.assert[0].value.includes('Full fail if the final answer'));
  assert.equal(audit.assert[1].type, 'contains');
  assert.equal(audit.assert[1].value, 'RULE-CPP-02');
});

test('selector uses canonical activation prompts without forbidding secondary loads', () => {
  const tests = loadRouting();
  assert.equal(tests.length, JSON.parse(fs.readFileSync(path.resolve(__dirname, '../runtime/routing.json'))).length);
  const sql = tests.find(item => item.description.includes('ydb sql'));
  assert.ok(sql.vars.user_prompt.includes('--explain'));
  assert.equal(sql.assert.length, 1);
  assert.ok(new RegExp(sql.assert[0].value).test('ydb-table'));
  assert.ok(!new RegExp(sql.assert[0].value).test('ydb-table ydb-core'));
});

test('loader refuses to silently run without fixtures or with stale metadata', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ydb-adapter-test-'));
  try {
    fs.mkdirSync(path.join(root, 'skills/example/evals'), { recursive: true });
    fs.mkdirSync(path.join(root, 'tests/runtime'), { recursive: true });
    const metadata = path.join(root, 'tests/runtime/scenario-checks.json');
    const file = path.join(root, 'skills/example/evals/scenarios.json');
    const suite = { skill_name: 'example', evals: [{ id: 1, name: 'one', prompt: 'task', files: ['input.csv'], expectations: ['correct'] }] };
    fs.writeFileSync(metadata, '{}');
    fs.writeFileSync(file, JSON.stringify(suite));
    assert.throws(() => loadScenarios(root), /fixture support/);
    suite.evals[0].files = [];
    fs.writeFileSync(file, JSON.stringify(suite));
    fs.writeFileSync(metadata, JSON.stringify({ 'example:deleted': {} }));
    assert.throws(() => loadScenarios(root), /Stale scenario metadata/);
    fs.writeFileSync(metadata, JSON.stringify({
      'example:one': { additional_checks: [{ expectation: 0, type: 'contains', value: 'missing requirement' }] },
    }));
    assert.throws(() => loadScenarios(root), /additional check disagrees/);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
