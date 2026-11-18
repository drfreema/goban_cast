"""Frame capture from a video device.

Coordinate space: frames are raw camera images in ``camera_px`` space.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class Frame:
    """A single camera frame."""

    image_bgr: np.ndarray
    timestamp: float
    index: int


@dataclass(frozen=True)
class ProbeResult:
    device: str
    opened: bool
    backend: str
    width: int | None = None
    height: int | None = None
    fps_reported: float | None = None
    fourcc: str | None = None
    frame_count: int = 0
    first_frame_ms: float | None = None
    mean_ms: float | None = None

    def to_dict(self) -> dict:
        return {
            "device": self.device,
            "opened": self.opened,
            "backend": self.backend,
            "width": self.width,
            "height": self.height,
            "fps_reported": self.fps_reported,
            "fourcc": self.fourcc,
            "frame_count": self.frame_count,
            "first_frame_ms": self.first_frame_ms,
            "mean_ms": self.mean_ms,
        }


def _decode_fourcc(value: float) -> str | None:
    try:
        code = int(value)
    except (TypeError, ValueError):
        return None
    if code <= 0:
        return None
    chars = [chr((code >> (8 * i)) & 0xFF) for i in range(4)]
    text = "".join(chars)
    return text if text.strip("\x00") else None


class CameraSource:
    """OpenCV-backed camera source.

    ``device`` may be a device path/index string or an image/video path for tests.
    """

    def __init__(
        self,
        device: str | int = 0,
        *,
        width: int | None = None,
        height: int | None = None,
        fps: float | None = None,
        api_preference: int = cv2.CAP_ANY,
    ) -> None:
        self.device = device
        self.requested_width = width
        self.requested_height = height
        self.requested_fps = fps
        self.api_preference = api_preference
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> cv2.VideoCapture:
        if self._cap is not None and self._cap.isOpened():
            return self._cap
        dev = self.device
        if isinstance(dev, str) and dev.isdigit():
            dev = int(dev)
        cap = cv2.VideoCapture(dev, self.api_preference)
        if not cap.isOpened() and self.api_preference != cv2.CAP_ANY:
            cap = cv2.VideoCapture(dev)
        if self.requested_width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.requested_width))
        if self.requested_height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.requested_height))
        if self.requested_fps:
            cap.set(cv2.CAP_PROP_FPS, float(self.requested_fps))
        # Prefer low-latency reads where supported.
        with contextlib.suppress(Exception):
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap
        return cap

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def read(self, *, timeout_s: float = 5.0) -> Frame | None:
        cap = self.open()
        if not cap.isOpened():
            return None
        deadline = time.monotonic() + timeout_s
        index = int(cap.get(cv2.CAP_PROP_POS_FRAMES) or 0)
        while time.monotonic() < deadline:
            ok, image = cap.read()
            if ok and image is not None:
                return Frame(image_bgr=image, timestamp=time.time(), index=index)
            # For live cameras a failed read can be transient; for files it means EOF.
            if isinstance(self.device, str) and Path(self.device).is_file():
                return None
            time.sleep(0.01)
        return None

    def frames(self, *, max_frames: int | None = None) -> Iterator[Frame]:
        count = 0
        while max_frames is None or count < max_frames:
            frame = self.read()
            if frame is None:
                return
            yield frame
            count += 1

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> CameraSource:
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class LatestFrameReader:
    """Background reader that keeps only the newest frame (drop-old-frames)."""

    def __init__(self, source: CameraSource) -> None:
        self.source = source
        self._lock = threading.Lock()
        self._latest: Frame | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="capture-reader", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            frame = self.source.read(timeout_s=1.0)
            if frame is None:
                if isinstance(self.source.device, str) and Path(self.source.device).is_file():
                    return
                continue
            with self._lock:
                self._latest = frame

    def latest(self) -> Frame | None:
        with self._lock:
            return self._latest

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self.source.release()


def probe_device(device: str | int, *, frames: int = 10, warmup: int = 3) -> ProbeResult:
    cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(device)
    backend = cap.getBackendName() if cap.isOpened() else ""
    if not cap.isOpened():
        return ProbeResult(device=str(device), opened=False, backend=backend)
    try:
        for _ in range(max(0, warmup)):
            cap.read()
        times = []
        got = 0
        shape = None
        first_ms = None
        start = time.monotonic()
        for _ in range(frames):
            t0 = time.monotonic()
            ok, frame = cap.read()
            t1 = time.monotonic()
            if not ok or frame is None:
                continue
            got += 1
            shape = frame.shape
            dt = (t1 - t0) * 1000.0
            if first_ms is None:
                first_ms = (t0 - start) * 1000.0
            times.append(dt)
        return ProbeResult(
            device=str(device),
            opened=True,
            backend=backend,
            width=int(shape[1]) if shape is not None else None,
            height=int(shape[0]) if shape is not None else None,
            fps_reported=float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or None,
            fourcc=_decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC)),
            frame_count=got,
            first_frame_ms=first_ms,
            mean_ms=float(np.mean(times)) if times else None,
        )
    finally:
        cap.release()
