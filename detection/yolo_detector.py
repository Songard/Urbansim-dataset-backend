"""
YOLO11检测和分割模型封装

基于YOLO11实现person和dog的检测与分割功能
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional, Union
import logging
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None
    logging.warning("ultralytics not found. Please install: pip install ultralytics")


class YOLODetector:
    """YOLO11检测器封装类"""
    
    PERSON_CLASS = 0
    DOG_CLASS = 16
    TARGET_CLASSES = [PERSON_CLASS, DOG_CLASS]
    CLASS_NAMES = {PERSON_CLASS: "person", DOG_CLASS: "dog"}
    
    def __init__(self, model_name: str = None, 
                 conf_threshold: float = None,
                 device: str = None):
        """
        初始化YOLO检测器
        
        Args:
            model_name: 模型名称或路径
            conf_threshold: 置信度阈值
            device: 计算设备 ('cpu', 'cuda', '0', etc.)
        """
        if YOLO is None:
            raise ImportError("ultralytics package is required. Please install: pip install ultralytics")
        
        # Use centralized config with parameter override
        from config import Config
        self.model_name = model_name or Config.YOLO_MODEL_NAME
        self.conf_threshold = conf_threshold if conf_threshold is not None else Config.YOLO_CONF_THRESHOLD
        self.device = device or Config.YOLO_DEVICE
        self.model = None
        self.seg_model = None
        
        self._load_models()
    
    def _load_models(self):
        """加载YOLO模型"""
        try:
            # 检测模型
            self.model = YOLO(self.model_name)
            self.model.to(self.device)
            
            # 分割模型
            # 生成分割模型名称：yolo11n.pt -> yolo11n-seg.pt
            if self.model_name.endswith('.pt'):
                base_name = self.model_name[:-3]  # 移除.pt
                if base_name == 'yolo11n':
                    seg_model_name = 'yolo11n-seg.pt'
                else:
                    seg_model_name = base_name + '-seg.pt'
            else:
                seg_model_name = self.model_name + '-seg'
            try:
                self.seg_model = YOLO(seg_model_name)
                self.seg_model.to(self.device)
                logging.info(f"Loaded segmentation model: {seg_model_name}")
            except Exception as e:
                logging.warning(f"Segmentation model {seg_model_name} not found, attempting to download...")
                try:
                    # 自动下载分割模型
                    self.seg_model = YOLO(seg_model_name)  # YOLO会自动下载不存在的模型
                    self.seg_model.to(self.device)
                    logging.info(f"Successfully downloaded and loaded segmentation model: {seg_model_name}")
                except Exception as download_error:
                    logging.error(f"CRITICAL: Failed to download segmentation model: {download_error}")
                    self.seg_model = None
            
            logging.info(f"Loaded detection model: {self.model_name}")
            
        except Exception as e:
            logging.error(f"Failed to load YOLO model: {e}")
            raise
    
    def detect_batch(self, images: List[np.ndarray], 
                    batch_size: int = 16) -> List[Dict]:
        """
        批量检测图像中的目标
        
        Args:
            images: 图像列表
            batch_size: 批处理大小
            
        Returns:
            检测结果列表
        """
        if not self.model:
            raise RuntimeError("Model not loaded")
        
        results = []
        
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            
            try:
                batch_results = self.model(
                    batch,
                    classes=self.TARGET_CLASSES,
                    conf=self.conf_threshold,
                    verbose=False
                )
                
                for result in batch_results:
                    detections = self._parse_detection_result(result)
                    results.append(detections)
                    
            except Exception as e:
                logging.error(f"Batch detection failed: {e}")
                # 为失败的批次添加空结果
                for _ in range(len(batch)):
                    results.append({"detections": [], "error": str(e)})
        
        return results
    
    def segment_batch(self, images: List[np.ndarray], 
                     batch_size: int = 8) -> List[Dict]:
        """
        批量分割图像中的目标
        
        Args:
            images: 图像列表
            batch_size: 批处理大小（分割比检测慢，用较小批次）
            
        Returns:
            分割结果列表
        """
        if not self.seg_model:
            # 只在第一次调用时警告，避免重复日志
            if not hasattr(self, '_seg_warning_shown'):
                logging.error("CRITICAL: Segmentation model not available, falling back to detection model - this may impact accuracy")
                self._seg_warning_shown = True
            return self.detect_batch(images, batch_size)
        
        results = []
        
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            
            try:
                batch_results = self.seg_model(
                    batch,
                    classes=self.TARGET_CLASSES,
                    conf=self.conf_threshold,
                    verbose=False
                )
                
                for result in batch_results:
                    segmentations = self._parse_segmentation_result(result)
                    results.append(segmentations)
                    
            except Exception as e:
                logging.error(f"Batch segmentation failed: {e}")
                # 为失败的批次添加空结果
                for _ in range(len(batch)):
                    results.append({"segmentations": [], "error": str(e)})
        
        return results
    
    def detect_single(self, image: np.ndarray) -> Dict:
        """
        检测单张图像
        
        Args:
            image: 输入图像
            
        Returns:
            检测结果
        """
        return self.detect_batch([image])[0]
    
    def segment_single(self, image: np.ndarray) -> Dict:
        """
        分割单张图像
        
        Args:
            image: 输入图像
            
        Returns:
            分割结果
        """
        return self.segment_batch([image])[0]
    
    def _parse_detection_result(self, result) -> Dict:
        """
        解析检测结果
        
        Args:
            result: YOLO检测结果
            
        Returns:
            解析后的检测结果
        """
        detections = {
            "detections": [],
            "image_shape": result.orig_shape if hasattr(result, 'orig_shape') else None
        }
        
        if result.boxes is not None and len(result.boxes) > 0:
            boxes = result.boxes.xyxy.cpu().numpy()  # x1, y1, x2, y2
            confidences = result.boxes.conf.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy().astype(int)
            
            for i, (box, conf, cls) in enumerate(zip(boxes, confidences, classes)):
                if cls in self.TARGET_CLASSES:
                    detection = {
                        "bbox": box.tolist(),  # [x1, y1, x2, y2]
                        "confidence": float(conf),
                        "class_id": int(cls),
                        "class_name": self.CLASS_NAMES.get(cls, f"class_{cls}")
                    }
                    detections["detections"].append(detection)
        
        return detections
    
    def _parse_segmentation_result(self, result) -> Dict:
        """
        解析分割结果
        
        Args:
            result: YOLO分割结果
            
        Returns:
            解析后的分割结果
        """
        segmentations = {
            "segmentations": [],
            "image_shape": result.orig_shape if hasattr(result, 'orig_shape') else None
        }
        
        # 首先解析检测框
        detection_result = self._parse_detection_result(result)
        
        # 如果有分割掩码
        if hasattr(result, 'masks') and result.masks is not None:
            masks_data = result.masks.data.cpu().numpy()  # (N, H, W)
            
            for i, detection in enumerate(detection_result["detections"]):
                if i < len(masks_data):
                    mask = masks_data[i]
                    
                    # 计算掩码面积
                    from config import Config
                    mask_area = np.sum(mask > Config.REGION_MASK_THRESHOLD)
                    total_pixels = mask.shape[0] * mask.shape[1]
                    area_ratio = mask_area / total_pixels if total_pixels > 0 else 0
                    
                    # 获取掩码轮廓点
                    mask_points = self._extract_mask_points(mask)
                    
                    segmentation = {
                        **detection,  # 包含检测框信息
                        "mask_area": int(mask_area),
                        "area_ratio": float(area_ratio),
                        "mask_points": mask_points,
                        "has_mask": True
                    }
                else:
                    # 没有对应掩码，只保留检测信息
                    segmentation = {
                        **detection,
                        "mask_area": 0,
                        "area_ratio": 0.0,
                        "mask_points": [],
                        "has_mask": False
                    }
                
                segmentations["segmentations"].append(segmentation)
        else:
            # 没有分割掩码，将检测结果转换为分割格式
            for detection in detection_result["detections"]:
                segmentation = {
                    **detection,
                    "mask_area": 0,
                    "area_ratio": 0.0,
                    "mask_points": [],
                    "has_mask": False
                }
                segmentations["segmentations"].append(segmentation)
        
        return segmentations
    
    def _extract_mask_points(self, mask: np.ndarray, 
                           sample_ratio: float = None) -> List[Tuple[float, float]]:
        """
        从掩码中提取采样点
        
        Args:
            mask: 二值掩码
            sample_ratio: 采样比例，默认使用配置值
            
        Returns:
            采样点列表
        """
        from config import Config
        if sample_ratio is None:
            sample_ratio = Config.REGION_MASK_SAMPLE_RATIO
            
        # 找到掩码中的非零点
        y_coords, x_coords = np.where(mask > Config.REGION_MASK_THRESHOLD)
        
        if len(x_coords) == 0:
            return []
        
        # 采样点（减少计算量）
        total_points = len(x_coords)
        sample_count = max(1, int(total_points * sample_ratio))
        
        if sample_count < total_points:
            indices = np.random.choice(total_points, sample_count, replace=False)
            x_coords = x_coords[indices]
            y_coords = y_coords[indices]
        
        return [(float(x), float(y)) for x, y in zip(x_coords, y_coords)]
    
    def get_model_info(self) -> Dict:
        """
        获取模型信息
        
        Returns:
            模型信息字典
        """
        return {
            "detection_model": self.model_name,
            "segmentation_available": self.seg_model is not None,
            "target_classes": {
                "person": self.PERSON_CLASS,
                "dog": self.DOG_CLASS
            },
            "confidence_threshold": self.conf_threshold,
            "device": self.device
        }


class AdaptiveSampler:
    """自适应采样器"""
    
    @staticmethod
    def calculate_sampling_rates(total_frames: int) -> Dict[str, int]:
        """
        根据总帧数计算采样率
        
        Args:
            total_frames: 总帧数
            
        Returns:
            采样率配置
        """
        if total_frames <= 200:
            return {"detection": 1, "segmentation": 1}
        elif total_frames <= 500:
            return {"detection": 2, "segmentation": 3}
        elif total_frames <= 1000:
            return {"detection": 4, "segmentation": 6}
        else:
            return {"detection": 6, "segmentation": 9}
    
    @staticmethod
    def sample_frames(total_frames: int, sampling_rate: int, 
                     start_frame: int = 0) -> List[int]:
        """
        生成采样帧索引
        
        Args:
            total_frames: 总帧数
            sampling_rate: 采样率（每N帧采样一帧）
            start_frame: 起始帧
            
        Returns:
            采样帧索引列表
        """
        return list(range(start_frame, total_frames, sampling_rate))