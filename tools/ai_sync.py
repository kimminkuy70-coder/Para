"""Development-only, sequential Claude/Codex Git synchronization (stdlib only)."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "version_rev1"
REMOTE = "origin"


def git(*args):
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace"
    ).strip()


def require_ready():
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError(f"Switch to {BRANCH} after preserving your current work.")
    if git("status", "--porcelain"):
        raise RuntimeError("Uncommitted files found. Review and commit your work first; nothing was discarded.")
    for kind in (False, True):
        args = ("remote", "get-url", "--push", REMOTE) if kind else ("remote", "get-url", REMOTE)
        url = git(*args).removesuffix(".git").rstrip("/")
        if url not in ("https://github.com/kimminkuy70-coder/Para", "git@github.com:kimminkuy70-coder/Para"):
            raise RuntimeError("origin must point to kimminkuy70-coder/Para (fetch and push).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "publish"))
    action = parser.parse_args().action
    require_ready()
    git("fetch", REMOTE, "+refs/heads/" + BRANCH + ":refs/remotes/origin/" + BRANCH)
    ahead, behind = map(int, git("rev-list", "--left-right", "--count", "HEAD...origin/" + BRANCH).split())
    if action == "start":
        if ahead:
            raise RuntimeError("Local unpublished commits found. Review and publish/integrate them before starting.")
        git("merge", "--ff-only", "origin/" + BRANCH)
        print("Ready:", BRANCH, git("rev-parse", "HEAD"))
        print("Read AGENTS.md, docs/AI_HANDOFF.md, CLAUDE.md and relevant source/tests.")
    else:
        if behind:
            raise RuntimeError("Remote changed. Review, integrate and retest before publishing; no force push.")
        git("push", REMOTE, "HEAD:refs/heads/" + BRANCH)
        print("Published:", BRANCH, git("rev-parse", "HEAD"))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print("STOP:", exc, file=sys.stderr)
        sys.exit(1)
