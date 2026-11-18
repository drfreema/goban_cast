from __future__ import annotations

import numpy as np

from goban_cast.geometry import Orientation
from goban_cast.vision.board import BoardGeometry, order_corners_tl_tr_br_bl


def test_order_corners_tl_tr_br_bl():
    pts = np.array([[10, 10], [10, 0], [0, 10], [0, 0]], dtype=np.float64)  # br, tr, bl, tl shuffled
    ordered = order_corners_tl_tr_br_bl(pts)
    assert ordered.tolist() == [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]


def test_board_geometry_rotation_round_trip():
    corners = np.array([[100.0, 50.0], [500.0, 60.0], [490.0, 460.0], [110.0, 450.0]])
    geom = BoardGeometry.from_corners(corners, size=9, orientation=Orientation.DEG_90)
    for y in range(9):
        for x in range(9):
            cam = geom.intersection_camera_px(x, y)
            disp = geom.camera_to_canonical(cam.reshape(1, 2))[0]
            assert abs(disp[0] - x) < 1e-6
            assert abs(disp[1] - y) < 1e-6
    # identity when unrotated corners map through base view
    base = BoardGeometry.from_corners(corners, size=9)
    assert np.allclose(base.all_intersections_camera_px()[0], base.intersection_camera_px(0, 0))
