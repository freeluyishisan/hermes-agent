"""Smoke tests for the You.com research skill."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "research" / "youdotcom"
SKILL_MD = SKILL_DIR / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def frontmatter(skill_text: str) -> dict[str, object]:
    match = re.search(r"^---\n(.*?)\n---", skill_text, re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter"
    data: dict[str, object] = {}
    for line in match.group(1).splitlines():
        if ": " in line and not line.startswith("  "):
            key, value = line.split(": ", 1)
            data[key] = value
    return data


def test_skill_dir_exists() -> None:
    assert SKILL_DIR.is_dir()
    assert SKILL_MD.is_file()


def test_description_matches_skill_standard(frontmatter: dict[str, object]) -> None:
    description = str(frontmatter["description"])
    assert len(description) <= 60
    assert description.endswith(".")


def test_required_api_key_setup_metadata_present(skill_text: str) -> None:
    assert "required_environment_variables:" in skill_text
    assert "name: YDC_API_KEY" in skill_text
    assert "required_for: Research and Finance Research API access" in skill_text


def test_modern_section_order(skill_text: str) -> None:
    headings = [
        "# You.com Research Skill",
        "## When to Use",
        "## Prerequisites",
        "## How to Run",
        "## Quick Reference",
        "## Procedure",
        "## Pitfalls",
        "## Verification",
    ]
    positions = [skill_text.index(heading) for heading in headings]
    assert positions == sorted(positions)


def test_terminal_tool_is_the_direct_api_surface(skill_text: str) -> None:
    assert "Use the `terminal` tool for direct HTTPS requests" in skill_text
    assert "called directly via curl" not in skill_text
    assert "### Using via terminal" not in skill_text


def test_research_and_finance_endpoints_documented(skill_text: str) -> None:
    assert "https://api.you.com/v1/research" in skill_text
    assert "https://api.you.com/v1/finance_research" in skill_text
    assert "`output_schema`" in skill_text
    assert "`source_control`" in skill_text
