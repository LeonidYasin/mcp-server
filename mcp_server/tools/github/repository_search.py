"""Opt-in public Search observations using the existing client, no global crawl."""
from datetime import datetime, timezone
import json
import re
import time
from urllib.parse import parse_qsl, urlsplit

import httpx

API = 'https://api.github.com/search/repositories'
BODY_CAP = 1048576
OUTPUT_CAP = 65536
SEARCH_WINDOW = 1000
LOGIN = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?')
NAME = re.compile(r'[A-Za-z0-9_.-]{1,100}')


def _now():
    return datetime.now(timezone.utc).isoformat()


def _integer(value, minimum=0):
    return type(value) is int and minimum <= value <= 9223372036854775807


def _dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _constant(_):
    raise ValueError('nonfinite JSON')


def _text(value, cap, credential):
    if not isinstance(value, str) or not value.strip() or any(not c.isprintable() for c in value):
        return None
    if credential and len(credential) >= 8 and credential in value:
        return None
    return value[:cap]


def _date(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return d.astimezone(timezone.utc).isoformat() if d.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _row(data, credential):
    if not isinstance(data, dict) or data.get('private') is not False or not _integer(data.get('id'), 1):
        return None
    owner, full = data.get('owner'), data.get('full_name')
    if not isinstance(owner, dict) or not _integer(owner.get('id'), 1) or not isinstance(full, str):
        return None
    login = owner.get('login')
    parts = full.split('/')
    if (not isinstance(login, str) or not LOGIN.fullmatch(login) or len(parts) != 2 or
            parts[0].lower() != login.lower() or not NAME.fullmatch(parts[1]) or parts[1] in ('.', '..') or
            (credential and len(credential) >= 8 and credential in full)):
        return None
    desc = _text(data.get('description'), 160, credential)
    language = _text(data.get('language'), 64, credential)
    if language is not None and len(data['language']) > 64:
        language = None
    topics = data.get('topics')
    topics = [x for x in topics[:20] if isinstance(x, str) and
              re.fullmatch(r'[a-z0-9][a-z0-9-]{0,49}', x) and
              not (credential and len(credential) >= 8 and credential in x)] if isinstance(topics, list) else None
    return {'id': data['id'], 'full_name': full, 'url': 'https://github.com/' + full,
        'owner': {'id': owner['id'], 'login': login,
                  'type': owner.get('type') if owner.get('type') in ('User', 'Organization', 'Bot') else None},
        'stars': data.get('stargazers_count') if _integer(data.get('stargazers_count')) else None,
        'forks': data.get('forks_count') if _integer(data.get('forks_count')) else None,
        'fork': data.get('fork') if type(data.get('fork')) is bool else None,
        'archived': data.get('archived') if type(data.get('archived')) is bool else None,
        'language': language, 'topics': topics, 'description': desc,
        'description_truncated': desc is not None and len(data['description']) > 160,
        'untrusted_source_text': True,
        'created_at': _date(data.get('created_at')), 'updated_at': _date(data.get('updated_at')),
        'pushed_at': _date(data.get('pushed_at')), 'parent': None,
        'fork_originality': 'not_checked', 'solo_author_verified': False, 'source': 0}


def _pagination(link, params, raw_count, total, incomplete):
    page, size = params['page'], params['per_page']
    cap = page * size >= SEARCH_WINDOW
    if not link:
        more = False if incomplete is False and raw_count < size and total is not None and total == (page - 1) * size + raw_count else None
        return more, None, 'search_window_cap' if cap else 'short_page_observed' if more is False else 'pagination_not_proven'
    try:
        relations = {}
        for part in link.split(','):
            m = re.fullmatch(r'\s*<([^<>]+)>;\s*rel="([a-z ]+)"\s*', part)
            if not m:
                raise ValueError('link shape')
            for relation in m[2].split():
                if relation in relations:
                    raise ValueError('duplicate relation')
                relations[relation] = m[1]
        if 'next' not in relations:
            # Do not treat unrelated/last links as scope-validated exhaustion evidence.
            return None, None, 'search_window_cap' if cap else 'pagination_not_proven'
        url = urlsplit(relations['next'])
        if (url.scheme != 'https' or url.netloc != 'api.github.com' or
                url.path != '/search/repositories' or url.fragment):
            raise ValueError('origin/path')
        pairs = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True)
        q = dict(pairs)
        if len(q) != len(pairs) or set(q) != set(params):
            raise ValueError('query keys')
        expected = {k: str(v) for k, v in params.items()} | {'page': str(page + 1)}
        if q != expected:
            raise ValueError('changed scope/page')
        if (page * size) >= SEARCH_WINDOW:
            return True, None, 'search_window_cap'
        return True, page + 1, 'next_page_observed'
    except (ValueError, OverflowError):
        return None, None, 'search_window_cap' if cap else 'invalid_link'


def observe(client, **kwargs):
    """Exactly one bounded anonymous GET; caller selected mode=public explicitly."""
    source = {'url': API, 'query': None, 'attempted_at': None, 'fetched_at': None,
              'http_status': None, 'error': None}
    result = {'schema_version': 1, 'mode': 'public_repository_search_page', 'state': 'invalid_input',
        'items': None, 'reported_total_count': None, 'incomplete_results': None, 'returned': None,
        'raw_received': None, 'excluded': None, 'duplicates': None, 'source': source,
        'next_request': None, 'error': None,
        'coverage': {'global_complete': False, 'complete_query_results': False, 'has_more': None,
                     'search_result_window': SEARCH_WINDOW, 'search_window_limited': None, 'stop_reason': 'not_requested'},
        'budget': {'requests': 0, 'max_requests': 1, 'body_cap_bytes': BODY_CAP,
                   'output_cap_bytes': OUTPUT_CAP, 'checked_deadline_seconds': 8, 'socket_timeout_seconds_max': 5},
        'limitations': ['One live Search page, not a catalog, snapshot history, trend or similarity engine.',
            'Provider query defines scope. Fork inclusion requires an explicit supported query qualifier such as fork:true.',
            'No implicit star threshold, automatic pagination, retries, parent lookup, code/README fetch or writes.',
            'Search indexing/visibility and cross-page mutation limit coverage; empty results do not prove no analogs.',
            'Descriptions/topics/names are untrusted data. Literal credential exclusion is not semantic sanitization.',
            'Owner type does not prove solo authorship; fork originality/parent are not checked.']}

    def done():
        text = _dump(result)
        if len(text.encode()) <= OUTPUT_CAP:
            return text
        result.update(state='partial', items=None, returned=None, next_request=None, error='output_budget')
        result['coverage'].update(has_more=None, stop_reason='output_budget')
        return _dump(result)

    query = kwargs.get('query')
    size, page = kwargs.get('limit', 20), kwargs.get('page', 1)
    sort, order = kwargs.get('sort', 'best_match'), kwargs.get('order', 'desc')
    headers = getattr(client, '_headers', {})
    credential = str(headers.get('Authorization', '')).removeprefix('Bearer ') if isinstance(headers, dict) else ''
    if (set(kwargs) - {'query', 'mode', 'limit', 'page', 'sort', 'order'} or
            not isinstance(query, str) or not query.strip() or len(query) > 256 or
            any(not c.isprintable() for c in query) or
            (credential and len(credential) >= 8 and credential in query) or
            not _integer(size, 1) or size > 100 or not _integer(page, 1) or (page - 1) * size >= SEARCH_WINDOW or
            sort not in ('best_match', 'stars', 'forks', 'help-wanted-issues', 'updated') or
            order not in ('asc', 'desc')):
        result['error'] = 'invalid_input'
        return done()
    params = {'q': query.strip(), 'per_page': size, 'page': page}
    if sort != 'best_match':
        params.update(sort=sort, order=order)
    source['query'] = params
    result['state'] = 'unavailable'
    if client is None or not hasattr(client, '_client'):
        result['error'] = source['error'] = 'client_unavailable'
        return done()
    deadline = time.monotonic() + 8
    response = None
    link = ''
    try:
        request = client._client.build_request('GET', API, params=params, timeout=5.0)
        request.url = httpx.URL(API, params=params)
        request.headers = httpx.Headers({'Host': 'api.github.com', 'Accept': 'application/vnd.github+json',
            'Accept-Encoding': 'identity', 'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'mcp-public-repository-observation'})
        source['attempted_at'] = _now()
        result['budget']['requests'] = 1
        response = client._client.send(request, auth=None, follow_redirects=False, stream=True)
        source['http_status'] = response.status_code
        hints = {}
        for key in ('x-ratelimit-limit', 'x-ratelimit-remaining', 'x-ratelimit-reset', 'retry-after'):
            value = response.headers.get(key, '')
            if re.fullmatch(r'[0-9]{1,12}', value):
                hints[key] = int(value)
        if hints:
            source['rate_hints'] = hints
        if response.status_code != 200:
            source['error'] = 'redirect_rejected' if 300 <= response.status_code < 400 else 'http_refused'
        elif response.headers.get('content-encoding', 'identity').lower() not in ('', 'identity'):
            source['error'] = 'compressed_response_rejected'
        else:
            chunks, count = [], 0
            for chunk in response.iter_bytes(chunk_size=8192):
                count += len(chunk)
                result['budget']['response_bytes'] = count
                if count > BODY_CAP:
                    source['error'] = 'response_too_large'
                    break
                if time.monotonic() >= deadline:
                    source['error'] = 'time_budget'
                    break
                chunks.append(chunk)
            if source['error'] is None:
                data = json.loads(b''.join(chunks), parse_constant=_constant)
                if (not isinstance(data, dict) or not isinstance(data.get('items'), list) or len(data['items']) > size):
                    raise ValueError('envelope')
                if time.monotonic() >= deadline:
                    source['error'] = 'time_budget'
                else:
                    source['fetched_at'] = _now()
                    link = response.headers.get('link', '')
                    if len(link) > 4096:
                        link = 'invalid'
    except httpx.TimeoutException:
        source['error'] = 'timeout'
    except Exception:
        source['error'] = 'invalid_or_unavailable_response'
    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                source['cleanup_error'] = 'response_close_failed'
    if source['error'] is not None:
        result['error'] = source['error']
        return done()
    total = data.get('total_count') if _integer(data.get('total_count')) else None
    incomplete = data.get('incomplete_results') if type(data.get('incomplete_results')) is bool else None
    items, seen, excluded, duplicates = [], set(), 0, 0
    invalid_fields = False
    for raw in data['items']:
        item = _row(raw, credential)
        if item is None:
            excluded += 1
        elif item['id'] in seen:
            duplicates += 1
        else:
            seen.add(item['id'])
            items.append(item)
            invalid_fields |= any(item[k] is None for k in ('stars', 'forks', 'fork', 'archived'))
    more, next_page, reason = _pagination(link, params, len(data['items']), total, incomplete)
    result.update(state='partial' if incomplete is not False or total is None or excluded or duplicates or invalid_fields else 'observed',
        items=items, reported_total_count=total, incomplete_results=incomplete,
        raw_received=len(data['items']), returned=len(items), excluded=excluded, duplicates=duplicates)
    result['coverage'].update(has_more=more, search_window_limited=(total > SEARCH_WINDOW) if total is not None else None, stop_reason=reason)
    if next_page is not None:
        result['next_request'] = {'query': params['q'], 'mode': 'public', 'limit': size,
                                  'page': next_page, 'sort': sort, 'order': order}
    return done()
