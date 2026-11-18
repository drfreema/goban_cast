from __future__ import annotations

import glob
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from goban_cast.vision.board import BoardGeometry
from goban_cast.vision.corners import detect_board_corners
from goban_cast.vision.detect import compute_baseline_means
from goban_cast.vision.state import load_corners, read_state_from_image

FIXTURE_DIR = Path("tests/fixtures/bamboo-overhead-720p/empty")
EXTRA_DIR = Path("tests/fixtures/bamboo-overhead-720p/empty_frames")


@pytest.mark.vision
def test_empty_bamboo_fixture_matches_expected_with_baseline():
    image = cv2.imread(str(FIXTURE_DIR / "frame.png"))
    assert image is not None
    expected = json.loads((FIXTURE_DIR / "expected.json").read_text())
    corners = load_corners(FIXTURE_DIR / "corners.json")
    geom = BoardGeometry.from_corners(corners, size=expected["size"])
    baseline = compute_baseline_means(image, geom)
    readout = read_state_from_image(
        image,
        size=expected["size"],
        corners_camera_px=corners,
        baseline_means=baseline,
    )
    assert readout.sparse() == expected["stones"]
    assert all(s == "empty" for row in readout.state for s in row)


@pytest.mark.vision
def test_empty_bamboo_frames_stable_zero_false_stones():
    base = cv2.imread(str(FIXTURE_DIR / "frame.png"))
    corners = load_corners(FIXTURE_DIR / "corners.json")
    geom = BoardGeometry.from_corners(corners, size=9)
    baseline = compute_baseline_means(base, geom)
    paths = [FIXTURE_DIR / "frame.png", *sorted(Path(p) for p in glob.glob(str(EXTRA_DIR / "frame_*.png")))]
    assert len(paths) >= 5
    for path in paths:
        image = cv2.imread(str(path))
        assert image is not None, f"failed to read {path}"
        readout = read_state_from_image(image, size=9, corners_camera_px=corners, baseline_means=baseline)
        assert readout.sparse() == [], f"false stones in {path}: {readout.sparse()}"


@pytest.mark.vision
def test_auto_corner_detection_finds_board_quad():
    image = cv2.imread(str(FIXTURE_DIR / "frame.png"))
    detected = detect_board_corners(image)
    assert detected is not None
    assert detected.shape == (4, 2)
    # Should be broadly near the saved corners (same board, heuristic contour).
    saved = load_corners(FIXTURE_DIR / "corners.json")
    # Compare as set of points with tolerance after ordering.
    assert np.all(np.linalg.norm(detected - saved, axis=1) < 40.0)
