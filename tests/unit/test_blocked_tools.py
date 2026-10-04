"""
Filesystem tools must never be exposed by the remote server.

download_course_gpx accepts an arbitrary output path, so on the server a single
(possibly prompt-injected) call could overwrite the OAuth token store, the Garmin
token or the application code. These tests pin the hard block in _ToolFilter.
"""
import asyncio
from unittest.mock import Mock

import pytest
from mcp.server.fastmcp import FastMCP

import garmin_mcp
from garmin_mcp import BLOCKED_TOOLS, _ToolFilter

FILESYSTEM_TOOLS = {"download_activity_file", "download_course_gpx", "set_fit_download_dir", "upload_course"}


def _registered_tools(enabled=frozenset(), disabled=frozenset()):
    app = _ToolFilter(FastMCP("test"), set(enabled), set(disabled))
    for module in garmin_mcp._MODULES:
        module.configure(Mock())
        module.register_tools(app)
    return {t.name for t in asyncio.run(app.list_tools())}


def test_blocklist_covers_all_filesystem_tools():
    assert FILESYSTEM_TOOLS <= BLOCKED_TOOLS


def test_filesystem_tools_not_registered_by_default():
    tools = _registered_tools()
    assert not tools & FILESYSTEM_TOOLS
    assert "get_activities" in tools  # sanity: normal tools still register


def test_allowlist_cannot_reenable_filesystem_tools():
    tools = _registered_tools(enabled={"get_activities", *FILESYSTEM_TOOLS})
    assert tools == {"get_activities"}


@pytest.mark.parametrize("name", sorted(FILESYSTEM_TOOLS))
def test_blocked_regardless_of_case(name):
    app = _ToolFilter(FastMCP("test"), {name.upper()}, set())
    assert app._allowed(name.upper()) is False


def test_every_module_tool_with_a_path_parameter_is_blocked():
    """Guard for future upstream merges: new path-taking tools must be reviewed."""
    app = FastMCP("test")
    for module in garmin_mcp._MODULES:
        module.configure(Mock())
        module.register_tools(app)
    path_tools = {
        t.name for t in asyncio.run(app.list_tools())
        if any(k in p for p in (t.inputSchema.get("properties") or {}) for k in ("path", "dir", "file"))
    }
    assert path_tools <= BLOCKED_TOOLS, f"unreviewed filesystem tools: {sorted(path_tools - BLOCKED_TOOLS)}"
