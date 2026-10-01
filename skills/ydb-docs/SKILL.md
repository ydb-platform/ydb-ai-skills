---
name: ydb-docs
description: "Use only when the user explicitly asks to find, locate, open, or cite official YDB documentation, requests source links or citations, or says to verify a claim against the documentation. Retrieves pages through ydb.tech/llms.txt and supports Russian or English and version-specific documentation indexes."
---

# YDB Documentation

Find and read official YDB documentation starting at https://ydb.tech/llms.txt.

## Workflow

1. Identify the documentation topic, the user's language, and any requested YDB version.
2. Fetch https://ydb.tech/llms.txt with an available web or HTTP tool. Follow its Russian or English documentation index and its instructions for selecting a product branch. Use `main` when no version is requested.
3. Search the index for the topic, then read the relevant linked pages. Prefer the Markdown URLs supplied by the index, preserve the version query parameter, and fetch only the pages needed.
4. Answer from the pages actually read, cite them, and make version-dependent limitations explicit. If the sources do not establish a claim, say so.

## Gotchas

- `llms.txt` is an index, not evidence for product behavior; open the relevant documentation pages before verifying a claim.
- `main` is a documentation branch, not a promise that a feature is available in a released YDB version.
- Keep the selected version when following links so the answer does not silently mix releases.
- YQL documentation for YT is not a substitute for YDB's dialect documentation.

## Content rules

This skill only locates and reads documentation; it does not require database access or credentials. Do not infer syntax or behavior from another database when the YDB sources do not cover the question.

If the root index is unavailable, try the direct indexes:

- English: https://ydb.tech/docs/en/llms.txt?version=main
- Russian: https://ydb.tech/docs/ru/llms.txt?version=main

For a requested product branch, use its version parameter as described by the root index. If the indexes are unavailable, try https://ydb.tech/docs/ or a site-restricted search. State any retrieval failure or version mismatch rather than implying the requested documentation was verified.
