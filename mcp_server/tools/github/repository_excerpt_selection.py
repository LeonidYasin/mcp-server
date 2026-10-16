"""Bounded source-window hints. Parse/lex only; never import or execute source."""
import ast
import re

MAX_SCAN_LINES = 8000
MAX_AST_NODES = 20000
MAX_CANDIDATES = 256
SKIP_NAMES = frozenset({"init", "new", "close", "spec", "response", "repr", "str",
                        "constructor", "if", "for", "while", "switch", "catch"})
PRIORITY = (
    frozenset({"execute"}),
    frozenset({"call"}),
    frozenset({"handle", "dispatch", "audit", "simulate", "validate", "compute", "process", "query", "prepare"}),
    frozenset({"run", "serve", "main", "request", "parse"}),
)


def _priority(name):
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).strip("_").lower()
    if normalized in SKIP_NAMES:
        return None
    if normalized in ("run_query", "handle_call_tool", "handle_tool_call"):
        return 0
    verb = normalized.split("_", 1)[0]
    return next((i for i, words in enumerate(PRIORITY) if verb in words), len(PRIORITY))


def _masked(source, extension):
    """Conservative C-family comment/string mask preserving LF lines.

    Not a language parser: Scala symbols, JS regexp/interpolation and exotic syntax
    can be missed. Masking a template as a whole intentionally omits interpolated code.
    """
    out = list(source)
    i, state, depth, quote = 0, "code", 0, ""
    while i < len(source):
        if state == "code":
            if source.startswith("//", i):
                state = "line"
            elif source.startswith("/*", i):
                state, depth = "block", 1
                out[i:i + 2] = [" ", " "]
                i += 2
                continue
            elif source.startswith('"""', i):
                state, quote = "string", '"""'
                out[i:i + 3] = [" "] * 3
                i += 3
                continue
            elif source[i] in "\"'`":
                state, quote = "string", source[i]
            else:
                i += 1
                continue
        elif state == "line" and source[i] == "\n":
            state = "code"
            i += 1
            continue
        elif state == "block":
            if source.startswith("/*", i):
                depth += 1
                out[i:i + 2] = [" ", " "]
                i += 2
                continue
            if source.startswith("*/", i):
                depth -= 1
                state = "code" if depth == 0 else "block"
                out[i:i + 2] = [" ", " "]
                i += 2
                continue
        elif state == "string":
            if source.startswith(quote, i):
                width = len(quote)
                out[i:i + width] = [" "] * width
                i += width
                state = "code"
                continue
            escapes = quote != '"""' and (quote != "`" or extension in ("js", "jsx", "ts", "tsx"))
            if source[i] == "\\" and escapes and i + 1 < len(source):
                out[i] = " "
                if source[i + 1] != "\n":
                    out[i + 1] = " "
                i += 2
                continue
        if source[i] != "\n":
            out[i] = " "
        i += 1
    return "".join(out)


GO = re.compile(r"^\s*func(?:\s*\([^)\n]*\))?\s+(?P<name>[A-Za-z_]\w*)\s*(?:\[[^\n]*\])?\s*\(")
SCALA = re.compile(r"^\s*(?:(?:private|protected|override|final|implicit|inline|transparent)\s+)*def\s+"
                   r"(?P<name>[A-Za-z_]\w*)\s*(?:\[[^\n]*\])?\s*(?:\(|:|=)")
JS_FUNCTION = re.compile(r"^\s*(?:(?:export|default|async)\s+)*function\s*\*?\s*(?P<name>[A-Za-z_$][\w$]*)\s*\(")
JS_ARROW = re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*"
                      r"(?:async\s*)?(?:\([^)\n]*\)|[A-Za-z_$][\w$]*)\s*(?::[^=\n]+)?=>")
JS_METHOD = re.compile(r"^\s*(?:(?:public|private|protected|static|async|override|abstract)\s+)*"
                       r"(?P<name>[A-Za-z_$][\w$]*)\s*\([^)\n]*\)\s*(?::[^{;\n]+)?\s*\{")


def select_window(path, lines, role_hint, limit=80):
    """One contiguous <=80-line window; names indicate where to look, not behavior."""
    result = {"strategy": "auto_callable_v1", "method": "header", "reason": None,
              "start_line": 1, "max_lines": limit, "anchor": None,
              "candidate_count": None, "candidate_scan_complete": False,
              "scan_limits": {"lines": MAX_SCAN_LINES, "ast_nodes": MAX_AST_NODES,
                              "candidates": MAX_CANDIDATES},
              "semantic_relevance_verified": False, "full_callable_verified": False}

    def fallback(reason):
        result["reason"] = reason
        return result

    if role_hint != "implementation":
        return fallback("non_implementation_header")
    if len(lines) <= limit:
        return fallback("short_file_included_from_start")
    if len(lines) > MAX_SCAN_LINES:
        return fallback("line_scan_cap")
    if any("\r" in line for line in lines):
        return fallback("bare_carriage_return_fallback")
    extension = path.rsplit(".", 1)[-1].lower()
    candidates = []
    if extension == "py":
        result["method"] = "python_ast"
        try:
            tree = ast.parse("\n".join(lines))
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            return fallback("python_parse_failed")
        for count, node in enumerate(ast.walk(tree), 1):
            if count > MAX_AST_NODES:
                return fallback("ast_node_cap")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                priority = _priority(node.name)
                if priority is not None:
                    candidates.append({"name": node.name[:128], "line": node.lineno,
                                       "end_line": node.end_lineno, "priority": priority})
            if len(candidates) >= MAX_CANDIDATES:
                return fallback("candidate_cap")
    elif extension in ("go", "scala", "js", "jsx", "ts", "tsx"):
        result["method"] = extension + "_lexical"
        patterns = ((GO,) if extension == "go" else (SCALA,) if extension == "scala"
                    else (JS_FUNCTION, JS_ARROW, JS_METHOD))
        for number, line in enumerate(_masked("\n".join(lines), extension).split("\n"), 1):
            for pattern in patterns:
                match = pattern.match(line)
                if match:
                    name = match["name"]
                    priority = _priority(name)
                    if priority is not None:
                        candidates.append({"name": name[:128], "line": number,
                                           "end_line": None, "priority": priority})
                    break
            if len(candidates) >= MAX_CANDIDATES:
                return fallback("candidate_cap")
    else:
        return fallback("unsupported_language_header")
    result.update(candidate_count=len(candidates), candidate_scan_complete=True)
    if not candidates:
        return fallback("no_callable_declaration")
    anchor = min(candidates, key=lambda c: (c["priority"], c["line"], c["name"]))
    result.update(anchor=anchor, start_line=max(1, anchor["line"] - 2),
                  reason="priority_callable_name" if anchor["priority"] < len(PRIORITY) else "first_non_boilerplate_callable")
    return result