"""Command-line reconstruction tool."""
from __future__ import annotations

import argparse
from pathlib import Path

from measurement_analysis import analyze_groove
from offline_reconstruction import ReconstructionConfig, reconstruct_directory


def main() -> int:
    parser = argparse.ArgumentParser(description="从连续激光图像重建点云并测量 V 型槽")
    parser.add_argument("source", type=Path, help="原始图片目录")
    parser.add_argument("--output", type=Path, default=Path("outputs/cli_reconstruction"))
    parser.add_argument("--x-scale", type=float, default=0.020)
    parser.add_argument("--frame-step", type=float, default=0.400)
    parser.add_argument("--height-scale", type=float, default=0.010)
    args = parser.parse_args()

    config = ReconstructionConfig(
        x_scale_mm_per_px=args.x_scale,
        frame_step_mm=args.frame_step,
        height_scale_mm_per_px=args.height_scale,
    )
    reconstruction = reconstruct_directory(args.source, args.output, config)
    result = analyze_groove(reconstruction["points"])
    print(f"有效帧：{reconstruction['valid_frames']}/{reconstruction['original_frames']}")
    print(f"点云点数：{reconstruction['point_count']}")
    print(f"槽深均值：{result.depth_mean:.4f} mm")
    print(f"槽宽均值：{result.width_mean:.4f} mm")
    print(f"点云文件：{reconstruction['point_cloud_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
