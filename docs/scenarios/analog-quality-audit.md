# Analog-search quality audit — Agora control case

## Target and honest boundary

Find conceptually related implementations for an arbitrary public repository, including synonyms, low/zero-star projects, forks and different stacks. **All analogs on GitHub cannot be guaranteed:** indexing, private/unindexed content, terminology and the Search1000-result window limit recall. There is no numeric semantic score or market-demand inference. Current changes improve controllable retrieval and source evidence, not semantic perfection.

## Observed deficiencies and fixes

| Deficiency | Candidate fix | Not implied |
| --- | --- | --- |
| Only2–4 formulations | Up to8 explicit problem/mechanism/workflow/domain formulations | Automatic paraphrase/translation or all possible formulations |
| First page only with a different low-level cursor | Executable safe next_page_requests; probe_pages and probe_only | Automatic crawling or exhausted GitHub coverage |
| Fingerprint returned but not enforced | expected_plan_fingerprint checked before network | Signed continuation or persisted history |
| Small candidate pool could hide fetched rows | Up to30rows/probe,100candidates; explicit safe replay on omission | Similarity ranking or invisible truncation |
| Retrieval order looked like a recommendation | Optional facet_coverage with formulation/probe provenance and selection_basis | Semantic equivalence or market opportunity |
| Core concepts absent from default text scope | Plan-time `query_coverage` advisories for each core facet without explicit README scope | Automatic expansion or semantic coverage certification |
| Large REST commit response blocked Agora source profile | Compact exact branch/SHA Git-commit pin recovery within existing budgets | Ignoring a refusal, auth fallback, more permissive caps or execution |

## Agora source profile

Public source: LeonidYasin/agora-mcp, commit8428e8484f785e91a8689c0c8d3d2ec57c80e1b5. [db.ts60–119](https://github.com/LeonidYasin/agora-mcp/blob/8428e8484f785e91a8689c0c8d3d2ec57c80e1b5/mcp-server/src/db.ts#L60-L119) verifies owned/active source items, opposite offer/want type, other-user exclusion, embedding availability, cosine-distance ordering and match-row upsert. This is implemented complementary-intent retrieval, not generic chatbot similarity or a same-stack search.

Before fix: public metadata + commits/main stopped after2GETs with body_budget; no source delivered. After fix: same requested source/profile observed,7GETs total including preserved refusal, full commit/tree/blob pin and SHA256 validation; db.ts and README excerpts delivered. No source repository code ran.

Test formulations deliberately separate problem (supply/demand, needs/offers, resource matching), mechanism (offer/want, semantic matchmaking, pgvector), workflow (barter) and domain (mutual aid). These are analyst-approved public queries, not private idea text automatically sent to Search. A shared keyword, copied catalog or pgvector infrastructure hit is a negative/insufficient-evidence control, not automatically an analog.

## Current acceptance

Local regression tests cover exact page continuation, sibling isolation, fingerprint drift, candidate omission recovery, malformed/forged pagination, window cap, rate/refusal retention, ordering without star preference, large-commit recovery integrity and no fallback on HTTP/rate/total-budget refusal. No Python/shell executed on VPS; source changes do not deploy TEST or production.

### Live public retrieval observation (2026-10-17, local sandbox)

Eight analyst-supplied formulations were observed in broad/zero-star/fork lanes:

| Facet | Terms | Scope |
| --- | --- | --- |
| problem | `"supply demand" matching` | default |
| mechanism | `"offer" "want" matching` | default |
| problem | `"needs" "offers"` | README |
| mechanism | `semantic matchmaking` | default |
| workflow | `barter matching` | README |
| domain | `"mutual aid" platform` | default |
| problem | `resource matching marketplace` | default |
| mechanism | `pgvector matching` | default |

Six explicit four-GET batches observed all24 first-page probes; stable-ID union of
returned candidates was155. One additional explicit validated next-page request observed
page2 of a selected probe in1GET, without visiting siblings. Total25SearchGETs. These are
**retrieval observations, not155 verified analogs**; most source implementations were not
read. The union excludes the separate page2 observation. An independent ID-set count
reproduced155. Requests were public/credential-free and did not execute any repository code.

**Negative control result:** the eight-formulation plan did not rediscover the previously
source-supported adjacent project `buidanhhuong/can-co`. It is therefore NOT a quality pass,
even though every planned first page was observed. More queries/candidates do not by
themselves establish better recall or relevance.

### Explicit control recovery, not a hidden retry

A separate two-formulation plan used the previously documented README queries:
`"offer" "want" marketplace` (problem) and `pgvector matching agent` (mechanism).
Six probes in two explicit three-GET batches rediscovered repository ID1188558768,
`buidanhhuong/can-co`, with zero stars in mechanism/zero_star probe3. Observation time:
2026-10-17T16:30:06Z, page1, limit10, HTTP200. The exact public query was:

```
pgvector matching agent in:readme is:public fork:true stars:0 -repo:LeonidYasin/agora-mcp
```

This control changes both wording and scope; it does NOT isolate a causal effect of
README scope or establish population-wide precision/recall. Its broad reported total
also exceeds the accessible1000-result window. Live indexes/order can change; this is not
a frozen benchmark. Server warnings now make missing README coverage visible before
network, without silently rewriting queries or treating absence of warnings as success.
The source evidence for [can-co filtering/ranking](https://github.com/buidanhhuong/can-co/blob/8d97d1fc675f32eee9e8ae7af17be9c07aeba915/lib/engine/matching.ts#L158-L242)
supports adjacent need/have matching, not complete Agora equivalence or reuse permission.

### Regression and remaining quality gates

Final source regression: **1114 passed**. Wheel/sdist build passed; the same1114 tests
passed from a clean extracted sdist (import origin verified). Registry remains114default/
144all-enabled. New tests cover warnings without network or silent query expansion;
these prove contract behavior, not semantic judgment.

Before calling this generally high-quality, retain a labeled set of different repository
ideas, source-supported positives and hard negatives; assess missed positives and review
candidate mechanisms, not names/keywords/stars. For each source repo: extract the actual
user/problem/input→transformation→output and alternative vocabulary; inspect relevant code
at one SHA; use at least problem+mechanism README formulations; preserve and explain misses;
classify each reviewed candidate as source-supported related/adjacent, rejected, or
insufficient evidence. Record distinctions, reusable components and license unknowns.
No claim of exhaustive recall, measured semantic accuracy, novelty or commercial demand
has passed. Review/install in TEST and client acceptance remain separately authorized gates.

[Contract](../repository-analogs.md) · [Evidence reader](../repository-evidence.md) · [Earlier external acceptance](../idea-analog-external-acceptance.md) · [Roadmap](../../ROADMAP.md).
