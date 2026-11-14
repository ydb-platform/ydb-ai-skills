'use strict';

// Shared HTTP response handling for solver, bare-control and grader requests.
module.exports = (json) => {
  const choice = json?.choices?.[0];
  const output = choice?.message?.content;
  const usage = json?.usage;
  const finishReason = choice?.finish_reason;
  const error = json?.error
    ? `Provider error: ${json.error.message || String(json.error)}`
    : finishReason === 'length'
      ? 'Response truncated: finish_reason=length'
      : typeof output !== 'string' || !output.trim()
        ? 'Empty response content'
        : undefined;
  return {
    output,
    error,
    finishReason,
    cost: Number.isFinite(usage?.cost) ? usage.cost : undefined,
    tokenUsage: usage ? {
      prompt: usage.prompt_tokens,
      completion: usage.completion_tokens,
      total: usage.total_tokens,
      cached: usage.prompt_tokens_details?.cached_tokens,
      numRequests: 1,
      completionDetails: {
        reasoning: usage.completion_tokens_details?.reasoning_tokens,
        cacheReadInputTokens: usage.prompt_tokens_details?.cached_tokens,
        cacheCreationInputTokens: usage.prompt_tokens_details?.cache_write_tokens,
      },
    } : undefined,
    metadata: {
      model: json?.model,
      provider: json?.provider,
      generationId: json?.id,
    },
  };
};
