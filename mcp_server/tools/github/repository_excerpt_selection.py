"""Bounded source-window hints. Parse/lex only; never import or execute source."""
import ast
import re

from mcp_server.tools.github.repository_framework_hints import MAX_BINDINGS

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
            raw = (re.match(r'(?:br|cr|r)(#{0,255})"', source[i:i + 260])
                   if extension == "rs" and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] == "_"))
                   else None)
            lifetime = re.match(r"'[A-Za-z_]\w*", source[i:i + 256]) if extension == "rs" and source[i] == "'" else None
            if raw:
                state, quote = "raw_string", '"' + raw[1]
                width = raw.end()
                out[i:i + width] = [" "] * width
                i += width
                continue
            if lifetime and (i + lifetime.end() == len(source) or source[i + lifetime.end()] != "'"):
                i += 1
                continue
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
        elif state in ("string", "raw_string"):
            if source.startswith(quote, i):
                width = len(quote)
                out[i:i + width] = [" "] * width
                i += width
                state = "code"
                continue
            escapes = state != "raw_string" and quote != '"""' and (quote != "`" or extension in ("js", "jsx", "ts", "tsx"))
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
    result = {"strategy": "auto_callable_v2", "method": "header", "reason": None,
              "start_line": 1, "max_lines": limit, "anchor": None,
              "candidate_count": None, "candidate_scan_complete": False,
              "scan_limits": {"lines": MAX_SCAN_LINES, "ast_nodes": MAX_AST_NODES,
                              "candidates": MAX_CANDIDATES, "framework_bindings": MAX_BINDINGS},
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
        nodes = []
        for count, node in enumerate(ast.walk(tree), 1):
            if count > MAX_AST_NODES:
                return fallback("ast_node_cap")
            nodes.append(node)
        from mcp_server.tools.github.repository_framework_hints import python_receivers, python_registration
        receivers = python_receivers(nodes)
        for node in nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                registration = python_registration(node, receivers)
                priority = _priority(node.name)
                if registration is not None or priority is not None:
                    candidates.append({"name": node.name[:128], "line": node.lineno,
                                       "end_line": node.end_lineno,
                                       "priority": -1 if registration else priority, **(registration or {})})
            if len(candidates) >= MAX_CANDIDATES:
                return fallback("candidate_cap")
    elif extension in ("go", "scala", "js", "jsx", "ts", "tsx", "rs"):
        result["method"] = extension + "_lexical"
        from mcp_server.tools.github.repository_framework_hints import js_receivers, js_registration, rust_declarations
        source = "\n".join(lines)
        masked = _masked(source, extension)
        masked_lines = masked.split("\n")
        if extension == "rs":
            for number, name, registration_line in rust_declarations(masked_lines):
                priority = _priority(name)
                if registration_line is not None or priority is not None:
                    candidates.append({"name": name[:128], "line": number, "end_line": None,
                                       "priority": -1 if registration_line is not None else priority,
                                       **({"kind": "tool_attribute_hint",
                                           "registration_line": registration_line, "binding_scope_verified": False}
                                          if registration_line is not None else {})})
                if len(candidates) >= MAX_CANDIDATES:
                    return fallback("candidate_cap")
        receivers = js_receivers(source, masked) if extension in ("js", "jsx", "ts", "tsx") else set()
        if receivers is None:
            return fallback("framework_binding_cap")
        patterns = ((GO,) if extension == "go" else (SCALA,) if extension == "scala"
                    else () if extension == "rs" else (JS_FUNCTION, JS_ARROW, JS_METHOD))
        for number, line in enumerate(masked_lines, 1):
            registration = js_registration(line, lines[number - 1], number,
                                           "\n".join(lines[number:number + 8]), receivers) if receivers else None
            if registration:
                candidates.append(registration)
                if len(candidates) >= MAX_CANDIDATES:
                    return fallback("candidate_cap")
                continue
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
    context_line = anchor["line"]
    registration_line = anchor.get("registration_line")
    if registration_line is not None and 0 <= anchor["line"] - registration_line <= 20:
        context_line = registration_line
    result.update(anchor=anchor, start_line=max(1, context_line - 2),
                  reason="framework_registration_hint" if anchor.get("kind") else
                  "priority_callable_name" if anchor["priority"] < len(PRIORITY) else "first_non_boilerplate_callable")
    return result