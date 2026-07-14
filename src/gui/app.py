import tkinter as tk
from tkinter import ttk
import ttkbootstrap as tb
from pathlib import Path

from .i18n import _, STRINGS
from .processing_tab import ProcessingTab
from .nasaaims_tab import NasaAimsTab
from .metadata_tab import MetadataTab
from .about_tab import AboutTab

SUPPORTED_LANGS = ["en", "fi", "fr"]


class MainWindow(tb.Window):
    """Main application window with notebook and language switching."""

    def __init__(self):
        super().__init__(themename="flatly")
        self.lang = tk.StringVar(value="en")

        # Build the current translation function
        self._current_lang = "en"

        self.title(_(self._current_lang, "app_title"))
        self.geometry("820x680")
        self.minsize(700, 560)

        self._build_menu()
        self._build_notebook()
        self._update_lang()

    # ── Menu bar ────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self)
        self.configure(menu=menubar)

        lang_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Language", menu=lang_menu)

        for code in SUPPORTED_LANGS:
            label = _(code, f"lang_{code}")
            lang_menu.add_radiobutton(
                label=label,
                variable=self.lang,
                value=code,
                command=lambda c=code: self._set_language(c),
            )

    # ── Notebook ────────────────────────────────────────────────────

    def _build_notebook(self):
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill=tk.BOTH, expand=True)

        self._tabs = {}
        for key, cls in [
            ("tab_export", ProcessingTab),
            ("tab_nasaaims", NasaAimsTab),
            ("tab_metadata", MetadataTab),
            ("tab_about", AboutTab),
        ]:
            tab = cls(self._notebook, self._mk_i18n())
            self._notebook.add(tab, text=_(self._current_lang, key))
            self._tabs[key] = tab

    # ── Language ────────────────────────────────────────────────────

    def _mk_i18n(self):
        """Return a bound lookup function for the current language."""
        lang = self._current_lang

        def lookup(key):
            return _(lang, key)
        return lookup

    def _set_language(self, code):
        self._current_lang = code
        self.lang.set(code)
        self._update_lang()

    def _update_lang(self):
        lang = self._current_lang
        self.title(_(lang, "app_title"))

        tab_keys = ["tab_export", "tab_nasaaims", "tab_metadata", "tab_about"]
        for key, tab in zip(tab_keys, self._notebook.tabs()):
            self._notebook.tab(tab, text=_(lang, key))

        for key, tab in self._tabs.items():
            tab.set_language(self._mk_i18n())
