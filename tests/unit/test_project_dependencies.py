"""Project metadata regression tests."""

import re
from pathlib import Path


def test_project_caps_mcp_to_v1_series() -> None:
    """The project must stay on the MCP v1 series (2.x renames mcp.server.fastmcp)."""
    repo_root = Path(__file__).resolve().parents[2]
    pyproject_text = (repo_root / "pyproject.toml").read_text()

    pinned_v1 = re.search(r'"mcp==1\.\d+\.\d+"', pyproject_text)
    capped_v1 = re.search(r'"mcp>=1\.[\d.]+,\s*<2(\.0\.0)?"', pyproject_text)
    assert pinned_v1 or capped_v1
