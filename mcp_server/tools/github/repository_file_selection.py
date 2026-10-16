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
    "gemfile", "mix.exs", "pubspec.yaml",
)
CODE = frozenset({".py", ".go", ".rs", ".ts", ".tsx", ".js", ".jsx", ".java",
                  ".scala", ".c", ".cpp", ".h", ".cs", ".rb", ".ex", ".kt", ".swift", ".php"})
ENTRYPOINTS = ("engine", "server", "main", "app", "tools", "query_executor", "client")


def _role(path):
    parts = path.lower().split("/")
    name = parts[-1]
    if any(part in IGNORED for part in parts[:-1]):
        return None
    if re.fullmatch(r"readme(?:\.(?:md|rst|txt))?", name):
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
            not name.endswith((".d.ts", "_generated.go", ".g.cs"))):
        return "implementation"
    return None


def select_files(blobs, comparison=None):
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

    def rank(path):
        role = candidates[path]
        name = path.rsplit("/", 1)[-1].lower()
        stem = name.rsplit(".", 1)[0]
        common = (path.count("/"), path.lower(), path)
        if role == "implementation":
            return (0 if changed is not None and path in changed else 1,
                    0 if path in added else 1,
                    ENTRYPOINTS.index(stem) if stem in ENTRYPOINTS else len(ENTRYPOINTS), *common)
        if role == "runtime":
            return (path.count("/"), MANIFESTS.index(name), path.lower(), path)
        return common

    chosen = []
    used = set()

    def take(role):
        options = sorted((p for p, r in candidates.items() if r == role and p not in used), key=rank)
        if not options or len(chosen) == 6:
            return
        path = options[0]
        used.add(path)
        is_changed = path in changed if changed is not None else None
        chosen.append({
            "path": path, "role_hint": role,
            "reason": ("added_source_path_in_observed_comparison"
                       if role == "implementation" and path in added else
                       "changed_source_path_in_observed_comparison"
                       if role == "implementation" and is_changed else "conventional_" + role + "_path"),
            "changed_in_observed_comparison": is_changed,
            "start_line": None, "max_lines": 80, "range_strategy": "auto_callable_v1",
        })

    for role in ("overview", "runtime", "architecture", "license", "implementation", "implementation"):
        take(role)
    for role in ("deployment", "runtime", "implementation", "architecture", "overview"):
        while len(chosen) < 6:
            before = len(chosen)
            take(role)
            if len(chosen) == before:
                break
    return {
        "strategy": "auto_paths_v1", "selected": chosen, "max_files": 6,
        "regular_paths_considered": len(blobs), "recognized_candidates": len(candidates),
        "semantic_relevance_verified": False, "selection_exhaustive": False,
        "comparison_paths_used": len(changed) if changed is not None else None,
        "limitations": [
            "Names/paths are hints, not proof of file contents or implementation quality.",
            "At most80 LF-delimited lines per file; callable-name hints may miss relevant logic. Explicit ranges remain available.",
            "Vendored/generated/test/example path conventions are excluded heuristically, not perfectly.",
            "Monorepos, unconventional names and incomplete trees/comparisons can hide relevant files.",
            "Changed means observed three-dot path changes, not novelty, importance or correctness.",
        ],
    }