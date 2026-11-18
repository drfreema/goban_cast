from __future__ import annotations

from goban_cast.capture.source import CameraSource


def test_camera_source_reads_image_file(tmp_path):
    # OpenCV can read image paths via VideoCapture in our wrapper.
    import cv2
    import numpy as np

    img = np.zeros((32, 48, 3), dtype=np.uint8)
    img[:] = (10, 20, 30)
    path = tmp_path / "frame.png"
    cv2.imwrite(str(path), img)
    with CameraSource(str(path)) as src:
        frame = src.read(timeout_s=1.0)
    assert frame is not None
    assert frame.image_bgr.shape == (32, 48, 3)
