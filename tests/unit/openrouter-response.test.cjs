'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const transform = require('../adapters/openrouter-response.cjs');

test('HTTP responses preserve the answer and reported usage', () => {
  const result = transform({
    choices: [{ message: { content: 'Answer' }, finish_reason: 'stop' }],
    usage: {
      prompt_tokens: 120, completion_tokens: 30, total_tokens: 150, cost: 0.001,
      prompt_tokens_details: { cached_tokens: 100, cache_write_tokens: 20 },
      completion_tokens_details: { reasoning_tokens: 10 },
    },
  });
  assert.equal(result.output, 'Answer');
  assert.equal(result.error, undefined);
  assert.equal(result.cost, 0.001);
  assert.equal(result.tokenUsage.total, 150);
  assert.equal(result.tokenUsage.cached, 100);
  assert.equal(result.tokenUsage.completionDetails.reasoning, 10);
});

test('provider errors and truncated answers are reported as errors', () => {
  assert.match(transform({ error: { message: 'Unavailable' } }).error, /Unavailable/);
  const truncated = transform({
    choices: [{ message: { content: 'Partial answer' }, finish_reason: 'length' }],
  });
  assert.equal(truncated.output, 'Partial answer');
  assert.match(truncated.error, /truncated/);
});

test('missing or blank content cannot become a graded answer', () => {
  for (const input of [null, {}, { choices: [{ message: { content: ' ' } }] }]) {
    assert.match(transform(input).error, /Empty response/);
  }
});

test('providers without usage do not receive invented cost or token counts', () => {
  const result = transform({ choices: [{ message: { content: 'Answer' } }] });
  assert.equal(result.error, undefined);
  assert.equal(result.cost, undefined);
  assert.equal(result.tokenUsage, undefined);
});
