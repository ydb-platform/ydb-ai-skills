'use strict';

// Promptfoo's dynamic test loader. Native JSON is the only scenario source.
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '../..');
const ONLINE_CASES = new Set(['ydb-docs:verify-source-chain']);
const PROFILES = new Set(['text', 'codex-offline', 'codex-online']);

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function loadScenarios(root = ROOT, { profile = 'text', reportSelection = false } = {}) {
  if (!PROFILES.has(profile)) throw new Error(`Unknown eval profile: ${profile}`);
  const metadata = readJson(path.join(root, 'tests/runtime/scenario-checks.json'));
  const used = new Set();
  const tests = [];
  for (const skill of fs.readdirSync(path.join(root, 'skills')).sort()) {
    const file = path.join(root, 'skills', skill, 'evals/scenarios.json');
    if (!fs.existsSync(file)) continue;
    const suite = readJson(file);
    if (suite.skill_name !== skill) throw new Error(`Wrong skill_name in ${file}`);
    for (const item of suite.evals) {
      const key = `${skill}:${item.name}`;
      const extra = metadata[key] || {};
      used.add(key);
      if (item.files?.length) {
        throw new Error(`${key}: add explicit fixture support before using Promptfoo`);
      }
      if (!item.expectations?.length) throw new Error(`${key}: missing expectations`);
      for (const index of Object.keys(extra.checks || {})) {
        if (!Number.isInteger(Number(index)) || !item.expectations[Number(index)]) {
          throw new Error(`${key}: stale assertion index ${index}`);
        }
      }
      const additional = (extra.additional_checks || []).map(check => {
        const { expectation, ...assertion } = check;
        if (!Number.isInteger(expectation) || expectation < 0 ||
            !item.expectations[expectation] || assertion.type !== 'contains' ||
            !assertion.value || !item.expectations[expectation].includes(assertion.value)) {
          throw new Error(`${key}: additional check disagrees with native expectation`);
        }
        return assertion;
      });
      tests.push({
        description: `${key} · ${item.covers || item.name}`,
        vars: { user_prompt: item.prompt },
        metadata: { skill, caseId: item.id, caseName: item.name },
        assert: [...item.expectations.map((value, index) => {
          const check = extra.checks?.[String(index)];
          if (check) {
            if (check.type !== 'contains' || !value.includes(check.value)) {
              throw new Error(`${key}: deterministic check ${index} disagrees with native expectation`);
            }
            return { ...check };
          }
          return {
            type: 'llm-rubric', value, threshold: 1,
            metric: extra.metric || `${skill}-outcome`,
            ...(profile.startsWith('codex-') ? {
              transform: `file://${path.join(__dirname, 'codex-judge-evidence.cjs')}`,
            } : {}),
          };
        }), ...additional],
      });
    }
  }
  for (const key of Object.keys(metadata)) {
    if (!used.has(key)) throw new Error(`Stale scenario metadata: ${key}`);
  }
  if (!tests.length) throw new Error('No native scenarios found');
  const selected = tests.filter(item => {
    const online = ONLINE_CASES.has(`${item.metadata.skill}:${item.metadata.caseName}`);
    return profile === 'codex-online' ? online : !online;
  });
  if (!selected.length) throw new Error(`No scenarios match eval profile ${profile}`);
  if (reportSelection) {
    const skipped = tests.filter(item => !selected.includes(item));
    console.error(`Eval profile ${profile}: selected ${selected.length}/${tests.length} canonical scenarios.`);
    console.error(`Excluded (${skipped.length}): ${skipped.map(item => `${item.metadata.skill}:${item.metadata.caseName}`).join(', ') || 'none'}`);
    if (profile !== 'codex-online') {
      console.error('Actual source retrieval is excluded: run npm run eval:codex:online separately. This is not the full quality suite.');
    }
  }
  return selected;
}

module.exports = async () => loadScenarios(ROOT, { reportSelection: true });
module.exports.loadScenarios = loadScenarios;
