"""Wrapper to run training and save output to log file."""
import subprocess
import sys
import os

script = os.path.join(os.path.dirname(__file__), "train_improved.py")
log_path = os.path.join(os.path.dirname(__file__), "..", "train_v2_log.txt")

with open(log_path, "w", encoding="utf-8") as log:
    proc = subprocess.Popen(
        [sys.executable, "-u", script, "--batch-size", "16", "--skip-consolidation"],
        stdout=log, stderr=subprocess.STDOUT,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    proc.wait()
    log.write(f"\n\nProcess exited with code: {proc.returncode}\n")

