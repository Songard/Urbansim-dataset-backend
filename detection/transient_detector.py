"""
主流程集成模块 - 移动障碍物检测器

整合所有子模块，提供完整的移动障碍物检测和质量评估流程
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional, Any, Union, Callable
import logging
from pathlib import Path
from dataclasses import dataclass
import time

from .region_manager import RegionManager
from .yolo_detector import YOLODetector, AdaptiveSampler
from .metrics_calculator import MetricsCalculator, FinalMetrics
from .sampling_optimizer import (
    FrameLoader, AdaptiveSamplingStrategy, ProcessingOptimizer, 
    EarlyTerminationManager, ResourceMonitor, SamplingConfig, ProcessingStats
)
from .quality_decision import QualityDecisionEngine, QualityReportGenerator, QualityAssessmentResult


@dataclass
class DetectionConfig:
    """检测配置"""
    # YOLO模型配置
    model_name: str = "yolo11n.pt"
    conf_threshold: float = 0.35
    device: str = "cpu"
    
    # 场景配置
    scene_type: str = "default"  # "indoor", "outdoor", "default"
    
    # 采样配置
    target_detection_frames: int = 200
    target_segmentation_frames: int = 100
    enable_early_termination: bool = True
    
    # 性能配置
    max_workers: int = 2
    memory_limit_mb: float = 2048
    
    # 输出配置
    output_format: str = "json"  # "json", "compact", "table"
    save_report: bool = False
    output_path: Optional[str] = None


@dataclass 
class DetectionResult:
    """检测结果"""
    quality_assessment: QualityAssessmentResult
    processing_stats: ProcessingStats
    performance_metrics: Dict[str, float]
    video_info: Dict[str, Any]
    config_used: DetectionConfig


class TransientDetector:
    """移动障碍物检测器主类"""
    
    def __init__(self, config: DetectionConfig):
        """
        初始化检测器
        
        Args:
            config: 检测配置
        """
        self.config = config
        
        # 初始化组件
        self.yolo_detector = None
        self.region_manager = None
        self.metrics_calculator = None
        self.decision_engine = None
        self.report_generator = None
        
        # 性能监控
        self.resource_monitor = ResourceMonitor(config.memory_limit_mb)
        self.early_termination_manager = EarlyTerminationManager()
        
        # 状态
        self.is_initialized = False
        
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志记录"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def initialize_models(self):
        """初始化模型和组件"""
        if self.is_initialized:
            return
        
        try:
            self.logger.info("Initializing YOLO detector...")
            self.yolo_detector = YOLODetector(
                model_name=self.config.model_name,
                conf_threshold=self.config.conf_threshold,
                device=self.config.device
            )
            
            self.decision_engine = QualityDecisionEngine(self.config.scene_type)
            self.report_generator = QualityReportGenerator(self.config.output_format)
            
            self.is_initialized = True
            self.logger.info("Models initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize models: {e}")
            raise
    
    def detect_video(self, video_path: Union[str, Path], 
                    progress_callback: Optional[Callable] = None) -> DetectionResult:
        """
        检测视频中的移动障碍物
        
        Args:
            video_path: 视频文件路径
            progress_callback: 进度回调函数
            
        Returns:
            检测结果
        """
        if not self.is_initialized:
            self.initialize_models()
        
        video_path = Path(video_path)
        self.logger.info(f"Starting detection for: {video_path}")
        
        # 加载视频
        frame_loader = FrameLoader(video_path)
        video_info = frame_loader.get_video_info()
        
        try:
            # 初始化组件
            self.region_manager = RegionManager(
                frame_loader.frame_width, 
                frame_loader.frame_height
            )
            self.metrics_calculator = MetricsCalculator(
                frame_loader.frame_width, 
                frame_loader.frame_height
            )
            
            # 计算采样配置
            sampling_config = AdaptiveSamplingStrategy.calculate_optimal_rates(
                total_frames=frame_loader.total_frames,
                target_detection_frames=self.config.target_detection_frames,
                target_segmentation_frames=self.config.target_segmentation_frames
            )
            
            # 生成采样计划
            sampling_plan = AdaptiveSamplingStrategy.generate_sampling_plan(
                frame_loader.total_frames, sampling_config
            )
            
            # 执行检测流程
            result = self._execute_detection_pipeline(
                frame_loader, sampling_config, sampling_plan, progress_callback
            )
            
            return result
            
        finally:
            frame_loader.close()
    
    def _execute_detection_pipeline(self, 
                                  frame_loader: FrameLoader,
                                  sampling_config: SamplingConfig,
                                  sampling_plan: Dict[str, List],
                                  progress_callback: Optional[Callable] = None) -> DetectionResult:
        """
        执行检测流程
        
        Args:
            frame_loader: 帧加载器
            sampling_config: 采样配置
            sampling_plan: 采样计划
            progress_callback: 进度回调
            
        Returns:
            检测结果
        """
        processing_stats = ProcessingStats()
        processing_stats.total_frames = frame_loader.total_frames
        
        optimizer = ProcessingOptimizer(sampling_config)
        optimizer.start_timing()
        
        try:
            # 执行检测
            self._process_detection_frames(
                frame_loader, sampling_plan["detection_frames"], 
                sampling_config, optimizer, processing_stats, progress_callback
            )
            
            # 执行分割（如果需要）
            if sampling_plan["segmentation_frames"]:
                self._process_segmentation_frames(
                    frame_loader, sampling_plan["segmentation_frames"],
                    sampling_config, optimizer, processing_stats, progress_callback
                )
            
            # 计算最终指标
            final_metrics = self._calculate_final_metrics(
                frame_loader.total_frames,
                {"detection": sampling_config.detection_rate, 
                 "segmentation": sampling_config.segmentation_rate}
            )
            
            # 质量判定
            quality_assessment = self._perform_quality_assessment(
                final_metrics, processing_stats, optimizer
            )
            
            # 生成报告
            if self.config.save_report and self.config.output_path:
                self.report_generator.save_report(quality_assessment, self.config.output_path)
            
            optimizer.stop_timing()
            
            return DetectionResult(
                quality_assessment=quality_assessment,
                processing_stats=processing_stats,
                performance_metrics=optimizer.get_performance_metrics(),
                video_info=frame_loader.get_video_info(),
                config_used=self.config
            )
            
        except Exception as e:
            self.logger.error(f"Detection pipeline failed: {e}")
            optimizer.stop_timing()
            raise
    
    def _process_detection_frames(self, 
                                frame_loader: FrameLoader,
                                detection_frames: List[int],
                                config: SamplingConfig,
                                optimizer: ProcessingOptimizer,
                                processing_stats: ProcessingStats,
                                progress_callback: Optional[Callable] = None):
        """处理检测帧"""
        self.logger.info(f"Processing {len(detection_frames)} detection frames...")
        
        # 批量处理
        detection_batches = AdaptiveSamplingStrategy._create_batches(
            detection_frames, config.batch_size_detection
        )
        
        for batch_idx, frame_indices in enumerate(detection_batches):
            # 检查内存使用
            if self.resource_monitor.is_memory_limit_exceeded():
                self.logger.warning("Memory limit approaching, reducing batch size")
                # 可以动态调整批处理大小
            
            # 加载帧
            frames_data = optimizer.optimize_frame_loading(frame_loader, frame_indices)
            
            # 准备批次数据
            batch_images = []
            valid_indices = []
            
            for frame_idx, frame in frames_data:
                if frame is not None:
                    batch_images.append(frame)
                    valid_indices.append(frame_idx)
            
            if not batch_images:
                continue
            
            # 执行批量检测
            batch_results = self.yolo_detector.detect_batch(batch_images)
            
            # 处理结果
            for i, result in enumerate(batch_results):
                if i < len(valid_indices):
                    frame_idx = valid_indices[i]
                    metrics = self.metrics_calculator.process_detection_frame(frame_idx, result)
                    processing_stats.detection_frames += 1
            
            processing_stats.frames_processed += len(valid_indices)
            
            # 进度回调
            if progress_callback:
                progress_ratio = processing_stats.frames_processed / processing_stats.total_frames
                progress_callback(progress_ratio, processing_stats)
            
            # 早期终止检查
            if (config.early_termination_enabled and 
                processing_stats.frames_processed > processing_stats.total_frames * 0.2):
                
                processed_ratio = processing_stats.frames_processed / processing_stats.total_frames
                should_terminate, reason = self.metrics_calculator.check_early_termination(processed_ratio)
                
                if should_terminate:
                    processing_stats.early_terminated = True
                    processing_stats.termination_reason = reason
                    self.logger.info(f"Early termination: {reason}")
                    break
    
    def _process_segmentation_frames(self,
                                   frame_loader: FrameLoader,
                                   segmentation_frames: List[int],
                                   config: SamplingConfig,
                                   optimizer: ProcessingOptimizer,
                                   processing_stats: ProcessingStats,
                                   progress_callback: Optional[Callable] = None):
        """处理分割帧"""
        if processing_stats.early_terminated:
            return
        
        self.logger.info(f"Processing {len(segmentation_frames)} segmentation frames...")
        
        # 批量处理
        segmentation_batches = AdaptiveSamplingStrategy._create_batches(
            segmentation_frames, config.batch_size_segmentation
        )
        
        for batch_idx, frame_indices in enumerate(segmentation_batches):
            # 加载帧
            frames_data = optimizer.optimize_frame_loading(frame_loader, frame_indices)
            
            # 准备批次数据
            batch_images = []
            valid_indices = []
            
            for frame_idx, frame in frames_data:
                if frame is not None:
                    batch_images.append(frame)
                    valid_indices.append(frame_idx)
            
            if not batch_images:
                continue
            
            # 执行批量分割
            batch_results = self.yolo_detector.segment_batch(batch_images)
            
            # 处理结果
            for i, result in enumerate(batch_results):
                if i < len(valid_indices):
                    frame_idx = valid_indices[i]
                    self.metrics_calculator.process_segmentation_frame(frame_idx, result)
                    processing_stats.segmentation_frames += 1
            
            # 进度回调
            if progress_callback:
                progress_ratio = processing_stats.frames_processed / processing_stats.total_frames
                progress_callback(progress_ratio, processing_stats)
    
    def _calculate_final_metrics(self, total_frames: int, sampling_rates: Dict[str, int]) -> FinalMetrics:
        """计算最终指标"""
        return self.metrics_calculator.calculate_final_metrics(total_frames, sampling_rates)
    
    def _perform_quality_assessment(self, 
                                  final_metrics: FinalMetrics,
                                  processing_stats: ProcessingStats,
                                  optimizer: ProcessingOptimizer) -> QualityAssessmentResult:
        """执行质量评估"""
        # 准备处理统计信息
        processing_info = {
            "early_terminated": processing_stats.early_terminated,
            "termination_reason": processing_stats.termination_reason,
            "detection_frames_processed": processing_stats.detection_frames,
            "segmentation_frames_processed": processing_stats.segmentation_frames
        }
        
        # 准备额外统计信息
        calculator_stats = self.metrics_calculator.get_statistics()
        performance_metrics = optimizer.get_performance_metrics()
        memory_info = self.resource_monitor.check_memory_usage()
        
        additional_stats = {
            "calculator_stats": calculator_stats,
            "performance_metrics": performance_metrics,
            "memory_usage": memory_info
        }
        
        # 执行质量评估
        return self.decision_engine.evaluate_quality(
            final_metrics, processing_info, additional_stats
        )
    
    def detect_batch(self, video_paths: List[Union[str, Path]], 
                    progress_callback: Optional[Callable] = None) -> List[DetectionResult]:
        """
        批量检测多个视频
        
        Args:
            video_paths: 视频文件路径列表
            progress_callback: 进度回调函数
            
        Returns:
            检测结果列表
        """
        results = []
        
        for i, video_path in enumerate(video_paths):
            self.logger.info(f"Processing video {i+1}/{len(video_paths)}: {video_path}")
            
            try:
                result = self.detect_video(video_path, progress_callback)
                results.append(result)
                
            except Exception as e:
                self.logger.error(f"Failed to process {video_path}: {e}")
                # 可以选择继续或停止
                continue
        
        return results
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        info = {
            "config": self.config.__dict__,
            "is_initialized": self.is_initialized
        }
        
        if self.yolo_detector:
            info["yolo_model"] = self.yolo_detector.get_model_info()
        
        if self.region_manager:
            info["region_config"] = self.region_manager.get_region_info()
        
        return info
    
    def reset(self):
        """重置检测器状态"""
        if self.metrics_calculator:
            self.metrics_calculator.reset()
        
        # 重置监控器
        self.resource_monitor = ResourceMonitor(self.config.memory_limit_mb)


def create_detector(model_name: str = "yolo11n.pt",
                   scene_type: str = "default",
                   device: str = "cpu",
                   **kwargs) -> TransientDetector:
    """
    创建检测器的便捷函数
    
    Args:
        model_name: YOLO模型名称
        scene_type: 场景类型
        device: 计算设备
        **kwargs: 其他配置参数
        
    Returns:
        配置好的检测器实例
    """
    config = DetectionConfig(
        model_name=model_name,
        scene_type=scene_type,
        device=device,
        **kwargs
    )
    
    return TransientDetector(config)


# 便捷函数
def quick_detect(video_path: Union[str, Path], 
                model_name: str = "yolo11n.pt",
                scene_type: str = "default") -> QualityAssessmentResult:
    """
    快速检测函数
    
    Args:
        video_path: 视频路径
        model_name: 模型名称
        scene_type: 场景类型
        
    Returns:
        质量评估结果
    """
    detector = create_detector(model_name=model_name, scene_type=scene_type)
    detector.initialize_models()
    
    result = detector.detect_video(video_path)
    return result.quality_assessment