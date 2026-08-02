"""Measurement task data model."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class MeasurementTask:
    sample_id: str = "DEMO-V-001"
    groove_type: str = "直线 V 型槽"
    data_nature: str = "离线演示数据"
    target_depth_mm: float = 0.6000
    target_width_mm: float = 0.8500
    tolerance_mm: float = 0.0200
    operator: str = ""
    notes: str = "Stage 5 软件闭环验证"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.target_depth_mm <= 0 or self.target_width_mm <= 0:
            raise ValueError("标准槽深和槽宽必须大于 0")
        if self.tolerance_mm <= 0:
            raise ValueError("允许误差必须大于 0")

    def to_dict(self) -> dict:
        return asdict(self)
