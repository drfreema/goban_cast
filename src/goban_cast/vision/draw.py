"""Drawing helpers for debug/preview overlays (camera_px space)."""

from __future__ import annotations

import cv2
import numpy as np

from goban_cast.vision.board import BoardGeometry


def draw_grid(
    image_bgr: np.ndarray,
    geometry: BoardGeometry,
    *,
    color=(0, 200, 255),
    thickness: int = 1,
    draw_points: bool = True,
) -> np.ndarray:
    out = image_bgr.copy()
    s = geometry.size
    # Grid lines: connect along rows and columns in canonical space.
    for i in range(s):
        row = np.array([geometry.intersection_camera_px(x, i) for x in range(s)], dtype=np.int32)
        col = np.array([geometry.intersection_camera_px(i, y) for y in range(s)], dtype=np.int32)
        cv2.polylines(out, [row.reshape(-1, 1, 2)], False, color, thickness, cv2.LINE_AA)
        cv2.polylines(out, [col.reshape(-1, 1, 2)], False, color, thickness, cv2.LINE_AA)
    if draw_points:
        for y in range(s):
            for x in range(s):
                px = tuple(np.rint(geometry.intersection_camera_px(x, y)).astype(int).tolist())
                cv2.circle(out, px, 3, color, -1, cv2.LINE_AA)
    # Mark corners
    for idx, pt in enumerate(geometry.corners_camera_px.astype(int)):
        cv2.circle(out, tuple(pt.tolist()), 7, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.putText(out, str(idx), (pt[0] + 6, pt[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
    return out


def draw_state(
    image_bgr: np.ndarray,
    geometry: BoardGeometry,
    state: list[list[str]],
    *,
    alpha: float = 0.6,
) -> np.ndarray:
    out = image_bgr.copy()
    overlay = out.copy()
    for y, row in enumerate(state):
        for x, stone in enumerate(row):
            if stone == "empty":
                continue
            center = tuple(np.rint(geometry.intersection_camera_px(x, y)).astype(int).tolist())
            color = (20, 20, 20) if stone == "black" else (235, 235, 235)
            edge = (240, 240, 240) if stone == "black" else (30, 30, 30)
            cv2.circle(overlay, center, 12, color, -1, cv2.LINE_AA)
            cv2.circle(overlay, center, 12, edge, 1, cv2.LINE_AA)
    return cv2.addWeighted(overlay, alpha, out, 1 - alpha, 0)
