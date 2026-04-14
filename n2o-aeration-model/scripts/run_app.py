"""Convenience launcher for the Streamlit interface."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "streamlit_app.py"

subprocess.run([sys.executable, "-m", "streamlit", "run", str(APP)], check=True)
