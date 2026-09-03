"""End-to-end smoke tests: stdio JSON-RPC exchange and streamable-HTTP initialize."""

import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
CATALOG = REPO / "test-catalog"


def _env():
    return {**os.environ, "SKILL_CATALOG_DIRS": str(CATALOG), "PYTHONPATH": str(REPO)}


def _rpc(proc, id_, method, params=None):
    msg = {"jsonrpc": "2.0", "id": id_, "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    assert line, f"no response for {method}: {proc.stderr.read()}"
    return json.loads(line)


def _notify(proc, method, params=None):
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def test_stdio_tools_roundtrip():
    proc = subprocess.Popen(
        [sys.executable, "-m", "skill_search.server"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=_env(),
    )
    try:
        r = _rpc(proc, 1, "initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "0"},
        })
        info = r["result"]["serverInfo"]
        assert info["name"] == "skill-search"
        assert info["version"], "serverInfo.version must not be empty"

        _notify(proc, "notifications/initialized")

        r = _rpc(proc, 2, "tools/list")
        names = {t["name"] for t in r["result"]["tools"]}
        assert names == {"skill_search", "skill_view", "skill_list"}

        r = _rpc(proc, 3, "tools/call", {
            "name": "skill_search",
            "arguments": {"query": "react"},
        })
        assert not r["result"]["isError"]
        assert "react-perf" in r["result"]["content"][0]["text"]
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_http_initialize():
    import uvicorn

    os.environ["SKILL_CATALOG_DIRS"] = str(CATALOG)
    from skill_search import server as srv

    mcp_app = srv.app.streamable_http_app(json_response=True, stateless_http=True, host="127.0.0.1")
    config = uvicorn.Config(mcp_app, host="127.0.0.1", port=0, log_level="error")
    u = uvicorn.Server(config)
    t = threading.Thread(target=u.run, daemon=True)
    t.start()
    while not u.started:
        time.sleep(0.05)
    port = u.servers[0].sockets[0].getsockname()[1]
    url = f"http://127.0.0.1:{port}/mcp"

    def post(payload):
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            assert resp.status == 200
            return json.loads(resp.read())

    try:
        data = post({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"},
            },
        })
        assert data["result"]["serverInfo"]["name"] == "skill-search"
        assert data["result"]["serverInfo"]["version"]

        # Stateless mode: every POST is independent, no session header needed.
        data = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in data["result"]["tools"]}
        assert names == {"skill_search", "skill_view", "skill_list"}
    finally:
        u.should_exit = True
        t.join(timeout=5)
