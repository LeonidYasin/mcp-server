# SDK registration and Rust windows: v2 regression sample

**Candidate-local, not deployed. Former held-out repositories are now regression cases,
not a new independent quality evaluation.** Observed 2026-10-16T22:51:43.670209+00:00.

The earlier frozen-v1 source replay identified callback/Rust gaps. After changes, three real
Flask MCP `tools/call` requests used `get_repo_info(mode=public_evidence,file_selection=auto)`
on the same pinned repositories, with **no caller file paths/ranges**. All calls explicitly
left `compare_parent=false`; fork ancestry/contribution is still not evaluated here.
The synthetic local-only token satisfied the unchanged dispatcher gate; upstream reads were
anonymous. This time the anonymous quota reset had passed, so the actual candidate metadata,
commit/tree verification, Contents/blob verification and excerpt pipeline ran. No retries,
auth upgrade, raw-source fallback or installation/import/execution of inspected project code occurred.

[Source metadata, arguments and exact tested runtime hashes](../examples/repository-evidence-framework-sample.json)
· [Current contract and limitations](../repository-evidence.md)
· [Earlier independent-source findings](https://github.com/LeonidYasin/mcp-server/pull/111#issuecomment-6225884191)

## Measured run

| Repository | Files returned | Anonymous GETs | Upstream body bytes | Tool JSON-text UTF-8 bytes | Local elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Aristide021/solana-dev-mcp | 4 | 7 | 38644 | 16578 | 0.895158 |
| peakflo/pfMCP | 6 | 9 | 436108 | 25282 | 1.366326 |
| bradsjm/mail-imap-mcp-rs | 6 | 9 | 112331 | 23492 | 1.171940 |
| Total | 16 | 25 | 587083 | 65352 | 3.433424 |

All25upstream responses were HTTP200; every call was observed without source gaps. At most
12GETs/call remains the general cap; this run requested no fork comparison. The same16files
and full-content SHA256s as the earlier source replay were selected. The new JSON snapshot
excludes verbatim third-party text, while recording verified blob SHA and real source statuses.

## Range comparison on identical content

| File | Earlier v1 source-replay range | V2 candidate-delivered range | Hint/fallback |
| --- | --- | --- | --- |
| `Aristide021/solana-dev-mcp/index.ts` | 1–80 | [16–95](https://github.com/Aristide021/solana-dev-mcp/blob/edcab432766f377d1506d163cd2f5bbbd48db759/index.ts#L16-L95) | getAccountInfo; mcp_registration_hint |
| `peakflo/pfMCP/src/servers/main.py` | 1–34 | [1–34](https://github.com/peakflo/pfMCP/blob/25b8cb988d6e0ca23dce445bc2bdb47fb897fdfb/src/servers/main.py#L1-L34) | short_file_included_from_start |
| `peakflo/pfMCP/src/servers/ahrefs/main.py` | 1846–1925 | [1846–1925](https://github.com/peakflo/pfMCP/blob/25b8cb988d6e0ca23dce445bc2bdb47fb897fdfb/src/servers/ahrefs/main.py#L1846-L1925) | handle_call_tool; callable_name |
| `bradsjm/mail-imap-mcp-rs/src/server.rs` | 1–80 | [78–157](https://github.com/bradsjm/mail-imap-mcp-rs/blob/10a73f41b3851e3cd7e3a07ba823088e1a264d13/src/server.rs#L78-L157) | list_accounts; tool_attribute_hint |
| `bradsjm/mail-imap-mcp-rs/src/main.rs` | 1–80 | [91–170](https://github.com/bradsjm/mail-imap-mcp-rs/blob/10a73f41b3851e3cd7e3a07ba823088e1a264d13/src/main.rs#L91-L170) | main; callable_name |

### What improved

- TypeScript now records an SDK-constructor-bound `server.tool(...)` registration-shaped call
  at line18with literal name `getAccountInfo`, instead of `no_callable_declaration`.
  Delivered16–95contains the registration and RPC implementation, including the parsed-transaction
  call beyond the old80line cutoff. This is syntax evidence, not a verified JS binding/call graph.
- Rust `server.rs` now includes the `#[tool]` registration from line80and `list_accounts` at84;
  delivered78–157moves past imports into actual handlers. Attribute and declaration retention
  are both true. Rust body endpoints remain unknown; mutation methods below this range are
  still not automatically audited.
- Rust `main.rs` now centers on `main` at93instead of an unsupported-language header.
- Python SDK decorators have synthetic coverage for standard constructors/aliases. pfMCP's
  compatibility-wrapper Server remains unresolved, so its Ahrefs handler correctly stays an
  ordinary callable-name hint; no false claim that the wrapper's SDK identity was resolved.

### What did not improve

The file-ranking policy is unchanged. pfMCP still selects a short launcher and one alphabetical
Ahrefs connector, plus generated requirements.txt. This does not represent all76connector-main
paths in the earlier displayed tree or establish the fork's contribution. Monorepo role
coverage and direct dependency inputs (requirements.in) remain separate pending work.

The previously observed package-license inconsistency in the Solana demo is not repaired or
legally resolved. No wallet, mailbox, connector credentials, IMAP server or business API was
accessed. No scientific/security/runtime/commercial correctness was verified.

## Bounds and interpretation

V2 adds standard-library parsing/lexical rules, no runtime dependency/tool/database/model.
JS/TS registration hints require observed named SDK imports and simple constructor assignments;
Python decorator hints require corresponding AST syntax. Scope/alias rebinding is not resolved.
Rust attributes are macro-shaped hints, not proof a macro belongs to MCP or was expanded.
False positives/misses and inactive/test code remain possible. Simple literal name extraction
never evaluates expressions and does not label a concatenation prefix as the tool's real name.
32binding/alias,256candidate,8000line and20000AST-node bounds supplement existing input/output
caps. Fixed reasons explain header fallbacks. Explicit caller ranges remain untouched.

Earlier held-out replay used authorized MCP discovery and separate raw-file snapshots; it was
not an anonymous end-to-end baseline. This run's25GETs/587083body bytes therefore cannot be
compared to its16raw-file GETs as a saving. Model context, billed tokens/credits and latency
guarantees are unmeasured. Tool JSON size/local elapsed above are observations, not benchmarks.

The cases were used to design these fixes and are no longer held out. They are regression
proof of targeted behavior, not generalization, accuracy or GitHub-wide coverage. A fresh
independent cohort is needed after further changes. Historical samples preserve their
original runtime hashes and are not relabelled as runs of v2.
