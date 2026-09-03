"""Installer tests against a fake home: JSON merge, backups, dry-run, argv generation."""

import json
import os
import subprocess
import sys

import pytest

import skill_search.install as inst
from skill_search.clients import resolve_config_path


def _fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("SKILL_CATALOG_DIRS", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _ns(client=(), all_=False, list_=False, dry_run=False, catalog=None):
    return type("NS", (), {
        "client": list(client), "all": all_, "list": list_,
        "dry_run": dry_run, "catalog": catalog,
    })()


def _fake_which(monkeypatch, mapping):
    monkeypatch.setattr(inst.shutil, "which", lambda name: mapping.get(name))


def test_gemini_install_merges_and_backs_up(tmp_path, monkeypatch, capsys):
    home = _fake_home(tmp_path, monkeypatch)
    cfg = home / ".gemini" / "settings.json"
    cfg.parent.mkdir()
    cfg.write_text(json.dumps({"theme": "dark", "model": "flash"}))
    _fake_which(monkeypatch, {"skill-search-mcp": "/fake/bin/skill-search-mcp"})
    cat = tmp_path / "catalog"

    inst.cmd_install(_ns(client=("gemini",), catalog=[str(cat)]))

    data = json.loads(cfg.read_text())
    assert data["theme"] == "dark" and data["model"] == "flash"
    entry = data["mcpServers"]["skill-search"]
    assert entry["command"] == "/fake/bin/skill-search-mcp"
    assert entry["args"] == []
    assert entry["env"]["SKILL_CATALOG_DIRS"] == str(cat.resolve())
    assert (home / ".gemini" / "settings.json.bak-1").exists()


def test_gemini_install_creates_missing_dirs(tmp_path, monkeypatch):
    home = _fake_home(tmp_path, monkeypatch)
    _fake_which(monkeypatch, {"skill-search-mcp": "/fake/bin/skill-search-mcp"})
    inst.cmd_install(_ns(client=("gemini",), catalog=[str(tmp_path / "c")]))
    data = json.loads((home / ".gemini" / "settings.json").read_text())
    assert "skill-search" in data["mcpServers"]


def test_install_is_idempotent(tmp_path, monkeypatch):
    home = _fake_home(tmp_path, monkeypatch)
    cfg = home / ".gemini" / "settings.json"
    cfg.parent.mkdir()
    _fake_which(monkeypatch, {"skill-search-mcp": "/fake/bin/skill-search-mcp"})
    cat = str(tmp_path / "c")

    inst.cmd_install(_ns(client=("gemini",), catalog=[cat]))
    first = cfg.read_text()
    inst.cmd_install(_ns(client=("gemini",), catalog=[cat]))

    assert cfg.read_text() == first
    assert not list(cfg.parent.glob("*.bak-*")), "no backup when nothing changed"


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    home = _fake_home(tmp_path, monkeypatch)
    _fake_which(monkeypatch, {"skill-search-mcp": "/fake/bin/skill-search-mcp"})
    inst.cmd_install(_ns(client=("gemini",), dry_run=True, catalog=[str(tmp_path / "c")]))
    assert not (home / ".gemini").exists()


def test_malformed_config_refuses_overwrite(tmp_path, monkeypatch):
    home = _fake_home(tmp_path, monkeypatch)
    cfg = home / ".gemini" / "settings.json"
    cfg.parent.mkdir()
    cfg.write_text("{not json")
    _fake_which(monkeypatch, {"skill-search-mcp": "/fake/bin/skill-search-mcp"})

    with pytest.raises(SystemExit):
        inst.cmd_install(_ns(client=("gemini",), catalog=[str(tmp_path / "c")]))
    assert cfg.read_text() == "{not json"
    assert not list(cfg.parent.glob("*.bak-*"))


def test_claude_code_argv(tmp_path, monkeypatch):
    runs = []
    monkeypatch.setattr(inst.subprocess, "run", lambda argv, **kw: runs.append(argv) or type("R", (), {"returncode": 0})())
    _fake_which(monkeypatch, {"claude": "/fake/claude", "skill-search-mcp": "/fake/bin/skill-search-mcp"})

    inst.cmd_install(_ns(client=("claude-code",), catalog=[str(tmp_path / "c")]))

    assert runs[0] == [
        "claude", "mcp", "add", "--scope", "user",
        "-e", f"SKILL_CATALOG_DIRS={tmp_path / 'c'}", "skill-search",
        "--", "/fake/bin/skill-search-mcp",
    ]


def test_command_backed_missing_binary_fails(tmp_path, monkeypatch):
    _fake_which(monkeypatch, {})  # nothing on PATH
    with pytest.raises(SystemExit):
        inst.cmd_install(_ns(client=("claude-code",), catalog=[str(tmp_path / "c")]))


def test_fallback_interpreter_command(tmp_path, monkeypatch):
    home = _fake_home(tmp_path, monkeypatch)
    _fake_which(monkeypatch, {})  # no skill-search-mcp script installed
    inst.cmd_install(_ns(client=("gemini",), catalog=[str(tmp_path / "c")]))
    entry = json.loads((home / ".gemini" / "settings.json").read_text())["mcpServers"]["skill-search"]
    assert entry["command"] == sys.executable
    assert entry["args"] == ["-m", "skill_search.server"]


def test_uninstall_removes_entry_keeps_siblings(tmp_path, monkeypatch):
    home = _fake_home(tmp_path, monkeypatch)
    cfg = home / ".gemini" / "settings.json"
    cfg.parent.mkdir()
    cfg.write_text(json.dumps({"theme": "dark", "mcpServers": {"other": {"command": "x"}}}))
    _fake_which(monkeypatch, {"skill-search-mcp": "/fake/bin/skill-search-mcp"})

    inst.cmd_install(_ns(client=("gemini",), catalog=[str(tmp_path / "c")]))
    inst.cmd_uninstall(_ns(client=("gemini",)))

    data = json.loads(cfg.read_text())
    assert data["theme"] == "dark"
    assert "skill-search" not in data["mcpServers"]
    assert "other" in data["mcpServers"]


def test_claude_desktop_appdata_path(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    import sys as _sys
    from skill_search import clients as cl
    from skill_search.clients import get_client
    c = get_client("claude-desktop")

    monkeypatch.setattr(_sys, "platform", "linux")
    assert resolve_config_path(c) is None  # no official Linux path

    monkeypatch.setattr(_sys, "platform", "darwin")
    (tmp_path / "Library" / "Application Support" / "Claude").mkdir(parents=True)
    assert resolve_config_path(c) == str(
        tmp_path / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")

    monkeypatch.setattr(_sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    assert resolve_config_path(c) == str(
        tmp_path / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json")


def test_pi_uses_project_root(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    _fake_which(monkeypatch, {"skill-search-mcp": "/fake/bin/skill-search-mcp"})
    inst.cmd_install(_ns(client=("pi",), catalog=[str(tmp_path / "c")]))
    data = json.loads((tmp_path / "mcp.json").read_text())
    assert "skill-search" in data["mcpServers"]


def test_chatgpt_prints_instructions_no_file(tmp_path, monkeypatch, capsys):
    _fake_home(tmp_path, monkeypatch)
    inst.cmd_install(_ns(client=("chatgpt",), catalog=[str(tmp_path / "c")]))
    out = capsys.readouterr().out
    assert "--http" in out and "https" in out.lower()
    assert list(tmp_path.iterdir()) == [p for p in tmp_path.iterdir() if p.name == "c"]


def test_install_list(tmp_path, monkeypatch, capsys):
    _fake_home(tmp_path, monkeypatch)
    inst.cmd_install(_ns(list_=True))
    out = capsys.readouterr().out
    for cid in ("claude-code", "codex", "gemini", "claude-desktop", "pi", "chatgpt", "openclaw", "hermes"):
        assert cid in out


def test_cli_wiring(tmp_path, monkeypatch, capsys):
    _fake_home(tmp_path, monkeypatch)
    from skill_search.cli import main
    monkeypatch.setattr(sys, "argv", ["skill-search", "install", "--list"])
    main()
    assert "claude-code" in capsys.readouterr().out
