"""Deterministic path heuristics, not semantic relevance or a quality score."""
import re

IGNORED = frozenset({
    "node_modules", "vendor", "third_party", "third-party", "generated", "dist", "build",
    ".git", "__pycache__", ".venv", "venv", "target", "coverage", "fixtures", "testdata",
    "tests", "test", "__tests__", "examples", "example", "samples",
})
MANIFESTS = (
    "pyproject.toml", "go.mod", "cargo.toml", "package.json", "pom.xml",
    "build.gradle.kts", "build.gradle", "requirements.txt", "composer.json",
    "gemfile", "mix.exs", "pubspec.yaml", "action.yml", "action.yaml",
)
CODE = frozenset({".py", ".go", ".rs", ".ts", ".tsx", ".js", ".jsx", ".java",
                  ".mjs", ".cjs", ".mts", ".cts",
                  ".scala", ".gs", ".sql", ".c", ".cpp", ".h", ".cs", ".rb", ".ex", ".kt", ".swift", ".php"})
FOCUS_PATH_TERMS_SCHEMA = {
    "type": "array", "minItems": 1, "maxItems": 8,
    "description": "Optional auto-selection only: explicit ASCII path-token prefixes (3–32 alphanumerics), "
                   "e.g. match/embed/calculate. Path hints, not semantic relevance or file-content search; no extra GETs.",
    "items": {"type": "string", "minLength": 3, "maxLength": 32, "pattern": "^[A-Za-z0-9]{3,32}$"},
}
ENTRYPOINTS = ("engine", "server", "main", "app", "tools", "query_executor", "client")
IMPLEMENTATION_ROLES = ("dispatch", "bootstrap", "authorization", "domain", "configuration", "other")
DOMAIN_DIRS = frozenset({"servers", "integrations", "connectors", "adapters", "providers", "plugins"})
AUTH_WORDS = frozenset({"auth", "authentication", "authorization", "oauth", "permissions",
                        "credentials", "credential", "security"})
IDENTITY_STOP = frozenset({"mcp", "server", "servers", "sdk", "api", "app", "demo",
                           "org", "team", "company", "src", "lib"})

def normalize_focus_path_terms(value):
    if (not isinstance(value, list) or not 1 <= len(value) <= 8 or
            any(not isinstance(term, str) or not re.fullmatch(r"[A-Za-z0-9]{3,32}", term)
                for term in value)):
        return None
    terms = [term.lower() for term in value]
    return terms if len(set(terms)) == len(terms) else None


def _focus_matches(path, terms):
    words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", path)
    tokens = re.split(r"[^a-z0-9]+", words.lower())
    return [term for term in terms if any(token.startswith(term) for token in tokens)]


def _identity_tokens(identity):
    if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", identity):
        return set()
    if any(part in (".", "..") for part in identity.split("/")):
        return set()
    return {part for part in re.split(r"[/_.-]+", identity.lower())
            if len(part) >= 3 and part not in IDENTITY_STOP}


def _implementation_hint(path, tokens):
    parts = path.lower().split("/")
    stem = parts[-1].rsplit(".", 1)[0]
    words = set(re.split(r"[_-]+", stem)) | set(parts[:-1])
    camel_stem = re.sub(r"([a-z])([A-Z])", r"\1_\2", path.rsplit("/", 1)[-1].rsplit(".", 1)[0])
    words.update(re.split(r"[_-]+", camel_stem.lower()))
    if words & AUTH_WORDS:
        return "authorization", "authorization", False
    for index, part in enumerate(parts[:-2]):
        if part in DOMAIN_DIRS:
            group = parts[index + 1]
            return "domain", group, group in tokens
    if stem in ("engine", "server", "router", "dispatcher", "handler", "handlers", "tools", "query_executor"):
        # Distinguish vendor/module namespaces without claiming their semantics.
        group = parts[1] if len(parts) > 2 and parts[0] in ("internal", "cmd", "pkg") else "/".join(parts[:-1])
        return "dispatch", group or "root", False
    if stem in ("main", "app", "index"):
        return "bootstrap", "bootstrap", False
    if stem in ("config", "configuration", "settings"):
        return "configuration", "configuration", False
    return "other", "/".join(parts[:-1]) or "root", False


def _role(path):
    parts = path.lower().split("/")
    name = parts[-1]
    if any(part in IGNORED for part in parts[:-1]):
        return None
    if re.fullmatch(r"readme(?:\.(?:md|rst|txt|adoc))?", name):
        return "overview"
    if name in MANIFESTS:
        return "runtime"
    if re.fullmatch(r"(?:license|licence|copying)(?:\.(?:md|txt|rst))?", name):
        return "license"
    if name in ("architecture.md", "architecture.rst", "design.md", "overview.md"):
        return "architecture"
    if name in ("dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        return "deployment"
    if (any(name.endswith(ext) for ext in CODE) and
            not re.search(r"(^test[_-]|[_-]test\.|\.test\.|\.spec\.|^conftest\.|^__(?:init|main)__\.|\.min\.)", name) and
            not name.endswith((".d.ts", ".d.mts", ".d.cts", "_generated.go", ".g.cs"))):
        return "implementation"
    return None


def select_files(blobs, comparison=None, repository_identity=None, focus_path_terms=None):
    """Return up to six diverse, explained choices from verified regular paths.

    Caller validates paths/blob modes and excludes known oversized files first.
    Comparison is deliberately limited to the displayed, provider-observed file rows.
    """
    changed = None if comparison is None else {
        row["path"] for row in comparison["files"] if row["status"] not in ("removed", "unchanged")
    }
    added = set() if comparison is None else {
        row["path"] for row in comparison["files"] if row["status"] == "added"
    }
    candidates = {}
    for path in blobs:
        role = _role(path)
        if role is not None:
            candidates[path] = role
    identity_tokens = _identity_tokens(repository_identity)
    focus = normalize_focus_path_terms(focus_path_terms) or []
    hints = {path: _implementation_hint(path, identity_tokens)
             for path, role in candidates.items() if role == "implementation"}
    focused = {path: _focus_matches(path, focus) for path in hints}

    def rank(path):
        role = candidates[path]
        name = path.rsplit("/", 1)[-1].lower()
        common = (path.count("/"), path.lower(), path)
        if role == "runtime":
            return (path.count("/"), MANIFESTS.index(name), path.lower(), path)
        return common

    chosen = []
    used = set()
    used_implementation_roles = set()
    used_implementation_groups = set()

    def source_rank(path):
        role, group, identity_match = hints[path]
        name = path.rsplit("/", 1)[-1].lower()
        stem = name.rsplit(".", 1)[0]
        change_class = 0 if path in added else 1 if changed is not None and path in changed else 2
        # Unknown roles do not displace a second recognized role just for diversity.
        diversity = 2 if role == "other" else int(role in used_implementation_roles)
        source_root = path.split("/", 1)[0].lower()
        return (change_class, 0 if focused[path] else 1,
                diversity, int((role, group) in used_implementation_groups),
                IMPLEMENTATION_ROLES.index(role), 0 if identity_match else 1,
                0 if source_root in ("src", "lib", "app", "internal", "cmd", "pkg") or "/" not in path else 1,
                0 if role == "authorization" and stem in ("auth", "factory", "authorization", "permissions") else 1,
                ENTRYPOINTS.index(stem) if stem in ENTRYPOINTS else len(ENTRYPOINTS),
                path.count("/"), path.lower(), path)

    def take(role):
        options = sorted((p for p, r in candidates.items() if r == role and p not in used),
                         key=source_rank if role == "implementation" else rank)
        if not options or len(chosen) == 6:
            return
        path = options[0]
        used.add(path)
        is_changed = path in changed if changed is not None else None
        item = {
            "path": path, "role_hint": role,
            "reason": ("added_source_path_in_observed_comparison"
                       if role == "implementation" and path in added else
                       "changed_source_path_in_observed_comparison"
                       if role == "implementation" and is_changed else
                       "caller_focus_path_prefix_hint" if role == "implementation" and focused[path] else
                       "identity_domain_path_hint" if role == "implementation" and hints[path][2] else
                       "diverse_implementation_role_hint" if role == "implementation" else
                       "conventional_" + role + "_path"),
            "changed_in_observed_comparison": is_changed,
            "start_line": None, "max_lines": 80, "range_strategy": "auto_callable_v2",
        }
        if role == "implementation":
            implementation_role, group, identity_match = hints[path]
            item.update(implementation_role_hint=implementation_role,
                        implementation_group_hint=group, identity_domain_match=identity_match,
                        focus_path_matches=focused[path])
            used_implementation_roles.add(implementation_role)
            used_implementation_groups.add((implementation_role, group))
        chosen.append(item)

    for role in ("overview", "runtime", "architecture", "license"):
        take(role)
    implementation_slots_after_documents = 6 - len(chosen)
    while len(chosen) < 6:
        before = len(chosen)
        take("implementation")
        if len(chosen) == before:
            break
    for role in ("deployment", "runtime", "architecture", "overview"):
        while len(chosen) < 6:
            before = len(chosen)
            take(role)
            if len(chosen) == before:
                break
    return {
        "strategy": "auto_paths_v2", "selected": chosen, "max_files": 6,
        "regular_paths_considered": len(blobs), "recognized_candidates": len(candidates),
        "semantic_relevance_verified": False, "selection_exhaustive": False,
        "comparison_paths_used": len(changed) if changed is not None else None,
        "implementation_role_coverage_hint": {
            "available": sorted({hint[0] for hint in hints.values()}),
            "selected": sorted(used_implementation_roles),
            "not_selected": sorted({hint[0] for hint in hints.values()} - used_implementation_roles),
            "coverage_verified": False,
        },
        "implementation_slots_after_documents": implementation_slots_after_documents,
        "identity_tokens_used": sorted(identity_tokens),
        "focus_path_terms_used": focus,
        "limitations": [
            "Names/paths are hints, not proof of file contents or implementation quality.",
            "Caller focus is a lexical path-token prefix preference after observed change class, not content/semantic search.",
            "At most80 LF-delimited lines per file; callable-name hints may miss relevant logic. Explicit ranges remain available.",
            "Vendored/generated/test/example path conventions are excluded heuristically, not perfectly.",
            "Monorepos, unconventional names and incomplete trees/comparisons can hide relevant files.",
            "Changed means observed three-dot path changes, not novelty, importance or correctness.",
            "Implementation roles/groups and owner/repo identity matches are path hints, not architecture/auth/domain verification.",
            "Documents consume slots first; not every implementation role can fit in six files. Unknown/factory/generated wiring can be missed.",
        ],
    }
