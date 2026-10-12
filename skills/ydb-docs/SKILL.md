---
name: ydb-docs
description: "Find and verify official documentation for the YDB database (СУБД YDB) on ydb.tech. Use for YDB documentation lookup, source links, citations, fact checking, and lookup plans without network access. Can support another YDB skill when documentation is needed. Supports Russian or English and requested product versions. This is specific to the YDB database, not a general YQL documentation tool; YT/Hahn is outside its scope."
---

# YDB Documentation

Find and read official YDB documentation starting at https://ydb.tech/llms.txt.

## Workflow

For a lookup plan or a no-network request, describe the retrieval steps without
fetching pages. Give a usable starting URL so the user can follow the plan later:
normally `https://ydb.tech/llms.txt`, or a known official language/version index.
Explain how to select the requested language and product version, then which
linked pages would need to be read. Distinguish a proposed lookup from sources
actually retrieved; do not present an unread page as verified evidence.
A network restriction still permits reading local skill instructions and files.
Do not make network requests when the user prohibits them.

1. Identify the documentation topic, the user's language, and any requested YDB version.
2. Use https://ydb.tech/llms.txt to discover the documentation indexes and version-selection instructions, or use a known official index for the requested language and version directly. Fetch it with an available web or HTTP tool. Use `main` when no version is requested.
3. Search the index for the topic, then read the relevant linked pages. Prefer the Markdown URLs supplied by the index, preserve the version query parameter, and fetch only the pages needed.
4. Answer from the pages actually read, cite them, and make version-dependent limitations explicit. If the sources do not establish a claim, say so.

## Gotchas

- `llms.txt` is an index, not evidence for product behavior; open the relevant documentation pages before verifying a claim.
- `main` is a documentation branch, not a promise that a feature is available in a released YDB version.
- Keep the selected version when following links so the answer does not silently mix releases.
- YQL documentation for YT is not a substitute for YDB's dialect documentation.

## Content rules

This skill only locates and reads documentation; it does not require database access or credentials. Do not infer syntax or behavior from another database when the YDB sources do not cover the question.

Choose the documentation branch before constructing a direct index URL. For a
requested product line `X.Y`, use `vX.Y`; keep an explicitly supplied branch
identifier unchanged. Use `main` only when no product version was requested.
The direct indexes, also usable if the root index is unavailable, are:

- English: `https://ydb.tech/docs/en/llms.txt?version={branch}`
- Russian: `https://ydb.tech/docs/ru/llms.txt?version={branch}`

Replace `{branch}` with the selected branch and preserve it in links followed
from that index. A constructed URL is a lookup target, not proof that the branch
was retrieved. If the requested branch cannot be retrieved, report that limitation
instead of silently substituting `main`. If the indexes are unavailable, try
https://ydb.tech/docs/ or a site-restricted search while preserving the requested
version. State any retrieval failure or version mismatch rather than implying
the requested documentation was verified.
