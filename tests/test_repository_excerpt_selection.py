"""Source parsing is not code execution or a semantic audit."""
import pytest

from mcp_server.tools.github import repository_excerpt_selection as module


def choose(source, path="src/engine.py", role="implementation"):
    return module.select_window(path, source.split("\n"), role)


def padded(source):
    return "\n" * 100 + source + "\n" * 90


def test_python_execute_after_call_and_helper_is_priority_not_first_declaration():
    result = choose(padded("def helper():\n    pass\n\ndef call():\n    pass\n\ndef execute():\n    return 1"))
    assert result["method"] == "python_ast" and result["anchor"]["name"] == "execute"
    assert result["anchor"]["line"] == 107 and result["start_line"] == 105
    assert result["anchor"]["end_line"] == 108
    assert result["candidate_scan_complete"] and result["candidate_count"] == 3
    assert not result["semantic_relevance_verified"] and not result["full_callable_verified"]


def test_python_async_method_is_parsed_without_importing_or_executing():
    source = "raise RuntimeError('MUST NOT EXECUTE')\n" + padded(
        "class Server:\n    async def execute_query(self):\n        return unknown_runtime_function()")
    result = choose(source)
    assert result["anchor"]["name"] == "execute_query" and result["start_line"] > 80


def test_nested_python_function_is_an_eligible_hint_not_reachability_proof():
    result = choose(padded("def outer():\n    def execute():\n        return 1\n    return execute"))
    assert result["anchor"]["name"] == "execute"
    assert not result["semantic_relevance_verified"]


def test_python_docstring_fake_declaration_does_not_win():
    result = choose(padded('text = """\ndef execute():\n    fake()\n"""\n# def execute(): pass\n\ndef handle():\n    return 1'))
    assert result["anchor"]["name"] == "handle" and result["candidate_count"] == 1


def test_python_parse_failure_is_explicit_header_not_fake_match():
    result = choose(padded("def execute(:\n    broken"))
    assert result["reason"] == "python_parse_failed" and result["start_line"] == 1
    assert result["anchor"] is None and result["candidate_count"] is None


@pytest.mark.parametrize("name", ["__init__", "new", "close", "spec", "response"])
def test_boilerplate_names_only_keep_header(name):
    result = choose(padded(f"def {name}():\n    pass"))
    assert result["reason"] == "no_callable_declaration"
    assert result["candidate_count"] == 0 and result["candidate_scan_complete"]


def test_other_callable_fallback_is_not_semantic_verdict():
    result = choose(padded("def frobnicate():\n    pass"))
    assert result["anchor"]["name"] == "frobnicate"
    assert result["reason"] == "first_non_boilerplate_callable"


@pytest.mark.parametrize("path,source,name,method", [
    ("src/main.go", "func (e *Engine) Execute(ctx context.Context) error {\nreturn nil\n}", "Execute", "go_lexical"),
    ("src/main.go", "func Call[T any](args T) {\n}", "Call", "go_lexical"),
    ("src/main.scala", "private def executeQuery(x: Int): Int = {\n  x\n}", "executeQuery", "scala_lexical"),
    ("src/main.scala", "def execute = 42", "execute", "scala_lexical"),
    ("src/main.ts", "export async function executeQuery(input: string) {\nreturn input;\n}", "executeQuery", "ts_lexical"),
    ("src/main.js", "const handle = async (input) => {\nreturn input;\n}", "handle", "js_lexical"),
    ("src/main.ts", "public async execute(input: string): Promise<void> {\n}", "execute", "ts_lexical"),
])
def test_supported_lexical_declarations(path, source, name, method):
    result = choose(padded(source), path)
    assert result["anchor"]["name"] == name and result["method"] == method
    assert result["anchor"]["end_line"] is None
    assert result["start_line"] == 99 and result["max_lines"] == 80


@pytest.mark.parametrize("path,fake", [
    ("src/main.go", '/*\nfunc Execute() {}\n*/\n'),
    ("src/main.go", 'const s = `\nfunc Execute() {}\n`\n'),
    ("src/main.scala", 'val s = """\ndef execute = 3\n"""\n'),
    ("src/main.ts", 'const s = `\nfunction execute() {}\n`;\n'),
    ("src/main.ts", 'const s = `escape \\`\nfunction execute() {}\n`;\n'),
    ("src/main.scala", '/* outer\n/* inner */\ndef execute = 3\n*/\n'),
])
def test_lexical_strings_and_comments_do_not_supply_false_anchor(path, fake):
    real = ("func Handle() {}" if path.endswith(".go") else
            "def handle = 1" if path.endswith(".scala") else "function handle() {}")
    result = choose(padded(fake + real), path)
    assert result["anchor"]["name"].lower() == "handle" and result["candidate_count"] == 1


def test_no_callable_scala_query_fragment_is_honest_header_fallback():
    result = choose(padded('val result = cpg.call.name("execute")'), "query.scala")
    assert result["reason"] == "no_callable_declaration" and result["anchor"] is None


def test_unsupported_language_is_explicit_not_regex_guess():
    result = choose(padded("fn execute() {}"), "engine.rs")
    assert result["reason"] == "unsupported_language_header" and result["start_line"] == 1


def test_document_and_short_file_keep_header():
    assert choose(padded("def execute(): pass"), "README.md", "overview")["reason"] == "non_implementation_header"
    assert choose("def execute(): pass")["reason"] == "short_file_included_from_start"


def test_candidate_cap_falls_back_without_pretending_scan_complete():
    result = choose("\n".join(f"def execute_{n}(): pass" for n in range(module.MAX_CANDIDATES + 1)))
    assert result["reason"] == "candidate_cap" and result["start_line"] == 1
    assert not result["candidate_scan_complete"] and result["candidate_count"] is None


def test_line_scan_cap():
    result = choose("\n" * module.MAX_SCAN_LINES + "def execute(): pass")
    assert result["reason"] == "line_scan_cap" and not result["candidate_scan_complete"]


def test_ast_node_cap(monkeypatch):
    monkeypatch.setattr(module, "MAX_AST_NODES", 2)
    result = choose(padded("def execute(): return [1,2,3]"))
    assert result["reason"] == "ast_node_cap" and result["anchor"] is None


def test_parser_recursion_failure_is_fallback(monkeypatch):
    def fail(_):
        raise RecursionError("synthetic")
    monkeypatch.setattr(module.ast, "parse", fail)
    assert choose(padded("def execute(): pass"))["reason"] == "python_parse_failed"


def test_bare_cr_does_not_shift_lf_citation_indices():
    result = choose(padded("x=1\rdef execute(): pass"))
    assert result["reason"] == "bare_carriage_return_fallback"


def test_deterministic_and_small_context_before_definition():
    source = padded("def execute(): pass")
    assert choose(source) == choose(source)
    result = choose(source)
    assert result["anchor"]["line"] - result["start_line"] == 2