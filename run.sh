#!/usr/bin/env bash
# cocos-mcp launcher — activates the bundled venv and starts the MCP server.
set -e
cd "$(dirname "$0")"
exec ./.venv/bin/python server.py
