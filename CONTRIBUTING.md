# Contributing to VideoToSprite

Thanks for taking a look. This is a small project, so the process is light: open an
issue for anything non-trivial, then send a PR. Bug reports with a video that
reproduces the problem (or its resolution / fps / codec) are especially welcome.

By contributing you agree that your contribution is licensed under the project's
[Apache-2.0 licence](LICENSE), and to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Setting up

```bash
./run.sh                                     # creates .venv (python3.12) and launches the app
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

`run.sh` does the venv bootstrap for you. To do it by hand:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
PYTHONPATH=src .venv/bin/python -m videotosprite
```

You also need **ffmpeg** and **ffprobe** on your `PATH` (`brew install ffmpeg`), or
use the in-app **Install ffmpeg** button — but note that the in-app installer is
**macOS-only** today ([`core/ffmpeg_setup.py`](src/videotosprite/core/ffmpeg_setup.py)).

## Running the tests

```bash
.venv/bin/python -m pytest
```

The suite is headless and runs in well under a second. Two ffmpeg integration tests
need a sample clip that is **not committed** — generate one and they light up:

```bash
ffmpeg -f lavfi -i testsrc=size=320x240:rate=30 -t 2 tests/sample.mp4
```

With the clip present you should see `49 passed`; without it, `47 passed, 2 skipped`.
`tests/sample.mp4` is gitignored — please don't commit media.

New logic in `core/` should come with a unit test. For UI handlers, use the mock
`Page` in [`tests/conftest.py`](tests/conftest.py) —
[`tests/test_ui.py`](tests/test_ui.py) is a good template, and shows how crop
mapping, frame selection and dialogs are all tested without a display.

## Things that will surprise you

Three project-specific rules. Getting them wrong is the usual cause of a confusing
failure.

### 1. The UI is authored in Portuguese and translated at runtime

[`ui/i18n.py`](src/videotosprite/ui/i18n.py) builds the control tree from the
**Portuguese** literals in the panel code, then rewrites it into the selected
language (English is the default). The upside is that static labels need no
per-string plumbing. The catch:

> **Any new user-facing string must get an entry in the `_PT_EN` table**
> in [`ui/i18n.py`](src/videotosprite/ui/i18n.py) — otherwise it silently ships as
> Portuguese to English users.

Strings composed at runtime (status, toasts, captions) go through `t()`.

### 2. `flet` is version-pinned on purpose

`flet==0.85.2` in both `requirements.txt` and `pyproject.toml` must match the `flet`
CLI used by `build_macos.sh`. The packaged Flutter shell and the Python package
speak a version-locked protocol — a mismatch opens the app to a **black window**
with no error. **Bump both together**, and see the packaging section of the
[README](README.md#package-as-a-macos-app-app) for the other two build gotchas
(Swift Package Manager, arm64-only).

### 3. `core/` must stay UI-agnostic

`core/` holds the logic — ffmpeg, chroma key, packing, render, export — and must
remain importable without Flet. `ui/panels/*` own their own controls and handlers,
and call back into the `VideoToSpriteApp` controller for anything cross-panel. Heavy
work runs off the UI thread via `page.run_thread`.

## Style

No linter is enforced; match the surrounding code:

- `from __future__ import annotations` at the top of every module.
- A module docstring on every module; docstrings on non-obvious functions.
- Lines up to ~100 columns.
- Type hints on `core/` signatures.
- Standard library / third-party / local import grouping (isort default order).

## Good first contributions

If you're looking for somewhere to start, these are known gaps rather than
hypotheticals:

- **Test isolation**: the `app` fixture reads — and one test writes —
  the real `~/.videotosprite/config.json`. An autouse fixture monkeypatching
  `config.CONFIG_PATH` would fix it.
- **Coverage in the ffmpeg layer**: `_output_size` in
  [`core/ffmpeg.py`](src/videotosprite/core/ffmpeg.py) reimplements ffmpeg's
  `scale=-2` rounding and has no unit test; neither does `effective_fps` in
  `ui/panels/video_panel.py`.
- **Portuguese leaking past i18n**: the export status strings in
  [`core/export.py`](src/videotosprite/core/export.py) are not in the `_PT_EN`
  table, so export progress shows in Portuguese even in English mode. Two file-picker
  dialog titles (`video_panel.py`, `export_panel.py`) have the same problem.
- **Linux/Windows support** for the ffmpeg auto-installer.
