"""Shared test fixtures.

The UI tests don't need a display: they drive ``VideoToSpriteApp`` against a fake
``Page`` that records the calls the app makes (``show_dialog``, ``run_thread`` …).
Stray ``control.update()`` calls (which require a control to be attached to a live
page) are neutralised so handlers can run headless.
"""
from __future__ import annotations

import numpy as np
import pytest
from flet.controls.base_control import BaseControl

# Handlers call control.update() directly; off a live page that raises, so no-op it.
BaseControl.update = lambda self, *a, **k: None


class _Window:
    width = 0
    height = 0


class MockPage:
    """Minimal stand-in for flet.Page that records what the app asks it to do."""

    def __init__(self):
        self.services = []
        self.controls = []
        self.window = _Window()
        self.title = self.theme_mode = self.padding = self.bgcolor = None
        self.on_keyboard_event = None
        self.dialog = None
        self.threads = []   # (fn, args) passed to run_thread
        self.tasks = []     # (fn, args) passed to run_task

    def add(self, *c):
        self.controls.extend(c)

    def update(self, *a, **k):
        pass

    def show_dialog(self, d):
        self.dialog = d

    def pop_dialog(self):
        self.dialog = None

    def run_thread(self, fn, *args):
        self.threads.append((fn, args))

    def run_task(self, fn, *args):
        self.tasks.append((fn, args))


@pytest.fixture(autouse=True)
def _force_pt():
    # keep the UI language deterministic (Portuguese source strings) for assertions
    from videotosprite.ui import i18n
    i18n.set_lang("pt")
    yield


@pytest.fixture
def page():
    return MockPage()


@pytest.fixture
def app(page):
    from videotosprite.ui.app import VideoToSpriteApp
    return VideoToSpriteApp(page)


@pytest.fixture
def loaded_app(app):
    """An app with 4 synthetic 16:9 frames already extracted."""
    from videotosprite.core.frames import Frame
    app.store.frames = [
        Frame(i, None, np.random.randint(0, 255, (90, 160, 3), np.uint8))
        for i in range(4)
    ]
    app.preview.populate(app.store)
    app.current = 0
    return app
