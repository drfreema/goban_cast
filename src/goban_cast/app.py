"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from goban_cast import __version__
from goban_cast.capture.source import CameraSource, LatestFrameReader, probe_device
from goban_cast.geometry import Orientation
from goban_cast.vision.board import BoardGeometry, order_corners_tl_tr_br_bl
from goban_cast.vision.corners import corners_to_jsonable, detect_board_corners
from goban_cast.vision.detect import compute_baseline_means, detect_board
from goban_cast.vision.draw import draw_grid, draw_state
from goban_cast.vision.state import load_corners, read_state_from_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="goban-cast",
        description="Read a physical Go board with a webcam and overlay the game state.",
    )
    parser.add_argument("--version", action="version", version=f"goban_cast {__version__}")
    parser.add_argument("--size", type=int, default=9, help="board size (default: 9)")
    parser.add_argument("--device", default=None, help="camera device path/index")
    parser.add_argument("--image", default=None, help="read a single image instead of a device")
    parser.add_argument("--corners", default=None, help="corners JSON (camera_px, TL TR BR BL)")
    parser.add_argument("--auto-corners", action="store_true", help="detect corners automatically")
    parser.add_argument("--rotation", type=int, default=0, choices=[0, 90, 180, 270])
    parser.add_argument("--mirror", action="store_true")
    parser.add_argument("--dump-state", action="store_true", help="print detected state as JSON")
    parser.add_argument("--probe", action="store_true", help="probe camera/device and print JSON")
    parser.add_argument("--save-frames", metavar="DIR", default=None, help="save N frames to DIR")
    parser.add_argument("--count", type=int, default=10, help="number of frames for --save-frames/--probe")
    parser.add_argument("--save-corners", metavar="PATH", default=None, help="write detected/resolved corners JSON")
    parser.add_argument("--save-debug", metavar="PATH", default=None, help="write debug image with grid/state")
    parser.add_argument(
        "--baseline-image",
        default=None,
        help="empty-board image used as per-intersection baseline for detection",
    )
    parser.add_argument(
        "--preview",
        nargs="?",
        const="live",
        metavar="DEVICE_OR_PROFILE",
        help="show live camera preview window with grid/rotation (M1)",
    )
    parser.add_argument(
        "--game",
        metavar="ID",
        type=int,
        help="attach to an existing online-go.com game id (M5)",
    )
    return parser


def _load_image(path: str) -> np.ndarray:
    image = cv2.imread(path)
    if image is None:
        raise ValueError(f"failed to read image: {path}")
    return image


def _resolve_image(args: argparse.Namespace) -> np.ndarray | None:
    if args.image:
        return _load_image(args.image)
    if args.device:
        with CameraSource(args.device) as src:
            frame = src.read()
        if frame is None:
            raise ValueError(f"failed to capture frame from {args.device}")
        return frame.image_bgr
    return None


def _resolve_corners(args: argparse.Namespace, image_bgr: np.ndarray | None) -> np.ndarray | None:
    if args.corners:
        return load_corners(args.corners)
    if args.auto_corners:
        if image_bgr is None:
            return None
        corners = detect_board_corners(image_bgr, size=args.size)
        if corners is None:
            raise ValueError("could not auto-detect board corners")
        return corners
    return None


def _baseline_means_for(
    image_bgr: np.ndarray, corners: np.ndarray, *, size: int
) -> np.ndarray:
    geometry = BoardGeometry.from_corners(corners, size=size)
    return compute_baseline_means(image_bgr, geometry)


def cmd_dump_state(args: argparse.Namespace) -> int:
    image = _resolve_image(args)
    if image is None:
        print("--dump-state requires --image or --device", file=sys.stderr)
        return 2
    corners = _resolve_corners(args, image)
    if corners is None:
        print("--dump-state requires --corners or --auto-corners", file=sys.stderr)
        return 2
    orientation = Orientation(args.rotation)
    baseline = None
    if args.baseline_image:
        baseline = _baseline_means_for(_load_image(args.baseline_image), corners, size=args.size)
    readout = read_state_from_image(
        image,
        size=args.size,
        corners_camera_px=corners,
        orientation=orientation,
        mirror=args.mirror,
        baseline_means=baseline,
    )
    data = readout.to_dict()
    if args.save_corners:
        Path(args.save_corners).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save_corners).write_text(json.dumps(corners_to_jsonable(corners), indent=2))
    if args.save_debug:
        geometry = BoardGeometry.from_corners(
            corners, size=args.size, orientation=orientation, mirror=args.mirror
        )
        debug = draw_state(draw_grid(image, geometry), geometry, data["state"])
        Path(args.save_debug).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(args.save_debug, debug)
    print(json.dumps(data, indent=2))
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    device = args.device or "/dev/video0"
    result = probe_device(device, frames=max(1, args.count))
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.opened else 1


def cmd_save_frames(args: argparse.Namespace) -> int:
    if not args.device:
        print("--save-frames requires --device", file=sys.stderr)
        return 2
    out = Path(args.save_frames)
    out.mkdir(parents=True, exist_ok=True)
    saved = 0
    with CameraSource(args.device) as src:
        for _ in range(5):
            src.read(timeout_s=2.0)
        for i in range(args.count):
            frame = src.read(timeout_s=5.0)
            if frame is None:
                break
            cv2.imwrite(str(out / f"frame_{i:02d}.png"), frame.image_bgr)
            saved += 1
    print(json.dumps({"saved": saved, "dir": str(out)}, indent=2))
    return 0 if saved else 1


def cmd_preview(args: argparse.Namespace) -> int:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except Exception as exc:  # pragma: no cover - environment dependent
        print(f"PySide6 unavailable: {exc}", file=sys.stderr)
        return 2

    device = args.device
    if not device:
        candidate = args.preview
        if candidate and candidate != "live" and not candidate.endswith(".toml"):
            device = candidate
    if not device:
        print("--preview requires --device (or a device argument)", file=sys.stderr)
        return 2

    def apply_view_image(image_bgr: np.ndarray, orientation: Orientation) -> np.ndarray:
        """Rotate camera image (camera_px frame) for display."""
        deg = int(orientation) % 360
        if deg == 90:
            return cv2.rotate(image_bgr, cv2.ROTATE_90_CLOCKWISE)
        if deg == 180:
            return cv2.rotate(image_bgr, cv2.ROTATE_180)
        if deg == 270:
            return cv2.rotate(image_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return image_bgr

    def _rot_pt_fwd(x: float, y: float, w: float, h: float, deg: int) -> tuple[float, float]:
        if deg == 90:
            return h - 1.0 - y, x
        if deg == 180:
            return w - 1.0 - x, h - 1.0 - y
        if deg == 270:
            return y, w - 1.0 - x
        return x, y

    def orig_to_view_pts(
        pts_xy: np.ndarray, orig_hw: tuple[int, int], orientation: Orientation
    ) -> np.ndarray:
        """Map points from original camera_px image to rotated display image pixels."""
        pts = np.asarray(pts_xy, dtype=np.float64)
        if pts.size == 0:
            return pts.reshape(-1, 2)
        h, w = float(orig_hw[0]), float(orig_hw[1])
        deg = int(orientation) % 360
        out = np.empty_like(pts, dtype=np.float64)
        for i, (x, y) in enumerate(pts.reshape(-1, 2)):
            out[i, 0], out[i, 1] = _rot_pt_fwd(float(x), float(y), w, h, deg)
        return out

    def view_to_orig_pts(
        pts_xy: np.ndarray, view_hw: tuple[int, int], orientation: Orientation
    ) -> np.ndarray:
        """Map points from rotated display image pixels back to original camera_px."""
        pts = np.asarray(pts_xy, dtype=np.float64)
        if pts.size == 0:
            return pts.reshape(-1, 2)
        deg = int(orientation) % 360
        inv_deg = (-deg) % 360
        vw, vh = float(view_hw[1]), float(view_hw[0])
        if deg in (90, 270):
            orig_w, orig_h = vh, vw
        else:
            orig_w, orig_h = vw, vh
        out = np.empty_like(pts, dtype=np.float64)
        for i, (x, y) in enumerate(pts.reshape(-1, 2)):
            x2, y2 = _rot_pt_fwd(float(x), float(y), vw, vh, inv_deg)
            out[i, 0] = min(max(x2, 0.0), orig_w - 1.0)
            out[i, 1] = min(max(y2, 0.0), orig_h - 1.0)
        return out

    class PreviewWindow(QtWidgets.QLabel):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("goban_cast preview (M1)")
            self.resize(960, 540)
            self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
            self.orientation = Orientation(args.rotation)
            self.board_size = int(args.size)
            # stored in original camera_px space for stability across view changes
            self.clicked_camera_px: list[list[float]] = []
            self.corners_camera_px: np.ndarray | None = (
                load_corners(args.corners) if args.corners else None
            )
            self.auto_corners = bool(args.auto_corners)
            self.baseline: np.ndarray | None = None
            self._status = "r rotate, c clear, a auto, s save corners, q quit"
            self._flash_status: str | None = None
            self._flash_until = 0.0

            self._lock = threading.Lock()
            self._latest_view_shape: tuple[int, int] | None = None  # (h, w) of displayed image
            self._latest_qimage: QtGui.QImage | None = None
            self._stop = threading.Event()

            self.reader = LatestFrameReader(CameraSource(device))
            self.reader.start()
            self.worker = threading.Thread(target=self._process_loop, daemon=True)
            self.worker.start()

            self.timer = QtCore.QTimer(self)
            self.timer.timeout.connect(self._update_pixmap)
            self.timer.start(33)
            self.setFocus()

        def _process_loop(self) -> None:
            while not self._stop.is_set():
                frame = self.reader.latest()
                if frame is None:
                    time.sleep(0.01)
                    continue
                orig = frame.image_bgr
                orig_h, orig_w = orig.shape[:2]
                orientation = self.orientation
                board_size = self.board_size
                corners_cam = self.corners_camera_px
                clicked_cam = list(self.clicked_camera_px)
                auto = self.auto_corners

                # Auto-detect playable corners on original image, keep in camera_px.
                if corners_cam is None and auto and not clicked_cam:
                    try:
                        detected = detect_board_corners(orig, size=board_size)
                    except Exception:
                        detected = None
                    if detected is not None:
                        corners_cam = detected
                        self.corners_camera_px = detected
                        self.auto_corners = False
                        self._flash_status = "corners detected"
                        self._flash_until = time.monotonic() + 1.5

                # Rotate the displayed camera image so view changes are visible.
                view_img = apply_view_image(orig, orientation)
                disp = view_img.copy()
                try:
                    if corners_cam is not None and len(np.asarray(corners_cam)) == 4:
                        corners_view = orig_to_view_pts(
                            np.asarray(corners_cam, dtype=np.float64),
                            (orig_h, orig_w),
                            orientation,
                        )
                        geometry = BoardGeometry.from_corners(
                            corners_view, size=board_size, orientation=Orientation.DEG_0
                        )
                        # Detection sampling should happen on the same image we draw on.
                        state = detect_board(view_img, geometry, baseline_means=self.baseline)
                        disp = draw_state(draw_grid(view_img, geometry), geometry, state)
                except Exception:
                    disp = view_img.copy()

                # Draw pending manual corner picks in the displayed view.
                if clicked_cam:
                    clicked_view = orig_to_view_pts(
                        np.asarray(clicked_cam, dtype=np.float64),
                        (orig_h, orig_w),
                        orientation,
                    )
                    for i, pt in enumerate(clicked_view):
                        p = (round(float(pt[0])), round(float(pt[1])))
                        cv2.circle(disp, p, 7, (255, 0, 0), 2)
                        cv2.putText(
                            disp,
                            str(i),
                            (p[0] + 6, p[1] - 6),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (255, 0, 0),
                            2,
                        )

                computed = self._status
                if corners_cam is not None and not clicked_cam:
                    computed = f"rot {int(orientation)}° | r rotate c clear a auto s save q quit"
                if self._flash_status and time.monotonic() < self._flash_until:
                    status = self._flash_status
                else:
                    status = computed
                cv2.putText(
                    disp,
                    status,
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (50, 255, 50),
                    2,
                )

                rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
                vh, vw, ch = rgb.shape
                qimg = QtGui.QImage(
                    rgb.data, vw, vh, ch * vw, QtGui.QImage.Format.Format_RGB888
                ).copy()
                with self._lock:
                    self._latest_qimage = qimg
                    self._latest_view_shape = (vh, vw)
                time.sleep(0.005)

        def _label_image_rect(self) -> tuple[float, float, float, float] | None:
            with self._lock:
                shape = self._latest_view_shape
            if shape is None:
                return None
            ih, iw = shape
            lw, lh = max(1, self.width()), max(1, self.height())
            scale = min(lw / iw, lh / ih)
            pw, ph = iw * scale, ih * scale
            ox = (lw - pw) / 2.0
            oy = (lh - ph) / 2.0
            return ox, oy, pw, ph

        def _update_pixmap(self) -> None:
            with self._lock:
                qimg = self._latest_qimage
            if qimg is None:
                return
            pix = QtGui.QPixmap.fromImage(qimg)
            self.setPixmap(
                pix.scaled(
                    self.size(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
            )

        def mousePressEvent(self, event) -> None:
            rect = self._label_image_rect()
            if rect is None:
                return
            ox, oy, pw, ph = rect
            with self._lock:
                view_shape = self._latest_view_shape
            if view_shape is None or pw <= 0 or ph <= 0:
                return
            ih, iw = view_shape
            x = event.position().x() - ox
            y = event.position().y() - oy
            if x < 0 or y < 0 or x >= pw or y >= ph:
                return
            view_x = float(x * (iw / pw))
            view_y = float(y * (ih / ph))
            orig_pt = view_to_orig_pts(
                np.array([[view_x, view_y]], dtype=np.float64),
                view_shape,
                self.orientation,
            )[0]
            self.clicked_camera_px.append([float(orig_pt[0]), float(orig_pt[1])])
            if len(self.clicked_camera_px) == 4:
                clicked_view = orig_to_view_pts(
                    np.asarray(self.clicked_camera_px, dtype=np.float64),
                    view_shape,
                    self.orientation,
                )
                ordered_view = order_corners_tl_tr_br_bl(clicked_view)
                ordered_orig = view_to_orig_pts(ordered_view, view_shape, self.orientation)
                self.corners_camera_px = ordered_orig
                self.clicked_camera_px = []
                self.auto_corners = False
                self._flash_status = "corners set from clicks"
                self._flash_until = time.monotonic() + 2.0

        def keyPressEvent(self, event) -> None:
            key = event.key()
            text = (event.text() or "").lower()
            if key in (QtCore.Qt.Key.Key_Q, QtCore.Qt.Key.Key_Escape):
                self.close()
            elif key == QtCore.Qt.Key.Key_R or text == "r":
                steps = [0, 90, 180, 270]
                idx = steps.index(int(self.orientation))
                self.orientation = Orientation(steps[(idx + 1) % 4])
                self._flash_status = f"rotation {int(self.orientation)}°"
                self._flash_until = time.monotonic() + 2.0
                print(f"orientation: {int(self.orientation)}", flush=True)
            elif key == QtCore.Qt.Key.Key_C or text == "c":
                self.clicked_camera_px = []
                self.corners_camera_px = None
                self.auto_corners = False
                self._flash_status = "cleared | click 4 playable corners TL,TR,BR,BL or press a"
                self._flash_until = time.monotonic() + 3.0
                print("corners cleared", flush=True)
            elif key == QtCore.Qt.Key.Key_A or text == "a":
                self.corners_camera_px = None
                self.clicked_camera_px = []
                self.auto_corners = True
                self._flash_status = "auto-detecting playable corners..."
                self._flash_until = time.monotonic() + 5.0
                print("auto-detecting corners...", flush=True)
            elif key == QtCore.Qt.Key.Key_S or text == "s":
                if self.corners_camera_px is None:
                    self._flash_status = "no corners to save (detect or click 4 corners first)"
                    self._flash_until = time.monotonic() + 2.5
                    print("save skipped: no corners", flush=True)
                else:
                    out = Path(args.save_corners or "corners.json")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(
                        json.dumps(corners_to_jsonable(self.corners_camera_px), indent=2) + "\n"
                    )
                    self._flash_status = f"saved corners -> {out}"
                    self._flash_until = time.monotonic() + 4.0
                    self._status = f"saved corners -> {out}"
                    print(f"saved corners -> {out}", flush=True)

        def closeEvent(self, event) -> None:
            self._stop.set()
            self.timer.stop()
            self.reader.stop()
            self.worker.join(timeout=2.0)
            super().closeEvent(event)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    win = PreviewWindow()
    win.show()
    win.raise_()
    win.activateWindow()
    win.setFocus()
    return int(app.exec())


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.preview and args.game is not None:
        print("--preview and --game are not supported together yet", file=sys.stderr)
        return 2

    if args.probe:
        return cmd_probe(args)
    if args.save_frames is not None:
        return cmd_save_frames(args)
    if args.dump_state:
        return cmd_dump_state(args)
    if args.preview:
        return cmd_preview(args)

    print(
        f"goban_cast {__version__} (pre-alpha, M1). "
        "Use --probe, --save-frames, --dump-state, or --preview; see docs/plan.md."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
