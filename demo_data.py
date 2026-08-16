"""Generate deterministic, realistic laser-line frames for a V-groove on a curved carrier."""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np


def imwrite_unicode(path: str | Path, image: np.ndarray) -> None:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".png", image)
    if not ok: raise ValueError(f"无法编码图像：{path}")
    encoded.tofile(str(path))


def _smooth_random_series(rng: np.random.Generator, count: int, scale: float, window: int) -> np.ndarray:
    raw = rng.normal(0.0, 1.0, count + window * 2)
    kernel = np.hanning(window); kernel /= kernel.sum()
    smooth = np.convolve(raw, kernel, mode="same")[window:-window]
    smooth -= smooth.mean(); peak = np.max(np.abs(smooth))
    return smooth / peak * scale if peak > 0 else smooth


def generate_demo_frames(output_dir: str | Path, frame_count: int = 181, width: int = 640,
                         height: int = 360, groove_depth_px: float = 60.0,
                         groove_half_width_px: float = 136.0, seed: int = 20260816) -> Path:
    """Generate a tight field of view: ~2.0 mm total width with a ~0.85 mm groove.

    The groove occupies a large proportion of the transverse field. Only short curved
    shoulders remain on both sides, matching the intended cylindrical/arc workpiece view.
    """
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    x = np.arange(width, dtype=float)
    xn = (x - width / 2.0) / (width / 2.0)

    depth_drift = _smooth_random_series(rng, frame_count, 0.75, 37)
    width_drift = _smooth_random_series(rng, frame_count, 1.8, 41)
    center_drift = _smooth_random_series(rng, frame_count, 1.6, 45)
    curve_drift = _smooth_random_series(rng, frame_count, 1.8, 51)
    baseline_drift = _smooth_random_series(rng, frame_count, 1.1, 47)
    brightness_drift = _smooth_random_series(rng, frame_count, 11.0, 35)

    for index in range(frame_count):
        phase = 2.0 * np.pi * index / max(frame_count - 1, 1)
        # Visible curved carrier. The edge-to-center sag is about 0.14~0.18 mm after scaling.
        curve_sag = 16.0 + curve_drift[index] + 0.7 * np.sin(1.31 * phase + 0.4)
        baseline = height * 0.31 + baseline_drift[index] + 0.35 * np.sin(2.1 * phase)
        carrier = baseline + curve_sag * xn**2
        carrier += 0.55 * np.sin(0.8 * np.pi * xn + 0.28 * phase)
        carrier += 0.35 * xn**3 * np.sin(1.7 * phase + 0.8)

        center = width / 2.0 + center_drift[index] + 0.45 * np.sin(2.7 * phase + 0.2)
        local_depth = groove_depth_px + depth_drift[index] + 0.20 * np.sin(4.1 * phase + 0.7)
        local_half_width = groove_half_width_px + width_drift[index] + 0.55 * np.sin(3.3 * phase)

        dx = x - center
        asym = 1.0 + 0.010 * np.sin(1.9 * phase + 0.5)
        effective_half = np.where(dx < 0, local_half_width / asym, local_half_width * asym)
        groove = np.clip(1.0 - np.abs(dx) / effective_half, 0.0, 1.0)
        centerline = carrier + local_depth * groove

        rough = rng.normal(0.0, 0.16, width)
        rough = np.convolve(rough, np.array([0.2, 0.6, 0.2]), mode="same")
        centerline += rough

        yy = np.arange(height, dtype=float)[:, None]
        background = 9.0 + 2.0 * yy / height + rng.normal(0.0, 2.2, size=(height, width))
        image = np.clip(background, 0, 255).astype(np.uint8)
        peak = int(np.clip(238 + brightness_drift[index], 212, 252))
        shoulder = int(np.clip(152 + 0.45 * brightness_drift[index], 128, 178))
        halo = int(np.clip(66 + 0.20 * brightness_drift[index], 52, 80))
        for column, row_float in enumerate(centerline):
            row = int(round(row_float))
            for offset, intensity in ((-2, halo), (-1, shoulder), (0, peak), (1, shoulder), (2, halo)):
                rr = row + offset
                if 0 <= rr < height:
                    image[rr, column] = max(int(image[rr, column]), intensity)

        for _ in range(int(rng.integers(70, 120))):
            rr = int(rng.integers(0, height)); cc = int(rng.integers(0, width))
            image[rr, cc] = max(int(image[rr, cc]), int(rng.integers(20, 74)))
        if index % 31 in (9, 10):
            cx = int(width * (0.18 + 0.64 * rng.random())); cy = int(height * (0.15 + 0.62 * rng.random()))
            cv2.circle(image, (cx, cy), int(rng.integers(2, 4)), int(rng.integers(28, 48)), -1)
        image = cv2.GaussianBlur(image, (3, 3), 0.72)
        imwrite_unicode(output / f"frame_{index:05d}.png", image)
    return output


def ensure_demo_frames(output_dir: str | Path, frame_count: int = 181) -> Path:
    output = Path(output_dir)
    existing = sorted(output.glob("frame_*.*")) if output.exists() else []
    if len(existing) != frame_count:
        for file in existing: file.unlink(missing_ok=True)
        generate_demo_frames(output, frame_count=frame_count)
    return output
