"""
Base Validation Framework

Defines the core interfaces and base classes for the validation system.
This provides a foundation for implementing different validation strategies
and scoring algorithms.

Key Validation Metrics (for transient object detection):
- WDD (Weighted Detection Density): Measures frequency of person/dog detections across image regions
  Higher values indicate more moving objects that could interfere with 3D reconstruction
- WPO (Weighted Pixel Occupancy): Percentage of image area covered by person/dog objects
  Higher values mean objects block more of the scene, affecting reconstruction quality  
- SAI (Self-Appearance Index): Percentage indicating photographer visibility in their own images
  Higher values create unwanted artifacts in 3D models as the photographer shouldn't be in the scene

数据契约说明：
- 所有validator必须返回标准的ValidationResult
- metadata必须包含{validator_name}_validation字段
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

class ValidationLevel(Enum):
    """Validation strictness levels"""
    STRICT = "strict"
    STANDARD = "standard" 
    LENIENT = "lenient"

@dataclass
class ValidationResult:
    """
    Standardized validation result structure

    IMPORTANT: Score vs is_valid Mechanism
    =======================================
    - score (0-100): Quality metric for tracking/reporting, NOT a gate
    - is_valid (True/False): The actual gate that determines if processing proceeds
    - A package can have low score (e.g., 40/100) but still process if is_valid=True
    - is_valid is based on error count/type, NOT on score threshold
    - Only is_valid=False blocks 3D reconstruction processing

    数据契约要求：
    ===== METADATA结构契约 =====
    metadata必须包含：

    1. 提取的元数据（从数据包解析）：
       - extracted_metadata: Dict (包含start_time, duration, location等)
       
    3. VALIDATOR结果（每个validator必须添加）：
       - {validator_name}_validation: ValidatorDataContract
       
    4. 流水线结果（多validator组合时）：
       - validation_pipeline: Dict (组合验证的结果和权重)
       
    VALIDATOR结果格式契约：
    {validator_name}_validation = {
        "decision": str,              # 必须来自ValidationDecisionContract (PASS/FAIL/NEED_REVIEW/ERROR/SKIP)
        "confidence": float,          # 可选：0.0-1.0
        "timestamp": str,             # ISO格式时间戳
        "metrics": {                  # 可选：详细指标
            "score": float,           # 得分
            "任何自定义指标": Any       # validator特定的指标
        },
        "problems_found": List[str],  # 发现的问题
        "processing_time_ms": float,  # 可选：处理时间
        "details": Dict              # 可选：validator特定的详细信息
    }
    
    示例：
    metadata = {
        "manager_version": "1.0",
        "selected_validator": "TransientValidator",
        "extracted_metadata": {
            "start_time": "2025-08-10 07:40:52",
            "location": {"latitude": "40.692°N", "longitude": "73.989°W"}
        },
        "transient_validation": {
            "transient_detection": {
                "decision": "PASS",
                "metrics": {"WDD": 0.14, "WPO": 0.0, "SAI": 5.6},
                "problems_found": []
            }
        }
    }
    """
    is_valid: bool
    validation_level: ValidationLevel
    score: float  # 0-100 score
    errors: List[str]
    warnings: List[str] 
    missing_files: List[str]
    missing_directories: List[str]
    extra_files: List[str]
    file_details: Dict[str, Dict[str, Any]]
    summary: str
    validator_type: str = "unknown"
    metadata: Dict[str, Any] = None  # 必须符合STANDARD_METADATA_FORMAT契约
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class BaseValidator(ABC):
    """
    Abstract base class for all validators.
    
    This provides the interface that all validators must implement,
    allowing for easy extension and consistent behavior.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the validator
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.validator_type = self.__class__.__name__
    
    @abstractmethod
    def validate(self, target_path: str, validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
        """
        Perform validation on the target
        
        Args:
            target_path: Path to validate
            validation_level: Strictness level for validation
            
        Returns:
            ValidationResult: Complete validation results
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """
        Get list of supported data formats/types
        
        Returns:
            List of supported format identifiers
        """
        pass
    
    def calculate_score(self, errors: List[str], warnings: List[str], 
                       missing_files: List[str], missing_directories: List[str]) -> float:
        """
        Calculate validation score based on issues found.
        Can be overridden by specific validators for custom scoring.
        
        Args:
            errors: List of error messages
            warnings: List of warning messages  
            missing_files: List of missing file paths
            missing_directories: List of missing directory paths
            
        Returns:
            float: Score from 0.0 to 100.0
        """
        # Use centralized config for scoring weights
        from config import Config
        base_score = Config.VALIDATION_BASE_SCORE
        
        # Get weights from config (allow validator-specific override)
        error_weight = self.config.get('error_weight', Config.VALIDATION_ERROR_WEIGHT)
        warning_weight = self.config.get('warning_weight', Config.VALIDATION_WARNING_WEIGHT)
        missing_weight = self.config.get('missing_weight', Config.VALIDATION_MISSING_WEIGHT)
        
        # Calculate penalties
        error_penalty = len(errors) * error_weight
        warning_penalty = len(warnings) * warning_weight
        missing_penalty = (len(missing_files) + len(missing_directories)) * missing_weight
        
        # Calculate final score
        final_score = max(0.0, base_score - error_penalty - warning_penalty - missing_penalty)
        
        return final_score
    
    def determine_validity(self, validation_level: ValidationLevel, errors: List[str],
                          missing_files: List[str], missing_directories: List[str]) -> bool:
        """
        Determine if validation passes based on level and issues found.
        Can be overridden by specific validators.
        
        Args:
            validation_level: Validation strictness level
            errors: List of errors found
            missing_files: List of missing files
            missing_directories: List of missing directories
            
        Returns:
            bool: Whether validation passes
        """
        if validation_level == ValidationLevel.STRICT:
            return len(errors) == 0 and len(missing_files) == 0 and len(missing_directories) == 0
        
        elif validation_level == ValidationLevel.STANDARD:
            # Allow minor issues but not critical errors
            from config import Config
            critical_errors = [e for e in errors if self._is_critical_error(e)]
            return len(critical_errors) == 0 and len(missing_files) <= Config.VALIDATION_STANDARD_MAX_MISSING_FILES
        
        else:  # LENIENT
            from config import Config
            return len(errors) <= Config.VALIDATION_LENIENT_MAX_ERRORS
    
    def _is_critical_error(self, error: str) -> bool:
        """
        Determine if an error is critical.
        Can be overridden by specific validators.
        
        Args:
            error: Error message to check
            
        Returns:
            bool: Whether the error is critical
        """
        critical_keywords = ['corruption', 'invalid format', 'missing schema', 'parsing error']
        return any(keyword in error.lower() for keyword in critical_keywords)
    
    def generate_summary(self, is_valid: bool, score: float, 
                        error_count: int, warning_count: int) -> str:
        """
        Generate a summary message for validation results
        
        Args:
            is_valid: Whether validation passed
            score: Validation score
            error_count: Number of errors
            warning_count: Number of warnings
            
        Returns:
            str: Summary message
        """
        status = "PASS" if is_valid else "FAIL"
        return f"Validation {status} - Score: {score:.1f}/100, Errors: {error_count}, Warnings: {warning_count}"

class ValidationException(Exception):
    """Custom exception for validation errors"""
    
    def __init__(self, message: str, validator_type: str = None, context: Dict[str, Any] = None):
        super().__init__(message)
        self.validator_type = validator_type
        self.context = context or {}