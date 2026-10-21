# Workflow demonstration: a first look at a public GitHub author

**Candidate, not deployed or accepted.** One user question, one task-level MCP call, a useful answer, explicit coverage and measured components. This is a local-dispatch demonstration at runtime commit `3d8de2757460b7d3920c27e481590577b1d6a09a`, not a production MCP-host/session/model test. It does not close #99, #77 or #105. This author-workflow demonstration is not selection of a third market-facing product: #105 still lists repository discoverability audit and cross-platform idea research as its product hypotheses. It supplies a concrete usefulness/cost report format, not market-fit evidence.

## User question

> Покажи до пяти публичных проектов LeonidYasin, их языки и доступную недавнюю активность; помоги выбрать, что открыть первым, и обозначь пробелы данных.

[Measured request, result and costs](../examples/github-author-user-scenario.json) · [Runtime contract](../github-author-analytics.md).

The agent chose one `analyze_github_author` call with username=LeonidYasin, per_page=5, repo_page=1, include_text=true, include_activity=true, activity_days=30, event_page=1. One explicit repository page and one public Events page; no automatic continuation, README fetch or per-repository fan-out.

## Example answer an agent can give

The following Russian synthesis is agent-authored from the saved result, not an independently billed model run. Descriptions and historical event names remain untrusted source data. This is not a judgement of code quality or the author's professional ability.

> На первой странице пять публичных проектов — **по алфавиту, не рейтинг лучших**:
>
> | Проект | Основной язык | Что видно без чтения кода |
> | --- | --- | --- |
> | [agora-mcp](https://github.com/LeonidYasin/agora-mcp) | Python | По описанию — marketplace для ИИ-агентов с MCP и embeddings. 0 звёзд; не исключён из результата. |
> | [AI-Code-Assistant-Bot](https://github.com/LeonidYasin/AI-Code-Assistant-Bot) | Python | Описания нет; назначение и готовность по одному названию не подтверждаю. |
> | [AI-Side-Panel-Extension](https://github.com/LeonidYasin/AI-Side-Panel-Extension) | JavaScript | Fork; описание указывает на боковую панель для доступа к AI-сервисам. Описание обрезано. |
> | [ai-social-marketplace](https://github.com/LeonidYasin/ai-social-marketplace) | JavaScript | По описанию — social marketplace с Telegram, рекомендациями и shopping assistant. |
> | [ai_gallery_serv](https://github.com/LeonidYasin/ai_gallery_serv) | Не определён | Короткое описание: «ai local server». Не называю отсутствующий язык нулевой активностью. |
>
> Среди этих пяти: Python — 2, JavaScript — 2, язык неизвестен — 1. Это распределение основных языков **только возвращённых репозиториев**, не всего кода автора.
>
> В одной странице Events — 20 событий в запрошенном 30-дневном окне: 15 IssueCommentEvent, 3 PushEvent, 1 PullRequestEvent, 1 CreateEvent. Все помечены историческим именем `LeonidYasin/mcp-server`. Это повод отдельно открыть этот проект, если интересен текущий публичный рабочий контекст, но не доказательство основной занятости автора и не количество коммитов. Часть событий связана с нашей же работой над PR/issues; это не независимый сигнал спроса или популярности.
>
> **Что открыть первым:** если интересуют MCP и agent-native продукты — `agora-mcp` из показанной пятёрки: у него явно соответствующее описание. Если интересен наблюдавшийся рабочий контекст — отдельно проверить `mcp-server`: его карточки на этой странице нет. Это выбор по релевантности вопросу, не оценка качества. README, установка, безопасность и работоспособность проектов ещё не проверены.
>
> **Пробелы:** у списка проектов и Events есть следующая страница; их не запрашивали. Подсказка public_repos=52 не означает проверенные 52 проекта. Полного покрытия аккаунта/истории, private-активности и числа коммитов нет. Продолжение потребует явного дополнительного запроса.

All factual observations above come from the linked saved result, measured at `2026-10-16T20:12:55.082472+00:00`. Repository links are navigation for the human; the harness did not fetch them. Provider data may have changed since observation.

## Actual measured components — not a savings/billing claim

| Component | Observed |
| --- | ---: |
| Local MCP discovery | 1 tools/list call, 114 tool definitions |
| Local task invocation | 1 tools/call |
| Anonymous upstream GETs | 3, all HTTP200 |
| Local dispatcher elapsed time | 0.8149 s, one run, not a latency percentile |
| Upstream body bytes accounted by bounded reader | 181,939 |
| Tool result text, UTF-8 | 8,140 bytes |
| Local task HTTP response body | 9,068 bytes, includes JSON-RPC wrapping/escaping |
| Selected tool definition, compact UTF-8 JSON | 1,271 bytes |
| Full local tools/list HTTP response body | 114,295 bytes |
| Task request HTTP body | 232 bytes |
| Automatic next-page requests | 0 |
| Real host input/output tokens and credits | Unknown, not measured |

These quantities are different serialized components, not additive invoices or token counts. The local catalog response is much larger than the selected tool schema/result; **it does not prove that a real MCP host injects the whole catalog into the model**. No equally covered baseline workflow was measured, so no percentage saving is claimed. The harness invokes no paid model; that does not mean this chat/session is free.

## Workflow verdict and next action

- **Demonstrated locally:** one bounded task call provides enough evidence for a first-look answer, keeps zero-star/fork rows, reports unknown language and continuation, and does not overstate Events as commits/history.
- **Non-blocking limitation for this stated question:** the first alphabetical page is not a recommendation ranking or full account review. Recommendation reasons must name that scope. An event-referenced repo absent from the page is a follow-up lead, not an inspected project.
- **Open release/host-validation gates:** real MCP-host invocation with an existing supported connection, actual catalog/context and token/credit measurements, maintainer review, broader-author edge cases and integration reconciliation with #91/#107. No approval or deployment is implied.
- **Next workflow experiment:** replay this same question once from the real host, using an explicitly approved candidate environment; record the host's catalog behavior and usage when exposed. Compare answer quality against the same evidence before deciding whether compact discovery or smaller response fields are needed. Do not add another overlapping tool on the basis of this one run.
- **Not evidence of demand:** this is the maintainer's account and includes our own development events. Before outreach or popularity claims, use an agreed pilot audience and independent feedback; no HN/Reddit/catalog post has been sent.

## Manual reproduction and honest runner status

From this candidate checkout with its development dependencies installed:

```bash
PYTHONPATH=. python scripts/run_author_scenario.py --allow-public-network --output /tmp/author-scenario.json
```

The explicit network flag is required. This sends at most three anonymous fixed-origin GETs, and makes one local discovery plus one local task call using Flask's test client. A **non-secret placeholder** satisfies the existing local dispatcher gate, with client construction patched to a public-only observed client. No real credential, deployment, background service or paid model is needed. This is not proof of real PAT validation, host authentication, networked MCP session handling or production security. The output path is user-selected; the script writes only that local report.

In the recorded run, the MCP invocation and JSON report write succeeded. The runner's final console-summary expression then raised KeyError because it expected a `name` row field instead of `full_name`. The saved result is intact. The expression was corrected and checked offline against the saved result; **no second live invocation was made and the corrected runner has not been live-rerun**. The report records this distinction. Do not label the entire original process as an unqualified clean run.

Future manual runs return fresh provider data and timings, not this exact fixture. CI must not call the live harness automatically. Retain partial/refused observations rather than retrying or replacing them with fabricated success.
