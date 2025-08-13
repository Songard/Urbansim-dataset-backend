"""
移动障碍物检测系统使用示例

展示如何使用TransientDetector进行移动障碍物检测和质量评估
"""

import sys
from pathlib import Path
import logging

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from detection.transient_detector import TransientDetector, DetectionConfig, create_detector, quick_detect
from detection.quality_decision import QualityDecision


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def progress_callback(progress_ratio: float, processing_stats):
    """进度回调函数"""
    percentage = progress_ratio * 100
    print(f"处理进度: {percentage:.1f}% - "
          f"已处理帧数: {processing_stats.frames_processed}, "
          f"检测帧数: {processing_stats.detection_frames}, "
          f"分割帧数: {processing_stats.segmentation_frames}")


def example_basic_detection():
    """基础检测示例"""
    print("=" * 60)
    print("基础检测示例")
    print("=" * 60)
    
    # 视频文件路径（需要替换为实际路径）
    video_path = "path/to/your/video.mp4"
    
    # 使用快速检测函数
    try:
        print(f"开始检测视频: {video_path}")
        result = quick_detect(video_path, model_name="yolo11n.pt", scene_type="outdoor")
        
        print(f"检测完成！判定结果: {result.decision.value}")
        print(f"WDD: {result.metrics['WDD']:.2f}")
        print(f"WPO: {result.metrics['WPO']:.1f}%")
        print(f"SAI: {result.metrics['SAI']:.1f}%")
        
        if result.problems_found:
            print("发现问题:")
            for problem in result.problems_found:
                print(f"  - {problem}")
    
    except FileNotFoundError:
        print(f"视频文件不存在: {video_path}")
        print("请替换为实际的视频文件路径")
    except Exception as e:
        print(f"检测失败: {e}")


def example_advanced_detection():
    """高级检测示例"""
    print("=" * 60)
    print("高级检测示例")
    print("=" * 60)
    
    # 创建自定义配置
    config = DetectionConfig(
        model_name="yolo11n.pt",
        conf_threshold=0.4,
        device="cpu",  # 改为"cuda"以使用GPU
        scene_type="indoor",
        target_detection_frames=150,
        target_segmentation_frames=75,
        enable_early_termination=True,
        max_workers=2,
        memory_limit_mb=1024,
        output_format="table",
        save_report=True,
        output_path="detection_report.txt"
    )
    
    # 创建检测器
    detector = TransientDetector(config)
    
    try:
        # 初始化模型
        print("初始化模型...")
        detector.initialize_models()
        
        # 显示模型信息
        model_info = detector.get_model_info()
        print("模型信息:")
        print(f"  YOLO模型: {model_info.get('yolo_model', {}).get('detection_model', 'N/A')}")
        print(f"  设备: {model_info['config']['device']}")
        print(f"  场景类型: {model_info['config']['scene_type']}")
        
        # 检测视频
        video_path = "path/to/your/video.mp4"  # 替换为实际路径
        print(f"开始检测: {video_path}")
        
        result = detector.detect_video(video_path, progress_callback=progress_callback)
        
        # 显示结果
        print("\n检测完成！")
        print(f"判定结果: {result.quality_assessment.decision.value}")
        print(f"处理统计: {result.processing_stats}")
        print(f"性能指标: {result.performance_metrics}")
        
        # 显示详细报告
        from detection.quality_decision import ResultFormatter
        table_report = ResultFormatter.to_table_format(result.quality_assessment)
        print("\n详细报告:")
        print(table_report)
        
    except FileNotFoundError:
        print(f"视频文件不存在，请替换为实际的视频文件路径")
    except Exception as e:
        print(f"检测失败: {e}")
        import traceback
        traceback.print_exc()


def example_batch_detection():
    """批量检测示例"""
    print("=" * 60)
    print("批量检测示例")
    print("=" * 60)
    
    # 视频文件列表（需要替换为实际路径）
    video_paths = [
        "path/to/video1.mp4",
        "path/to/video2.mp4",
        "path/to/video3.mp4"
    ]
    
    # 创建检测器
    detector = create_detector(
        model_name="yolo11n.pt",
        scene_type="default",
        enable_early_termination=True
    )
    
    try:
        detector.initialize_models()
        
        # 批量检测
        results = detector.detect_batch(video_paths, progress_callback=progress_callback)
        
        print(f"\n批量检测完成！共处理 {len(results)} 个视频")
        
        # 统计结果
        decision_counts = {}
        for result in results:
            decision = result.quality_assessment.decision.value
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        
        print("判定结果统计:")
        for decision, count in decision_counts.items():
            print(f"  {decision}: {count}")
        
        # 生成批量摘要报告
        from detection.quality_decision import QualityReportGenerator
        generator = QualityReportGenerator()
        summary = generator.generate_batch_summary([r.quality_assessment for r in results])
        print("\n批量摘要:")
        print(summary)
        
    except Exception as e:
        print(f"批量检测失败: {e}")


def example_custom_thresholds():
    """自定义阈值示例"""
    print("=" * 60)
    print("自定义阈值示例")
    print("=" * 60)
    
    from detection.metrics_calculator import ThresholdManager
    
    # 创建阈值管理器
    threshold_manager = ThresholdManager("indoor")  # 室内场景，更严格的阈值
    
    # 显示默认阈值
    print("默认阈值配置:")
    for metric, thresholds in threshold_manager.thresholds.items():
        print(f"  {metric}: {thresholds}")
    
    # 评估示例指标
    test_metrics = {
        "WDD": 1.8,
        "WPO": 12.5,
        "SAI": 8.3
    }
    
    print("\n指标评估:")
    for metric, value in test_metrics.items():
        level = threshold_manager.evaluate_metric(metric, value)
        print(f"  {metric} = {value:.1f} -> {level}")


def example_region_analysis():
    """区域分析示例"""
    print("=" * 60)
    print("区域分析示例")
    print("=" * 60)
    
    from detection.region_manager import RegionManager
    
    # 创建区域管理器（假设1920x1080分辨率）
    region_manager = RegionManager(1920, 1080)
    
    # 显示区域配置
    region_info = region_manager.get_region_info()
    print("区域配置:")
    print(f"  图像尺寸: {region_info['image_size']}")
    print(f"  中心点: {region_info['center']}")
    print(f"  参考长度: {region_info['reference_length']}")
    
    # 测试不同位置的区域分类
    test_points = [
        (960, 540),   # 中心点
        (100, 100),   # 左上角
        (1800, 980),  # 右下角
        (500, 900),   # 左下（自身入镜区域）
    ]
    
    print("\n位置区域分类:")
    for x, y in test_points:
        region = region_manager.get_point_region(x, y)
        weight = region_manager.get_region_weight(region)
        print(f"  ({x:4d}, {y:4d}) -> {region:10s} (权重: {weight:.1f})")


if __name__ == "__main__":
    setup_logging()
    
    print("移动障碍物检测系统使用示例")
    print("请确保已安装必要的依赖: pip install ultralytics opencv-python")
    print()
    
    # 运行示例
    try:
        example_region_analysis()
        print()
        
        example_custom_thresholds()
        print()
        
        # 注意：以下示例需要实际的视频文件
        print("注意：以下示例需要实际的视频文件路径")
        
        # example_basic_detection()
        # print()
        
        # example_advanced_detection()
        # print()
        
        # example_batch_detection()
        
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"示例运行失败: {e}")
        import traceback
        traceback.print_exc()