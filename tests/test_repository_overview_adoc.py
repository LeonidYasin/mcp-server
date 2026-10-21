"""Offline regression for the Decidim README.adoc discovery case."""
import pytest

from mcp_server.tools.github.repository_file_selection import select_files


@pytest.mark.parametrize("path", [
    "README.adoc", "ReadMe.ADOC", "docs/README.adoc",
    "README", "README.md", "README.rst", "README.txt",
])
def test_readme_formats_are_overview_not_source(path):
    # select_files consumes verified regular path keys; validation is upstream.
    blobs = {path: "a" * 40, "src/main.py": "b" * 40}
    result = select_files(blobs)
    overview = next(item for item in result["selected"] if item["path"] == path)
    assert overview["role_hint"] == "overview"
    assert overview["reason"] == "conventional_overview_path"
    assert result["selected"][0]["path"] == path
    assert result["semantic_relevance_verified"] is False
    assert result["selection_exhaustive"] is False
    assert len(result["selected"]) <= result["max_files"] == 6


@pytest.mark.parametrize("path", ["vendor/README.adoc", "tests/README.adoc"])
def test_asciidoc_does_not_bypass_ignored_directories(path):
    result = select_files({path: "a" * 40, "src/main.py": "b" * 40})
    assert path not in {item["path"] for item in result["selected"]}


def test_asciidoc_backup_is_not_a_readme():
    result = select_files({"README.adoc.bak": "a" * 40})
    assert result["selected"] == []
