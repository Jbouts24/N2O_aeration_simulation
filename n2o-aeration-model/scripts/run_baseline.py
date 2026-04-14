from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(ROOT / "main.py"), "run", "--config", str(ROOT / "configs/base_case.yaml")], check=True)
