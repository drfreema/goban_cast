from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_dump_state_on_fixture(tmp_path):
    out_debug = tmp_path / "debug.png"
    cmd = [
        sys.executable,
        "-m",
        "goban_cast.app",
        "--dump-state",
        "--image",
        "tests/fixtures/bamboo-overhead-720p/empty/frame.png",
        "--corners",
        "tests/fixtures/bamboo-overhead-720p/empty/corners.json",
        "--baseline-image",
        "tests/fixtures/bamboo-overhead-720p/empty/frame.png",
        "--size",
        "9",
        "--save-debug",
        str(out_debug),
    ]
    # run as module via src on path: use uv run in CI, but plain python with PYTHONPATH works here
    env = dict(**__import__("os").environ)
    src = str(Path("src").resolve())
    env["PYTHONPATH"] = src + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(Path.cwd()))
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(proc.stdout)
    assert data["stones"] == []
    assert data["size"] == 9
    assert out_debug.exists()
