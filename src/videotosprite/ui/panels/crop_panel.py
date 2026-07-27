"""Dedicated crop panel: toggle crop mode, see the selection's position/size in
pixels, and edit those numbers directly (in sync with dragging on the preview)."""
from __future__ import annotations

import flet as ft

from ..i18n import t
from ..widgets import CROP_COLOR, card, to_int


class CropPanel:
    def __init__(self, app):
        self.app = app
        self._build()

    def _build(self):
        self.crop_btn = ft.Button("✂ Ativar recorte", on_click=self.toggle,
                                  disabled=True)
        self.x = ft.TextField(label="X", width=78, disabled=True, on_change=self.on_field)
        self.y = ft.TextField(label="Y", width=78, disabled=True, on_change=self.on_field)
        self.w = ft.TextField(label="Largura", width=92, disabled=True,
                              on_change=self.on_field)
        self.h = ft.TextField(label="Altura", width=92, disabled=True,
                              on_change=self.on_field)
        self.size_lbl = ft.Text("sem recorte", size=12, color="#8fc")
        self.clear_btn = ft.TextButton("limpar recorte", on_click=self.clear)

        self.card = card("2 · Recortar", [
            self.crop_btn,
            ft.Row([self.x, self.y]),
            ft.Row([self.w, self.h]),
            self.size_lbl, self.clear_btn,
            ft.Text("Arraste no preview ou edite os valores (px do frame).",
                    size=11, color="#999"),
        ])

    # ------------------------------------------------------------- actions
    def toggle(self, e):
        self.app.preview.toggle_crop()

    def clear(self, e):
        self.app.preview.clear_crop()

    def on_field(self, e):
        """User typed a value — rebuild the normalised crop and push it to the app."""
        fw, fh = self.app.store.size
        if not fw:
            return
        x = max(0, min(to_int(self.x.value, 0), fw - 1))
        y = max(0, min(to_int(self.y.value, 0), fh - 1))
        w = max(1, min(to_int(self.w.value, fw), fw - x))
        h = max(1, min(to_int(self.h.value, fh), fh - y))
        self.app.set_crop_norm((x / fw, y / fh, w / fw, h / fh))
        self._update_label(x, y, w, h)

    # ------------------------------------------------------------- display
    def show_norm(self, crop):
        """Fill X/Y/W/H + label from a normalised crop (None clears)."""
        fw, fh = self.app.store.size
        if crop is None or not fw:
            self.x.value = self.y.value = self.w.value = self.h.value = ""
            self.size_lbl.value = t("sem recorte")
        else:
            x, y, w, h = (round(crop[0] * fw), round(crop[1] * fh),
                          round(crop[2] * fw), round(crop[3] * fh))
            self.x.value, self.y.value = str(x), str(y)
            self.w.value, self.h.value = str(w), str(h)
            self._update_label(x, y, w, h)
        # push so the live readout updates during a drag (no full page.update there)
        for c in (self.x, self.y, self.w, self.h, self.size_lbl):
            c.update()

    def _update_label(self, x, y, w, h):
        self.size_lbl.value = f"{w} × {h} px  @ ({x}, {y})"

    # --------------------------------------------------------------- state
    def set_active(self, on: bool):
        self.crop_btn.bgcolor = CROP_COLOR if on else None
        self.crop_btn.color = "#222" if on else None
        self.crop_btn.content = "✂ Recorte ativo (arraste)" if on else "✂ Ativar recorte"

    def set_enabled(self, on: bool):
        for c in (self.crop_btn, self.x, self.y, self.w, self.h):
            c.disabled = not on

    def set_busy(self, busy: bool):
        self.crop_btn.disabled = busy or len(self.app.store) == 0
