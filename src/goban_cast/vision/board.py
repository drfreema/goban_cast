"""Board geometry helpers in camera/board spaces.

This module maps intersections between ``camera_px`` and ``board_mm`` (grid units)
using :mod:`goban_cast.geometry`. It does not implement detection policy.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from goban_cast.geometry import BoardView, Homography, Orientation, square_corners


@dataclass(frozen=True)
class BoardGeometry:
    """Resolved geometry for one camera view of a board."""

    size: int
    corners_camera_px: np.ndarray  # (4,2) TL,TR,BR,BL in camera_px
    view: BoardView
    orientation: Orientation = Orientation.DEG_0
    mirror: bool = False

    @classmethod
    def from_corners(
        cls,
        corners_camera_px,
        *,
        size: int,
        orientation: Orientation = Orientation.DEG_0,
        mirror: bool = False,
    ) -> BoardGeometry:
        corners = np.asarray(corners_camera_px, dtype=np.float64)
        if corners.shape != (4, 2):
            raise ValueError(f"corners_camera_px must be (4,2), got {corners.shape}")
        camera_to_board = Homography.from_quads(corners, square_corners(size))
        view = BoardView(
            size=size,
            camera_to_board=camera_to_board,
            orientation=orientation,
            mirror=mirror,
        )
        return cls(
            size=size,
            corners_camera_px=corners,
            view=view,
            orientation=orientation,
            mirror=mirror,
        )

    def with_orientation(
        self, orientation: Orientation, *, mirror: bool | None = None
    ) -> BoardGeometry:
        use_mirror = self.mirror if mirror is None else mirror
        return BoardGeometry(
            size=self.size,
            corners_camera_px=self.corners_camera_px.copy(),
            view=self.view.rotated(orientation, mirror=use_mirror),
            orientation=orientation,
            mirror=use_mirror,
        )

    def intersection_camera_px(self, x: int, y: int) -> np.ndarray:
        """Canonical/display intersection ``(x, y)`` mapped to camera_px."""
        pt = np.array([[float(x), float(y)]], dtype=np.float64)
        return self.view.display_to_camera(pt)[0]

    def all_intersections_camera_px(self) -> np.ndarray:
        """All canonical intersections in row-major order, shape (size*size, 2), camera_px."""
        pts = []
        for y in range(self.size):
            for x in range(self.size):
                pts.append(self.intersection_camera_px(x, y))
        return np.asarray(pts, dtype=np.float64)

    def warp(self, image_bgr: np.ndarray, *, pixels_per_cell: int = 80) -> np.ndarray:
        """Rectified board image in a synthetic board-aligned pixel space (not canonical mm)."""
        side = int((self.size - 1) * pixels_per_cell)
        dst = np.array(
            [[0, 0], [side, 0], [side, side], [0, side]], dtype=np.float32
        )
        matrix = cv2.getPerspectiveTransform(
            self.corners_camera_px.astype(np.float32), dst
        )
        return cv2.warpPerspective(image_bgr, matrix, (side + 1, side + 1))

    def camera_to_canonical(self, camera_px_points: np.ndarray) -> np.ndarray:
        """Map camera_px points to displayed canonical board_mm coordinates."""
        return self.view.camera_to_display(np.asarray(camera_px_points, dtype=np.float64))

    def canonical_to_camera(self, canonical_points: np.ndarray) -> np.ndarray:
        """Map displayed canonical board_mm points to camera_px."""
        return self.view.display_to_camera(np.asarray(canonical_points, dtype=np.float64))


def order_corners_tl_tr_br_bl(points: np.ndarray) -> np.ndarray:
    """Order four camera_px points as TL, TR, BR, BL."""
    pts = np.asarray(points, dtype=np.float64)
    if pts.shape != (4, 2):
        raise ValueError(f"expected 4 points, got {pts.shape}")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float64)
