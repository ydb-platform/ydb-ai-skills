# Version compatibility

The search guidance was checked on 2026-10-02 against **main at `169565ba`** and the supplied **stable-26-3-1 snapshot at `4cdb81ee`**. Match the requested server revision before applying branch-specific behavior.

| Topic | stable-26-3-1 at `4cdb81ee` | main at `169565ba` |
|---|---|---|
| Hybrid prefix equalities | Full-text requires every prefix column; vector accepts a nonempty contiguous leading prefix | Both full-text and vector require **every** prefix column; a leading subset is rejected |
| `TTableServiceConfig.EnableHybridSearch` | Proto default `false` | Proto default `true` |
| `EnableFulltextIndexPrefix` | Proto default `false` | Proto default `true` |
| `EnableCompactFulltextIndex` | Proto default `false` | Proto default `true` |
| `EnableFulltextIndexRowId` | Proto default `false` | Proto default `true` |

Main enables those four features by default unless the cluster overrides them. Do not carry stable-branch defaults into an answer about main. For an unknown target, establish its version and effective configuration; feature verification is not an instruction to change cluster configuration.

For hybrid SQL, bind every prefix column unless the requested version has been verified to accept a partial prefix. For a specified release, consult its documentation and implementation; source presence alone does not establish released availability.

For updated documentation, start at [YDB's documentation index](https://ydb.tech/llms.txt), preserve the requested product version when following links, and read the relevant feature pages. If the requested version cannot be retrieved, state that limitation rather than presenting `main` as verified released behavior.
