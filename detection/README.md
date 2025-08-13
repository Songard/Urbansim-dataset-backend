# 移动障碍物检测系统

基于YOLO11的移动障碍物检测和数据质量评估系统。该系统专门用于检测视频中的人员（person）和狗（dog）等移动物体，并通过三大核心指标评估数据质量。

## 功能特点

- **智能检测**：基于YOLO11的高精度检测和分割
- **区域权重**：根据画面区域重要性进行加权评估
- **三大指标**：WDD（加权检测密度）、WPO（加权像素占用率）、SAI（自身入镜指数）
- **自适应采样**：根据视频长度自动调整采样策略
- **早期终止**：检测到严重问题时可提前终止节省时间
- **批量处理**：支持多视频批量检测
- **多种输出**：JSON、紧凑格式、表格格式

## 核心指标说明

### 1. 加权检测密度 (WDD)
衡量移动物体的出现频率，考虑位置重要性。

- **计算方法**：检测数 × 区域权重 / 采样帧数
- **评判标准**：
  - 优秀：< 1.0
  - 可接受：1.0 ~ 1.5
  - 需复核：1.5 ~ 2.0
  - 拒绝：≥ 8.0

### 2. 加权像素占用率 (WPO)
衡量移动物体的画面占用程度，近距离物体影响更大。

- **计算方法**：分割面积占比 × 区域权重
- **评判标准**：
  - 优秀：< 1%
  - 可接受：1% ~ 5%
  - 需复核：5% ~ 10%
  - 拒绝：≥ 30%

### 3. 自身入镜指数 (SAI)
专门检测采集者自己出现在画面中的情况。

- **检测条件**：位于画面下方区域且占画面 > 5%
- **评判标准**：
  - 优秀：< 5%
  - 可接受：5% ~ 15%
  - 需复核：15% ~ 25%
  - 拒绝：≥ 25%

## 安装依赖

```bash
pip install ultralytics opencv-python numpy pathlib dataclasses
```

## 快速开始

### 1. 基础使用

```python
from detection.transient_detector import quick_detect

# 快速检测单个视频
result = quick_detect("path/to/video.mp4", 
                     model_name="yolo11n.pt", 
                     scene_type="outdoor")

print(f"判定结果: {result.decision.value}")
print(f"WDD: {result.metrics['WDD']:.2f}")
print(f"WPO: {result.metrics['WPO']:.1f}%")
print(f"SAI: {result.metrics['SAI']:.1f}%")
```

### 2. 高级配置

```python
from detection.transient_detector import TransientDetector, DetectionConfig

# 创建配置
config = DetectionConfig(
    model_name="yolo11n.pt",
    conf_threshold=0.4,
    device="cpu",  # 使用GPU: "cuda"
    scene_type="indoor",
    target_detection_frames=200,
    target_segmentation_frames=100,
    enable_early_termination=True,
    output_format="table",
    save_report=True,
    output_path="report.txt"
)

# 创建检测器
detector = TransientDetector(config)
detector.initialize_models()

# 执行检测
result = detector.detect_video("video.mp4", progress_callback=my_callback)
```

### 3. 批量处理

```python
# 批量检测多个视频
video_paths = ["video1.mp4", "video2.mp4", "video3.mp4"]
results = detector.detect_batch(video_paths)

# 生成批量摘要
from detection.quality_decision import QualityReportGenerator
generator = QualityReportGenerator()
summary = generator.generate_batch_summary([r.quality_assessment for r in results])
print(summary)
```

## 模块结构

```
detection/
├── __init__.py                 # 模块初始化
├── region_manager.py           # 区域定义和权重计算
├── yolo_detector.py            # YOLO11检测和分割封装
├── metrics_calculator.py       # 三大核心指标计算
├── sampling_optimizer.py       # 采样策略和优化
├── quality_decision.py         # 综合判定和输出
├── transient_detector.py       # 主流程集成
├── example_usage.py            # 使用示例
└── README.md                   # 说明文档
```

## 配置选项

### 场景类型
- `"indoor"`：室内环境，更严格的阈值
- `"outdoor"`：室外环境，稍宽松的阈值
- `"default"`：默认阈值

### 设备选择
- `"cpu"`：使用CPU计算
- `"cuda"`：使用GPU加速
- `"0"`, `"1"`：指定GPU设备

### 输出格式
- `"json"`：标准JSON格式
- `"compact"`：紧凑JSON格式
- `"table"`：表格格式

## 性能优化

### 采样策略
系统会根据视频长度自动调整采样率：
- ≤200帧：全检
- ≤500帧：隔帧检测
- ≤1000帧：每4帧检测一次
- >1000帧：每6帧检测一次

### 批处理优化
- 检测批大小：16（可配置）
- 分割批大小：8（可配置）
- 并行处理：支持多线程

### 早期终止
当检测到严重超标时，系统可以提前终止以节省时间：
- WDD > 12.0
- WPO > 40.0%
- SAI > 35.0%

## 示例输出

### JSON格式
```json
{
  "metrics": {
    "WDD": 1.25,
    "WPO": 8.3,
    "SAI": 12.1
  },
  "decision": "NEED_REVIEW",
  "details": {
    "frames_sampled": 150,
    "frames_total": 600,
    "sampling_rate": 4
  },
  "timestamp": "2024-01-15T10:30:00"
}
```

### 表格格式
```
============================================================
移动障碍物检测质量评估结果
============================================================
时间: 2024-01-15T10:30:00
场景类型: outdoor
判定结果: NEED_REVIEW

指标详情:
----------------------------------------
  WDD:     1.25 (acceptable)
  WPO:     8.30 (review)
  SAI:    12.10 (acceptable)

处理信息:
----------------------------------------
  总帧数: 600
  采样帧数: 150
  检测采样率: 1/4
  分割采样率: 1/6
============================================================
```

## 常见问题

### Q1: 如何提高检测精度？
A: 可以调低 `conf_threshold`（如0.3），但会增加误检。

### Q2: 如何加速处理？
A: 
- 使用GPU：设置 `device="cuda"`
- 增大批处理：调整 `batch_size_detection` 和 `batch_size_segmentation`
- 启用早期终止：`enable_early_termination=True`

### Q3: 内存不足怎么办？
A: 
- 减小批处理大小
- 调整 `memory_limit_mb` 参数
- 使用更小的模型（如yolo11n而不是yolo11x）

### Q4: 如何自定义阈值？
A: 
```python
from detection.metrics_calculator import ThresholdManager
threshold_manager = ThresholdManager("custom")
# 修改阈值配置
```

## 许可证

本项目遵循相关开源许可证。