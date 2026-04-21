"""MCP tool registration, grouped by concern.

server.py used to be a 1200-line wall of `@mcp.tool()` decorators.
Each submodule here exposes a `register(mcp: FastMCP) -> None` that
attaches its slice of tools to a given FastMCP instance. The single
entry-point `register_all(mcp)` wires them all up in one call.

Splitting on concern (not on type) keeps related tools — e.g. all the
UI components, all the build/preview tools — together so they're easier
to grep and to reason about.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from . import (
    build,
    core,
    interact,
    media,
    physics_3d,
    physics_ui,
    rendering_3d,
    scaffolds,
    scene,
    ui_patterns,
)

if TYPE_CHECKING:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

__all__ = [
    "build",
    "core",
    "interact",
    "media",
    "physics_3d",
    "physics_ui",
    "register_all",
    "rendering_3d",
    "scaffolds",
    "scene",
    "ui_patterns",
]


def register_all(mcp: FastMCP) -> None:
    """Attach every cocos-mcp tool to the given FastMCP instance."""
    core.register(mcp)
    scene.register(mcp)
    physics_ui.register(mcp)
    physics_3d.register(mcp)
    rendering_3d.register(mcp)
    media.register(mcp)
    ui_patterns.register(mcp)
    build.register(mcp)
    interact.register(mcp)
    scaffolds.register(mcp)
