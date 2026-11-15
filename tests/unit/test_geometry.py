"""Round-trip and invariant tests for the geometry kernel."""

from __future__ import annotations

import numpy as np
import pytest

from goban_cast.geometry import (
    BoardView,
    GeometryError,
    Homography,
    Orientation,
    apply_affine,
    grid_points,
    orientation_affine,
    rotate_index,
    square_corners,
)


def test_grid_points_is_row_major_and_sized() -> None:
    points = grid_points(9)
    assert points.shape == (81, 2)
    assert points[0].tolist() == [0.0, 0.0]
    assert points[1].tolist() == [1.0, 0.0]
    assert points[9].tolist() == [0.0, 1.0]
    assert points[-1].tolist() == [8.0, 8.0]


@pytest.mark.parametrize("size", [9, 13, 19])
def test_square_corners_are_clockwise(size: int) -> None:
    corners = square_corners(size)
    assert corners.tolist() == [
        [0.0, 0.0],
        [float(size - 1), 0.0],
        [float(size - 1), float(size - 1)],
        [0.0, float(size - 1)],
    ]


def test_homography_maps_quads_exactly() -> None:
    source = np.array([[0.0, 0.0], [640.0, 0.0], [640.0, 480.0], [0.0, 480.0]])
    destination = square_corners(9)
    homography = Homography.from_quads(source, destination)
    mapped = homography.apply(source)
    np.testing.assert_allclose(mapped, destination, atol=1e-9)


def test_homography_round_trip() -> None:
    source = np.array([[112.0, 44.0], [902.0, 61.0], [880.0, 700.0], [130.0, 688.0]])
    homography = Homography.from_quads(source, square_corners(9))
    probe = np.array([[0.0, 0.0], [8.0, 8.0], [3.5, 6.25], [1.0, 7.0]])
    board = homography.apply(probe)
    back = homography.inverse.apply(board)
    np.testing.assert_allclose(back, probe, atol=1e-9)


def test_homography_rejects_degenerate_points() -> None:
    collinear = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0], [3.0, 3.0]])
    with pytest.raises(GeometryError):
        Homography.from_quads(collinear, square_corners(9))


def test_homography_rejects_wrong_shape() -> None:
    with pytest.raises(GeometryError):
        Homography(np.eye(2))


def test_identity_homography_is_noop() -> None:
    points = grid_points(9)
    np.testing.assert_allclose(Homography.identity().apply(points), points)


@pytest.mark.parametrize("turns", [1, 2, 3, 4])
def test_orientation_quarter_turns_compose(turns: int) -> None:
    size = 9
    orientation = Orientation((90 * turns) % 360)
    quarter = orientation_affine(size, Orientation.DEG_90)
    composed = np.linalg.matrix_power(quarter, turns)
    # Four quarter turns must return to the identity; anything else must match the
    # equivalent single-step orientation.
    if turns == 4:
        np.testing.assert_allclose(composed, np.eye(3))
    else:
        np.testing.assert_allclose(composed, orientation_affine(size, orientation))


def test_clockwise_quarter_turn_maps_corners() -> None:
    size = 9
    corners = square_corners(size)
    rotated = apply_affine(orientation_affine(size, Orientation.DEG_90), corners)
    expected = np.array([[8.0, 0.0], [8.0, 8.0], [0.0, 8.0], [0.0, 0.0]])
    np.testing.assert_allclose(rotated, expected)


def test_mirror_twice_is_identity() -> None:
    size = 9
    once = orientation_affine(size, Orientation.DEG_0, mirror=True)
    twice = once @ once
    np.testing.assert_allclose(twice, np.eye(3))


def test_rotate_index_matches_quarter_turn() -> None:
    size = 9
    assert rotate_index((0, 0), size, Orientation.DEG_90) == (8, 0)
    assert rotate_index((8, 8), size, Orientation.DEG_180) == (0, 0)
    # (4, 2) -> (6, 4) after one clockwise turn, -> (4, 6) after two, -> (2, 4) after three.
    assert rotate_index((4, 2), size, Orientation.DEG_90) == (6, 4)
    assert rotate_index((4, 2), size, Orientation.DEG_270) == (2, 4)


def test_board_view_snaps_camera_pixels_to_intersections() -> None:
    size = 9
    camera_corners = np.array([[100.0, 50.0], [820.0, 60.0], [810.0, 770.0], [110.0, 760.0]])
    view = BoardView(size=size, camera_to_board=Homography.from_quads(camera_corners, square_corners(size)))
    # Centre of the camera quad is intersection (4, 4).
    centre = camera_corners.mean(axis=0, keepdims=True)
    assert view.nearest_intersection(centre) == [(4, 4)]


def test_board_view_rotation_changes_snapping() -> None:
    size = 9
    view = BoardView(size=size, camera_to_board=Homography.identity())
    point = np.array([[0.0, 0.0]])
    assert view.nearest_intersection(point) == [(0, 0)]
    assert view.rotated(Orientation.DEG_90).nearest_intersection(point) == [(8, 0)]


def test_board_view_round_trip_display_to_camera() -> None:
    size = 9
    camera_corners = np.array([[100.0, 50.0], [820.0, 60.0], [810.0, 770.0], [110.0, 760.0]])
    view = BoardView(
        size=size,
        camera_to_board=Homography.from_quads(camera_corners, square_corners(size)),
        orientation=Orientation.DEG_270,
        mirror=True,
    )
    display = grid_points(size)[::7]
    camera = view.display_to_camera(display)
    np.testing.assert_allclose(view.camera_to_display(camera), display, atol=1e-6)
