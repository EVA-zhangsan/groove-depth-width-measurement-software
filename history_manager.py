"""CSV-based measurement history."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

HISTORY_FIELDS = [
    "timestamp", "sample_id", "groove_type", "data_nature",
    "target_depth_mm", "measured_depth_mm", "target_width_mm",
    "measured_width_mm", "tolerance_mm", "depth_status", "width_status",
    "point_count", "valid_sections", "read_seconds", "analysis_seconds",
    "report_seconds", "report_path",
]


def append_history(path: str | Path, row: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    normalized = {field: row.get(field, "") for field in HISTORY_FIELDS}
    normalized["timestamp"] = normalized["timestamp"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=HISTORY_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(normalized)
    return path


def read_recent_history(path: str | Path, limit: int = 10) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    return rows[-limit:]
