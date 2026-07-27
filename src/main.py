"""Entry point used by `flet build` / `flet run` (the packaged app loads this).

The real UI lives in the ``videotosprite`` package; this thin shim just hands the
page handler to the Flet runtime.
"""
import flet as ft

from videotosprite.ui.app import main as _main

ft.run(_main)
