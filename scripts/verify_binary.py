#!/usr/bin/env python3
"""对编出来的 cocos-mcp 二进制做启动 + MCP 握手 + 工具调用验证。

走完这 4 步就认为 binary 可以交付：
  1. 进程能启起来，stderr 打印 "cocos-mcp: N tools registered…"
  2. MCP `initialize` 正常返回 serverInfo
  3. `tools/list` 返回的工具数 ≥ 180（防未来新增工具时忘更新，硬下限）
  4. `tools/call` 调 cocos_new_uuid 返回合法 UUID

用法：
    python scripts/verify_binary.py dist/cocos-mcp-darwin-x64
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path


UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
MIN_TOOLS = 180


def main(binary: str) -> int:
    b = Path(binary).resolve()
    if not b.is_file():
        print(f"FAIL: {b} 不存在", file=sys.stderr)
        return 1

    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "verify", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "cocos_new_uuid", "arguments": {}}},
    ]
    payload = "\n".join(json.dumps(m) for m in msgs) + "\n"

    t0 = time.perf_counter()
    proc = subprocess.Popen(
        [str(b)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    # Write payload but keep stdin open — closing it too early causes onefile
    # bootloaders to signal EOF to the child before the last message is read
    # off the pipe, silently dropping the final response.
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
    proc.stdin.write(payload)
    proc.stdin.flush()

    # Hard-kill watchdog so a stuck proc.stdout.readline() can't hang forever.
    # Windows subprocess pipes are blocking and don't respect Python-level
    # deadlines; killing the child process is the reliable way to unblock
    # readline() across platforms. macOS onefile cold-start can take 30-60s
    # when Gatekeeper scans the freshly-extracted runtime, hence the generous
    # limits below.
    HARD_TIMEOUT = 180
    killer = threading.Timer(HARD_TIMEOUT, proc.kill)
    killer.daemon = True
    killer.start()

    # Read stdout line-by-line until we've collected responses for every id
    # with "id" in msgs (notifications have no id and produce no response).
    want_ids = {m["id"] for m in msgs if "id" in m}
    seen: dict[int, dict] = {}
    lines: list[str] = []
    deadline = time.perf_counter() + 150
    while seen.keys() != want_ids and time.perf_counter() < deadline:
        line = proc.stdout.readline()
        if not line:  # EOF / child killed by watchdog / pipe closed
            break
        lines.append(line)
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" in obj:
            seen[obj["id"]] = obj
    killer.cancel()
    proc.terminate()
    try:
        stderr = proc.stderr.read()
    except Exception:
        stderr = ""
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    stdout = "".join(lines)
    elapsed = time.perf_counter() - t0

    # Step 1 — startup banner
    if "tools registered" not in stderr:
        print("FAIL [1/4]: 没看到启动 banner", file=sys.stderr)
        print("stderr:", stderr[:500], file=sys.stderr)
        return 3
    print(f"OK   [1/4] 启动 banner: {stderr.splitlines()[0]}")

    responses = seen

    # Step 2 — initialize
    init = responses.get(1, {})
    server_name = init.get("result", {}).get("serverInfo", {}).get("name")
    if server_name != "cocos-mcp":
        print(f"FAIL [2/4]: initialize 返回 serverInfo.name={server_name!r}", file=sys.stderr)
        return 4
    print(f"OK   [2/4] initialize → serverInfo.name='{server_name}'")

    # Step 3 — tools/list
    list_res = responses.get(2, {}).get("result", {})
    tools = list_res.get("tools", [])
    if len(tools) < MIN_TOOLS:
        print(f"FAIL [3/4]: tools/list 返回 {len(tools)} < {MIN_TOOLS}", file=sys.stderr)
        return 5
    print(f"OK   [3/4] tools/list → {len(tools)} tools registered")

    # Step 4 — cocos_new_uuid
    call_res = responses.get(3, {}).get("result", {})
    content = call_res.get("content", [])
    uuid_txt = content[0].get("text", "").strip() if content else ""
    if not UUID_RE.match(uuid_txt):
        print(f"FAIL [4/4]: cocos_new_uuid 返回非 UUID: {uuid_txt!r}", file=sys.stderr)
        return 6
    print(f"OK   [4/4] cocos_new_uuid → {uuid_txt}")

    print(f"\nALL PASS ({elapsed:.2f}s, binary {b.stat().st_size // (1024*1024)} MB)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"用法: {sys.argv[0]} <binary-path>", file=sys.stderr)
        sys.exit(99)
    sys.exit(main(sys.argv[1]))
