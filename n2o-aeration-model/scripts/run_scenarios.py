from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
subprocess.run(
    [
        sys.executable,
        str(ROOT / "main.py"),
        "compare",
        "--configs",
        str(ROOT / "configs/low_do.yaml"),
        str(ROOT / "configs/medium_do.yaml"),
        str(ROOT / "configs/high_do.yaml"),
        str(ROOT / "configs/dynamic_do.yaml"),
    ],
    check=True,
)
