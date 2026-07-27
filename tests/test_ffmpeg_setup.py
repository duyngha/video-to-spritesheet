"""Tests for the on-demand ffmpeg download.

Nothing here hits the network: the download is faked so we can check the plumbing
(which tools get fetched, where they land, permissions, error handling).
"""
from __future__ import annotations

import gzip
import io
import platform

import pytest

from videotosprite.core import ffmpeg, ffmpeg_setup


@pytest.fixture
def bin_dir(monkeypatch, tmp_path):
    """Point both the installer and the finder at a throw-away bin dir."""
    d = tmp_path / "bin"
    monkeypatch.setattr(ffmpeg_setup, "MANAGED_BIN_DIR", d)
    monkeypatch.setattr(ffmpeg, "MANAGED_BIN_DIR", d)
    monkeypatch.setattr(ffmpeg, "_EXTRA_DIRS", (str(tmp_path / "nowhere"),))
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda n: None)
    return d


class _FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _fake_download(monkeypatch, body: bytes = b"#!/bin/sh\nexit 0\n"):
    payload = gzip.compress(body)
    urls: list[str] = []

    def fake_urlopen(req, timeout=None):
        urls.append(req.full_url)
        return _FakeResponse(payload)

    monkeypatch.setattr(ffmpeg_setup.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(ffmpeg_setup, "_verify", lambda path: None)
    return urls


def test_download_url_matches_this_machine():
    url = ffmpeg_setup.download_url("ffprobe")
    arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "x64"
    assert url.endswith(f"ffprobe-darwin-{arch}.gz")


def test_install_writes_both_executables(monkeypatch, bin_dir):
    urls = _fake_download(monkeypatch)
    progress: list[tuple[str, float]] = []

    installed = ffmpeg_setup.install(progress=lambda tool, f: progress.append((tool, f)))

    assert [p.name for p in installed] == ["ffmpeg", "ffprobe"]
    assert len(urls) == 2
    for path in installed:
        assert path.parent == bin_dir
        assert path.stat().st_mode & 0o111  # executable
    assert progress[-1][1] == 1.0


def test_install_skips_already_present_tools(monkeypatch, bin_dir):
    urls = _fake_download(monkeypatch)
    monkeypatch.setattr(ffmpeg.shutil, "which",
                        lambda n: "/usr/bin/ffmpeg" if n == "ffmpeg" else None)

    installed = ffmpeg_setup.install()

    assert [p.name for p in installed] == ["ffprobe"]
    assert len(urls) == 1


def test_install_reports_network_failure(monkeypatch, bin_dir):
    def boom(req, timeout=None):
        raise OSError("no route to host")

    monkeypatch.setattr(ffmpeg_setup.urllib.request, "urlopen", boom)
    with pytest.raises(ffmpeg_setup.InstallError, match="Falha ao baixar"):
        ffmpeg_setup.install()
    assert not list(bin_dir.glob("*"))


def test_install_refuses_outside_macos(monkeypatch, bin_dir):
    monkeypatch.setattr(ffmpeg_setup.platform, "system", lambda: "Linux")
    with pytest.raises(ffmpeg_setup.InstallError, match="macOS"):
        ffmpeg_setup.install()
