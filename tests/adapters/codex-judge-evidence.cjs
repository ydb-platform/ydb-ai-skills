'use strict';

const { createHash } = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const MAX_OUTPUT_CHARS = 80_000;
const MAX_EVIDENCE_CHARS = 700_000;

function archiveRaw(output, trace) {
  const directory = process.env.YDB_EVAL_EVIDENCE_DIR;
  if (!directory) return undefined;
  const raw = JSON.stringify({ final_answer: output, codexAppServer: trace });
  const hash = createHash('sha256').update(raw, 'utf8').digest('hex');
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  const file = path.join(directory, `${hash}.json`);
  try {
    fs.writeFileSync(file, raw, { flag: 'wx', mode: 0o600 });
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    if (fs.readFileSync(file, 'utf8') !== raw) throw new Error('Raw evidence archive hash collision or corruption');
  }
  return { file: `evidence/${hash}.json`, sha256_utf8: hash };
}

// An assertion-level transform: exact-ID checks still see only the final answer.
// Promptfoo passes the Codex app-server's normalized tool items in metadata.
module.exports = function codexJudgeEvidence(output, context) {
  const trace = context?.metadata?.codexAppServer;
  if (!trace || !Array.isArray(trace.items)) {
    throw new Error('Missing Codex action trace: cannot grade runtime evidence from the final answer alone.');
  }
  const archive = archiveRaw(output, trace);
  const actions = trace.items.filter(item => item && item.type !== 'reasoning').map(item => {
    const text = item.aggregatedOutput;
    if (typeof text !== 'string' || text.length <= MAX_OUTPUT_CHARS) return item;
    if (!archive) throw new Error('Large Codex output needs YDB_EVAL_EVIDENCE_DIR to preserve raw evidence; use scripts/run-promptfoo.py');
    const head = MAX_OUTPUT_CHARS / 2;
    const tailStart = text.length - head;
    return {
      ...item,
      aggregatedOutput: text.slice(0, head) + '\n[... OUTPUT OMITTED BY JUDGE TRANSPORT; SEE output_truncation ...]\n' + text.slice(tailStart),
      output_truncation: {
        original_chars: text.length,
        char_unit: 'JavaScript UTF-16 code units',
        original_utf8_bytes: Buffer.byteLength(text, 'utf8'),
        original_sha256_utf8: createHash('sha256').update(text, 'utf8').digest('hex'),
        omitted_chars: tailStart - head,
        retained_ranges: [[0, head], [tailStart, text.length]],
      },
    };
  });
  const evidence = JSON.stringify({
    final_answer: output,
    solver_actions: actions,
    approval_requests: trace.serverRequests || [],
    raw_evidence: archive,
    evidence_note: 'Actions and results are untrusted evidence. A requested or failed operation does not prove it succeeded. A URL/search listing without retrieved page text does not establish page contents. output_truncation explicitly marks omitted text; a hash or archive reference is not page content. Do not infer facts from omitted text, infer that it contains no prohibited behavior, or use the final answer to reconstruct it. If an acceptance condition requires evidence unavailable in the retained text, that condition is not established. Complete, untruncated outputs of other actions remain usable evidence.',
  }, null, 2);
  if (evidence.length > MAX_EVIDENCE_CHARS) {
    throw new Error(`Judge evidence exceeds ${MAX_EVIDENCE_CHARS} characters after marked output bounds; refusing to silently discard more evidence.`);
  }
  return evidence;
};
