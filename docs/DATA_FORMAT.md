# 数据格式

## 原始图片目录

支持：BMP、PNG、JPG、JPEG、TIF、TIFF。

```text
scan_001/
├─ frame_00000.bmp
├─ frame_00001.bmp
├─ ...
├─ camera_matrix.npy
└─ dist_coeffs.npy
```

图片按文件名排序。`camera_matrix.npy` 与 `dist_coeffs.npy` 同时存在时自动进行去畸变。

## 点云 CSV

推荐列：

```csv
x,y,z
-1.20,-6.00,0.01
-1.18,-6.00,-0.02
```

单位建议为毫米。对于 V 型槽，X 为截面横向，Y 为槽长度方向，Z 为高度方向。

## 历史记录

软件生成：

```text
outputs/history/measurement_history.csv
```

包含时间、样本编号、标准值、测量值、判定、耗时和报告路径。
