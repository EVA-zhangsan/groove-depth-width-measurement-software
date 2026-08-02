"""PDF report generation for one measurement task."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import perf_counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _status(value: float, target: float, tolerance: float) -> str:
    return "合格" if abs(value - target) <= tolerance else "超差"


def generate_measurement_report(task, reconstruction: dict, result, output_path: str | Path) -> tuple[Path, float]:
    start = perf_counter()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path = output_path.with_name(output_path.stem + "_trend.png")

    ys = [section.y_mm for section in result.sections]
    depths = [section.depth_mm for section in result.sections]
    widths = [section.width_mm for section in result.sections]
    fig, ax = plt.subplots(figsize=(8.2, 3.8))
    ax.plot(ys, depths, marker="o", markersize=2.5, label="Depth (mm)")
    ax.plot(ys, widths, marker="o", markersize=2.5, label="Width (mm)")
    ax.axhline(task.target_depth_mm, linestyle="--", linewidth=1, label="Target depth")
    ax.axhline(task.target_width_mm, linestyle="--", linewidth=1, label="Target width")
    ax.set_xlabel("Y position (mm)")
    ax.set_ylabel("Measurement (mm)")
    ax.grid(True, alpha=0.3)
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(chart_path, dpi=160)
    plt.close(fig)

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ChineseTitle", parent=styles["Title"], fontName="STSong-Light", fontSize=20, leading=26, alignment=TA_CENTER)
    h_style = ParagraphStyle("ChineseHeading", parent=styles["Heading2"], fontName="STSong-Light", fontSize=13, leading=18)
    body_style = ParagraphStyle("ChineseBody", parent=styles["BodyText"], fontName="STSong-Light", fontSize=9.5, leading=15)

    doc = SimpleDocTemplate(str(output_path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    story = [
        Paragraph("槽型深度宽度测量报告", title_style),
        Spacer(1, 5 * mm),
        Paragraph(f"报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style),
        Spacer(1, 4 * mm),
        Paragraph("1. 测量任务", h_style),
    ]

    task_data = [
        ["样本编号", task.sample_id, "槽型", task.groove_type],
        ["数据性质", task.data_nature, "操作人员", task.operator or "未填写"],
        ["标准槽深/mm", f"{task.target_depth_mm:.4f}", "标准槽宽/mm", f"{task.target_width_mm:.4f}"],
        ["允许误差/mm", f"±{task.tolerance_mm:.4f}", "备注", task.notes or "—"],
    ]
    task_table = Table(task_data, colWidths=[30 * mm, 55 * mm, 30 * mm, 55 * mm])
    task_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9aa4ad")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e9eef3")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e9eef3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [task_table, Spacer(1, 5 * mm), Paragraph("2. 数据处理记录", h_style)]

    process_data = [
        ["原始帧", reconstruction.get("original_frames", "—"), "有效帧", reconstruction.get("valid_frames", "—")],
        ["点云点数", reconstruction.get("point_count", "—"), "有效截面", len(result.sections)],
        ["读取/重建耗时", f"{reconstruction.get('read_seconds', 0):.3f} s", "分析耗时", f"{result.analysis_seconds:.3f} s"],
        ["标定文件", "已读取" if reconstruction.get("calibration_applied") else "未读取", "点云文件", Path(reconstruction.get("point_cloud_csv", "")).name],
    ]
    process_table = Table(process_data, colWidths=[35 * mm, 45 * mm, 35 * mm, 55 * mm])
    process_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9aa4ad")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e9eef3")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e9eef3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [process_table, Spacer(1, 5 * mm), Paragraph("3. 测量结果", h_style)]

    depth_status = _status(result.depth_mean, task.target_depth_mm, task.tolerance_mm)
    width_status = _status(result.width_mean, task.target_width_mm, task.tolerance_mm)
    result_data = [
        ["指标", "标准值/mm", "测量均值/mm", "最小值/mm", "最大值/mm", "标准差/mm", "判定"],
        ["槽深", f"{task.target_depth_mm:.4f}", f"{result.depth_mean:.4f}", f"{result.depth_min:.4f}", f"{result.depth_max:.4f}", f"{result.depth_std:.4f}", depth_status],
        ["槽宽", f"{task.target_width_mm:.4f}", f"{result.width_mean:.4f}", f"{result.width_min:.4f}", f"{result.width_max:.4f}", f"{result.width_std:.4f}", width_status],
    ]
    result_table = Table(result_data, colWidths=[22 * mm, 25 * mm, 27 * mm, 24 * mm, 24 * mm, 24 * mm, 20 * mm])
    result_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9aa4ad")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce7f1")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [result_table, Spacer(1, 4 * mm)]
    story += [Paragraph(f"槽深最小值位置：Y={result.depth_min_y:.3f} mm；槽深最大值位置：Y={result.depth_max_y:.3f} mm。", body_style)]
    story += [Paragraph(f"槽宽最小值位置：Y={result.width_min_y:.3f} mm；槽宽最大值位置：Y={result.width_max_y:.3f} mm。", body_style)]
    story += [Spacer(1, 4 * mm), Image(str(chart_path), width=170 * mm, height=79 * mm)]

    preview_paths = [
        ("原始激光图像", reconstruction.get("preview_original")),
        ("激光中心提取", reconstruction.get("preview_overlay")),
        ("二值掩膜", reconstruction.get("preview_mask")),
    ]
    existing = [(name, path) for name, path in preview_paths if path and Path(path).exists()]
    if existing:
        story += [PageBreak(), Paragraph("4. 图像处理结果", h_style)]
        images = []
        captions = []
        for name, path in existing:
            images.append(Image(str(path), width=54 * mm, height=31 * mm))
            captions.append(Paragraph(name, body_style))
        image_table = Table([images, captions], colWidths=[58 * mm] * len(images))
        image_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story.append(image_table)

    story += [Spacer(1, 6 * mm), Paragraph("说明：公差判定依据当前任务设置完成。内置演示数据用于验证软件闭环；实际计量精度需结合正式标定参数和参考样本复核。", body_style)]
    doc.build(story)
    chart_path.unlink(missing_ok=True)
    return output_path, perf_counter() - start
