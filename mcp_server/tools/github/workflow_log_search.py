"""Fixed subprocess worker bounds regex wall time without modifying server signals."""
import json
import re
import sys


def search(segments, pattern, case_sensitive, context, max_matches, max_lines, max_chars):
    rx = re.compile(pattern, 0 if case_sensitive else re.IGNORECASE)
    hits, output, remaining, chars, truncated = 0, [], max_lines, 0, False
    for segment in segments:
        lines = segment['lines']
        indexes = [i for i, line in enumerate(lines) if rx.search(line)]
        blocks = []
        for idx in indexes:
            hits += 1
            if hits > max_matches:
                truncated = True
                continue
            a, b = max(0, idx - context), min(len(lines), idx + context + 1)
            if blocks and a <= blocks[-1][1]:
                blocks[-1][1] = max(blocks[-1][1], b)
            else:
                blocks.append([a, b])
        returned = []
        for a, b in blocks:
            for i in range(a, b):
                if remaining <= 0 or chars >= max_chars:
                    truncated = True
                    continue
                text = lines[i][:max_chars-chars]
                if len(text) != len(lines[i]):
                    truncated = True
                returned.append({'line': i+1, 'text': text})
                chars += len(text)
                remaining -= 1
        if returned:
            output.append({k: v for k,v in segment.items() if k != 'lines'} | {'lines': returned})
    return {'matches': hits, 'segments': output, 'returned_lines': max_lines-remaining,
            'output_truncated': truncated}


def main():
    try:
        args = json.load(sys.stdin)
        result = search(**args)
    except re.error:
        result = {'error': 'invalid_pattern'}
    except Exception:
        result = {'error': 'search_failed'}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
