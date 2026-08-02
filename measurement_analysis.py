"""V-groove depth and width analysis for reconstructed point clouds."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter

import numpy as np


@dataclass
class SectionMeasurement:
    y_mm: float
    depth_mm: float
    width_mm: float


@dataclass
class MeasurementResult:
    sections: list[SectionMeasurement]
    depth_mean: float
    depth_min: float
    depth_max: float
    depth_std: float
    depth_min_y: float
    depth_max_y: float
    width_mean: float
    width_min: float
    width_max: float
    width_std: float
    width_min_y: float
    width_max_y: float
    analysis_seconds: float

    def to_dict(self) -> dict:
        data = asdict(self)
        data["sections"] = [asdict(section) for section in self.sections]
        return data


def _fit_section(x: np.ndarray, z: np.ndarray) -> tuple[float, float] | None:
    order = np.argsort(x)
    x, z = x[order], z[order]
    if x.size < 20:
        return None

    edge_count = max(5, int(x.size * 0.18))
    baseline = float(np.median(np.concatenate([z[:edge_count], z[-edge_count:]])))
    minimum_index = int(np.argmin(z))
    center_x = float(x[minimum_index])
    raw_depth = baseline - float(z[minimum_index])
    if raw_depth <= 1e-6:
        return None

    lower = baseline - raw_depth * 0.95
    upper = baseline - raw_depth * 0.05
    left_mask = (x < center_x) & (z > lower) & (z < upper)
    right_mask = (x > center_x) & (z > lower) & (z < upper)

    depth = raw_depth
    width = 0.0
    if left_mask.sum() >= 4 and right_mask.sum() >= 4:
        left_m, left_b = np.polyfit(x[left_mask], z[left_mask], 1)
        right_m, right_b = np.polyfit(x[right_mask], z[right_mask], 1)
        if abs(left_m) > 1e-9 and abs(right_m) > 1e-9 and abs(left_m - right_m) > 1e-9:
            left_top = (baseline - left_b) / left_m
            right_top = (baseline - right_b) / right_m
            intersection_x = (right_b - left_b) / (left_m - right_m)
            intersection_z = left_m * intersection_x + left_b
            candidate_depth = baseline - intersection_z
            candidate_width = right_top - left_top
            if 0 < candidate_depth < raw_depth * 1.4 and candidate_width > 0:
                depth, width = float(candidate_depth), float(candidate_width)

    if width <= 0:
        groove_mask = z < baseline - raw_depth * 0.03
        if groove_mask.sum() >= 2:
            width = float(x[groove_mask].max() - x[groove_mask].min())

    return (depth, width) if depth > 0 and width > 0 else None


def analyze_groove(points: np.ndarray) -> MeasurementResult:
    start = perf_counter()
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] < 3:
        raise ValueError("点云必须是 N×3 数组")

    rounded_y = np.round(points[:, 1], 6)
    sections: list[SectionMeasurement] = []
    for y_value in np.unique(rounded_y):
        section_points = points[rounded_y == y_value]
        fitted = _fit_section(section_points[:, 0], section_points[:, 2])
        if fitted is not None:
            sections.append(SectionMeasurement(float(y_value), fitted[0], fitted[1]))

    if not sections:
        raise ValueError("没有获得有效槽型截面")

    depths = np.asarray([section.depth_mm for section in sections])
    widths = np.asarray([section.width_mm for section in sections])
    ys = np.asarray([section.y_mm for section in sections])
    dmin, dmax = int(np.argmin(depths)), int(np.argmax(depths))
    wmin, wmax = int(np.argmin(widths)), int(np.argmax(widths))

    return MeasurementResult(
        sections=sections,
        depth_mean=float(depths.mean()), depth_min=float(depths.min()), depth_max=float(depths.max()),
        depth_std=float(depths.std(ddof=0)), depth_min_y=float(ys[dmin]), depth_max_y=float(ys[dmax]),
        width_mean=float(widths.mean()), width_min=float(widths.min()), width_max=float(widths.max()),
        width_std=float(widths.std(ddof=0)), width_min_y=float(ys[wmin]), width_max_y=float(ys[wmax]),
        analysis_seconds=perf_counter() - start,
    )
