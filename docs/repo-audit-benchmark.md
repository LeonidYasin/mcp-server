# Repository audit: bounded token-accounting experiment (#77 / #103)

This is a software benchmark artifact, **not actual Notion credits or a paid-model bill**. No GitHub API or model requests are made by measured scenarios; all GitHub routes use httpx.MockTransport. Tokenizer setup may fetch a public vocabulary on its first uncached invocation. The standalone new tool definition is measured separately; it is not assumed to equal the marginal catalog delta.

[Machine-readable evidence](examples/repo-audit-benchmark.json) is the source for the table below. Method: cl100k_base tokens in the same complete candidate tools catalog (once), JSON-RPC call arguments and normalized JSON-RPC result envelopes. Input body hashes and raw input file hash are included. A second calculation over the saved full RPC transcripts independently reconciled every total and call count. Two unique input rows were profiled: no duplicates or missing cells; constant provenance is intentional because both use the same fixture-generation method.

| Fixture | Scenario | MCP-visible cl100k_base tokens | Tool calls | Mock HTTP GETs |
| --- | --- | ---: | ---: | ---: |
| synthetic-small | legacy_shared_subset | 16415 | 5 | 5 |
| synthetic-small | legacy_batched_subset | 16375 | 4 | 5 |
| synthetic-small | audit_full_scope | 17138 | 1 | 6 |
| public-readme-snapshot | legacy_shared_subset | 26189 | 5 | 5 |
| public-readme-snapshot | legacy_batched_subset | 26150 | 4 | 5 |
| public-readme-snapshot | audit_full_scope | 17203 | 1 | 6 |

## Interpretation and limits

The short-input audit report has overhead: it is **not universally cheaper** than fetching a small amount of source context. Avoiding a full long README can reduce visible context in that fixture, but this is **not an equal-evidence savings claim**. The 5-call legacy chain and 4-call batched alternative do not supply all audit evidence (license, disabled Issues, Pages, root completeness, pinned snapshot resolution or generated actions). Baseline refs are supplied for free. These selected chains are not a proof of the optimal possible workflow.

One composite call does not necessarily reduce five or four model turns to one: the legacy calls can be parallelized into one response round. Bounds (parallel lower/sequential upper) are recorded, not observed agent turns. The composite can make more upstream GETs; mock request counts are not network latency.

Both paths see the same full candidate catalog. The prior catalog without audit is separately recorded. A real host may resend/cache/select tool schemas differently. System/chat/history/reasoning/summary text, actual host wrappers, actual model tokenizer and billing are excluded. The two fixtures are not a representative repository sample: the large case uses real public README/pyproject bytes from pinned mcp-server0c12a375, but synthetic routes/metadata and a fixed clock. Do not call this live acceptance or predict production savings. Exact final-report equivalence and real host usage remain pending #77.

## Reproduce

From a full Git checkout containing commit0c12a375, with the project's dev dependencies and an optional locally installed tiktoken (not a runtime dependency):

```bash
python -m pip install tiktoken
python scripts/benchmark_repo_discoverability.py --prepare-inputs \
  --input /tmp/audit-inputs-new.json \
  --output /tmp/audit-benchmark.json \
  --transcript /tmp/audit-transcripts.json
```

--prepare-inputs refuses to overwrite raw inputs. Omit it to rerun an existing input JSON. Inputs contain no credentials; input setup only reads public snapshot files from local git. Measured paths use a synthetic non-credential and a fixed clock; no fixture string is executed. Raw transcripts are optional debugging artifacts; they include full fixture source text and should not be inserted into a model context just to read the totals.
