---
name: ydb-docs
description: "Find and verify official documentation for the YDB database (СУБД YDB) on ydb.tech. Load only when the requested documentation concerns YDB itself or a YDB-specific part of a mixed question. Covers YDB source links, citations, fact checking, and lookup plans without network access. Can support another YDB skill when documentation is needed. Supports Russian or English and requested YDB product versions."
---

# YDB Documentation

Find and read official YDB documentation starting at https://ydb.tech/llms.txt.

## Workflow

1. **Choose the mode before using tools.** For a lookup plan or a no-network
   request, provide only the steps that would be performed later. Do not fetch
   pages. A local skill/file read is allowed. In this mode, explicitly say that
   the plan has not been executed and product behavior remains unverified.
   Otherwise, retrieve and read the sources as described below.
2. **Choose language and branch before constructing a URL.** Honor the
   requested language. Map a product line `X.Y` to branch `vX.Y`, including
   the `v` prefix; preserve an explicitly supplied branch identifier. Default
   an unspecified language to English and an unspecified version to `main`.
3. **Start at the root index:** `https://ydb.tech/llms.txt`. It discovers the
   documentation indexes. Select the branch on the language-specific index,
   rather than adding a version selector to the root URL.
4. **Follow the first available route, in order:**

   | Availability | Next step |
   | --- | --- |
   | Root index is available | Follow its selected language/branch index, then the topic pages. |
   | Root index is unavailable | Try `https://ydb.tech/docs/{lang}/llms.txt?version={branch}` directly before falling back to navigation. |
   | Root and documentation indexes are unavailable | Use official documentation navigation or site-restricted search, preserving language and branch. |

5. **Read the relevant linked pages before answering product questions.**
   Locating an index or a promising page title is not enough. In plan mode,
   describe this as a future prerequisite, not as a completed verification.
   Do not guess page contents or a missing page URL from the topic name.
6. **Report the evidence boundary.** In retrieval mode, cite only sources
   actually read and state any access or version limitation. In plan mode,
   provide the usable starting URL and route, and finish by distinguishing the
   unexecuted plan from retrieved evidence. Do not answer the substantive
   product question from memory.

## Plan-only response

Keep the plan concise, but include these four items explicitly:

- **Start:** a usable official index URL, selected language, and selected branch.
- **Fallback:** if the root index fails, try the selected direct documentation
  index; if that index also fails, use official navigation or site search.
- **Before answering:** read the relevant pages linked by the index before
  making product claims. Merely finding their URLs does not establish content.
- **Status:** this is an unexecuted plan; no pages have been retrieved or verified.

## Gotchas

- `llms.txt` is an index, not evidence for product behavior; open the relevant documentation pages before verifying a claim.
- `main` is a documentation branch, not a promise that a feature is available in a released YDB version.
- Keep the selected version when following links so the answer does not silently mix releases.
- YQL documentation for YT is not a substitute for YDB's dialect documentation.

## Content rules

This skill only locates and reads documentation; it does not require database access or credentials. Do not infer syntax or behavior from another database when the YDB sources do not cover the question.

The direct indexes, using the branch chosen in workflow step 2, are:

- English: `https://ydb.tech/docs/en/llms.txt?version={branch}`
- Russian: `https://ydb.tech/docs/ru/llms.txt?version={branch}`

Replace `{branch}` with the selected branch and preserve it in links followed
from that index. A constructed URL is a lookup target, not proof that the branch
was retrieved. If the requested branch cannot be retrieved, report that limitation
instead of silently substituting `main`. If the indexes are unavailable, try
https://ydb.tech/docs/ or a site-restricted search while preserving the requested
version. State any retrieval failure or version mismatch rather than implying
the requested documentation was verified.
