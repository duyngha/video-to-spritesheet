"""Shared UI constants and small reusable builders for the Flet panels."""
from __future__ import annotations

import flet as ft

# palette / sizing
ACCENT = "#569cd6"
CARD_BG = "#26262b"
CROP_COLOR = "#ffd166"
PREVIEW_MAX_W = 760
PREVIEW_MAX_H = 520
PREVIEW_RENDER_MAX = 720   # cap working resolution for snappy live preview


def fmt_time(seconds: float) -> str:
    m, s = divmod(max(seconds, 0), 60)
    return f"{int(m):02d}:{s:05.2f}"


def to_float(text, default: float) -> float:
    try:
        return float(str(text).replace(",", "."))
    except (TypeError, ValueError):
        return default


def to_int(text, default: int) -> int:
    try:
        return int(float(str(text)))
    except (TypeError, ValueError):
        return default


def card(title: str, controls: list[ft.Control]) -> ft.Container:
    return ft.Container(
        content=ft.Column([ft.Text(title, weight=ft.FontWeight.BOLD, color=ACCENT),
                           *controls], spacing=6, tight=True),
        bgcolor=CARD_BG, border_radius=8, padding=12)


class LabeledSlider:
    """A 0..1 slider with a caption that shows its live value.

    ``on_change`` is a no-arg callback fired after the value updates.
    """

    def __init__(self, label: str, value: float, on_change):
        from .i18n import t
        self._label = label
        self._cb = on_change
        self.text = ft.Text(f"{t(label)}: {value:.2f}", size=12)
        self.slider = ft.Slider(min=0, max=1, value=value, divisions=100,
                                active_color=ACCENT, on_change=self._on)

    def _on(self, e):
        from .i18n import t
        self.text.value = f"{t(self._label)}: {self.slider.value:.2f}"
        self._cb()

    def set(self, value: float):
        from .i18n import t
        self.slider.value = value
        self.text.value = f"{t(self._label)}: {value:.2f}"

    @property
    def value(self) -> float:
        return self.slider.value

    @property
    def controls(self) -> list[ft.Control]:
        return [self.text, self.slider]
