"""High-level state readout for a single frame."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from goban_cast.geometry import Orientation
from goban_cast.vision.board import BoardGeometry
from goban_cast.vision.corners import corners_from_jsonable, detect_board_corners
from goban_cast.vision.detect import DetectionConfig, detect_board, state_to_sparse


@dataclass(frozen=True)
class Readout:
    size: int
    corners_camera_px: list[list[float]]
    orientation_deg: int
    mirror: bool
    state: list[list[str]]  # [y][x] canonical

    def sparse(self) -> list[list[object]]:
        return state_to_sparse(self.state)

    def to_dict(self) -> dict:
        return {
            "size": self.size,
            "orientation": self.orientation_deg,
            "mirror": self.mirror,
            "corners_camera_px": self.corners_camera_px,
            "stones": self.sparse(),
            "state": self.state,
        }


def load_corners(path: str | Path) -> np.ndarray:
    data = json.loads(Path(path).read_text())
    return corners_from_jsonable(data)


def read_state_from_image(
    image_bgr: np.ndarray,
    *,
    size: int,
    corners_camera_px: np.ndarray | None = None,
    orientation: Orientation = Orientation.DEG_0,
    mirror: bool = False,
    config: DetectionConfig | None = None,
    baseline_means: np.ndarray | None = None,
) -> Readout:
    if corners_camera_px is None:
        corners_camera_px = detect_board_corners(image_bgr, size=size)
    if corners_camera_px is None:
        raise ValueError("could not determine board corners")
    corners = np.asarray(corners_camera_px, dtype=np.float64)
    geometry = BoardGeometry.from_corners(
        corners, size=size, orientation=orientation, mirror=mirror
    )
    state = detect_board(image_bgr, geometry, config=config, baseline_means=baseline_means)
    return Readout(
        size=size,
        corners_camera_px=[[float(x), float(y)] for x, y in corners.tolist()],
        orientation_deg=int(orientation),
        mirror=mirror,
        state=state,
    )
