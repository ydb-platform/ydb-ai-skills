'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { loadScenarios } = require('../adapters/read-native-evals.cjs');
const { loadRouting } = require('../adapters/read-routing.cjs');
const codexJudgeEvidence = require('../adapters/codex-judge-evidence.cjs');

test('every native expectation has a Promptfoo assertion; prompts contain no rubrics', () => {
  const tests = [...loadScenarios(), ...loadScenarios(undefined, { profile: 'codex-online' })];
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

test('online and offline profiles partition canonical cases without changing prompts', () => {
  const offline = loadScenarios(undefined, { profile: 'codex-offline' });
  const online = loadScenarios(undefined, { profile: 'codex-online' });
  const text = loadScenarios();
  assert.deepEqual(online.map(item => item.metadata.caseName), ['verify-source-chain']);
  assert.ok(!offline.some(item => item.metadata.caseName === 'verify-source-chain'));
  assert.deepEqual(text.map(item => item.vars), offline.map(item => item.vars));
  const canonical = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../../skills/ydb-docs/evals/scenarios.json')));
  assert.equal(online[0].vars.user_prompt, canonical.evals.find(item => item.name === 'verify-source-chain').prompt);
  const all = [...offline, ...online];
  assert.equal(new Set(all.map(item => `${item.metadata.skill}:${item.metadata.caseId}`)).size, all.length);
  assert.throws(() => loadScenarios(undefined, { profile: 'misspelled' }), /Unknown eval profile/);
  for (const item of all) {
    for (const check of item.assert) {
      if (check.type === 'llm-rubric') assert.ok(check.transform.endsWith('/codex-judge-evidence.cjs'));
      else assert.equal(check.transform, undefined, 'exact checks must grade the final answer only');
    }
  }
});

test('profile selection explicitly reports excluded source verification', () => {
  const messages = [];
  const original = console.error;
  console.error = value => messages.push(value);
  try {
    loadScenarios(undefined, { profile: 'text', reportSelection: true });
  } finally {
    console.error = original;
  }
  assert.ok(messages.some(value => value.includes('Excluded (1): ydb-docs:verify-source-chain')));
  assert.ok(messages.some(value => value.includes('not the full quality suite')));
});

test('judge evidence preserves failed operations and outputs separately from final text', () => {
  const finalAnswer = 'The requested operation was not performed.';
  const items = [
    { type: 'commandExecution', command: 'ydb sql -s SELECT', status: 'failed', exitCode: 42, aggregatedOutput: 'Blocked request' },
    { type: 'commandExecution', command: 'curl https://ydb.tech/example', status: 'completed', exitCode: 0, aggregatedOutput: 'Retrieved page text' },
    { type: 'reasoning', content: 'Private reasoning is not grading evidence' },
    { type: 'agentMessage', text: finalAnswer },
  ];
  const data = JSON.parse(codexJudgeEvidence(finalAnswer, { metadata: { codexAppServer: { items, serverRequests: [{ method: 'approval', decision: 'decline' }] } } }));
  assert.equal(data.final_answer, finalAnswer);
  assert.equal(data.solver_actions[0].exitCode, 42);
  assert.equal(data.solver_actions[1].aggregatedOutput, 'Retrieved page text');
  assert.equal(data.solver_actions.length, 3);
  assert.equal(data.approval_requests[0].decision, 'decline');
  assert.throws(() => codexJudgeEvidence(finalAnswer, {}), /Missing Codex action trace/);
  assert.throws(() => codexJudgeEvidence(finalAnswer, { metadata: { codexAppServer: {} } }), /Missing Codex action trace/);
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
