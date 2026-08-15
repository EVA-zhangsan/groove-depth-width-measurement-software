"""Validate the complex software test image sequence."""
from __future__ import annotations

from pathlib import Path

from measurement_analysis import analyze_groove
from offline_reconstruction import reconstruct_directory
from synthetic_scan_generator import generate_complex_scan_sequence

ROOT = Path(__file__).resolve().parent


def main() -> int:
    input_dir = ROOT / "outputs" / "complex_sequence_validation" / "input"
    output_dir = ROOT / "outputs" / "complex_sequence_validation" / "reconstruction"
    generate_complex_scan_sequence(input_dir, frame_count=61)
    reconstruction = reconstruct_directory(input_dir, output_dir)
    result = analyze_groove(reconstruction["points"])

    depth_error = abs(result.depth_mean - 0.6000)
    width_error = abs(result.width_mean - 0.8500)

    assert reconstruction["original_frames"] == 61
    assert reconstruction["valid_frames"] >= 59
    assert reconstruction["point_count"] > 30000
    assert len(result.sections) >= 59
    assert depth_error <= 0.0200
    assert width_error <= 0.0200
    assert result.depth_std > 0.0005
    assert result.width_std > 0.0005

    print("Complex sequence validation passed")
    print(f"frames: {reconstruction['valid_frames']}/{reconstruction['original_frames']}")
    print(f"points: {reconstruction['point_count']}")
    print(f"sections: {len(result.sections)}")
    print(f"depth: {result.depth_mean:.4f} mm, std: {result.depth_std:.4f}, error: {depth_error:.4f} mm")
    print(f"width: {result.width_mean:.4f} mm, std: {result.width_std:.4f}, error: {width_error:.4f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
