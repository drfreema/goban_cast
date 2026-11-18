"""Stone detection on a calibrated/known board view.

Approach inspired by Seth-Rothschild/goban_irl (GPL-3.0) — sampling per
intersection and classifying by image intensity — reimplemented here for
parameterized board sizes and optional per-intersection empty-board baselines.
No goban_irl source code is copied verbatim; goban_cast is GPL-3.0.

Coordinate spaces:
- sampling locations are derived from canonical intersections mapped to ``camera_px``.
- outputs are per-canonical intersection labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from goban_cast.vision.board import BoardGeometry

Stone = Literal["empty", "black", "white"]


@dataclass(frozen=True)
class DetectionConfig:
    """Detection parameters (tune per setup/profile, not hardcoded globally)."""

    patch_radius_px: int = 18
    inner_radius_ratio: float = 0.55
    # Absolute gray fallback (used when no baseline is provided)
    black_max_gray: float = 95.0
    white_min_gray: float = 210.0
    # Baseline-relative thresholds (gray delta = mean(patch) - baseline_mean)
    black_delta_max: float = -28.0
    white_delta_min: float = 28.0
    min_std_for_stone: float = 6.0


def _sample_patch(
    image_bgr: np.ndarray, center_camera_px: np.ndarray, radius: int
) -> np.ndarray | None:
    h, w = image_bgr.shape[:2]
    x = round(float(center_camera_px[0]))
    y = round(float(center_camera_px[1]))
    x0 = max(0, x - radius)
    x1 = min(w, x + radius)
    y0 = max(0, y - radius)
    y1 = min(h, y + radius)
    if x1 <= x0 or y1 <= y0:
        return None
    patch = image_bgr[y0:y1, x0:x1]
    return patch if patch.size else None


def _circular_means(patch_bgr: np.ndarray, inner_ratio: float) -> tuple[float, float, float]:
    gray = cv2.cvtColor(patch_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    cy, cx = h / 2.0, w / 2.0
    yy, xx = np.ogrid[:h, :w]
    dist2 = (yy - cy) ** 2 + (xx - cx) ** 2
    outer_r = min(h, w) / 2.0
    inner_r = max(1.0, outer_r * inner_ratio)
    inner = dist2 <= inner_r**2
    ring = (dist2 <= outer_r**2) & (~inner)
    inner_vals = gray[inner]
    ring_vals = gray[ring] if np.any(ring) else gray.reshape(-1)
    if inner_vals.size == 0:
        inner_vals = gray.reshape(-1)
    return float(inner_vals.mean()), float(inner_vals.std()), float(ring_vals.mean())


def classify_intersection(
    image_bgr: np.ndarray,
    center_camera_px: np.ndarray,
    *,
    config: DetectionConfig | None = None,
    baseline_mean: float | None = None,
) -> tuple[Stone, dict[str, float]]:
    cfg = config or DetectionConfig()
    patch = _sample_patch(image_bgr, center_camera_px, cfg.patch_radius_px)
    if patch is None:
        return "empty", {"reason": -1.0}
    mean, std, ring_mean = _circular_means(patch, cfg.inner_radius_ratio)
    info = {"mean": mean, "std": std, "ring_mean": ring_mean}
    if baseline_mean is not None:
        delta = mean - float(baseline_mean)
        info["baseline_mean"] = float(baseline_mean)
        info["delta"] = delta
        # Stones should differ from this intersection's own empty appearance.
        if delta <= cfg.black_delta_max:
            return "black", info
        if delta >= cfg.white_delta_min and std >= cfg.min_std_for_stone:
            return "white", info
        return "empty", info

    # Fallback: simple absolute thresholds (fragile; prefer baseline).
    if mean <= cfg.black_max_gray:
        return "black", info
    if mean >= cfg.white_min_gray and std >= cfg.min_std_for_stone:
        return "white", info
    return "empty", info


def detect_board(
    image_bgr: np.ndarray,
    geometry: BoardGeometry,
    *,
    config: DetectionConfig | None = None,
    baseline_means: np.ndarray | None = None,
) -> list[list[Stone]]:
    """Return board state as ``state[y][x]`` in canonical/display space."""
    size = geometry.size
    if baseline_means is not None:
        baseline_means = np.asarray(baseline_means, dtype=np.float64)
        if baseline_means.shape != (size, size):
            raise ValueError(f"baseline_means must be {(size, size)}, got {baseline_means.shape}")
    state: list[list[Stone]] = [["empty" for _ in range(size)] for _ in range(size)]
    for y in range(size):
        for x in range(size):
            center = geometry.intersection_camera_px(x, y)
            bmean = None if baseline_means is None else float(baseline_means[y, x])
            stone, _ = classify_intersection(image_bgr, center, config=config, baseline_mean=bmean)
            state[y][x] = stone
    return state


def state_to_sparse(state: list[list[Stone]]) -> list[list[object]]:
    stones: list[list[object]] = []
    for y, row in enumerate(state):
        for x, stone in enumerate(row):
            if stone != "empty":
                stones.append([x, y, stone])
    return stones


def sparse_to_state(size: int, stones: list[list[object]]) -> list[list[Stone]]:
    state: list[list[Stone]] = [["empty" for _ in range(size)] for _ in range(size)]
    for x, y, color in stones:
        xi, yi = int(x), int(y)
        if not (0 <= xi < size and 0 <= yi < size):
            raise ValueError(f"stone out of bounds: {(xi, yi)} for size {size}")
        if color not in ("black", "white"):
            raise ValueError(f"invalid stone color: {color}")
        state[yi][xi] = color  # type: ignore[assignment]
    return state


def compute_baseline_means(
    image_bgr: np.ndarray, geometry: BoardGeometry, *, config: DetectionConfig | None = None
) -> np.ndarray:
    """Per-intersection inner-patch mean gray values from an empty-board frame."""
    cfg = config or DetectionConfig()
    means = np.zeros((geometry.size, geometry.size), dtype=np.float64)
    for y in range(geometry.size):
        for x in range(geometry.size):
            center = geometry.intersection_camera_px(x, y)
            patch = _sample_patch(image_bgr, center, cfg.patch_radius_px)
            if patch is None:
                means[y, x] = 0.0
                continue
            mean, _, _ = _circular_means(patch, cfg.inner_radius_ratio)
            means[y, x] = mean
    return means
