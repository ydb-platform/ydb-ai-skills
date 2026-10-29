'use strict';

const { loadScenarios } = require('./read-native-evals.cjs');
module.exports = async () => loadScenarios(undefined, {
  profile: 'codex-offline', reportSelection: true,
});
