#!/usr/bin/env python3
"""cocos-mcp — headless Cocos Creator MCP server.

Lets Claude (or any MCP client) build a complete Cocos Creator 3.8 game
**without ever opening the editor GUI**. All operations are direct file
I/O on the project's JSON / TS / PNG / meta files, plus invoking
`CocosCreator --build` headlessly.

Companion to but independent from DaxianLee/cocos-mcp-server, which is a
Cocos Creator editor plugin (requires the editor to be running). Use this
one for CI / autonomous AI development; use the editor plugin when the
human is actively working inside the editor.

Tool naming follows DaxianLee's verb-first style for cross-tool consistency.

This file is intentionally thin: every `@mcp.tool()` lives under
`cocos/tools/<concern>.py`. Add new tools by editing one of those modules
and (if creating a new module) adding an entry to `tools.register_all`.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the local `cocos` package importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP

from cocos import tools

mcp = FastMCP("cocos-mcp")
tools.register_all(mcp)


def _registered_tool_count() -> int:
    """Best-effort introspection of how many @mcp.tool() are registered.

    FastMCP's internal layout has changed across versions, so we probe a
    few attribute names; falls back to 0 (and prints "?") if none match.
    """
    for attr in ("_tools", "tools", "_tool_handlers"):
        bag = getattr(mcp, attr, None)
        if isinstance(bag, dict):
            return len(bag)
    mgr = getattr(mcp, "_tool_manager", None)
    if mgr is not None:
        for attr in ("_tools", "tools"):
            bag = getattr(mgr, attr, None)
            if isinstance(bag, dict):
                return len(bag)
    return 0


if __name__ == "__main__":
    n = _registered_tool_count()
    print(f"cocos-mcp: {n or '?'} tools registered, starting on stdio…", file=sys.stderr)
    mcp.run()
