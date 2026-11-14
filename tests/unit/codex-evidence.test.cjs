'use strict';

const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const evidence = require('../adapters/codex-judge-evidence.cjs');

function withArchive(run) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'ydb-evidence-test-'));
  const previous = process.env.YDB_EVAL_EVIDENCE_DIR;
  process.env.YDB_EVAL_EVIDENCE_DIR = directory;
  try { run(directory); } finally {
    if (previous === undefined) delete process.env.YDB_EVAL_EVIDENCE_DIR;
    else process.env.YDB_EVAL_EVIDENCE_DIR = previous;
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

test('large HTML is explicitly bounded, complete Markdown survives, and raw trace is retained', () => {
  withArchive(directory => {
    const html = 'START\n' + '<div>html boilerplate</div>'.repeat(45_000) + '\nEND';
    const markdown = '# Official page\n' + 'Complete source paragraph.\n'.repeat(2_000);
    const trace = { items: [
      { type: 'commandExecution', command: 'curl https://example.test/page', aggregatedOutput: html, status: 'failed', exitCode: 23 },
      { type: 'commandExecution', command: 'curl https://example.test/page.md', aggregatedOutput: markdown, status: 'completed', exitCode: 0 },
    ], serverRequests: [{ method: 'approval', decision: 'decline' }], rawEvents: ['original event'] };
    const context = { metadata: { codexAppServer: trace } };
    const result = JSON.parse(evidence('Original final answer', context));
    assert.equal(result.final_answer, 'Original final answer');
    const clipped = result.solver_actions[0];
    assert.equal(clipped.status, 'failed');
    assert.equal(clipped.exitCode, 23);
    assert.match(clipped.aggregatedOutput, /OUTPUT OMITTED/);
    assert.ok(clipped.aggregatedOutput.startsWith('START'));
    assert.ok(clipped.aggregatedOutput.endsWith('END'));
    assert.equal(clipped.output_truncation.original_chars, html.length);
    assert.equal(clipped.output_truncation.original_sha256_utf8, createHash('sha256').update(html).digest('hex'));
    assert.ok(clipped.output_truncation.omitted_chars > 1_000_000);
    assert.equal(result.solver_actions[1].aggregatedOutput, markdown);
    assert.equal(result.solver_actions[1].output_truncation, undefined);
    assert.deepEqual(result.approval_requests, trace.serverRequests);
    assert.match(result.evidence_note, /condition is not established/);
    assert.equal(trace.items[0].aggregatedOutput, html, 'never mutate the stored provider response');
    const files = fs.readdirSync(directory);
    assert.equal(files.length, 1);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(directory, files[0]))), {
      final_answer: 'Original final answer', codexAppServer: trace,
    });
    evidence('Original final answer', context);
    assert.equal(fs.readdirSync(directory).length, 1, 'several criteria share the same archived response');
  });
});

test('truncation refuses to proceed without a durable raw archive', () => {
  const previous = process.env.YDB_EVAL_EVIDENCE_DIR;
  delete process.env.YDB_EVAL_EVIDENCE_DIR;
  try {
    assert.throws(() => evidence('answer', { metadata: { codexAppServer: {
      items: [{ type: 'commandExecution', aggregatedOutput: 'x'.repeat(1_100_000) }],
    } } }), /preserve raw evidence/);
  } finally {
    if (previous !== undefined) process.env.YDB_EVAL_EVIDENCE_DIR = previous;
  }
});

test('oversized remaining evidence fails closed after preserving the complete response', () => {
  withArchive(directory => {
    const answer = 'x'.repeat(1_100_000);
    assert.throws(() => evidence(answer, { metadata: { codexAppServer: { items: [] } } }), /refusing to silently discard/);
    const file = fs.readdirSync(directory)[0];
    assert.equal(JSON.parse(fs.readFileSync(path.join(directory, file))).final_answer, answer);
  });
});
