"""
移动障碍物验证器 (Transient Object Validator)

Integrates YOLO11 detection system into the validation framework to process image sequences 
from cameras/left and cameras/right folders.

This validator detects and analyzes moving objects (people, dogs) in MetaCam image sequences
to assess their impact on 3D reconstruction quality using three core metrics:

WDD (Weighted Detection Density): Measures how frequently person/dog objects are detected
    - Weighted by image region importance (center regions have higher weights)
    - Higher values = more frequent detection = more interference with reconstruction

WPO (Weighted Pixel Occupancy): Percentage of image pixels occupied by person/dog objects  
    - Calculated from segmentation masks to determine actual coverage area
    - Higher values = more scene obstruction = worse reconstruction quality

SAI (Self-Appearance Index): Percentage indicating photographer appearing in their own capture
    - Detected when person appears in bottom center region with appropriate size
    - Higher values = more self-appearance artifacts = degraded 3D model quality

Decision Logic:
- PASS: All metrics below problem thresholds, good for 3D reconstruction
- NEED_REVIEW: 2+ metrics exceed problem thresholds, manual review recommended  
- REJECT: Any metric exceeds critical threshold, unsuitable for 3D reconstruction
- ERROR: Technical issues during detection process
"""

import os
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

import sys
import os
from pathlib import Path

# 添加项目根目录到path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from validation.base import BaseValidator, ValidationResult, ValidationLevel
from detection.transient_detector import create_detector, DetectionConfig
from detection.quality_decision import QualityDecision, QualityAssessmentResult
from utils.logger import get_logger

logger = get_logger(__name__)


class CameraImageSequenceLoader:
    """相机图像序列加载器，专门处理cameras/left和right文件夹"""
    
    def __init__(self, cameras_path: str):
        """
        初始化图像序列加载器
        
        Args:
            cameras_path: cameras文件夹路径
        """
        self.cameras_path = Path(cameras_path)
        self.left_path = self.cameras_path / "left"
        self.right_path = self.cameras_path / "right"
        
        self.left_images = []
        self.right_images = []
        self.total_images = 0
        
        self._load_image_lists()
    
    def _load_image_lists(self):
        """加载图像文件列表"""
        # 加载left文件夹图像
        if self.left_path.exists():
            self.left_images = sorted([
                f for f in self.left_path.glob("*") 
                if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']
            ])
            logger.info(f"Found {len(self.left_images)} left camera images")
        
        # 加载right文件夹图像
        if self.right_path.exists():
            self.right_images = sorted([
                f for f in self.right_path.glob("*")
                if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.bmp']
            ])
            logger.info(f"Found {len(self.right_images)} right camera images")
        
        self.total_images = len(self.left_images) + len(self.right_images)
    
    def load_image_batch(self, camera_side: str, indices: List[int]) -> List[Tuple[int, Optional[np.ndarray]]]:
        """
        批量加载指定相机的图像
        
        Args:
            camera_side: 相机侧别 ("left" or "right")
            indices: 图像索引列表
            
        Returns:
            (图像索引, 图像数据)的列表
        """
        if camera_side == "left":
            image_list = self.left_images
        elif camera_side == "right":
            image_list = self.right_images
        else:
            raise ValueError(f"Invalid camera side: {camera_side}")
        
        results = []
        for idx in indices:
            if idx < len(image_list):
                try:
                    image_path = image_list[idx]
                    image = cv2.imread(str(image_path))
                    results.append((idx, image))
                except Exception as e:
                    logger.warning(f"Failed to load image {image_path}: {e}")
                    results.append((idx, None))
            else:
                results.append((idx, None))
        
        return results
    
    def get_camera_info(self) -> Dict[str, Any]:
        """获取相机信息"""
        info = {
            "cameras_path": str(self.cameras_path),
            "left_camera": {
                "path": str(self.left_path),
                "exists": self.left_path.exists(),
                "image_count": len(self.left_images),
                "first_image": str(self.left_images[0]) if self.left_images else None
            },
            "right_camera": {
                "path": str(self.right_path),
                "exists": self.right_path.exists(),
                "image_count": len(self.right_images),
                "first_image": str(self.right_images[0]) if self.right_images else None
            },
            "total_images": self.total_images
        }
        
        # 获取图像尺寸信息
        if self.left_images:
            try:
                first_image = cv2.imread(str(self.left_images[0]))
                if first_image is not None:
                    info["image_dimensions"] = {
                        "height": first_image.shape[0],
                        "width": first_image.shape[1],
                        "channels": first_image.shape[2]
                    }
            except Exception as e:
                logger.warning(f"Failed to get image dimensions: {e}")
        
        return info


class TransientValidator(BaseValidator):
    """移动障碍物验证器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化移动障碍物验证器
        
        Args:
            config: 验证器配置
        """
        super().__init__(config)
        self.validator_type = "TransientValidator"
        
        # 检测器配置
        if config is None:
            config = {}
        
        # Use centralized config for detection parameters
        from config import Config
        self.detection_config = DetectionConfig(
            model_name=config.get('model_name', Config.YOLO_MODEL_NAME),
            conf_threshold=config.get('conf_threshold', Config.YOLO_CONF_THRESHOLD),
            device=config.get('device', Config.YOLO_DEVICE),
            scene_type=config.get('scene_type', 'default'),
            target_detection_frames=config.get('target_detection_frames', Config.DETECTION_TARGET_DETECTION_FRAMES),
            target_segmentation_frames=config.get('target_segmentation_frames', Config.DETECTION_TARGET_SEGMENTATION_FRAMES),
            enable_early_termination=config.get('enable_early_termination', Config.DETECTION_ENABLE_EARLY_TERMINATION),
            max_workers=config.get('max_workers', Config.DETECTION_MAX_WORKERS),
            memory_limit_mb=config.get('memory_limit_mb', Config.DETECTION_MEMORY_LIMIT_MB),
            output_format='compact'
        )
        
        self.detector = None
        self._initialize_detector()
    
    def _initialize_detector(self):
        """初始化检测器"""
        try:
            # 创建检测器配置，避免参数重复
            detector_config = {
                'model_name': self.detection_config.model_name,
                'scene_type': self.detection_config.scene_type,
                'device': self.detection_config.device,
                'enable_early_termination': self.detection_config.enable_early_termination,
                'max_workers': self.detection_config.max_workers,
                'memory_limit_mb': self.detection_config.memory_limit_mb
            }
            
            self.detector = create_detector(**detector_config)
            # 不要立即初始化模型，留到需要时再初始化
            logger.info("Transient detector created successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize transient detector (this is expected if dependencies are missing): {e}")
            self.detector = None
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的格式"""
        return ["camera_images", "stereo_camera", "image_sequence"]
    
    def _find_camera_directory_recursive(self, root_path: str, max_depth: int = 2) -> Optional[str]:
        """
        Recursively search for camera directory following MetaCam schema standard.
        
        This method searches for the 'camera' directory which contains left/right image sequences
        used for transient object detection. The search is limited in depth to avoid
        performance issues with deeply nested directory structures.
        
        Args:
            root_path: Root directory to start the search from
            max_depth: Maximum recursion depth (default: 2 levels)
            
        Returns:
            Path to camera directory if found, None otherwise
        """
        def search_recursive(current_path: str, depth: int) -> Optional[str]:
            # Limit search depth to prevent infinite recursion and performance issues
            if depth > max_depth:
                return None
            
            try:
                for item in os.listdir(current_path):
                    item_path = os.path.join(current_path, item)
                    if os.path.isdir(item_path):
                        # Check if this is the camera directory (case-insensitive)
                        # Following MetaCam schema: only 'camera' (not 'cameras') is valid
                        if item.lower() == 'camera':
                            return item_path
                        
                        # Recursively search subdirectories
                        if depth < max_depth:
                            result = search_recursive(item_path, depth + 1)
                            if result:
                                return result
            except (PermissionError, FileNotFoundError):
                # Silently skip directories we can't access
                pass
            
            return None
        
        return search_recursive(root_path, 0)
    
    def validate(self, target_path: str, validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
        """
        Perform transient object detection validation on camera image sequences.
        
        This method analyzes camera images from MetaCam data packages to detect moving
        obstacles (people, dogs) that could negatively impact 3D reconstruction quality.
        Uses YOLO11 models for object detection and segmentation.
        
        Validation Process:
        1. Search for camera directory (camera/left, camera/right)
        2. Load and validate image sequences
        3. Apply YOLO11 detection and segmentation models
        4. Calculate quality metrics (WDD, WPO, SAI)
        5. Make quality decision (PASS/NEED_REVIEW/REJECT)
        
        Args:
            target_path: Path to the MetaCam data package directory
            validation_level: Validation strictness level (STRICT/STANDARD/LENIENT)
            
        Returns:
            ValidationResult with transient detection analysis and quality metrics
        """
        logger.info(f"Starting transient validation for: {target_path}")
        
        # Initialize validation result containers
        errors = []
        warnings = []
        missing_files = []
        missing_directories = []
        extra_files = []
        file_details = {}
        metadata = {}
        
        try:
            # Stage 1: Camera directory detection and validation
            # Look for standard MetaCam camera directory structure
            camera_path = os.path.join(target_path, "camera")
            
            logger.info(f"Checking for camera directory in: {target_path}")
            
            # Diagnostic logging to help troubleshoot directory structure issues
            try:
                items_in_target = os.listdir(target_path)
                logger.info(f"Contents of target path: {items_in_target}")
                
                # List all subdirectories for diagnostic purposes
                subdirs = [item for item in items_in_target 
                          if os.path.isdir(os.path.join(target_path, item))]
                logger.info(f"All subdirectories: {subdirs}")
                
            except Exception as e:
                logger.warning(f"Failed to list target directory contents: {e}")
            
            # Check for camera directory at expected location
            if os.path.exists(camera_path):
                base_camera_path = camera_path
                logger.info(f"Found camera directory: {camera_path}")
            else:
                # Fallback: search recursively in subdirectories
                # This handles cases where data is nested after extraction
                found_camera_path = self._find_camera_directory_recursive(target_path)
                if found_camera_path:
                    base_camera_path = found_camera_path
                    logger.info(f"Found camera directory in subdirectory: {found_camera_path}")
                else:
                    # Camera directory not found - critical error for transient detection
                    detailed_error = f"Missing camera directory. Searched in: {target_path}"
                    try:
                        available_dirs = [d for d in os.listdir(target_path) 
                                        if os.path.isdir(os.path.join(target_path, d))]
                        detailed_error += f". Available directories: {available_dirs}"
                    except:
                        pass
                    errors.append(detailed_error)
                    missing_directories.append("camera")
                    return self._create_failed_result(
                        validation_level, errors, warnings, missing_files, 
                        missing_directories, extra_files, file_details, metadata
                    )
            
            # Stage 2: Validate camera subdirectories (left/right)
            # MetaCam format requires at least one camera subdirectory
            left_path = os.path.join(base_camera_path, "left")
            right_path = os.path.join(base_camera_path, "right")
            
            cameras_to_check = []
            if os.path.exists(left_path):
                cameras_to_check.append(("left", left_path))
            else:
                warnings.append(f"Missing camera/left directory")
            
            if os.path.exists(right_path):
                cameras_to_check.append(("right", right_path))
            else:
                warnings.append(f"Missing camera/right directory")
            
            # At least one camera directory is required for transient detection
            if not cameras_to_check:
                errors.append("No camera directories found (left or right)")
                return self._create_failed_result(
                    validation_level, errors, warnings, missing_files,
                    missing_directories, extra_files, file_details, metadata
                )
            
            # Stage 3: Load and validate image sequences
            # Initialize camera image sequence loader for stereo camera setup
            image_loader = CameraImageSequenceLoader(base_camera_path)
            camera_info = image_loader.get_camera_info()
            
            # Ensure we have images to process
            if image_loader.total_images == 0:
                errors.append("No images found in camera directories")
                return self._create_failed_result(
                    validation_level, errors, warnings, missing_files,
                    missing_directories, extra_files, file_details, metadata
                )
            
            # Stage 4: Execute transient object detection using YOLO11 models
            # Process each available camera (left/right) and combine results
            detection_results = {}
            overall_assessment = None
            
            for camera_side, camera_path in cameras_to_check:
                logger.info(f"Processing {camera_side} camera images...")
                
                try:
                    # Run YOLO11 detection and segmentation on camera image sequence
                    assessment = self._detect_camera_sequence(
                        image_loader, camera_side, camera_info
                    )
                    detection_results[camera_side] = assessment
                    
                    # Use the worst assessment as overall result (most conservative approach)
                    # This ensures quality thresholds are maintained across all cameras
                    if (overall_assessment is None or 
                        self._is_worse_decision(assessment.decision, overall_assessment.decision)):
                        overall_assessment = assessment
                        
                except Exception as e:
                    error_msg = f"Detection failed for {camera_side} camera: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # Stage 5: Process and convert detection results to validation result
            if overall_assessment:
                # Convert YOLO11 detection assessment to standardized validation result
                # This includes quality metrics (WDD, WPO, SAI) and decision mapping
                validation_result = self._convert_assessment_to_validation(
                    overall_assessment, detection_results, camera_info,
                    validation_level, errors, warnings, missing_files,
                    missing_directories, extra_files, file_details
                )
                
                logger.info(f"Transient validation completed: {validation_result.summary}")
                return validation_result
            else:
                # All camera processing failed - return error result
                errors.append("All camera detection failed")
                return self._create_failed_result(
                    validation_level, errors, warnings, missing_files,
                    missing_directories, extra_files, file_details, metadata
                )
        
        except Exception as e:
            error_msg = f"Transient validation exception: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            return self._create_failed_result(
                validation_level, errors, warnings, missing_files,
                missing_directories, extra_files, file_details, metadata
            )
    
    def _detect_camera_sequence(self, image_loader: CameraImageSequenceLoader, 
                               camera_side: str, camera_info: Dict) -> QualityAssessmentResult:
        """
        检测相机图像序列中的移动障碍物
        
        Args:
            image_loader: 图像加载器
            camera_side: 相机侧别
            camera_info: 相机信息
            
        Returns:
            质量评估结果
        """
        if not self.detector:
            raise RuntimeError("Transient detector not initialized")
        
        # 获取图像列表
        if camera_side == "left":
            image_list = image_loader.left_images
        else:
            image_list = image_loader.right_images
        
        if not image_list:
            raise RuntimeError(f"No images found for {camera_side} camera")
        
        # 创建一个临时的"视频"检测流程，但使用图像序列
        return self._process_image_sequence(image_list, camera_info)
    
    def _process_image_sequence(self, image_paths: List[Path], 
                               camera_info: Dict) -> QualityAssessmentResult:
        """
        处理图像序列进行移动障碍物检测
        
        Args:
            image_paths: 图像路径列表
            camera_info: 相机信息
            
        Returns:
            质量评估结果
        """
        from detection.metrics_calculator import MetricsCalculator
        from detection.region_manager import RegionManager
        from detection.quality_decision import QualityDecisionEngine
        from detection.sampling_optimizer import AdaptiveSamplingStrategy
        
        # 获取图像尺寸
        img_width = camera_info.get('image_dimensions', {}).get('width', 1920)
        img_height = camera_info.get('image_dimensions', {}).get('height', 1080)
        
        # 初始化组件
        region_manager = RegionManager(img_width, img_height)
        metrics_calculator = MetricsCalculator(img_width, img_height)
        decision_engine = QualityDecisionEngine(self.detection_config.scene_type)
        
        # 计算采样策略
        total_frames = len(image_paths)
        sampling_config = AdaptiveSamplingStrategy.calculate_optimal_rates(
            total_frames,
            target_detection_frames=min(self.detection_config.target_detection_frames, total_frames // 2),
            target_segmentation_frames=min(self.detection_config.target_segmentation_frames, total_frames // 4)
        )
        
        # 生成采样索引
        detection_indices = list(range(0, total_frames, sampling_config.detection_rate))
        segmentation_indices = list(range(0, total_frames, sampling_config.segmentation_rate))
        
        logger.info(f"Processing {len(detection_indices)} frames for detection, "
                   f"{len(segmentation_indices)} frames for segmentation")
        
        # 初始化检测器模型
        self.detector.initialize_models()
        
        # 批量处理检测
        self._process_detection_batch(
            image_paths, detection_indices, metrics_calculator, sampling_config.batch_size_detection
        )
        
        # 批量处理分割（如果需要）
        if segmentation_indices:
            self._process_segmentation_batch(
                image_paths, segmentation_indices, metrics_calculator, sampling_config.batch_size_segmentation
            )
        
        # 计算最终指标
        final_metrics = metrics_calculator.calculate_final_metrics(
            total_frames,
            {"detection": sampling_config.detection_rate, "segmentation": sampling_config.segmentation_rate}
        )
        
        # 生成质量评估
        processing_stats = {
            "total_frames": total_frames,
            "detection_frames_processed": len(detection_indices),
            "segmentation_frames_processed": len(segmentation_indices),
            "early_terminated": False
        }
        
        additional_stats = {
            "camera_info": camera_info,
            "sampling_config": sampling_config.__dict__,
            "calculator_stats": metrics_calculator.get_statistics()
        }
        
        return decision_engine.evaluate_quality(final_metrics, processing_stats, additional_stats)
    
    def _process_detection_batch(self, image_paths: List[Path], detection_indices: List[int],
                                metrics_calculator, batch_size: int):
        """批量处理检测"""
        for i in range(0, len(detection_indices), batch_size):
            batch_indices = detection_indices[i:i + batch_size]
            
            # 加载批次图像
            batch_images = []
            valid_indices = []
            
            for idx in batch_indices:
                try:
                    image = cv2.imread(str(image_paths[idx]))
                    if image is not None:
                        batch_images.append(image)
                        valid_indices.append(idx)
                except Exception as e:
                    logger.warning(f"Failed to load image {idx}: {e}")
            
            if not batch_images:
                continue
            
            # 执行批量检测
            try:
                batch_results = self.detector.yolo_detector.detect_batch(batch_images)
                
                # 处理结果
                for j, result in enumerate(batch_results):
                    if j < len(valid_indices):
                        frame_idx = valid_indices[j]
                        metrics_calculator.process_detection_frame(frame_idx, result)
            
            except Exception as e:
                logger.error(f"Detection batch processing failed: {e}")
    
    def _process_segmentation_batch(self, image_paths: List[Path], segmentation_indices: List[int],
                                   metrics_calculator, batch_size: int):
        """批量处理分割"""
        for i in range(0, len(segmentation_indices), batch_size):
            batch_indices = segmentation_indices[i:i + batch_size]
            
            # 加载批次图像
            batch_images = []
            valid_indices = []
            
            for idx in batch_indices:
                try:
                    image = cv2.imread(str(image_paths[idx]))
                    if image is not None:
                        batch_images.append(image)
                        valid_indices.append(idx)
                except Exception as e:
                    logger.warning(f"Failed to load image {idx}: {e}")
            
            if not batch_images:
                continue
            
            # 执行批量分割
            try:
                batch_results = self.detector.yolo_detector.segment_batch(batch_images)
                
                # 处理结果
                for j, result in enumerate(batch_results):
                    if j < len(valid_indices):
                        frame_idx = valid_indices[j]
                        metrics_calculator.process_segmentation_frame(frame_idx, result)
            
            except Exception as e:
                logger.error(f"Segmentation batch processing failed: {e}")
    
    def _is_worse_decision(self, decision1: QualityDecision, decision2: QualityDecision) -> bool:
        """判断哪个决策结果更严重"""
        severity_order = {
            QualityDecision.PASS: 0,
            QualityDecision.NEED_REVIEW: 1,
            QualityDecision.REJECT: 2,
            QualityDecision.ERROR: 3
        }
        return severity_order.get(decision1, 3) > severity_order.get(decision2, 0)
    
    def _convert_assessment_to_validation(self, assessment: QualityAssessmentResult,
                                        detection_results: Dict, camera_info: Dict,
                                        validation_level: ValidationLevel,
                                        errors: List[str], warnings: List[str],
                                        missing_files: List[str], missing_directories: List[str],
                                        extra_files: List[str], file_details: Dict[str, Dict[str, Any]]) -> ValidationResult:
        """
        将检测评估结果转换为验证结果
        
        ===== METADATA契约要求 =====
        返回的ValidationResult.metadata必须包含：
        
        transient_validation: {
            transient_detection: {
                decision: str,           # 来自ValidationDecisionContract (PASS/NEED_REVIEW/REJECT/ERROR)
                metrics: {
                    WDD: float,          # 加权检测密度
                    WPO: float,          # 加权人员占用率 
                    SAI: float           # 场景活动指数
                },
                assessment_timestamp: str,    # ISO时间戳
                problems_found: List[str],    # 问题列表
                scene_type: str              # 场景类型
            },
            camera_info: Dict,              # 相机信息
            detection_results: Dict,        # 详细检测结果
            processing_details: Dict,       # 处理详情
            statistics: Dict               # 统计信息
        }
        """
        
        # 根据检测决策添加相应的错误或警告
        if assessment.decision == QualityDecision.REJECT:
            errors.extend(assessment.problems_found)
        elif assessment.decision == QualityDecision.NEED_REVIEW:
            warnings.extend(assessment.problems_found)
        elif assessment.decision == QualityDecision.ERROR:
            errors.append("移动障碍物检测过程出现错误")
        
        # 计算验证分数（基于检测指标）
        score = self._calculate_transient_score(assessment)
        
        # 判断验证是否通过
        is_valid = self._determine_transient_validity(assessment, validation_level)
        
        # 生成摘要
        summary = self._generate_transient_summary(assessment, is_valid, score)
        
        # 准备元数据
        metadata = {
            "transient_detection": {
                "metrics": assessment.metrics,
                "decision": assessment.decision.value,
                "assessment_timestamp": assessment.timestamp,
                "problems_found": assessment.problems_found,
                "scene_type": assessment.scene_type
            },
            "camera_info": camera_info,
            "detection_results": {
                camera: {
                    "metrics": result.metrics,
                    "decision": result.decision.value
                }
                for camera, result in detection_results.items()
            },
            "processing_details": assessment.processing_details,
            "statistics": assessment.statistics
        }
        
        return ValidationResult(
            is_valid=is_valid,
            validation_level=validation_level,
            score=score,
            errors=errors,
            warnings=warnings,
            missing_files=missing_files,
            missing_directories=missing_directories,
            extra_files=extra_files,
            file_details=file_details,
            summary=summary,
            validator_type=self.validator_type,
            metadata=metadata
        )
    
    def _calculate_transient_score(self, assessment: QualityAssessmentResult) -> float:
        """基于检测评估计算验证分数"""
        from config import Config
        base_score = Config.VALIDATION_BASE_SCORE
        
        # 根据检测决策扣分
        if assessment.decision == QualityDecision.REJECT:
            base_score -= Config.TRANSIENT_REJECT_SCORE_PENALTY
        elif assessment.decision == QualityDecision.NEED_REVIEW:
            base_score -= Config.TRANSIENT_REVIEW_SCORE_PENALTY
        elif assessment.decision == QualityDecision.ERROR:
            base_score -= Config.TRANSIENT_ERROR_SCORE_PENALTY
        
        # 根据具体指标进一步调整分数
        metrics = assessment.metrics
        
        # WDD指标影响
        wdd = metrics.get('WDD', 0)
        if wdd >= Config.TRANSIENT_WDD_SEVERE_THRESHOLD:
            base_score -= Config.TRANSIENT_WDD_SEVERE_PENALTY
        elif wdd >= Config.TRANSIENT_WDD_HIGH_THRESHOLD:
            base_score -= Config.TRANSIENT_WDD_HIGH_PENALTY
        elif wdd >= Config.TRANSIENT_WDD_MEDIUM_THRESHOLD:
            base_score -= Config.TRANSIENT_WDD_MEDIUM_PENALTY
        
        # WPO指标影响
        wpo = metrics.get('WPO', 0)
        if wpo >= Config.TRANSIENT_WPO_SEVERE_THRESHOLD:
            base_score -= Config.TRANSIENT_WPO_SEVERE_PENALTY
        elif wpo >= Config.TRANSIENT_WPO_HIGH_THRESHOLD:
            base_score -= Config.TRANSIENT_WPO_HIGH_PENALTY
        elif wpo >= Config.TRANSIENT_WPO_MEDIUM_THRESHOLD:
            base_score -= Config.TRANSIENT_WPO_MEDIUM_PENALTY
        
        # SAI指标影响
        sai = metrics.get('SAI', 0)
        if sai >= Config.TRANSIENT_SAI_SEVERE_THRESHOLD:
            base_score -= Config.TRANSIENT_SAI_SEVERE_PENALTY
        elif sai >= Config.TRANSIENT_SAI_HIGH_THRESHOLD:
            base_score -= Config.TRANSIENT_SAI_HIGH_PENALTY
        elif sai >= Config.TRANSIENT_SAI_MEDIUM_THRESHOLD:
            base_score -= Config.TRANSIENT_SAI_MEDIUM_PENALTY
        
        return max(0.0, base_score)
    
    def _determine_transient_validity(self, assessment: QualityAssessmentResult, 
                                    validation_level: ValidationLevel) -> bool:
        """根据检测评估和验证级别判断是否通过"""
        if validation_level == ValidationLevel.STRICT:
            return assessment.decision == QualityDecision.PASS
        elif validation_level == ValidationLevel.STANDARD:
            return assessment.decision in [QualityDecision.PASS, QualityDecision.NEED_REVIEW]
        else:  # LENIENT
            return assessment.decision != QualityDecision.REJECT
    
    def _generate_transient_summary(self, assessment: QualityAssessmentResult, 
                                   is_valid: bool, score: float) -> str:
        """生成移动障碍物检测验证摘要"""
        status = "PASS" if is_valid else "FAIL"
        decision = assessment.decision.value
        
        metrics = assessment.metrics
        wdd = metrics.get('WDD', 0)
        wpo = metrics.get('WPO', 0)
        sai = metrics.get('SAI', 0)
        
        return (f"Transient Validation {status} - Score: {score:.1f}/100, "
                f"Decision: {decision}, WDD: {wdd:.2f}, WPO: {wpo:.1f}%, SAI: {sai:.1f}%")
    
    def _create_failed_result(self, validation_level: ValidationLevel,
                             errors: List[str], warnings: List[str],
                             missing_files: List[str], missing_directories: List[str],
                             extra_files: List[str], file_details: Dict[str, Dict[str, Any]],
                             metadata: Dict[str, Any]) -> ValidationResult:
        """创建失败的验证结果"""
        score = self.calculate_score(errors, warnings, missing_files, missing_directories)
        summary = self.generate_summary(False, score, len(errors), len(warnings))
        
        return ValidationResult(
            is_valid=False,
            validation_level=validation_level,
            score=score,
            errors=errors,
            warnings=warnings,
            missing_files=missing_files,
            missing_directories=missing_directories,
            extra_files=extra_files,
            file_details=file_details,
            summary=summary,
            validator_type=self.validator_type,
            metadata=metadata
        )