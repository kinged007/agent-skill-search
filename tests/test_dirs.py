"""`skill-search dirs`: show active dirs, persist/reset a custom default."""

import json
import os

import skill_search.cli as cli
import skill_search.install as inst
from skill_search.engine import config_path, read_config_default


def _fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.delenv("SKILL_CATALOG_DIRS", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _ns(**kw):
    base = {"dirs": None, "include_known": None, "set": None, "reset": False}
    base.update(kw)
    return type("NS", (), base)()


def test_dirs_shows_builtin_default(tmp_path, monkeypatch, capsys):
    _fake_home(tmp_path, monkeypatch)
    cli.cmd_dirs(_ns())
    out = capsys.readouterr().out
    assert "~/.agents/skills-catalog" in out or ".agents/skills-catalog" in out
    assert "(builtin)" in out


def test_dirs_set_persists_and_reset_restores(tmp_path, monkeypatch, capsys):
    home = _fake_home(tmp_path, monkeypatch)
    target = home / "my-skills"

    cli.cmd_dirs(_ns(set=str(target)))
    assert target.is_dir()
    assert json.loads((home / ".config" / "skill-search" / "config.json").read_text()) == {
        "default_dir": str(target)
    }
    assert cli.get_default_dirs() == [str(target)]

    # install honors the persisted default too
    monkeypatch.setattr(inst.shutil, "which", lambda name: None)
    assert inst.resolve_catalog_dirs(None) == [str(target)]

    cli.cmd_dirs(_ns(reset=True))
    assert "reset" in capsys.readouterr().out.lower()
    assert read_config_default() is None
    assert not os.path.exists(config_path())
