# Agora analog research: identity, service payments and checkout

## Scope and observation boundary

This follow-up used ordinary GitHub MCP reads and Draft-branch writes only. No shell,
Python, SSH, foreign source execution, manual Actions dispatch, merge or deployment.
GitHub may automatically run existing CI on commits; its outcome must be checked separately.
The connected public reader still has the older auto_paths_v2 implementation. New source
selection below is a Draft candidate, not deployed acceptance or semantic equivalence.

One new public Search page was observed for `"agent commerce" in:name,description is:public
fork:true -repo:LeonidYasin/agora-mcp`, page1, limit5. It reported4431 indexed hits,
incomplete_results=false, has_more=true and a1000-result accessible window. Only five
rows were returned; this is not an exhaustive search. Awesome lists are pointers, not
implemented analogs. Two previously surfaced pointers now received pinned source review.

## Agent Commerce Kit: useful component, not Agora replacement

Repository: https://github.com/agentcommercekit/ack

Observed revision: `3db94d67f84e6a0677c7a383a787f5c6c7d4416c`.

- [README lines1–80](https://github.com/agentcommercekit/ack/blob/3db94d67f84e6a0677c7a383a787f5c6c7d4416c/README.md#L1-L80)
  presents independent ACK-ID and ACK-Pay protocols, DID/VC-based ownership chains and
  paid service access. These are project claims, not runtime/security validation.
- [Payment demo lines81–153](https://github.com/agentcommercekit/ack/blob/3db94d67f84e6a0677c7a383a787f5c6c7d4416c/demos/payments/src/server.ts#L81-L153)
  actually creates a signed payment request, responds402 when a receipt is absent,
  and calls verifyPaymentReceipt with trusted issuer, payment-request issuer and
  token-verification options before returning access. This is a demo call site:
  cryptographic correctness, replay resistance and real settlements were not tested.
- [Credential issuer lines66–100](https://github.com/agentcommercekit/ack/blob/3db94d67f84e6a0677c7a383a787f5c6c7d4416c/demos/identity/src/credential-issuer.ts#L66-L100)
  verifies a submitted JWT, parses controller/subject, creates an ownership credential
  and signs it. The code sets aud:false; authorization of ownership claims and full
  identity-policy enforcement have NOT been established by this selected review.
- [Root LICENSE](https://github.com/agentcommercekit/ack/blob/3db94d67f84e6a0677c7a383a787f5c6c7d4416c/LICENSE)
  is MIT, copyright2025 Catena Labs and contributors. Dependencies, trademarks and the
  complete integration still need their own review.

**Useful for Agora:** evaluate owner-to-agent credentials and billing for platform/service
usage. Do not silently reinterpret Agora's economy as mandatory payment/escrow between
market participants. Complementary offer/want matching or a Republic layer was not
established in these excerpts. Adoption decision: inspect SDK implementations and design
trust/revocation/replay policies before considering an adapter, not wholesale replacement.

Auto evidence selected demo files ahead of core SDK logic; it proves neither SDK coverage
nor production readiness. A first tree request failed with a disconnect, misleadingly
labelled as missing main; later verified metadata established main. No alternate account,
IP or authentication fallback was used to bypass a quota refusal.

## Agentic Commerce Protocol: interoperable checkout specification

Repository: https://github.com/agentic-commerce-protocol/agentic-commerce-protocol

Observed revision: `7fdd78df677a94dce04c770644b0fbbb1401272b`.

- [README lines1–100](https://github.com/agentic-commerce-protocol/agentic-commerce-protocol/blob/7fdd78df677a94dce04c770644b0fbbb1401272b/README.md#L1-L100)
  describes buyer/agent/business checkout, versioned OpenAPI/JSON Schema and beta status.
  This repository is treated as a specification, not an executed merchant implementation.
- [MCP binding lines1–80](https://github.com/agentic-commerce-protocol/agentic-commerce-protocol/blob/7fdd78df677a94dce04c770644b0fbbb1401272b/docs/mcp-binding.md#L1-L80)
  defines create/get/update/complete/cancel checkout tools over JSON-RPC and Streamable
  HTTP; shared schemas and well-known discovery are specified. No live interoperability
  or payment success was tested. Metadata says Apache-2.0; full license review remains open.

**Useful for Agora:** a possible later adapter from a successful match to merchant checkout.
Agora's first market can already be useful without conducting transactions. This spec is
not evidence of the same cross-owner offer/want algorithm, personal-agent polity or full
Agora substitute. Do not implement checkout before it serves a concrete user need.

## Draft selector correction prompted by source review

Earlier Skill_Exchange inspection showed a lexical collision: focus terms skill/match
matched the project namespace Skill_Exchange on almost every source path. Generic
bootstrap/auth heuristics could then beat GetMatchingUsersHandler.cs. Source ranking now
uses observed change class first, then basename focus, directory-only focus, no focus,
then the unchanged role/diversity ordering. A directory-only matching/core.ts hint remains
usable. No-focus behavior is unchanged. No special repository names or idea dictionary
were added to the implementation.

Ten offline regression cases cover four filename styles, directory fallback, added and
modified precedence, ignored/declaration paths, deterministic ordering and absent focus.
The six-file/80-line policy, GET/byte budgets, exclusions, provenance and false semantic
coverage flags stay unchanged. This is an inspectable path heuristic, not a measured
improvement in global recall or semantic precision. No claim is made that DataBarista's
serendipity logic can now be found automatically from unrelated focus terms.

## Next quality gates

1. Check all automatic CI jobs on the final Draft HEAD; a source edit alone is not a test pass.
2. Evaluate the actual SDK, not only demos, before proposing identity/paywall reuse.
3. Keep market matching, agent consent, service billing, merchant checkout and governance
   separate in relevance reports. A useful component is not a full product analog.
4. Continue explicit terminology/language/date partitions with a coverage ledger; stop on
   refusals. Automatic date-partition planning and exhaustive corpus coverage remain open.
5. Deploy/test the new selector only with separate operator approval. VPS Python/shell
   still requires the user's separate confirmation and special password each time.

See [previous MCP-only research](agora-mcp-only-research.md) for DataBarista, can-co,
Skill_Exchange, Bitterbot and Decidim, including pinned implementation observations,
fork deduplication and unresolved license/runtime questions.
