"""Generate deterministic structure-light scan test sequences.

The generated images are software test data. They emulate common optical
perturbations (noise, intensity variation, stripe jitter and small geometry
variation) and are not a substitute for metrology-grade hardware validation.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def imwrite_unicode(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        raise ValueError(f"无法编码图像：{path}")
    encoded.tofile(str(path))


def generate_complex_scan_sequence(
    output_dir: str | Path,
    frame_count: int = 61,
    width: int = 640,
    height: int = 360,
    seed: int = 20260815,
) -> Path:
    """Generate a V-groove laser sequence with realistic, bounded disturbances.

    Geometry is centered around 0.600 mm depth and 0.850 mm width under the
    default reconstruction scales (0.010 mm/px in Z, 0.020 mm/px in X).
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob("frame_*.*"):
        old.unlink(missing_ok=True)

    rng = np.random.default_rng(seed)
    x = np.arange(width, dtype=float)
    yy, xx = np.mgrid[0:height, 0:width]

    # Smooth illumination field and vignetting to avoid an ideal black canvas.
    radial = ((xx - width / 2.0) / (width / 2.0)) ** 2 + ((yy - height / 2.0) / (height / 2.0)) ** 2
    illumination = 14.0 + 3.5 * (yy / height) - 2.2 * np.clip(radial, 0, 1.5)

    for index in range(frame_count):
        phase = 2.0 * np.pi * index / frame_count

        # Scan-to-scan pose drift and mild surface waviness.
        baseline_scalar = height * 0.36 + 2.8 * np.sin(phase * 1.25) + 0.7 * np.sin(index / 2.9)
        baseline = (
            baseline_scalar
            + 0.65 * (x - width / 2.0) / width
            + 0.35 * np.sin(x / 86.0 + phase * 0.8)
        )

        # The groove center is not perfectly straight along the scan direction.
        groove_center = width / 2.0 + 5.0 * np.sin(phase) + 1.2 * np.sin(index / 3.1)

        # Bounded geometry variation, kept inside the nominal ±0.020 mm task tolerance.
        depth_px = 60.0 + 0.65 * np.sin(index / 4.4) + 0.22 * np.cos(index / 2.8)
        half_width_px = 21.25 + 0.16 * np.sin(index / 5.2) + 0.07 * np.cos(index / 3.7)
        v_profile = np.clip(1.0 - np.abs(x - groove_center) / half_width_px, 0.0, 1.0)

        # A tiny rounded-apex contribution makes the stripe less mathematically ideal
        # while keeping the sidewalls close to linear for the current fitting method.
        rounded = np.exp(-0.5 * ((x - groove_center) / 2.2) ** 2)
        centerline = baseline + depth_px * v_profile + 0.40 * rounded

        frame_gain = 0.92 + 0.11 * np.sin(index / 6.0) + 0.035 * rng.normal()
        image = illumination + rng.normal(0.0, 4.2, size=(height, width))

        # Column-wise laser power fluctuation and local attenuation windows.
        column_gain = 0.93 + 0.10 * np.sin(x / 41.0 + phase * 1.7) + rng.normal(0.0, 0.025, size=width)
        column_gain = np.clip(column_gain, 0.72, 1.12)
        for _ in range(2):
            start = int(rng.integers(35, width - 80))
            length = int(rng.integers(18, 48))
            column_gain[start:start + length] *= float(rng.uniform(0.62, 0.80))

        # Gaussian laser stripe with variable thickness and a weak optical halo.
        sigma = 1.15 + 0.12 * np.sin(index / 7.0)
        halo_sigma = sigma * 2.8
        rows = np.arange(height, dtype=float)[:, None]
        distance = rows - centerline[None, :]
        core = 228.0 * np.exp(-0.5 * (distance / sigma) ** 2)
        halo = 27.0 * np.exp(-0.5 * (distance / halo_sigma) ** 2)
        image += frame_gain * column_gain[None, :] * (core + halo)

        # Sparse reflective/dust artifacts away from the stripe.
        for _ in range(75):
            rr = int(rng.integers(0, height))
            cc = int(rng.integers(0, width))
            image[max(0, rr - 1):min(height, rr + 2), max(0, cc - 1):min(width, cc + 2)] += float(rng.uniform(10, 42))

        image = np.clip(image, 0, 255).astype(np.uint8)
        image = cv2.GaussianBlur(image, (3, 3), 0.75)
        imwrite_unicode(output / f"frame_{index:05d}.png", image)

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="生成结构光槽型软件测试图像序列")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=61)
    args = parser.parse_args()
    generate_complex_scan_sequence(args.output, frame_count=args.frames)
    print(f"generated {args.frames} frames -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
