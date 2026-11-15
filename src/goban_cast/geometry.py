"""Coordinate transforms for goban_cast.

Four spaces are used throughout the project, in this order:

    camera_px  --H_cam-->  board_mm  --orientation-->  canonical  --H_proj^-1-->  projector_px

* ``camera_px``   - pixels in the raw camera frame.
* ``board_mm``    - continuous coordinates on the board in grid units (0..size-1).
* ``canonical``   - integer ``(x, y)`` intersections, x = column, y = row, y pointing down.
* ``projector_px``- pixels in the projector's native resolution.

Everything here is pure numpy so it can be tested without OpenCV or hardware.
All public functions name the coordinate space they consume or return.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np

PointArray = np.ndarray  # shape (N, 2) float64


class GeometryError(ValueError):
    """Raised when a transform cannot be built, e.g. degenerate point sets."""


class Orientation(IntEnum):
    """View orientation of the board, rotated clockwise in 90 degree steps."""

    DEG_0 = 0
    DEG_90 = 90
    DEG_180 = 180
    DEG_270 = 270

    @property
    def quarter_turns(self) -> int:
        return int(self) // 90


def _as_points(points, *, name: str) -> PointArray:
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise GeometryError(f"{name} must have shape (N, 2), got {array.shape}")
    return array


def grid_points(size: int) -> PointArray:
    """All intersections of a ``size`` x ``size`` board in unrotated canoncial space."""
    if size < 2:
        raise GeometryError(f"board size must be >= 2, got {size}")
    xs, ys = np.meshgrid(np.arange(size, dtype=np.float64), np.arange(size, dtype=np.float64))
    # meshgrid gives row-major (y outer, x inner), which matches np.rot90 conventions.
    return np.column_stack([xs.ravel(), ys.ravel()])


def square_corners(size: int) -> PointArray:
    """Playable corners in board_mm, clockwise: top-left, top-right, bottom-right, bottom-left."""
    last = float(size - 1)
    return np.array([[0.0, 0.0], [last, 0.0], [last, last], [0.0, last]])


def orientation_affine(
    size: int, orientation: Orientation = Orientation.DEG_0, *, mirror: bool = False
) -> np.ndarray:
    """3x3 homogeneous matrix mapping unrotated ``board_mm`` to displayed ``board_mm``.

    Rotation is clockwise around the board centre. ``mirror`` flips the board
    horizontally afterwards, which is what a player sitting opposite the camera needs.
    """
    last = float(size - 1)
    turns = orientation.quarter_turns % 4
    # One clockwise quarter turn in canonical (x = column, y = row) coordinates:
    # top-left (0, 0) must land on top-right (last, 0).
    clockwise = np.array([[0.0, -1.0, last], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    matrix = np.eye(3)
    for _ in range(turns):
        matrix = clockwise @ matrix
    if mirror:
        flip = np.array([[-1.0, 0.0, last], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
        matrix = flip @ matrix
    return matrix


def apply_affine(matrix: np.ndarray, points: PointArray) -> PointArray:
    """Apply a 3x3 homogeneous matrix to ``(N, 2)`` board_mm points."""
    points = _as_points(points, name="points")
    homogeneous = np.column_stack([points, np.ones(len(points))])
    transformed = homogeneous @ np.asarray(matrix, dtype=np.float64).T
    w = transformed[:, 2:3]
    if np.any(np.isclose(w, 0.0)):
        raise GeometryError("point maps to infinity")
    return transformed[:, :2] / w


def rotate_index(
    index: tuple[int, int],
    size: int,
    orientation: Orientation = Orientation.DEG_0,
    *,
    mirror: bool = False,
) -> tuple[int, int]:
    """Rotate an integer canonical ``(x, y)`` index the same way the view is rotated."""
    matrix = orientation_affine(size, orientation, mirror=mirror)
    rotated = apply_affine(matrix, np.array([[index[0], index[1]]], dtype=np.float64))[0]
    return round(rotated[0]), round(rotated[1])


@dataclass(frozen=True)
class Homography:
    """Projective 3x3 transform, used camera_px <-> board_mm and projector_px <-> board_mm."""

    matrix: np.ndarray

    def __post_init__(self) -> None:
        matrix = np.asarray(self.matrix, dtype=np.float64)
        if matrix.shape != (3, 3):
            raise GeometryError(f"homography must be 3x3, got {matrix.shape}")
        if np.isclose(np.linalg.det(matrix), 0.0):
            raise GeometryError("homography matrix is singular")
        object.__setattr__(self, "matrix", matrix)

    @classmethod
    def identity(cls) -> Homography:
        return cls(np.eye(3))

    @classmethod
    def from_quads(cls, source, destination) -> Homography:
        """Solve the homography mapping four ``source`` points onto four ``destination`` points.

        Points must be ordered consistently (e.g. clockwise from top-left); the
        four-point direct linear transform is exact, no least squares needed.
        """
        src = _as_points(source, name="source")
        dst = _as_points(destination, name="destination")
        if len(src) != 4 or len(dst) != 4:
            raise GeometryError(f"need exactly 4 points, got {len(src)} and {len(dst)}")
        rows = []
        for (x, y), (u, v) in zip(src, dst, strict=True):
            rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y, -u])
            rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y, -v])
        _, _, vt = np.linalg.svd(np.asarray(rows, dtype=np.float64))
        h = vt[-1]
        if np.isclose(np.linalg.norm(h), 0.0):
            raise GeometryError("degenerate four-point set")
        matrix = h.reshape(3, 3)
        try:
            return cls(matrix)
        except GeometryError as exc:  # pragma: no cover - kept for a clear message
            raise GeometryError("source points are collinear") from exc

    @property
    def inverse(self) -> Homography:
        return Homography(np.linalg.inv(self.matrix))

    def apply(self, points: PointArray) -> PointArray:
        """Map ``(N, 2)`` points through this homography."""
        points = _as_points(points, name="points")
        homogeneous = np.column_stack([points, np.ones(len(points))])
        transformed = homogeneous @ self.matrix.T
        w = transformed[:, 2:3]
        if np.any(np.isclose(w, 0.0)):
            raise GeometryError("point maps to infinity")
        return transformed[:, :2] / w

    def then(self, other: Homography) -> Homography:
        """Compose: apply ``self`` first, then ``other``."""
        return Homography(other.matrix @ self.matrix)


@dataclass(frozen=True)
class BoardView:
    """Maps camera pixels to displayed canonical intersections and back.

    ``camera_to_board`` goes from camera_px to unrotated board_mm; the orientation
    is applied afterwards so callers never have to think about it.
    """

    size: int
    camera_to_board: Homography
    orientation: Orientation = Orientation.DEG_0
    mirror: bool = False

    def __post_init__(self) -> None:
        if self.size < 2:
            raise GeometryError(f"board size must be >= 2, got {self.size}")
        if not isinstance(self.orientation, Orientation):
            object.__setattr__(self, "orientation", Orientation(int(self.orientation)))

    @property
    def display_affine(self) -> np.ndarray:
        return orientation_affine(self.size, self.orientation, mirror=self.mirror)

    def camera_to_display(self, camera_px: PointArray) -> PointArray:
        return apply_affine(self.display_affine, self.camera_to_board.apply(camera_px))

    def display_to_camera(self, display_mm: PointArray) -> PointArray:
        return self.camera_to_board.inverse.apply(apply_affine(np.linalg.inv(self.display_affine), display_mm))

    def nearest_intersection(self, camera_px: PointArray) -> list[tuple[int, int]]:
        """Snap camera_px points to displayed integer ``(x, y)`` intersections."""
        display = self.camera_to_display(camera_px)
        snapped = np.rint(display).astype(int)
        snapped[:, 0] = np.clip(snapped[:, 0], 0, self.size - 1)
        snapped[:, 1] = np.clip(snapped[:, 1], 0, self.size - 1)
        return [(int(x), int(y)) for x, y in snapped]

    def rotated(self, orientation: Orientation, *, mirror: bool | None = None) -> BoardView:
        return BoardView(
            size=self.size,
            camera_to_board=self.camera_to_board,
            orientation=orientation,
            mirror=self.mirror if mirror is None else mirror,
        )
