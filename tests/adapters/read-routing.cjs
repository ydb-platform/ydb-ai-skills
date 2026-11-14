'use strict';

const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.resolve(__dirname, '../..');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));

function loadRouting(root = ROOT) {
  return read(path.join(root, 'tests/runtime/routing.json')).map(item => {
    const suite = read(path.join(root, 'skills', item.skill, 'evals/activations.json'));
    const cases = suite.cases.filter(candidate => candidate.id === item.id);
    if (cases.length !== 1) throw new Error(`Missing activation case ${item.skill}:${item.id}`);
    // A primary selector is deliberately distinct from allowed secondary loads.
    return {
      description: item.description,
      vars: { user_prompt: cases[0].prompt },
      assert: [{ type: 'regex', value: `^\\s*${item.primary_target}\\s*$` }],
    };
  });
}

module.exports = async () => loadRouting();
module.exports.loadRouting = loadRouting;
