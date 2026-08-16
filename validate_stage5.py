"""Hardware-free Stage 5 validation."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from demo_data import ensure_demo_frames
from history_manager import append_history
from measurement_analysis import analyze_groove
from measurement_task import MeasurementTask
from offline_reconstruction import reconstruct_directory
from report_generator import generate_measurement_report

ROOT = Path(__file__).resolve().parent


def main() -> int:
    task = MeasurementTask(
        sample_id="SIM-V-STAGE5",
        groove_type="直线 V 型槽",
        data_nature="离线演示数据",
        target_depth_mm=0.6000,
        target_width_mm=0.8500,
        tolerance_mm=0.0200,
        operator="Stage5 Validator",
        notes="181帧曲面工件自动闭环验证",
    )
    demo_dir = ensure_demo_frames(ROOT / "samples" / "raw_laser_demo", frame_count=181)
    session = ROOT / "outputs" / "validation" / datetime.now().strftime("%Y%m%d_%H%M%S")
    reconstruction = reconstruct_directory(demo_dir, session)
    result = analyze_groove(reconstruction["points"])
    report_path, report_seconds = generate_measurement_report(task, reconstruction, result, session / "SIM-V-STAGE5_measurement_report.pdf")

    depth_error = abs(result.depth_mean - task.target_depth_mm)
    width_error = abs(result.width_mean - task.target_width_mm)
    assert reconstruction["original_frames"] == 181
    assert reconstruction["valid_frames"] == 181
    assert reconstruction["point_count"] > 100000
    assert len(result.sections) >= 170
    assert depth_error <= task.tolerance_mm
    assert width_error <= task.tolerance_mm
    assert report_path.exists()

    append_history(ROOT / "outputs" / "history" / "measurement_history.csv", {
        "sample_id": task.sample_id, "groove_type": task.groove_type, "data_nature": task.data_nature,
        "target_depth_mm": task.target_depth_mm, "measured_depth_mm": result.depth_mean,
        "target_width_mm": task.target_width_mm, "measured_width_mm": result.width_mean,
        "tolerance_mm": task.tolerance_mm, "depth_status": "合格", "width_status": "合格",
        "point_count": reconstruction["point_count"], "valid_sections": len(result.sections),
        "read_seconds": reconstruction["read_seconds"], "analysis_seconds": result.analysis_seconds,
        "report_seconds": report_seconds, "report_path": str(report_path),
    })

    print("Stage 5 validation passed")
    print(f"frames: {reconstruction['valid_frames']}/{reconstruction['original_frames']}")
    print(f"points: {reconstruction['point_count']}")
    print(f"sections: {len(result.sections)}")
    print(f"depth: {result.depth_mean:.4f} mm, error: {depth_error:.4f} mm")
    print(f"width: {result.width_mean:.4f} mm, error: {width_error:.4f} mm")
    print(f"report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
