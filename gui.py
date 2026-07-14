#!/usr/bin/env python3
"""
raw_to_woudc - Tkinter GUI for WOUDC export and metadata table generation.

Usage:
    python gui.py

Requires: ttkbootstrap, numpy, pandas, openpyxl (for XLSX tables)
"""

import sys
from pathlib import Path

# Ensure src/ is on the Python path
_SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(_SRC))

from gui.app import MainWindow


def main():
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
