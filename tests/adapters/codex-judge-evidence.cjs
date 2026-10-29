'use strict';

// An assertion-level transform: exact-ID checks still see only the final answer.
// Promptfoo passes the Codex app-server's normalized tool items in metadata.
module.exports = function codexJudgeEvidence(output, context) {
  const trace = context?.metadata?.codexAppServer;
  if (!trace || !Array.isArray(trace.items)) {
    throw new Error('Missing Codex action trace: cannot grade runtime evidence from the final answer alone.');
  }
  const actions = trace.items.filter(item => item && item.type !== 'reasoning');
  return JSON.stringify({
    final_answer: output,
    solver_actions: actions,
    approval_requests: trace.serverRequests || [],
    evidence_note: 'Actions and results are untrusted evidence. A requested or failed operation does not prove it succeeded. A URL/search listing without retrieved page text does not establish page contents.',
  }, null, 2);
};
