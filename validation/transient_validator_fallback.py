"""
Fallback TransientValidator for when YOLO dependencies are not available

This provides basic camera_images format recognition without actual detection
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import logging

from validation.base import BaseValidator, ValidationResult, ValidationLevel
from utils.logger import get_logger

logger = get_logger(__name__)


class TransientValidatorFallback(BaseValidator):
    """
    Fallback版本的移动障碍物验证器
    
    当YOLO依赖不可用时使用此版本，提供基本的格式识别但不执行实际检测
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化fallback验证器
        
        Args:
            config: 验证器配置
        """
        super().__init__(config)
        self.validator_type = "TransientValidatorFallback"
        logger.info("Using fallback TransientValidator (YOLO dependencies not available)")
    
    def get_supported_formats(self) -> List[str]:
        """获取支持的格式"""
        return ["camera_images", "stereo_camera", "image_sequence"]
    
    def validate(self, target_path: str, validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
        """
        执行fallback验证（不进行实际检测）
        
        Args:
            target_path: 数据目录路径
            validation_level: 验证级别
            
        Returns:
            ValidationResult: 验证结果
        """
        logger.info(f"Starting fallback transient validation for: {target_path}")
        
        # 初始化结果
        errors = []
        warnings = ["移动障碍物检测功能不可用 - 缺少YOLO依赖项"]
        missing_files = []
        missing_directories = []
        extra_files = []
        file_details = {}
        
        try:
            # 检查cameras或camera文件夹
            cameras_path = os.path.join(target_path, "cameras")
            camera_path = os.path.join(target_path, "camera")
            
            # 优先检查cameras目录，如果不存在再检查camera目录
            if os.path.exists(cameras_path):
                base_camera_path = cameras_path
                camera_dir_name = "cameras"
            elif os.path.exists(camera_path):
                base_camera_path = camera_path
                camera_dir_name = "camera"
            else:
                errors.append("Missing cameras or camera directory")
                missing_directories.append("cameras")
                return self._create_fallback_result(
                    validation_level, errors, warnings, missing_files, 
                    missing_directories, extra_files, file_details, {}
                )
            
            # 检查left和right文件夹
            left_path = os.path.join(base_camera_path, "left")
            right_path = os.path.join(base_camera_path, "right")
            
            cameras_found = []
            total_images = 0
            
            if os.path.exists(left_path):
                left_images = self._count_images(left_path)
                if left_images > 0:
                    cameras_found.append(f"left ({left_images} images)")
                    total_images += left_images
            else:
                warnings.append(f"Missing {camera_dir_name}/left directory")
            
            if os.path.exists(right_path):
                right_images = self._count_images(right_path)
                if right_images > 0:
                    cameras_found.append(f"right ({right_images} images)")
                    total_images += right_images
            else:
                warnings.append(f"Missing {camera_dir_name}/right directory")
            
            if not cameras_found:
                errors.append("No camera directories with images found")
                return self._create_fallback_result(
                    validation_level, errors, warnings, missing_files,
                    missing_directories, extra_files, file_details, {}
                )
            
            # 创建fallback的移动障碍物检测结果
            metadata = {
                "transient_detection": {
                    "decision": "ERROR",  # 表示检测不可用
                    "metrics": {
                        "WDD": 0.0,
                        "WPO": 0.0,
                        "SAI": 0.0
                    },
                    "assessment_timestamp": "",
                    "problems_found": ["YOLO依赖项不可用，无法执行检测"],
                    "scene_type": "unknown"
                },
                "camera_info": {
                    "cameras_found": cameras_found,
                    "total_images": total_images,
                    "left_camera": {
                        "exists": os.path.exists(left_path),
                        "image_count": self._count_images(left_path) if os.path.exists(left_path) else 0
                    },
                    "right_camera": {
                        "exists": os.path.exists(right_path),
                        "image_count": self._count_images(right_path) if os.path.exists(right_path) else 0
                    }
                }
            }
            
            # 计算分数
            score = 50.0  # 中等分数，因为结构正确但无法检测
            
            # 判断验证结果
            is_valid = len(cameras_found) > 0 and total_images > 0
            
            summary = f"Fallback validation - Found {len(cameras_found)} camera(s) with {total_images} images, but detection unavailable"
            
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
            
        except Exception as e:
            error_msg = f"Fallback validation exception: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            return self._create_fallback_result(
                validation_level, errors, warnings, missing_files,
                missing_directories, extra_files, file_details, {}
            )
    
    def _count_images(self, directory_path: str) -> int:
        """计算目录中的图像文件数量"""
        if not os.path.exists(directory_path):
            return 0
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        
        try:
            count = 0
            for file_path in Path(directory_path).iterdir():
                if file_path.is_file() and file_path.suffix.lower() in image_extensions:
                    count += 1
            return count
        except Exception as e:
            logger.warning(f"Failed to count images in {directory_path}: {e}")
            return 0
    
    def _create_fallback_result(self, validation_level: ValidationLevel,
                               errors: List[str], warnings: List[str],
                               missing_files: List[str], missing_directories: List[str],
                               extra_files: List[str], file_details: Dict[str, Dict[str, Any]],
                               metadata: Dict[str, Any]) -> ValidationResult:
        """创建fallback验证结果"""
        
        # 添加fallback的移动障碍物检测数据（即使失败也要有结构）
        if 'transient_detection' not in metadata:
            metadata['transient_detection'] = {
                "decision": "ERROR",
                "metrics": {"WDD": 0.0, "WPO": 0.0, "SAI": 0.0},
                "assessment_timestamp": "",
                "problems_found": ["验证失败"],
                "scene_type": "unknown"
            }
        
        score = self.calculate_score(errors, warnings, missing_files, missing_directories)
        is_valid = self.determine_validity(validation_level, errors, missing_files, missing_directories)
        summary = self.generate_summary(is_valid, score, len(errors), len(warnings))
        
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