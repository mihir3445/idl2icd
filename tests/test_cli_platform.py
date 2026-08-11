from pathlib import Path

import idl2icd.cli as cli


def test_open_path_uses_platform_launcher(monkeypatch, tmp_path: Path):
    calls: list[list[str]] = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        return None

    monkeypatch.setattr(cli.sys, "platform", "linux", raising=False)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    target = tmp_path / "site"
    target.mkdir()
    assert cli._open_path(target) is True
    assert calls[0][0] == "xdg-open"
    assert calls[0][1] == str(target.resolve())
