"""Dump detected 9x9 state from an image or device (headless)."""

from __future__ import annotations

import argparse
import json

import cv2

from goban_cast.capture.source import CameraSource
from goban_cast.geometry import Orientation
from goban_cast.vision.state import load_corners, read_state_from_image


def main() -> int:
    p = argparse.ArgumentParser()
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--image")
    src.add_argument("--device")
    p.add_argument("--corners", help="JSON file with {points:[[x,y]..]} in camera_px TL,TR,BR,BL")
    p.add_argument("--size", type=int, default=9)
    p.add_argument("--rotation", type=int, default=0, choices=[0, 90, 180, 270])
    p.add_argument("--mirror", action="store_true")
    args = p.parse_args()

    if args.image:
        image = cv2.imread(args.image)
        if image is None:
            raise SystemExit(f"failed to read {args.image}")
    else:
        with CameraSource(args.device) as cam:
            frame = cam.read()
        if frame is None:
            raise SystemExit("failed to capture frame")
        image = frame.image_bgr

    corners = load_corners(args.corners) if args.corners else None
    readout = read_state_from_image(
        image,
        size=args.size,
        corners_camera_px=corners,
        orientation=Orientation(args.rotation),
        mirror=args.mirror,
    )
    print(json.dumps(readout.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
