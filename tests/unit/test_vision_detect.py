from __future__ import annotations

import numpy as np

from goban_cast.vision.board import BoardGeometry
from goban_cast.vision.detect import (
    compute_baseline_means,
    detect_board,
    sparse_to_state,
    state_to_sparse,
)


def _synthetic_board_image(size=9, cell=40):
    side = (size - 1) * cell + 1
    img = np.full((side, side, 3), 180, dtype=np.uint8)
    # draw grid for realism
    for i in range(size):
        p = i * cell
        img[p, :, :] = 80
        img[:, p, :] = 80
    return img


def test_sparse_state_round_trip():
    state = [["empty"] * 9 for _ in range(9)]
    state[0][0] = "black"
    state[8][4] = "white"
    sparse = state_to_sparse(state)
    assert sparse == [[0, 0, "black"], [4, 8, "white"]]
    back = sparse_to_state(9, sparse)
    assert back == state


def test_empty_board_with_self_baseline_is_empty():
    size = 9
    cell = 60
    img = _synthetic_board_image(size=size, cell=cell)
    side = (size - 1) * cell
    corners = np.array([[0, 0], [side, 0], [side, side], [0, side]], dtype=np.float64)
    geom = BoardGeometry.from_corners(corners, size=size)
    baseline = compute_baseline_means(img, geom)
    state = detect_board(img, geom, baseline_means=baseline)
    assert all(s == "empty" for row in state for s in row)
