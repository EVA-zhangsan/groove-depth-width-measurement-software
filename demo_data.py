"""Generate deterministic laser-line demo frames."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def imwrite_unicode(path: str | Path, image: np.ndarray) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    extension = path.suffix or ".png"
    ok, encoded = cv2.imencode(extension, image)
    if not ok:
        raise ValueError(f"无法编码图像：{path}")
    encoded.tofile(str(path))


def generate_demo_frames(
    output_dir: str | Path,
    frame_count: int = 31,
    width: int = 640,
    height: int = 360,
    groove_depth_px: float = 60.0,
    groove_half_width_px: float = 21.25,
    seed: int = 42,
) -> Path:
    """Create grayscale images containing a slightly varying V-shaped laser profile."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    x = np.arange(width, dtype=float)

    for index in range(frame_count):
        baseline = height * 0.36 + 1.6 * np.sin(index / 4.0)
        center = width / 2.0 + 2.0 * np.sin(index / 5.0)
        local_depth = groove_depth_px + 0.55 * np.sin(index / 3.0)
        local_half_width = groove_half_width_px + 0.18 * np.cos(index / 4.0)
        v_shape = np.clip(1.0 - np.abs(x - center) / local_half_width, 0.0, 1.0)
        centerline = baseline + local_depth * v_shape

        image = rng.normal(10.0, 2.5, size=(height, width)).clip(0, 255).astype(np.uint8)
        for column, row_float in enumerate(centerline):
            row = int(round(row_float))
            for offset, intensity in ((-2, 70), (-1, 155), (0, 245), (1, 155), (2, 70)):
                rr = row + offset
                if 0 <= rr < height:
                    image[rr, column] = max(int(image[rr, column]), intensity)

        for _ in range(90):
            rr = int(rng.integers(0, height))
            cc = int(rng.integers(0, width))
            image[rr, cc] = int(rng.integers(20, 75))

        image = cv2.GaussianBlur(image, (3, 3), 0.7)
        imwrite_unicode(output / f"frame_{index:05d}.png", image)

    return output


def ensure_demo_frames(output_dir: str | Path, frame_count: int = 31) -> Path:
    output = Path(output_dir)
    existing = sorted(output.glob("frame_*.*")) if output.exists() else []
    if len(existing) != frame_count:
        for file in existing:
            file.unlink(missing_ok=True)
        generate_demo_frames(output, frame_count=frame_count)
    return output
