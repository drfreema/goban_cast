"""Board/playable-corner detection and ordering utilities (camera_px)."""

from __future__ import annotations

import cv2
import numpy as np


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


def _detect_outer_board_quad(image_bgr: np.ndarray) -> np.ndarray | None:
    """Detect the outer board/wood quad in camera_px (TL,TR,BR,BL) or None."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    h, w = gray.shape[:2]
    frame_area = float(h * w)
    for contour in contours[:10]:
        area = cv2.contourArea(contour)
        if area < 0.05 * frame_area:
            continue
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) == 4:
            return order_corners_tl_tr_br_bl(approx.reshape(-1, 2).astype(np.float64))
    rect = cv2.minAreaRect(contours[0])
    box = cv2.boxPoints(rect)
    return order_corners_tl_tr_br_bl(box.astype(np.float64))


def _smooth1d(a: np.ndarray, k: int = 31) -> np.ndarray:
    k = max(3, int(k) | 1)
    kernel = np.ones(k, dtype=np.float64) / k
    pad = k // 2
    ap = np.pad(a.astype(np.float64), (pad, pad), mode="edge")
    return np.convolve(ap, kernel, mode="valid")


def _fit_grid_1d(profile: np.ndarray, n: int) -> list[int] | None:
    prof = np.asarray(profile, dtype=np.float64)
    L = int(prof.shape[0])
    if L <= 0 or n < 2:
        return None
    best: list[int] | None = None
    best_sc = -1e18
    f_min = max(2, int(L * 0.08))
    f_max = int(L * 0.38)
    d_min = max(4, int(L * 0.30 / (n - 1)))
    d_max = int(L * 0.90 / (n - 1))
    if d_min >= d_max or f_min >= f_max:
        return None
    step_f = 2 if L > 300 else 1
    step_d = 2 if L > 300 else 1
    for f in range(f_min, f_max + 1, step_f):
        for d in range(d_min, d_max + 1, step_d):
            pos = [f + i * d for i in range(n)]
            if pos[-1] >= L - int(L * 0.06):
                continue
            sc = 0.0
            win = 3
            for p in pos:
                lo = max(0, p - win)
                hi = min(L, p + win + 1)
                sc += float(prof[lo:hi].max())
            span = pos[-1] - pos[0]
            center = (pos[0] + pos[-1]) / 2.0
            sc += -abs(center - L / 2.0) / (L * 0.5) * 0.5
            sc += -abs(span - L * 0.58) / (L * 0.58) * 0.3
            if sc > best_sc:
                best_sc = sc
                best = pos
    if best is None:
        return None
    d_est = (best[-1] - best[0]) / float(n - 1)
    radius = max(3, int(d_est * 0.25))
    refined: list[int] = []
    for p in best:
        lo = max(0, p - radius)
        hi = min(L, p + radius + 1)
        idx = lo + int(np.argmax(prof[lo:hi]))
        refined.append(int(idx))
    # enforce strictly increasing
    for i in range(1, n):
        if refined[i] <= refined[i - 1]:
            refined[i] = refined[i - 1] + 1
    if refined[-1] >= L:
        refined[-1] = L - 1
        for i in range(n - 2, -1, -1):
            if refined[i] >= refined[i + 1]:
                refined[i] = refined[i + 1] - 1
    return refined


def detect_playable_corners(
    image_bgr: np.ndarray, size: int = 9, outer_quad_camera_px: np.ndarray | None = None
) -> np.ndarray | None:
    """Detect the four playable corner intersections in camera_px (TL,TR,BR,BL).

    This finds the outer board quad, rectifies it, detects the ``size`` grid
    lines in each direction, and returns the intersections of the first/last
    lines mapped back to camera pixels. Returns ``None`` if detection fails.
    """
    outer = (
        order_corners_tl_tr_br_bl(np.asarray(outer_quad_camera_px, dtype=np.float64))
        if outer_quad_camera_px is not None
        else _detect_outer_board_quad(image_bgr)
    )
    if outer is None:
        return None
    S = 900
    dst = np.array([[0, 0], [S, 0], [S, S], [0, S]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(outer.astype(np.float32), dst)
    Minv = np.linalg.inv(M)
    warped = cv2.warpPerspective(image_bgr, M, (S + 1, S + 1))
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    sobelx = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
    sobely = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
    inv = 255.0 - blur.astype(np.float32)

    def norm(a: np.ndarray) -> np.ndarray:
        aa = a.astype(np.float32)
        aa = aa - aa.min()
        m = float(aa.max())
        return aa / (m + 1e-6)

    px = norm(np.mean(np.abs(sobelx), axis=0)) * 0.6 + norm(np.mean(inv, axis=0)) * 0.4
    py = norm(np.mean(np.abs(sobely), axis=1)) * 0.6 + norm(np.mean(inv, axis=1)) * 0.4
    px = _smooth1d(px, 31)
    py = _smooth1d(py, 31)
    cx = _fit_grid_1d(px, size)
    cy = _fit_grid_1d(py, size)
    if not cx or not cy or len(cx) != size or len(cy) != size:
        return None
    pts_w = np.array(
        [[cx[0], cy[0]], [cx[-1], cy[0]], [cx[-1], cy[-1]], [cx[0], cy[-1]]],
        dtype=np.float32,
    ).reshape(-1, 1, 2)
    pts_c = cv2.perspectiveTransform(pts_w, Minv).reshape(-1, 2)
    return order_corners_tl_tr_br_bl(pts_c.astype(np.float64))


def detect_board_corners(image_bgr: np.ndarray, size: int = 9) -> np.ndarray | None:
    """Detect the four playable corner intersections in camera_px (TL,TR,BR,BL).

    These are the 1-1, (size-1)-1, (size-1)-(size-1), 1-(size-1) playable
    intersections (not the outer edge of the board). Returns ``None`` on failure.
    """
    return detect_playable_corners(image_bgr, size=size)


def corners_to_jsonable(corners_camera_px: np.ndarray) -> dict:
    pts = np.asarray(corners_camera_px, dtype=np.float64).reshape(4, 2)
    return {
        "space": "camera_px",
        "order": "tl_tr_br_bl",
        "kind": "playable_intersections",
        "points": [[round(float(x)), round(float(y))] for x, y in pts.tolist()],
    }


def corners_from_jsonable(data: dict) -> np.ndarray:
    points = data.get("points", data)
    arr = np.asarray(points, dtype=np.float64)
    if arr.shape != (4, 2):
        raise ValueError(f"expected 4 corner points, got {arr.shape}")
    return order_corners_tl_tr_br_bl(arr)
