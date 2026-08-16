"""Generate deterministic, realistic laser-line demo frames on a curved workpiece."""
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


def _smooth_random_series(rng: np.random.Generator, count: int, scale: float, window: int = 31) -> np.ndarray:
    """Low-frequency correlated variation, closer to machining/scan drift than white noise."""
    raw = rng.normal(0.0, 1.0, count + window * 2)
    kernel = np.hanning(window)
    kernel /= kernel.sum()
    smooth = np.convolve(raw, kernel, mode="same")[window:-window]
    smooth -= smooth.mean()
    peak = np.max(np.abs(smooth))
    return smooth / peak * scale if peak > 0 else smooth


def generate_demo_frames(
    output_dir: str | Path,
    frame_count: int = 181,
    width: int = 640,
    height: int = 360,
    groove_depth_px: float = 60.0,
    groove_half_width_px: float = 21.25,
    seed: int = 20260816,
) -> Path:
    """Create dense laser scans of a V-groove machined into a gently curved surface.

    The surface is intentionally not perfectly regular: groove dimensions, center position,
    curvature, illumination and texture vary smoothly along the scan direction.  The random
    seed keeps the competition demo reproducible.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    x = np.arange(width, dtype=float)
    xn = (x - width / 2.0) / (width / 2.0)

    # Correlated variations along Y/scan direction.  Amplitudes are deliberately small.
    depth_drift = _smooth_random_series(rng, frame_count, 0.70, 37)
    width_drift = _smooth_random_series(rng, frame_count, 0.28, 41)
    center_drift = _smooth_random_series(rng, frame_count, 1.35, 45)
    curve_drift = _smooth_random_series(rng, frame_count, 1.10, 51)
    baseline_drift = _smooth_random_series(rng, frame_count, 1.20, 47)
    brightness_drift = _smooth_random_series(rng, frame_count, 12.0, 35)

    for index in range(frame_count):
        phase = 2.0 * np.pi * index / max(frame_count - 1, 1)

        # A shallow cylindrical/arc-like carrier surface.  A tiny cubic term and smooth
        # frame-to-frame change prevent the reconstructed carrier from looking artificial.
        curve_sag = 20.0 + curve_drift[index] + 0.7 * np.sin(1.37 * phase + 0.4)
        baseline = height * 0.34 + baseline_drift[index] + 0.45 * np.sin(2.13 * phase)
        carrier = baseline + curve_sag * xn**2 + 0.75 * np.sin(0.65 * np.pi * xn + 0.3 * phase)
        carrier += 0.55 * xn**3 * np.sin(1.7 * phase + 0.8)

        center = width / 2.0 + center_drift[index] + 0.55 * np.sin(2.7 * phase + 0.2)
        local_depth = groove_depth_px + depth_drift[index] + 0.22 * np.sin(4.1 * phase + 0.7)
        local_half_width = groove_half_width_px + width_drift[index] + 0.08 * np.sin(3.3 * phase)

        # V-groove cut into the curved carrier.  Slight flank asymmetry mimics machining
        # variation while keeping the nominal 0.600 mm depth / 0.850 mm width scale.
        dx = x - center
        asym = 1.0 + 0.012 * np.sin(1.9 * phase + 0.5)
        effective_half = np.where(dx < 0, local_half_width / asym, local_half_width * asym)
        groove = np.clip(1.0 - np.abs(dx) / effective_half, 0.0, 1.0)
        centerline = carrier + local_depth * groove

        # Sub-pixel correlated roughness: small enough not to dominate the geometry.
        rough = rng.normal(0.0, 0.18, width)
        rough = np.convolve(rough, np.array([0.2, 0.6, 0.2]), mode="same")
        centerline += rough

        # Dark sensor background with mild vertical illumination gradient and speckle.
        yy = np.arange(height, dtype=float)[:, None]
        background = 9.0 + 2.0 * yy / height + rng.normal(0.0, 2.4, size=(height, width))
        image = np.clip(background, 0, 255).astype(np.uint8)

        peak = int(np.clip(238 + brightness_drift[index], 210, 252))
        shoulder = int(np.clip(150 + 0.45 * brightness_drift[index], 125, 175))
        halo = int(np.clip(66 + 0.20 * brightness_drift[index], 52, 80))
        for column, row_float in enumerate(centerline):
            row = int(round(row_float))
            for offset, intensity in ((-2, halo), (-1, shoulder), (0, peak), (1, shoulder), (2, halo)):
                rr = row + offset
                if 0 <= rr < height:
                    image[rr, column] = max(int(image[rr, column]), intensity)

        # Sparse sensor/hot-pixel-like clutter.  Count and intensity vary by frame.
        speckles = int(rng.integers(70, 125))
        for _ in range(speckles):
            rr = int(rng.integers(0, height))
            cc = int(rng.integers(0, width))
            image[rr, cc] = max(int(image[rr, cc]), int(rng.integers(20, 78)))

        # Occasional weak local glare, deliberately kept away from the main line intensity.
        if index % 29 in (7, 8):
            cx = int(width * (0.20 + 0.55 * rng.random()))
            cy = int(height * (0.18 + 0.58 * rng.random()))
            cv2.circle(image, (cx, cy), int(rng.integers(2, 5)), int(rng.integers(28, 52)), -1)

        image = cv2.GaussianBlur(image, (3, 3), 0.72)
        imwrite_unicode(output / f"frame_{index:05d}.png", image)

    return output


def ensure_demo_frames(output_dir: str | Path, frame_count: int = 181) -> Path:
    output = Path(output_dir)
    existing = sorted(output.glob("frame_*.*")) if output.exists() else []
    if len(existing) != frame_count:
        for file in existing:
            file.unlink(missing_ok=True)
        generate_demo_frames(output, frame_count=frame_count)
    return output
