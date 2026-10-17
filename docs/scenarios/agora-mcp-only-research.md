# Agora: MCP-only idea-analog research

## Scope and authority

This iteration used existing GitHub MCP reads and feature-branch writes only. No shell, run_python, SSH, background process, local script, project installation, candidate runtime invocation, merge or VPS deployment was performed. Existing GitHub Actions is the independent CI verifier for the submitted source/test changes, not a manually executed shell/Python session. Source reads do not prove runtime correctness, adoption, security or commercial demand.

The connected find_repository_analogs schema still exposes 2–4 problem/mechanism formulations, limit_per_probe<=10 and max_candidates<=40; it does NOT expose the PR112 candidate's 2–8 formulations, probe_only, probe_pages, expected_plan_fingerprint or query_coverage. Research therefore used the observed runtime schema, ordinary explicit search_repositories pages and source tools. Do not describe the new source candidate as installed.

## Correct source concept

Agora is a shared platform where personal AI agents represent people. Its first useful product is a complementary offer/want market; identity/access, service economics and future self-governance are distinct layers. Parliament/courts/elections are planned, not current server functions. The idea is not merely pgvector or a generic MCP endpoint.

Sources: [vision](https://github.com/LeonidYasin/agora-mcp/blob/8428e8484f785e91a8689c0c8d3d2ec57c80e1b5/docs/vision.md), [implemented opposite-type/other-owner matching](https://github.com/LeonidYasin/agora-mcp/blob/8428e8484f785e91a8689c0c8d3d2ec57c80e1b5/mcp-server/src/db.ts#L60-L119).

## Retrieval ledger: observations, not global coverage

The core plan used limit5, max_candidates30, evidence_limit0 and four formulations:

| Facet | Terms | Scope |
| --- | --- | --- |
| problem | `"needs" "offers"` | README |
| problem | `"skill exchange"` | default |
| mechanism | `"intent matching"` | README |
| mechanism | `"semantic matchmaking"` | README |

All broad/zero_star/forks first-page probes0–11 were observed in three explicit four-GET calls. Plan fingerprint stayed `624d5043075a25b5fbef0d2ab55bad9691c825ef6c3acbe235a7f6a7d27d34fb`. No candidate-cap omissions were reported in those batches. Completion of these planned first pages does not imply exhaustion of their result sets. No unique-union size or semantic precision/recall is claimed.

Four additional successful Search GETs:

- `"personal agents" marketplace in:readme is:public fork:true -repo:LeonidYasin/agora-mcp`, page1, limit6.
- `participatory democracy in:name,description is:public fork:true`, page1, limit5.
- `"agent commerce" in:name,description is:public fork:true -repo:LeonidYasin/agora-mcp`, page1, limit6.
- The returned explicit next request for core fork-only semantic-matchmaking probe: same query/limit5, page2. Its reported total was10, but coverage.has_more remained null and stop_reason was pagination_not_proven. Observing both pages is not promoted to a provider-proven terminal cursor.

A seventeenth Search attempt demonstrated a real stop, not a zero-result partition:

```
"skill exchange" in:name,description created:2025-01-01..2025-12-31 is:public fork:true -repo:LeonidYasin/agora-mcp
```

At 2026-10-17T17:00:49Z it returned HTTP403, http_refused, remaining0. Count/items are unknown. Search stopped; no retry, credential fallback, alternate IP or other connection was used to evade this quota. No date-partition completion is claimed. Overall:16 observed Search pages plus1 refused attempt, not17 successful searches.

## Source-reviewed findings

### 1. DataBarista — close partial analog of agent-mediated intent discovery

Newly surfaced by the semantic-matchmaking probe. Pinned revision `28200e9d03f1b0237b5d5df53495dac8d15c2ff4`.

The [README](https://github.com/amirmabhout/DataBarista/blob/28200e9d03f1b0237b5d5df53495dac8d15c2ff4/README.md#L1-L80) proposes conversation-derived collaboration intents, public/private knowledge and introductions. More importantly, [publishIntent2Dkg.ts751–835](https://github.com/amirmabhout/DataBarista/blob/28200e9d03f1b0237b5d5df53495dac8d15c2ff4/src/publishIntent2Dkg.ts#L751-L835) creates a DKG asset with public/private data, reads the profile and invokes candidate matching. [serendipityAction.ts156–255](https://github.com/amirmabhout/DataBarista/blob/28200e9d03f1b0237b5d5df53495dac8d15c2ff4/src/serendipityAction.ts#L156-L255) generates a SPARQL query from a profile and executes graph.query.

Related idea: an agent turns human goals into discoverable intentions and finds other people. Difference: generated graph queries/professional networking rather than the verified Agora opposite offer/want pgvector query. The generated-query prompt requests self-exclusion; runtime compliance or safety was NOT tested. README privacy claims are not a verified security guarantee. Root [MIT license](https://github.com/amirmabhout/DataBarista/blob/28200e9d03f1b0237b5d5df53495dac8d15c2ff4/LICENSE) was read; dependencies, attribution and integration still require review.

### 2. can-co — existing positive control for the offer/need market

This was a previously known control re-read explicitly, NOT a new discovery from the current core plan. At `8d97d1fc675f32eee9e8ae7af17be9c07aeba915`, [matching.ts158–242](https://github.com/buidanhhuong/can-co/blob/8d97d1fc675f32eee9e8ae7af17be9c07aeba915/lib/engine/matching.ts#L158-L242) selects opposite CAN/CO intents, excludes the same user, filters active/category/district/price and ranks a retrieved subset. This is concrete complementary-intent matching, not proof of the same semantic-distance algorithm, a whole-product replacement or live quality. No recognized SPDX license was returned; reuse permission remains unestablished.

### 3. Skill_Exchange — reciprocal skill exchange, same idea without embeddings

Found through the forks-only skill-exchange probe as faragelyan/Skill_Exchange. Public evidence identified parent mostafa630/Skill_Exchange; both observed heads were exactly `cb1083b3006fab9fb2fb5e4a724a39b9ae77e22c`, ahead0/behind0. Treat this as one source lineage, not two independent inventions. No patch was read.

The complete [GetMatchingUsersHandler.cs](https://github.com/faragelyan/Skill_Exchange/blob/cb1083b3006fab9fb2fb5e4a724a39b9ae77e22c/Skill_Exchange.Application/Services/User/Queries/Handlers/GetMatchingUsersHandler.cs) reads learning/teaching skills, excludes the caller, compares my-learning/their-teaching and my-teaching/their-learning, combines scores and orders results. Score uses skill-ID intersection and experience differences, not free-text semantics. Inspection also shows zero scores are retained and pagination precedes the final sorting, so do not infer reliable global top matches. Candidate for exchange-domain design, not a ready Agora replacement. License permission not established.

### 4. Bitterbot — partial analog of independently owned agents interacting

Pinned main `619ca967fe4d8a75142ec064ba00bb917efd3012`. [README](https://github.com/Bitterbot-AI/bitterbot-desktop/blob/619ca967fe4d8a75142ec064ba00bb917efd3012/README.md#L40-L69) describes independently owned agents connecting through Circles. [circle-p2p-transport.ts1–105](https://github.com/Bitterbot-AI/bitterbot-desktop/blob/619ca967fe4d8a75142ec064ba00bb917efd3012/src/circles/circle-p2p-transport.ts#L1-L105) implements a peer RPC bridge/client and outcome handling. [disclosure.ts1–115](https://github.com/Bitterbot-AI/bitterbot-desktop/blob/619ca967fe4d8a75142ec064ba00bb917efd3012/src/circles/disclosure.ts#L1-L115) implements category/circle-specific grants and a default-deny decision function.

Useful adjacent mechanism: human-controlled disclosure across agent connections. An offer/want market, democratic institutions and complete enforcement of these checks were not established by the selected reads. These are source observations, not a security audit. README's MIT badge alone is not complete legal clearance.

### 5. Decidim — component analog for Agora's future self-governance

Pinned develop `744d71bb60067af4395604a2a7af34c81aa1afc8`. Root overview is README.adoc, NOT README.md: the initial explicit README.md request returned404 and tree inspection found the actual file. [README.adoc](https://github.com/decidim/decidim/blob/744d71bb60067af4395604a2a7af34c81aa1afc8/README.adoc#L101-L168) discusses authorization, participation spaces, proposals and budgeting; it states Affero GPL3 obligations.

[create_proposal.rb](https://github.com/decidim/decidim/blob/744d71bb60067af4395604a2a7af34c81aa1afc8/decidim-proposals/app/commands/decidim/proposals/create_proposal.rb) validates and creates attributed proposals with traceability. [vote_proposal.rb](https://github.com/decidim/decidim/blob/744d71bb60067af4395604a2a7af34c81aa1afc8/decidim-proposals/app/commands/decidim/proposals/vote_proposal.rb) validates votes and saves them under transaction/lock. These are concrete proposal/voting components, not proof of Agora-style courts, a parliamentary constitution, one-person-one-vote or an agent marketplace. License compatibility must be considered before integration.

## Rejected or deferred hits

Broad needs/offers returned generic infrastructure such as FreeCAD/DataFusion; intent-matching surfaced NLU/chatbot classifiers. They are not accepted as market analogs from keyword coincidence. Their full source was not reviewed, so this is a shortlist decision, not proof that no relevant component exists anywhere in them. Awesome agent-commerce lists are discovery pointers, not implemented analogs. ACP/ACK/reference-checkout metadata was surfaced but implementation was not reviewed in this iteration.

## Concrete source improvement and remaining gaps

- Implemented in the Draft branch: auto overview recognition now includes README.adoc. Existing six-file/network budgets, ignored directories and semantic-coverage false flags are unchanged. Added regression cases for AsciiDoc/case/nested paths, old formats, ignored paths and lookalike backups. Use the new HEAD's CI; historical1114-test results do not validate this new change. No local shell/Python test was run this iteration.
- Auto selection needs better question-directed relevance. DataBarista auto mode spent source slots on bootstrap/cache/chat; explicit tree-derived paths found the actual publication/matching logic. Skill_Exchange focus term skill matched its project namespace and selected authorization/DTO files; reading the tree and explicit matching handler repaired this investigation, not the selector algorithm. Prefer precise file-related hints and inspect selection reasons.
- Automatic safe date-range partition planning, resumable coverage ledger and terminology expansion remain unimplemented. Existing search_repositories accepts explicit qualifiers, but a refused partition must remain unobserved. Counting search hits is not counting analogs.
- Runtime schema/source alignment needs separately authorized TEST rollout; no deployment is implied by this report.
- Commercial demand, whole-product equivalence, runtime correctness and license compatibility remain separate checks. No single full analog of all Agora layers was established.

[Tool contract](../repository-analogs.md) · [Earlier quality audit](analog-quality-audit.md) · [Roadmap](../../ROADMAP.md).
