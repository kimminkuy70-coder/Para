"""Run existing standalone tests without adding pytest or runtime dependencies."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    failed = []
    tests = sorted((ROOT / "tests").glob("test_*.py"))
    for path in tests:
        if path.name == "test_engine.py":
            print("SKIP test_engine.py: requires original .xlsm at Claude upload path; run separately when available.", flush=True)
            continue
        print("RUN", path.name, flush=True)
        if subprocess.run([sys.executable, str(path)], cwd=ROOT).returncode:
            failed.append(path.name)
    print("Failed files:", ", ".join(failed) or "none")
    print("Windows GUI, Excel, executable build and deployment require separate verification.")
    return bool(failed)


if __name__ == "__main__":
    sys.exit(main())
