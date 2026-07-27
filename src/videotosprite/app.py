"""Application entry point."""
from __future__ import annotations

import flet as ft

from .ui.app import main as _main


def main() -> None:
    ft.run(_main)


if __name__ == "__main__":
    main()
