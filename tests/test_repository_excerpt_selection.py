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
    result = choose(padded("fn execute() {}"), "engine.zig")
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


JS_IMPORT = 'import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";\n'
JS_INSTANCE = 'const server = new McpServer({name:"example",version:"1"});\n'


@pytest.mark.parametrize("method", ["tool", "registerTool"])
def test_sdk_registration_callback_is_a_hint_not_named_function(method):
    result = choose(JS_IMPORT + JS_INSTANCE + padded(
        f'server.{method}(\n  "lookup_account",\n  {{}},\n  async () => {{ return data; }}\n);'), "index.ts")
    anchor = result["anchor"]
    assert result["strategy"] == "auto_callable_v2"
    assert result["reason"] == "framework_registration_hint"
    assert anchor["name"] == anchor["static_tool_name"] == "lookup_account"
    assert anchor["kind"] == "mcp_registration_hint" and anchor["end_line"] is None
    assert anchor["binding_scope_verified"] is False
    assert anchor["line"] == 103


def test_js_sdk_alias_and_static_type_annotation():
    source = ('import { McpServer as Agent } from "@modelcontextprotocol/sdk/server/mcp.js";\n'
              'const mcp: Agent = new Agent({});\n' + padded('mcp.tool("list", {}, async () => {});'))
    assert choose(source, "main.ts")["anchor"]["name"] == "list"


def test_js_dynamic_name_is_not_evaluated_or_presented_as_literal():
    result = choose(JS_IMPORT + JS_INSTANCE + padded(
        'server.registerTool(getNameAndDoSomething(), {}, async () => {});'), "index.ts")
    assert result["anchor"]["static_tool_name"] is None
    assert result["anchor"]["name"] == "server.registerTool"


def test_js_literal_prefix_of_an_expression_is_not_a_static_tool_name():
    result = choose(JS_IMPORT + JS_INSTANCE + padded(
        'server.tool("prefix" + computeSuffix(), {}, async () => {});'), "index.ts")
    assert result["anchor"]["static_tool_name"] is None


@pytest.mark.parametrize("prefix", [
    'import { McpServer } from "unrelated-package";\n' + JS_INSTANCE,
    'const text = `\n' + JS_IMPORT + JS_INSTANCE + '`;\n',
    '/*\n' + JS_IMPORT + JS_INSTANCE + '*/\n',
    JS_IMPORT + '// ' + JS_INSTANCE,
    JS_IMPORT + 'const server = notAnSdkConstructor();\n',
])
def test_js_registration_without_observed_sdk_constructor_binding_is_not_promoted(prefix):
    result = choose(prefix + padded('server.tool("fake", {}, async () => {});'), "index.ts")
    assert result["anchor"] is None


def test_js_import_and_constructor_text_in_regex_literals_do_not_establish_context():
    source = ('const fakeImport = /import {McpServer} from "@modelcontextprotocol/sdk"/;\n'
              'const fakeConstructor = /const server = new McpServer()/;\n' +
              padded('server.tool("fake", {}, async () => {});'))
    assert choose(source, "index.ts")["anchor"] is None


@pytest.mark.parametrize("fake", [
    '// server.tool("fake", {}, async () => {});\n',
    'const text = `\nserver.tool("fake", {}, async () => {});\n`;\n',
    '/* server.tool("fake", {}, async () => {}); */\n',
])
def test_js_fake_registration_in_comments_and_templates_does_not_win(fake):
    result = choose(JS_IMPORT + JS_INSTANCE + padded(fake + 'server.tool("real", {}, async () => {});'), "index.ts")
    assert result["anchor"]["name"] == "real" and result["candidate_count"] == 1


@pytest.mark.parametrize("module,constructor", [("mcp.server.fastmcp", "FastMCP"), ("fastmcp", "FastMCP"),
                                             ("mcp.server.lowlevel", "Server")])
def test_python_sdk_decorator_registration_precedes_unregistered_execute(module, constructor):
    source = f"from {module} import {constructor} as Agent\nmcp = Agent('demo')\n"
    source += padded("def execute(): return 1\n\n@mcp.tool()\ndef list_accounts():\n    return []")
    result = choose(source)
    assert result["anchor"]["name"] == "list_accounts"
    assert result["anchor"]["kind"] == "mcp_decorator_hint"
    assert result["reason"] == "framework_registration_hint"
    assert result["start_line"] <= result["anchor"]["registration_line"] < result["anchor"]["line"]


def test_unresolved_python_wrapper_is_not_assumed_sdk_binding():
    source = "from local_wrapper import Server\nserver=Server()\n" + padded(
        "@server.call_tool()\nasync def handle_call_tool():\n    pass")
    result = choose(source)
    assert result["anchor"]["name"] == "handle_call_tool"
    assert "kind" not in result["anchor"]


@pytest.mark.parametrize("declaration", [
    "async fn execute_query<'a>(&'a self) {}",
    "pub(crate) async fn execute_query<T>(value: T) {}",
    "pub unsafe fn execute_query() {}",
])
def test_rust_fn_lifetimes_visibility_and_generics(declaration):
    result = choose(padded(declaration), "src/main.rs")
    assert result["method"] == "rs_lexical" and result["anchor"]["name"] == "execute_query"
    assert result["anchor"]["end_line"] is None


@pytest.mark.parametrize("attribute", [
    "#[tool]", "#[rmcp::tool]", '#[tool(\n name = "imap_list",\n description = "not a fn execute()"\n)]',
])
def test_rust_tool_attribute_prioritized_and_its_context_is_in_window(attribute):
    result = choose(padded("fn execute() {}\n\n" + attribute + "\nasync fn list_accounts(&self) {}"), "src/server.rs")
    assert result["anchor"]["name"] == "list_accounts"
    assert result["anchor"]["kind"] == "tool_attribute_hint"
    assert result["start_line"] <= result["anchor"]["registration_line"] < result["anchor"]["line"]
    assert result["anchor"]["end_line"] is None and not result["full_callable_verified"]


def test_rust_same_line_attribute():
    result = choose(padded("#[tool] async fn list_accounts() {}"), "src/server.rs")
    assert result["anchor"]["kind"] == "tool_attribute_hint" and result["anchor"]["line"] == 101


@pytest.mark.parametrize("fake", [
    'let text = r#"\n#[tool]\nfn fake() {}\n"#;\n',
    'let text = br###"\n" still raw "\n#[tool]\nfn fake() {}\n"###;\n',
    '/* outer /* inner */\n#[tool]\nfn fake() {}\n*/\n',
    '// #[tool]\n// fn fake() {}\n',
])
def test_rust_raw_strings_and_nested_comments_do_not_create_handlers(fake):
    result = choose(padded(fake + "async fn handle() {}"), "src/server.rs")
    assert result["anchor"]["name"] == "handle" and result["candidate_count"] == 1
    assert "kind" not in result["anchor"]


def test_rust_tool_router_attribute_is_not_tool_registration():
    result = choose(padded("#[tool_router]\nfn execute() {}"), "src/server.rs")
    assert "kind" not in result["anchor"]


def test_rust_unrelated_statement_breaks_pending_attribute():
    result = choose(padded("#[tool]\nconst X: u8 = 1;\nfn execute() {}"), "src/server.rs")
    assert "kind" not in result["anchor"]


def test_rust_distant_attribute_is_not_carried_into_later_function():
    result = choose(padded("#[tool]\n" + "\n" * 30 + "fn execute() {}"), "src/server.rs")
    assert "kind" not in result["anchor"]


def test_framework_candidate_cap_still_limits_registration_scan():
    source = JS_IMPORT + JS_INSTANCE + "\n".join(f'server.tool("t{i}", {{}}, async () => {{}});'
                                                 for i in range(module.MAX_CANDIDATES + 1))
    result = choose(source, "index.ts")
    assert result["reason"] == "candidate_cap" and result["anchor"] is None


def test_sdk_binding_cap_prevents_unbounded_receiver_matching():
    source = JS_IMPORT + "\n".join(f'const s{i}=new McpServer({{}});' for i in range(33))
    result = choose(padded(source), "index.ts")
    assert result["reason"] == "framework_binding_cap"
    assert result["anchor"] is None and not result["candidate_scan_complete"]


def test_gs_uses_javascript_like_hint_without_execution_or_verified_language():
    result = choose(padded('throw new Error("NEVER EXECUTE");\nfunction handleUpdate(e) {\nreturn e;\n}'), 'Kode.gs')
    assert result['anchor']['name'] == 'handleUpdate' and result['start_line'] > 80
    assert result['method'] == 'js_lexical'
    assert result['language_hint'] == 'javascript_like_gs_unverified'
    assert result['semantic_relevance_verified'] is False


def test_gs_comment_and_string_declarations_are_not_execution_evidence():
    result = choose(padded('// function execute() {}\nconst fake = "function execute() {}";\nfunction helper() {}'), 'bot.gs')
    assert result['candidate_count'] == 1 and result['anchor']['name'] == 'helper'


@pytest.mark.parametrize('extension,lexer', [('mjs', 'js'), ('cjs', 'js'), ('mts', 'ts'), ('cts', 'ts')])
def test_javascript_module_extensions_use_existing_bounded_lexical_policy(extension, lexer):
    result = choose(padded('throw new Error("NEVER EXECUTE");\nexport async function handleUpdate(e) { return e; }'),
                    'genaisrc/main.genai.' + extension)
    assert result['anchor']['name'] == 'handleUpdate' and result['start_line'] > 80
    assert result['syntax_extension_alias'] == {'extension': extension, 'lexer': lexer}
    assert result['semantic_relevance_verified'] is False
