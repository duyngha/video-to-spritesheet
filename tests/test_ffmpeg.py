"""Tests for the ffmpeg wrappers.

The probe/extract tests need the ffmpeg binaries and a sample clip; they skip
cleanly when either is missing so the suite still runs on a bare machine. The clip
is not committed — generate it locally (see CONTRIBUTING.md) with::

    ffmpeg -f lavfi -i testsrc=size=320x240:rate=30 -t 2 tests/sample.mp4
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from videotosprite.core import ffmpeg

SAMPLE = Path(__file__).resolve().parent / "sample.mp4"
_HAVE_FFMPEG = not ffmpeg.missing_tools()
_needs_ffmpeg = pytest.mark.skipif(not _HAVE_FFMPEG, reason="ffmpeg/ffprobe not on PATH")
_needs_sample = pytest.mark.skipif(
    not SAMPLE.exists(), reason="tests/sample.mp4 missing — see CONTRIBUTING.md"
)


def _nothing_installed(monkeypatch, tmp_path):
    """Pretend the machine has no ffmpeg at all (empty PATH and empty search dirs)."""
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda n: None)
    monkeypatch.setattr(ffmpeg, "_EXTRA_DIRS", (str(tmp_path / "nowhere"),))
    monkeypatch.setattr(ffmpeg, "MANAGED_BIN_DIR", tmp_path / "managed")


def test_missing_tools_detects_absence(monkeypatch, tmp_path):
    _nothing_installed(monkeypatch, tmp_path)
    assert ffmpeg.missing_tools() == ["ffmpeg", "ffprobe"]


def test_missing_tools_empty_when_present(monkeypatch):
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda n: "/usr/bin/" + n)
    assert ffmpeg.missing_tools() == []


def test_find_falls_back_to_managed_dir(monkeypatch, tmp_path):
    """A .app launched from Finder has a bare PATH — our own copy must still be found."""
    _nothing_installed(monkeypatch, tmp_path)
    managed = tmp_path / "managed"
    managed.mkdir()
    binary = managed / "ffmpeg"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    assert ffmpeg.find("ffmpeg") == str(binary)
    assert ffmpeg.find("ffprobe") is None
    assert ffmpeg.missing_tools() == ["ffprobe"]


def test_find_ignores_non_executable(monkeypatch, tmp_path):
    _nothing_installed(monkeypatch, tmp_path)
    managed = tmp_path / "managed"
    managed.mkdir()
    (managed / "ffmpeg").write_text("not executable")
    assert ffmpeg.find("ffmpeg") is None


@_needs_ffmpeg
@_needs_sample
def test_probe_reads_metadata():
    info = ffmpeg.probe(SAMPLE)
    assert info.width > 0 and info.height > 0
    assert info.duration > 0 and info.fps > 0


@_needs_ffmpeg
@_needs_sample
def test_extract_frames_count_and_overwrite(tmp_path):
    out = tmp_path / "frames"
    first = ffmpeg.extract_frames(SAMPLE, out, 0.0, 2.0, 6.0, max_width=160)
    assert len(first) > 0
    assert len(first) == len(list(out.glob("frame_*.png")))

    # a shorter second pass must not leave stale frames behind
    second = ffmpeg.extract_frames(SAMPLE, out, 0.0, 1.0, 3.0, max_width=160)
    assert len(second) < len(first)
    assert len(second) == len(list(out.glob("frame_*.png")))
