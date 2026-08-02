"""Offline laser-image reconstruction with Unicode-safe image I/O."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
import pandas as pd

IMAGE_EXTENSIONS = {".bmp", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


@dataclass
class ReconstructionConfig:
    x_scale_mm_per_px: float = 0.020
    frame_step_mm: float = 0.400
    height_scale_mm_per_px: float = 0.010
    threshold_percentile: float = 90.0
    minimum_columns: int = 80

    def to_dict(self) -> dict:
        return asdict(self)


def imread_unicode(path: str | Path, flags: int = cv2.IMREAD_GRAYSCALE) -> np.ndarray | None:
    try:
        data = np.fromfile(str(Path(path)), dtype=np.uint8)
        return cv2.imdecode(data, flags) if data.size else None
    except (OSError, ValueError):
        return None


def imwrite_unicode(path: str | Path, image: np.ndarray) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(path.suffix or ".png", image)
    if not ok:
        raise ValueError(f"无法编码图像：{path}")
    encoded.tofile(str(path))


def list_image_files(directory: str | Path) -> list[Path]:
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"图片目录不存在：{directory}")
    return sorted(
        file for file in directory.iterdir()
        if file.is_file() and file.suffix.lower() in IMAGE_EXTENSIONS
    )


def load_calibration(directory: str | Path) -> tuple[np.ndarray | None, np.ndarray | None]:
    directory = Path(directory)
    camera_path = directory / "camera_matrix.npy"
    dist_path = directory / "dist_coeffs.npy"
    if camera_path.exists() and dist_path.exists():
        try:
            return np.load(camera_path), np.load(dist_path)
        except (OSError, ValueError):
            pass
    return None, None


def extract_laser_center(gray: np.ndarray, threshold_percentile: float = 90.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if gray.ndim != 2:
        raise ValueError("激光中心提取需要灰度图像")

    blurred = cv2.GaussianBlur(gray, (3, 3), 0.7)
    threshold = max(45.0, float(np.percentile(blurred, threshold_percentile)))
    mask = (blurred >= threshold).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))

    columns: list[float] = []
    rows: list[float] = []
    for column in range(blurred.shape[1]):
        candidate_rows = np.flatnonzero(mask[:, column])
        if candidate_rows.size == 0:
            continue
        intensities = blurred[candidate_rows, column].astype(float)
        maximum = intensities.max()
        strong = intensities >= max(35.0, maximum * 0.55)
        selected_rows = candidate_rows[strong]
        selected_intensities = intensities[strong]
        if selected_rows.size == 0 or selected_intensities.sum() <= 0:
            continue
        columns.append(float(column))
        rows.append(float(np.average(selected_rows, weights=selected_intensities)))

    return np.asarray(columns), np.asarray(rows), mask


def create_overlay(gray: np.ndarray, columns: np.ndarray, rows: np.ndarray) -> np.ndarray:
    overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    for column, row in zip(columns.astype(int), rows.astype(int)):
        if 0 <= row < overlay.shape[0] and 0 <= column < overlay.shape[1]:
            overlay[max(0, row - 1): min(overlay.shape[0], row + 2), column] = (0, 255, 0)
    return overlay


def reconstruct_directory(
    source_dir: str | Path,
    output_dir: str | Path,
    config: ReconstructionConfig | None = None,
) -> dict:
    config = config or ReconstructionConfig()
    source = Path(source_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    debug_dir = output / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    image_files = list_image_files(source)
    if not image_files:
        raise FileNotFoundError(f"目录中没有可读取的原始图片：{source}")

    camera_matrix, dist_coeffs = load_calibration(source)
    points: list[np.ndarray] = []
    valid_frames = 0
    first_original: Path | None = None
    first_overlay: Path | None = None
    first_mask: Path | None = None
    start = perf_counter()

    for frame_index, image_path in enumerate(image_files):
        gray = imread_unicode(image_path)
        if gray is None:
            continue
        if camera_matrix is not None and dist_coeffs is not None:
            gray = cv2.undistort(gray, camera_matrix, dist_coeffs)

        columns, rows, mask = extract_laser_center(gray, config.threshold_percentile)
        if columns.size < config.minimum_columns:
            continue

        order = np.argsort(columns)
        columns, rows = columns[order], rows[order]
        edge = max(8, int(columns.size * 0.18))
        baseline = float(np.median(np.concatenate([rows[:edge], rows[-edge:]])))
        x_mm = (columns - gray.shape[1] / 2.0) * config.x_scale_mm_per_px
        y_mm = np.full_like(x_mm, (frame_index - (len(image_files) - 1) / 2.0) * config.frame_step_mm)
        z_mm = -(rows - baseline) * config.height_scale_mm_per_px
        points.append(np.column_stack([x_mm, y_mm, z_mm]))
        valid_frames += 1

        if first_original is None:
            first_original = debug_dir / "original.png"
            first_overlay = debug_dir / "center_overlay.png"
            first_mask = debug_dir / "binary_mask.png"
            imwrite_unicode(first_original, gray)
            imwrite_unicode(first_overlay, create_overlay(gray, columns, rows))
            imwrite_unicode(first_mask, mask)

    if not points:
        raise ValueError("未能从原始图片中重建出点云，请检查激光条纹或阈值参数")

    cloud = np.vstack(points)
    csv_path = output / "reconstructed_point_cloud.csv"
    pd.DataFrame(cloud, columns=["x", "y", "z"]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    return {
        "points": cloud,
        "source_dir": str(source),
        "output_dir": str(output),
        "point_cloud_csv": str(csv_path),
        "original_frames": len(image_files),
        "valid_frames": valid_frames,
        "point_count": int(cloud.shape[0]),
        "read_seconds": perf_counter() - start,
        "calibration_applied": camera_matrix is not None and dist_coeffs is not None,
        "preview_original": str(first_original) if first_original else "",
        "preview_overlay": str(first_overlay) if first_overlay else "",
        "preview_mask": str(first_mask) if first_mask else "",
        "config": config.to_dict(),
    }
