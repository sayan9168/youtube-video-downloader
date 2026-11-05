"""The Cloudflare Pages build must keep producing a complete static site."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_build_pages_outputs_static_site(tmp_path):
    out = tmp_path / "dist"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_pages.py"),
            "--api-base",
            "https://api.example.com/",
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, result.stderr

    index = (out / "index.html").read_text(encoding="utf-8")
    assert "settingsDialog" in index
    assert "/config.js" in index
    assert "{{ version }}" not in index

    config = (out / "config.js").read_text(encoding="utf-8")
    assert '"https://api.example.com"' in config  # trailing slash trimmed

    for relative in (
        "static/js/app.js",
        "static/css/app.css",
        "static/icons/icon-192.png",
        "sw.js",
        "manifest.webmanifest",
        "favicon.ico",
        "_headers",
        "_redirects",
    ):
        assert (out / relative).is_file(), relative

    redirects = (out / "_redirects").read_text(encoding="utf-8")
    assert "/index.html" in redirects


def _load_build_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_pages", ROOT / "scripts" / "build_pages.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_render_without_jinja(tmp_path, monkeypatch):
    """The Pages build image may not have jinja2: placeholders must still render."""
    module = _load_build_module()
    monkeypatch.setattr(module, "Environment", None)
    module._render_index(tmp_path)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "{{" not in html and "{%" not in html
    assert "/config.js" in html
