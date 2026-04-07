"""Wrapper to run training and save output to log file."""
import subprocess
import sys
import os
from pathlib import Path

script = os.path.join(os.path.dirname(__file__), "train_improved.py")
root_dir = Path(__file__).resolve().parent.parent
log_dir = root_dir / "artifacts" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_path = log_dir / "train_v2_log.txt"

with open(log_path, "w", encoding="utf-8") as log:
    proc = subprocess.Popen(
        [sys.executable, "-u", script, "--batch-size", "16", "--skip-consolidation"],
        stdout=log, stderr=subprocess.STDOUT,
        cwd=str(root_dir),
    )
    proc.wait()
    log.write(f"\n\nProcess exited with code: {proc.returncode}\n")

