# 槽型深度宽度测量软件

**Groove Depth and Width Measurement Software**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Stage](https://img.shields.io/badge/Stage-5%20Stable-2ea44f)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-informational)
![License](https://img.shields.io/badge/License-MIT-yellow)

面向带槽型工件的桌面测量软件，提供从**测量任务设置、原始激光图像读取、激光中心提取、离线点云重建、槽深槽宽分析、极值定位、三维可视化，到历史记录与 PDF 报告生成**的完整软件闭环。

本仓库为面向项目展示与交付整理的 Stage 5 稳定版本，默认提供可复现的离线演示数据生成器，也支持替换为相机采集的连续原始图像或外部点云文件。

## 核心功能

- 测量任务管理：样本编号、槽型、标准槽深、标准槽宽、公差和操作人员
- 三类数据入口：内置演示图像、原始图片目录、CSV/PLY/PCD/XYZ 点云
- 原始图像、激光中心提取结果和二值掩膜同步显示
- 连续激光截面离线重建与三维点云交互显示
- 多截面槽深、槽宽、均值、标准差、最大/最小值及位置分析
- 自动公差判定、运行耗时统计和历史记录
- 自动生成 PDF 测量报告
- 无硬件自检脚本，便于主办方快速复现软件流程

## 软件流程

```mermaid
flowchart LR
    A[测量任务设置] --> B[原始激光图像/点云导入]
    B --> C[激光中心提取]
    C --> D[离线三维点云重建]
    D --> E[多截面槽型分析]
    E --> F[槽深槽宽与极值定位]
    F --> G[三维显示与公差判定]
    G --> H[PDF报告与历史记录]
```

## 快速运行

### 1. 创建环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2. 运行完整自检

```powershell
python validate_stage5.py
```

自检会自动：

1. 生成 31 帧 V 型槽激光演示图；
2. 完成激光中心提取；
3. 重建三维点云；
4. 计算槽深与槽宽；
5. 生成 PDF 报告；
6. 写入历史记录。

### 3. 启动桌面软件

```powershell
python gui.py
```

Windows 也可双击：

```text
run_gui.bat
```

## 推荐动态演示顺序

1. 填写并应用测量任务参数；
2. 点击“运行内置演示”；
3. 切换查看原始图像、中心提取、二值掩膜；
4. 旋转和缩放三维点云；
5. 查看槽深、槽宽、公差判定及极值位置；
6. 生成 PDF 报告；
7. 查看历史测量记录。

详细讲解见 [`docs/DEMO_GUIDE.md`](docs/DEMO_GUIDE.md)。

## 项目结构

```text
.
├─ gui.py                         # PySide6 + PyVista 桌面界面
├─ demo_data.py                   # 内置激光演示帧生成
├─ offline_reconstruction.py      # 图像读取、中心提取、点云重建
├─ measurement_analysis.py        # 槽深槽宽与极值分析
├─ measurement_task.py            # 测量任务数据结构
├─ report_generator.py            # PDF 测量报告生成
├─ history_manager.py             # CSV 历史记录
├─ validate_stage5.py             # 无 GUI 完整闭环自检
├─ reconstruct_from_images.py     # 离线重建命令行工具
├─ requirements.txt
├─ requirements-ci.txt
├─ run_gui.bat
├─ run_validation.bat
├─ docs/
│  ├─ ARCHITECTURE.md
│  ├─ DATA_FORMAT.md
│  ├─ DEMO_GUIDE.md
│  └─ VALIDATION_PLAN.md
├─ samples/raw_laser_demo/
└─ outputs/
```

## 真实数据接入

推荐目录：

```text
real_scan_001/
├─ frame_00000.bmp
├─ frame_00001.bmp
├─ frame_00002.bmp
├─ ...
├─ camera_matrix.npy      # 可选：相机内参
└─ dist_coeffs.npy        # 可选：畸变系数
```

在软件中点击“选择原始图片目录”，选中该目录即可。图像按文件名排序处理。

点云 CSV 推荐使用：

```csv
x,y,z
-1.20,-6.00,0.01
-1.18,-6.00,-0.02
```

## 技术边界

- 内置数据用于验证软件闭环和动态演示；
- 真实毫米坐标需要相机内参、畸变参数、激光平面参数和扫描步距共同标定；
- 球弧面槽正式测量应先拟合局部球面或曲面基准，再沿局部法向截面计算槽深和槽宽；
- 软件中的公差判定表示结果是否落入用户设置的范围，不等同于第三方计量认证。

## 开源许可

本项目使用 MIT License。