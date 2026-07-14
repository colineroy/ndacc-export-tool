import tkinter as tk
from tkinter import ttk


class AboutTab(ttk.Frame):
    """Tab 3 - Documentation and references."""

    def __init__(self, parent, i18n):
        super().__init__(parent)
        self.i18n = i18n
        self._build_ui()

    def _build_ui(self):
        text = tk.Text(
            self, wrap=tk.WORD, padx=16, pady=16,
            font=("Segoe UI", 10), relief=tk.FLAT,
        )
        text.pack(fill=tk.BOTH, expand=True)
        text.configure(state=tk.DISABLED)

        self._text = text

    def set_language(self, i18n):
        self.i18n = i18n
        self._rebuild_content()

    def _rebuild_content(self):
        t = self.i18n
        lines = [
            f"\n{'='*50}\n",
            f"  {t('about_title')}\n",
            f"{'='*50}\n\n",
            t("about_intro"),
            f"\n{'─'*40}\n",
            f"  {t('about_sources')}\n",
            f"{'─'*40}\n\n",
            t("about_sources_text"),
            "\n",
            f"{'─'*40}\n",
            f"  {t('about_dqa')}\n",
            f"{'─'*40}\n\n",
            t("about_dqa_text"),
            "\n",
            f"{'─'*40}\n",
            f"  {t('about_woudc')}\n",
            f"{'─'*40}\n\n",
            t("about_woudc_text"),
            "\n",
            f"{'─'*40}\n",
            f"  {t('about_refs')}\n",
            f"{'─'*40}\n\n",
            t("about_refs_text"),
            "\n",
        ]
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", "".join(lines))
        self._text.configure(state=tk.DISABLED)
