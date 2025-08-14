"""
三大核心指标计算模块

实现WDD（加权检测密度）、WPO（加权像素占用率）、SAI（自身入镜指数）的计算
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
import logging
from dataclasses import dataclass

from .region_manager import RegionManager


@dataclass
class FrameMetrics:
    """单帧指标数据类"""
    frame_index: int
    wdd_score: float = 0.0
    wpo_score: float = 0.0
    has_self_appearance: bool = False
    detection_count: int = 0
    segmentation_count: int = 0
    total_area_ratio: float = 0.0


@dataclass
class FinalMetrics:
    """最终指标数据类"""
    WDD: float  # 加权检测密度
    WPO: float  # 加权像素占用率（百分比）
    SAI: float  # 自身入镜指数（百分比）
    frames_sampled: int
    frames_total: int
    sampling_rates: Dict[str, int]


class MetricsCalculator:
    """指标计算器"""
    
    def __init__(self, img_width: int, img_height: int):
        """
        初始化指标计算器
        
        Args:
            img_width: 图像宽度
            img_height: 图像高度
        """
        self.region_manager = RegionManager(img_width, img_height)
        self.frame_metrics: List[FrameMetrics] = []
        
        # 统计信息
        self.total_frames = 0
        self.detection_frames_count = 0
        self.segmentation_frames_count = 0
        
        # 早期终止检查
        self.early_termination_threshold = 0.2  # 处理20%后检查
        
    def process_detection_frame(self, frame_index: int, detections: Dict) -> FrameMetrics:
        """
        处理检测帧数据
        
        Args:
            frame_index: 帧索引
            detections: 检测结果
            
        Returns:
            单帧指标
        """
        metrics = FrameMetrics(frame_index=frame_index)
        
        if "error" in detections:
            logging.warning(f"Frame {frame_index} detection error: {detections['error']}")
            return metrics
        
        detection_list = detections.get("detections", [])
        metrics.detection_count = len(detection_list)
        
        # 计算WDD得分
        wdd_score = 0.0
        has_self_appearance = False
        
        for detection in detection_list:
            bbox = detection["bbox"]  # [x1, y1, x2, y2]
            class_name = detection.get("class_name", "")
            confidence = detection.get("confidence", 1.0)
            
            # 检查是否为目标类别
            if class_name not in ["person", "dog"]:
                continue
            
            # 获取检测框区域权重
            region_weights = self.region_manager.get_bbox_region_weights(tuple(bbox))
            
            # 计算加权得分
            weighted_score = self.region_manager.calculate_weighted_value(region_weights, 1.0)
            wdd_score += weighted_score
            
            # 检查自身入镜
            if (class_name == "person" and 
                self.region_manager.is_large_detection_in_self_zone(tuple(bbox))):
                has_self_appearance = True
        
        metrics.wdd_score = wdd_score
        metrics.has_self_appearance = has_self_appearance
        self.detection_frames_count += 1
        
        # 添加或更新帧指标
        self._update_frame_metrics(metrics)
        
        return metrics
    
    def process_segmentation_frame(self, frame_index: int, segmentations: Dict) -> FrameMetrics:
        """
        处理分割帧数据
        
        Args:
            frame_index: 帧索引
            segmentations: 分割结果
            
        Returns:
            更新后的单帧指标
        """
        # 查找已存在的帧指标或创建新的
        metrics = self._find_or_create_frame_metrics(frame_index)
        
        if "error" in segmentations:
            logging.warning(f"Frame {frame_index} segmentation error: {segmentations['error']}")
            return metrics
        
        segmentation_list = segmentations.get("segmentations", [])
        metrics.segmentation_count = len(segmentation_list)
        
        # 计算WPO得分
        total_weighted_area = 0.0
        image_area = self.region_manager.img_width * self.region_manager.img_height
        
        for segmentation in segmentation_list:
            class_name = segmentation.get("class_name", "")
            
            # 检查是否为目标类别
            if class_name not in ["person", "dog"]:
                continue
            
            if segmentation.get("has_mask", False):
                # 使用分割掩码计算
                mask_points = segmentation.get("mask_points", [])
                if mask_points:
                    region_weights = self.region_manager.get_mask_region_weights(mask_points)
                    mask_area = segmentation.get("mask_area", 0)
                    area_ratio = mask_area / image_area
                    
                    weighted_area = self.region_manager.calculate_weighted_value(
                        region_weights, area_ratio
                    )
                    total_weighted_area += weighted_area
            else:
                # 使用检测框估算面积
                bbox = segmentation.get("bbox", [0, 0, 0, 0])
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    bbox_area = (x2 - x1) * (y2 - y1)
                    area_ratio = bbox_area / image_area
                    
                    region_weights = self.region_manager.get_bbox_region_weights(tuple(bbox))
                    weighted_area = self.region_manager.calculate_weighted_value(
                        region_weights, area_ratio
                    )
                    total_weighted_area += weighted_area
        
        metrics.wpo_score = total_weighted_area
        metrics.total_area_ratio = total_weighted_area
        self.segmentation_frames_count += 1
        
        # 更新帧指标
        self._update_frame_metrics(metrics)
        
        return metrics
    
    def calculate_final_metrics(self, total_frames: int, 
                              sampling_rates: Dict[str, int]) -> FinalMetrics:
        """
        计算最终指标
        
        Args:
            total_frames: 总帧数
            sampling_rates: 采样率配置
            
        Returns:
            最终指标结果
        """
        self.total_frames = total_frames
        
        if not self.frame_metrics:
            return FinalMetrics(
                WDD=0.0, WPO=0.0, SAI=0.0,
                frames_sampled=0, frames_total=total_frames,
                sampling_rates=sampling_rates
            )
        
        # 计算WDD（加权检测密度）
        total_wdd_score = sum(fm.wdd_score for fm in self.frame_metrics)
        frames_with_detection = len([fm for fm in self.frame_metrics if fm.detection_count > 0])
        detection_frames_sampled = max(self.detection_frames_count, len(self.frame_metrics))
        
        WDD = total_wdd_score / detection_frames_sampled if detection_frames_sampled > 0 else 0.0
        
        # 计算WPO（加权像素占用率）
        frames_with_segmentation = [fm for fm in self.frame_metrics if fm.segmentation_count >= 0]
        if frames_with_segmentation:
            total_wpo_score = sum(fm.wpo_score for fm in frames_with_segmentation)
            WPO = (total_wpo_score / len(frames_with_segmentation)) * 100  # 转换为百分比
        else:
            WPO = 0.0
        
        # 计算SAI（自身入镜指数）
        frames_with_self_appearance = len([fm for fm in self.frame_metrics if fm.has_self_appearance])
        total_sampled_frames = len(self.frame_metrics)
        SAI = (frames_with_self_appearance / total_sampled_frames) * 100 if total_sampled_frames > 0 else 0.0
        
        return FinalMetrics(
            WDD=WDD,
            WPO=WPO,
            SAI=SAI,
            frames_sampled=total_sampled_frames,
            frames_total=total_frames,
            sampling_rates=sampling_rates
        )
    
    def check_early_termination(self, processed_ratio: float) -> Tuple[bool, Optional[str]]:
        """
        检查是否可以早期终止
        
        Args:
            processed_ratio: 已处理比例
            
        Returns:
            (是否终止, 终止原因)
        """
        if processed_ratio < self.early_termination_threshold:
            return False, None
        
        if not self.frame_metrics:
            return False, None
        
        # 计算当前的临时指标
        temp_metrics = self.calculate_final_metrics(
            total_frames=int(len(self.frame_metrics) / processed_ratio),
            sampling_rates={"detection": 1, "segmentation": 1}
        )
        
        # 严重超标检查
        if (temp_metrics.WDD > 12 or 
            temp_metrics.WPO > 40 or 
            temp_metrics.SAI > 35):
            
            reason = []
            if temp_metrics.WDD > 12:
                reason.append(f"WDD={temp_metrics.WDD:.1f}")
            if temp_metrics.WPO > 40:
                reason.append(f"WPO={temp_metrics.WPO:.1f}%")
            if temp_metrics.SAI > 35:
                reason.append(f"SAI={temp_metrics.SAI:.1f}%")
                
            return True, f"Early termination: {', '.join(reason)}"
        
        return False, None
    
    def _find_or_create_frame_metrics(self, frame_index: int) -> FrameMetrics:
        """查找或创建帧指标"""
        for metrics in self.frame_metrics:
            if metrics.frame_index == frame_index:
                return metrics
        
        # 创建新的帧指标
        new_metrics = FrameMetrics(frame_index=frame_index)
        self.frame_metrics.append(new_metrics)
        return new_metrics
    
    def _update_frame_metrics(self, updated_metrics: FrameMetrics):
        """更新帧指标"""
        for i, metrics in enumerate(self.frame_metrics):
            if metrics.frame_index == updated_metrics.frame_index:
                self.frame_metrics[i] = updated_metrics
                return
        
        # 如果没找到，添加新的
        self.frame_metrics.append(updated_metrics)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取计算统计信息
        
        Returns:
            统计信息字典
        """
        if not self.frame_metrics:
            return {
                "total_frames_processed": 0,
                "frames_with_detections": 0,
                "frames_with_segmentations": 0,
                "avg_detections_per_frame": 0.0,
                "avg_segmentations_per_frame": 0.0,
                "self_appearance_frames": 0
            }
        
        frames_with_detections = len([fm for fm in self.frame_metrics if fm.detection_count > 0])
        frames_with_segmentations = len([fm for fm in self.frame_metrics if fm.segmentation_count > 0])
        total_detections = sum(fm.detection_count for fm in self.frame_metrics)
        total_segmentations = sum(fm.segmentation_count for fm in self.frame_metrics)
        self_appearance_frames = len([fm for fm in self.frame_metrics if fm.has_self_appearance])
        
        return {
            "total_frames_processed": len(self.frame_metrics),
            "frames_with_detections": frames_with_detections,
            "frames_with_segmentations": frames_with_segmentations,
            "avg_detections_per_frame": total_detections / len(self.frame_metrics),
            "avg_segmentations_per_frame": total_segmentations / len(self.frame_metrics),
            "self_appearance_frames": self_appearance_frames,
            "detection_sampling_coverage": self.detection_frames_count,
            "segmentation_sampling_coverage": self.segmentation_frames_count
        }
    
    def reset(self):
        """重置计算器状态"""
        self.frame_metrics.clear()
        self.total_frames = 0
        self.detection_frames_count = 0
        self.segmentation_frames_count = 0


class ThresholdManager:
    """阈值管理器"""
    
    # 默认阈值配置
    DEFAULT_THRESHOLDS = {
        "WDD": {
            "excellent": 0.1,
            "acceptable": 0.25,
            "review": 1.0,
            "reject": 8.0
        },
        "WPO": {
            "excellent": 0.1,
            "acceptable": 0.25,
            "review": 1.0,
            "reject": 8.0
        },
        "SAI": {
            "excellent": 0.1,
            "acceptable": 0.5,
            "review": 2.0,
            "reject": 10.0
        }
    }
    
    def __init__(self, scene_type: str = "default"):
        """
        初始化阈值管理器
        
        Args:
            scene_type: 场景类型 ("indoor", "outdoor", "default")
        """
        self.scene_type = scene_type
        self.thresholds = self._get_scene_thresholds(scene_type)
    
    def _get_scene_thresholds(self, scene_type: str) -> Dict:
        """根据场景类型获取阈值配置"""
        # 可以根据场景类型调整阈值
        base_thresholds = self.DEFAULT_THRESHOLDS.copy()
        
        if scene_type == "indoor":
            # 室内环境更严格
            base_thresholds["WDD"]["reject"] = 4.0
            base_thresholds["WPO"]["reject"] = 4.0
        elif scene_type == "outdoor":
            # 室外稍宽松
            base_thresholds["WDD"]["reject"] = 8.0
            base_thresholds["WPO"]["reject"] = 8.0
        
        return base_thresholds
    
    def evaluate_metric(self, metric_name: str, value: float) -> str:
        """
        评估单个指标
        
        Args:
            metric_name: 指标名称
            value: 指标值
            
        Returns:
            评估等级 ("excellent", "acceptable", "review", "reject")
        """
        if metric_name not in self.thresholds:
            return "unknown"
        
        thresholds = self.thresholds[metric_name]
        
        if value < thresholds["excellent"]:
            return "excellent"
        elif value < thresholds["acceptable"]:
            return "acceptable"
        elif value < thresholds["review"]:
            return "review"
        else:
            return "reject"
    
    def get_threshold_info(self) -> Dict:
        """获取阈值配置信息"""
        return {
            "scene_type": self.scene_type,
            "thresholds": self.thresholds
        }