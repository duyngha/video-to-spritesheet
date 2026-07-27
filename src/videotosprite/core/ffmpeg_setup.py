"""On-demand install of the ffmpeg / ffprobe binaries (macOS).

The .app deliberately does **not** embed them (~90 MB each, plus codesigning and
licensing baggage). When the app starts and the tools are missing, it offers to
fetch static, ad-hoc-signed builds and drop them in
:data:`videotosprite.core.ffmpeg.MANAGED_BIN_DIR`, which ``core.ffmpeg`` searches
after PATH — so a Homebrew install, if there is one, keeps winning.
"""
from __future__ import annotations

import gzip
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from .ffmpeg import MANAGED_BIN_DIR, TOOLS, find

# Static macOS builds (arm64 + x86_64), ad-hoc signed so Gatekeeper lets them run.
RELEASE = "b6.1.1"
_BASE_URL = f"https://github.com/eugeneware/ffmpeg-static/releases/download/{RELEASE}"

#: Rough compressed size of each download, for the progress bar.
_APPROX_BYTES = 20_000_000

ProgressFn = Callable[[str, float], None]


class InstallError(RuntimeError):
    pass


def is_supported() -> bool:
    """The automatic download only covers macOS; elsewhere, use the package manager."""
    return platform.system() == "Darwin"


def download_url(tool: str) -> str:
    arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "x64"
    return f"{_BASE_URL}/{tool}-darwin-{arch}.gz"


def install(progress: Optional[ProgressFn] = None,
            should_cancel: Optional[Callable[[], bool]] = None) -> list[Path]:
    """Download the missing tools into ``MANAGED_BIN_DIR`` and return their paths.

    ``progress`` is called as ``(tool_name, fraction_0_to_1)`` while downloading.
    Already-installed tools are skipped. Raises :class:`InstallError` on failure.
    """
    if not is_supported():
        raise InstallError(
            f"Instalação automática só é suportada no macOS ({platform.system()} "
            f"detectado). Instale o ffmpeg pelo gerenciador de pacotes do sistema.")

    todo = [name for name in TOOLS if find(name) is None]
    installed: list[Path] = []
    MANAGED_BIN_DIR.mkdir(parents=True, exist_ok=True)

    for i, tool in enumerate(todo):
        def report(frac: float, tool=tool, i=i):
            if progress:
                progress(tool, (i + frac) / len(todo))

        dest = MANAGED_BIN_DIR / tool
        _download_gz(download_url(tool), dest, report, should_cancel)
        if should_cancel and should_cancel():
            dest.unlink(missing_ok=True)
            return installed
        _verify(dest)
        installed.append(dest)

    if progress:
        progress(todo[-1] if todo else "ffmpeg", 1.0)
    return installed


def _download_gz(url: str, dest: Path, report: Callable[[float], None],
                 should_cancel: Optional[Callable[[], bool]]) -> None:
    """Stream a .gz binary to ``dest`` (atomically, executable)."""
    fd, name = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}-")
    os.close(fd)
    tmp = Path(name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VideoToSprite"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length") or _APPROX_BYTES)
            counter = _CountingReader(resp)
            decomp = gzip.GzipFile(fileobj=counter)
            with tmp.open("wb") as out:
                while True:
                    if should_cancel and should_cancel():
                        return
                    chunk = decomp.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    report(min(counter.count / total, 0.99))
        tmp.chmod(0o755)
        tmp.replace(dest)
        _clear_quarantine(dest)
        report(1.0)
    except OSError as ex:
        raise InstallError(f"Falha ao baixar {dest.name}: {ex}") from ex
    finally:
        tmp.unlink(missing_ok=True)


class _CountingReader:
    """File-ish wrapper that tracks how many compressed bytes came off the socket."""

    def __init__(self, fileobj):
        self._f = fileobj
        self.count = 0

    def read(self, size: int = -1) -> bytes:
        data = self._f.read(size)
        self.count += len(data)
        return data


def _clear_quarantine(path: Path) -> None:
    xattr = shutil.which("xattr") or "/usr/bin/xattr"
    try:
        subprocess.run([xattr, "-d", "com.apple.quarantine", str(path)],
                       capture_output=True, check=False)
    except OSError:
        pass  # no xattr on this system: urllib downloads aren't quarantined anyway


def _verify(path: Path) -> None:
    """Make sure the freshly downloaded binary actually runs on this machine."""
    try:
        proc = subprocess.run([str(path), "-version"], capture_output=True, text=True,
                              timeout=30)
    except OSError as ex:
        path.unlink(missing_ok=True)
        raise InstallError(f"{path.name} baixado não executa: {ex}") from ex
    if proc.returncode != 0:
        path.unlink(missing_ok=True)
        raise InstallError(
            f"{path.name} baixado não executa (código {proc.returncode}). "
            f"Tente instalar com: brew install ffmpeg")
