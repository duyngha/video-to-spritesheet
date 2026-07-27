"""Thin wrappers around the native ffmpeg / ffprobe binaries.

We shell out to ffmpeg instead of decoding in Python because it is fast, frame
accurate and cheap to keep out of the app bundle. The binaries are not embedded:
they come from the system (Homebrew, MacPorts, …) or, when nothing is installed,
from :mod:`videotosprite.core.ffmpeg_setup`, which downloads them into
``MANAGED_BIN_DIR`` on demand.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

TOOLS = ("ffmpeg", "ffprobe")

#: Where our own download of the binaries lives (see ``ffmpeg_setup.install``).
MANAGED_BIN_DIR = Path.home() / ".videotosprite" / "bin"

# A .app launched from Finder inherits a bare PATH (/usr/bin:/bin:/usr/sbin:/sbin),
# so a Homebrew/MacPorts ffmpeg is invisible to shutil.which — look there directly.
_EXTRA_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin", "/usr/bin")


class FFmpegNotFound(RuntimeError):
    pass


def find(name: str) -> Optional[str]:
    """Return the path to ``name`` (ffmpeg/ffprobe), or None if it isn't installed.

    PATH wins, then the usual system install dirs, then our managed copy.
    """
    hit = shutil.which(name)
    if hit:
        return hit
    for directory in (*_EXTRA_DIRS, str(MANAGED_BIN_DIR)):
        cand = Path(directory) / name
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return None


def _bin(name: str) -> str:
    path = find(name)
    if not path:
        raise FFmpegNotFound(
            f"'{name}' não encontrado. Instale o ffmpeg (brew install ffmpeg) ou use "
            f"o botão 'Instalar ffmpeg' do app."
        )
    return path


def missing_tools() -> list[str]:
    """Return which of ffmpeg/ffprobe are NOT installed (empty list = all present)."""
    return [name for name in TOOLS if find(name) is None]


@dataclass
class VideoInfo:
    path: Path
    width: int
    height: int
    duration: float          # seconds
    fps: float               # source frame rate
    nb_frames: Optional[int] # may be None if container doesn't report it

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 1.0


def probe(path: str | Path) -> VideoInfo:
    """Read basic metadata of a video using ffprobe."""
    path = Path(path)
    cmd = [
        _bin("ffprobe"), "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate,nb_frames,duration:format=duration",
        "-of", "json", str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    data = json.loads(out)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}

    def _rate(value: str | None) -> float:
        if not value or value == "0/0":
            return 0.0
        if "/" in value:
            num, den = value.split("/")
            den_f = float(den)
            return float(num) / den_f if den_f else 0.0
        return float(value)

    fps = _rate(stream.get("avg_frame_rate")) or _rate(stream.get("r_frame_rate")) or 30.0
    duration = float(stream.get("duration") or fmt.get("duration") or 0.0)
    nb_frames = stream.get("nb_frames")
    return VideoInfo(
        path=path,
        width=int(stream.get("width") or 0),
        height=int(stream.get("height") or 0),
        duration=duration,
        fps=fps,
        nb_frames=int(nb_frames) if nb_frames and str(nb_frames).isdigit() else None,
    )


def grab_frame(path: str | Path, t: float, max_width: int | None = None,
               src_size: tuple[int, int] | None = None) -> np.ndarray:
    """Decode a single RGB frame at time ``t`` (seconds). Returns HxWx3 uint8.

    Pass ``src_size`` (width, height) when known to avoid a redundant ffprobe on
    every call (the live scrubber relies on this).
    """
    vf = []
    if max_width:
        vf.append(f"scale={max_width}:-2:flags=area")
    cmd = [
        _bin("ffmpeg"), "-v", "error",
        "-ss", f"{max(t, 0):.3f}", "-i", str(path),
        "-frames:v", "1",
    ]
    if vf:
        cmd += ["-vf", ",".join(vf)]
    cmd += ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    raw = proc.stdout
    # Recover the real dimensions ffmpeg produced (scale may round height).
    w, h = _output_size(path, max_width, src_size)
    expected = w * h * 3
    if len(raw) < expected:
        raise RuntimeError("ffmpeg retornou menos bytes que o esperado ao capturar o frame.")
    return np.frombuffer(raw[:expected], dtype=np.uint8).reshape(h, w, 3).copy()


def _output_size(path: str | Path, max_width: int | None,
                 src_size: tuple[int, int] | None) -> tuple[int, int]:
    if src_size is not None:
        w, h = src_size
    else:
        info = probe(path)
        w, h = info.width, info.height
    if max_width and w > max_width:
        new_w = max_width
        new_h = int(round(h * max_width / w))
        new_h -= new_h % 2  # scale=-2 keeps height even
        return new_w, max(new_h, 2)
    return w, h


def extract_frames(
    path: str | Path,
    out_dir: str | Path,
    start: float,
    end: float,
    fps: float,
    max_width: int | None = None,
    progress: Optional[Callable[[int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> list[Path]:
    """Extract frames between ``start`` and ``end`` seconds at ``fps``.

    Frames are written as ``frame_00001.png`` into ``out_dir`` and the sorted
    list of created paths is returned.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Clear frames from a previous extraction so stale (higher-numbered) frames
    # don't linger when the new run produces fewer frames.
    for old in out_dir.glob("frame_*.png"):
        old.unlink()
    duration = max(end - start, 0.0)

    vf = [f"fps={fps}"]
    if max_width:
        vf.append(f"scale='min({max_width},iw)':-2:flags=area")

    cmd = [
        _bin("ffmpeg"), "-v", "error", "-stats", "-y",
        "-ss", f"{start:.3f}", "-i", str(path),
        "-t", f"{duration:.3f}",
        "-vf", ",".join(vf),
        "-vsync", "0", "-start_number", "1",
        str(out_dir / "frame_%05d.png"),
    ]
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    # ffmpeg prints "frame=  N" progress lines on stderr (-stats).
    assert proc.stderr is not None
    for line in proc.stderr:
        if should_cancel and should_cancel():
            proc.terminate()
            break
        if progress and "frame=" in line:
            try:
                n = int(line.split("frame=")[1].split()[0])
                progress(n)
            except (ValueError, IndexError):
                pass
    proc.wait()
    if proc.returncode not in (0, None) and not (should_cancel and should_cancel()):
        raise RuntimeError(f"ffmpeg falhou (código {proc.returncode}).")
    return sorted(out_dir.glob("frame_*.png"))
