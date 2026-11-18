"""Probe a camera device and optionally save sample frames."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

from goban_cast.capture.source import CameraSource, probe_device


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--device", default="/dev/video42")
    p.add_argument("--frames", type=int, default=10)
    p.add_argument("--save-dir", default=None)
    args = p.parse_args()
    result = probe_device(args.device, frames=args.frames)
    print(json.dumps(result.to_dict(), indent=2))
    if args.save_dir:
        out = Path(args.save_dir)
        out.mkdir(parents=True, exist_ok=True)
        with CameraSource(args.device) as src:
            for i in range(args.frames):
                frame = src.read()
                if frame is None:
                    break
                cv2.imwrite(str(out / f"frame_{i:02d}.png"), frame.image_bgr)
        print(f"saved to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
