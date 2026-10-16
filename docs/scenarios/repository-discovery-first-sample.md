# First inclusive repository-discovery sample — not all GitHub

**Measured2026-10-16; candidate-local MCP dispatcher, real anonymous GitHub.** Topic for this first working example: **Model Context Protocol**. This deliberate thematic sample does not replace the user's broad all-topic GitHub research target. [Saved measurements, exact requests and results](../examples/repository-search-public-sample.json) · [Public Search mode contract](../repository-search-observations.md).

## What actually ran

| Explicit query | Purpose | Provider total hint | Read |
| --- | --- | ---: | ---: |
| `"model context protocol" stars:0 fork:true` | Include zero-star work and permit forks | 124306 | 5 rows |
| `"model context protocol" fork:only` | Ensure forks are not silently excluded | 106567 | 5 rows |
| `"model context protocol" created:>=2026-10-09 fork:true` | Recently created work, including forks | 2825 | 5 rows |

All three used page1, limit5, sort=updated/order=desc. No extra star/popularity filter. All returned HTTP200, incomplete_results=false, verified has_more=true and a reconstructed next_request, but **no next page was fetched**. All three reported totals exceed Search's1000-result accessible window. They are query-time provider hints, NOT counts we enumerated. Topics/text/README indexing biases remain even with fork inclusion.

One local discovery call plus three local MCP task calls -> **3anonymous upstream GETs**, 15returned rows, **14distinct repo IDs:13with0stars,5forks**. One repo appeared in two queries and is not counted twice. These subset counts are not population proportions or growth statistics. Task times0.5438s +0.3035s +0.2502s =1.0975s, excluding imports/discovery/model synthesis; not a latency percentile. Tool-result text totals15987UTF-8bytes; upstream bodies accounted by readers89220bytes. Local catalog113definitions/113592HTTPbodybytes; selected extended tool definition1100compactUTF-8bytes. Different components are not additive token invoices or equal-coverage savings evidence. Real-host token/credit use remains unknown.

## Useful first-look leads

The following relevance judgements are **agent-authored hypotheses based only on the returned metadata**, not verified source-code/license/install/security or market-demand findings. Repository descriptions are untrusted author claims. No README, code or parent was fetched.

| Lead | Observed metadata | Why consider it / what is still unknown |
| --- | --- | --- |
| [Furox-Art/scientific-toolkit](https://github.com/Furox-Art/scientific-toolkit) | 0stars, not flagged fork, Python; description says it integrates seven research/AI projects via MCP | Candidate for studying a single useful multi-tool workflow. Actual integrations and ease of use not verified. |
| [Primexz/netops-mcp](https://github.com/Primexz/netops-mcp) | 1star, not flagged fork, Go; created2026-10-16; description mentions Securepoint UTM/MikroTik management through MCP | Adjacent to the VPS/network-diagnostics workflow. Permissions, safety boundaries and whether writes require approval need inspection. |
| [Johnmelo/codebadger-mola](https://github.com/Johnmelo/codebadger-mola) | 0stars, **fork**, Python; description claims queryable code structure/data flow for agents | Relevant discovery lead for code-understanding/diagnostics. Parent, divergence and whether this fork adds anything remain unknown; not counted as an independent invention. |
| [OneZero-Network/mcp-threat-intel](https://github.com/OneZero-Network/mcp-threat-intel) | 0stars, not flagged fork; description claims automated OWASP scanning for MCP tools | Adjacent evidence for security concerns in the ecosystem, not proof of vulnerability accuracy, customer demand or production safety. |
| [Vocametrix/vocametrix-mcp](https://github.com/Vocametrix/vocametrix-mcp) | 0stars, not flagged fork, TypeScript; description claims clinical voice-analysis integration | Example of a domain-specific MCP use case beyond developer tools. Medical accuracy/clinical readiness is not established by a repository description. |

These are follow-up leads, not a ranking of quality or a list of all competitors. Stars are shown as facts, not quality scores. Personal-account names do not establish that a single person did the work.

## Similar-looking ideas and duplicate noise

Three distinct repos—`nguyenkmb/skills-integrate-mcp-with-copilot`, `eaglelandsonce/skills-integrate-mcp-with-copilot6`, `laraskak/skills-integrate-mcp-with-copilot`—have the same exercise description in the returned metadata. The first also appears in two queries. All three are reported fork=false: **fork metadata alone cannot detect template copies or establish independent novelty**. Treat this as a candidate tutorial/template cluster pending source comparison, not three independent new product ideas.

`adeyholar/python-sdk` is fork=true and carries an “official Python SDK” description. That text is not verification that this particular fork is the official upstream. `tourhabk-ui/mcphq-awesome-mcp-servers` is a forked catalog, not automatically a new MCP implementation. Preserve these records but label lineage/originality unknown rather than excluding or inflating novelty.

## What this does and does not establish

**Passed locally:** actual API retrieval includes zero-star projects and forks; JSON preserves stable identities, unknowns, time hints, provider incompleteness, window cap and explicit continuation. Three bounded requests produced a usable research shortlist without fetching whole repositories.

**Not established:** all-topic/all-repo coverage, verified solo authorship, parent divergence, working installs/security/licenses, independent demand, semantic similarity engine, trends, real MCP-host acceptance or cost savings. A single sample is not a trend baseline. Incomplete_results=false does not mean all GitHub was examined.

## Next implementation work

1. Evidence-grounded similarity explanations and template/fork-family grouping without deleting distinct forks or assuming fork=false means independent work.
2. Explicit resumable query partitions/checkpoints when the provider count exceeds1000. Coverage gaps and source bias must remain visible; no automatic global-completeness claim.
3. Comparable repeated snapshots before any trend/growth statement; separately budget stable storage, refresh and a broader catalog source.
4. Real-host workflow/usage measurement in an approved candidate environment. No deployment, large crawl, storage service, paid embeddings/model or VPS write/cleanup occurred in this scenario.

Exact requests in the saved JSON can be replayed against an approved candidate that has mode=public. The current deployed connection is not claimed to expose this new mode. Fresh results/timings will differ. The local dispatcher used a non-secret placeholder with observed anonymous outbound requests, not real PAT-validation/session acceptance. The harness itself invoked no paid model; that does not make this chat/session free.
