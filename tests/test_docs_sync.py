"""The documentation site repeats a few sources of truth; these tests keep them identical."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "skills" / "setup" / "references" / "factory-toml.md"
DOCS_PAGE = ROOT / "docs" / "content" / "factory-toml.md"


def toml_block(text: str) -> str:
    match = re.search(r"```toml\n(.*?)```", text, re.DOTALL)
    assert match, "no toml block"
    return match.group(1)


def stack_table(text: str) -> str:
    rows = [line for line in text.splitlines() if line.startswith("| ")]
    assert rows, "no table"
    return "\n".join(rows)


def test_docs_schema_matches_the_setup_reference():
    assert toml_block(DOCS_PAGE.read_text()) == toml_block(REFERENCE.read_text())


def test_docs_stack_table_matches_the_setup_reference():
    assert stack_table(DOCS_PAGE.read_text()) == stack_table(REFERENCE.read_text())


def test_the_two_plugin_manifests_agree():
    claude = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    portable = json.loads((ROOT / "plugin.json").read_text())
    for key in (
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
    ):
        assert claude[key] == portable[key], key
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    (entry,) = marketplace["plugins"]
    assert entry["name"] == claude["name"]
    assert claude["description"].startswith(entry["description"].rstrip("."))


def stage_rows(text: str) -> list[str]:
    """The rows of the table whose header starts with `| # | Stage |`."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("| # | Stage |"))
    rows = []
    for line in lines[start + 2 :]:
        if not line.startswith("| "):
            break
        rows.append(line)
    assert rows
    return rows


def test_verify_stage_tables_agree():
    skill = (ROOT / "skills" / "verify" / "SKILL.md").read_text()
    page = (ROOT / "docs" / "content" / "verify-loop.md").read_text()
    assert stage_rows(skill) == stage_rows(page)
