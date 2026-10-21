"""Conservative registration-shaped syntax hints, never resolved SDK semantics."""
import ast
import re

ATTR_LOOKBACK = 24
MAX_BINDINGS = 32
IDENT = r"[A-Za-z_$][\w$]*"
SDK_IMPORT = re.compile(
    r"(?m)^[ \t]*(?P<keyword>import)\s*\{(?P<bindings>[^{}]{1,500})\}\s*from\s*"
    r"(?P<q>[\"'])@modelcontextprotocol/sdk(?:/[^\"'\n]{0,120})?(?P=q)")
JS_BINDING = re.compile(
    rf"(?m)^[ \t]*(?:const|let|var)\s+(?P<receiver>{IDENT})(?:\s*:\s*[\w.$<>]+)?\s*=\s*new\s+"
    rf"(?P<constructor>{IDENT})\s*\(")
RUST_FN = re.compile(
    r"^\s*(?:pub(?:\([^)\n]*\))?\s+)?(?:(?:async|const|unsafe|extern)\s+)*"
    r"fn\s+(?P<name>[A-Za-z_]\w*)\s*(?:<[^>\n]*>)?\s*\(")
RUST_TOOL = re.compile(r"^\s*#\s*\[\s*(?:[A-Za-z_]\w*::)*tool(?=\s*[\](])")


def js_receivers(source, masked):
    constructors = set()
    for match in SDK_IMPORT.finditer(source):
        # A matching raw import inside a comment/string must not establish context.
        if not masked[match.start("keyword"):match.start("keyword") + 6].startswith("import"):
            continue
        for part in match["bindings"].split(","):
            binding = re.fullmatch(r"\s*(?:McpServer|Server)(?:\s+as\s+(" + IDENT + r"))?\s*", part)
            if binding:
                constructors.add(binding[1] or part.strip())
                if len(constructors) > MAX_BINDINGS:
                    return None
    receivers = set()
    for match in JS_BINDING.finditer(masked):
        if match["constructor"] in constructors:
            receivers.add(match["receiver"])
            if len(receivers) > MAX_BINDINGS:
                return None
    return receivers


def js_registration(line, original_line, number, following, receivers):
    for receiver in sorted(receivers):
        match = re.match(r"^\s*" + re.escape(receiver) +
                         r"\s*\.\s*(?P<method>tool|registerTool)\s*\(", line)
        if not match:
            continue
        # Only a simple literal name is read. Never decode/evaluate expressions.
        name_match = re.match(r"\s*([\"'])([-A-Za-z0-9_.:/]{1,128})\1(?=\s*(?:,|\)))",
                              (original_line[match.end():] + "\n" + following)[:512])
        name = name_match[2] if name_match else receiver + "." + match["method"]
        return {"name": name, "line": number, "end_line": None, "priority": -1,
                "kind": "mcp_registration_hint", "registration_line": number,
                "registration_method": match["method"], "receiver": receiver,
                "static_tool_name": name_match[2] if name_match else None,
                "binding_hint": "sdk_named_import_and_constructor", "binding_scope_verified": False}
    return None


def python_receivers(nodes):
    constructors = set()
    for node in nodes:
        if not isinstance(node, ast.ImportFrom) or node.level:
            continue
        accepted = ({"FastMCP"} if node.module in ("mcp.server.fastmcp", "fastmcp") else
                    {"Server"} if node.module in ("mcp.server", "mcp.server.lowlevel",
                                                 "mcp.server.lowlevel.server") else set())
        for alias in node.names:
            if alias.name in accepted:
                constructors.add(alias.asname or alias.name)
    receivers = set()
    for node in nodes:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in constructors:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                receivers.update(target.id for target in targets if isinstance(target, ast.Name))
    return receivers


def python_registration(node, receivers):
    for decorator in node.decorator_list:
        func = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id in receivers and func.attr in ("tool", "call_tool")):
            return {"kind": "mcp_decorator_hint", "registration_line": decorator.lineno,
                    "registration_method": func.attr, "receiver": func.value.id,
                    "binding_hint": "sdk_named_import_and_constructor", "binding_scope_verified": False}
    return None


def rust_declarations(masked_lines):
    """Basic fn and adjacent #[tool] hints. No macro expansion or Rust parser."""
    pending, depth = None, 0
    for number, line in enumerate(masked_lines, 1):
        if pending is not None and number - pending > ATTR_LOOKBACK:
            pending = None
        stripped = line.lstrip()
        if depth:
            depth += line.count("[") - line.count("]")
            if depth < 0:
                pending, depth = None, 0
            # Conservatively omit code sharing an attribute-closing line.
            continue
        if stripped.startswith("#[") or re.match(r"^#\s+\[", stripped):
            if RUST_TOOL.match(line):
                pending = number
            # Strip complete same-line attributes; preserve multiline state.
            while re.match(r"^\s*#\s*\[", line):
                opening = line.index("[")
                balance, closing = 1, None
                for index in range(opening + 1, len(line)):
                    balance += (line[index] == "[") - (line[index] == "]")
                    if balance == 0:
                        closing = index
                        break
                if closing is None:
                    depth = balance
                    line = ""
                    break
                line = line[closing + 1:]
            if not line.strip():
                continue
        match = RUST_FN.match(line)
        if match:
            yield number, match["name"], pending
            pending = None
        elif line.strip():
            pending = None