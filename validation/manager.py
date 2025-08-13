"""
Validation Manager

Centralized management of different validators with automatic
validator selection and coordination.
"""

import os
from typing import Dict, List, Optional, Any, Type
from pathlib import Path

from .base import BaseValidator, ValidationResult, ValidationLevel, ValidationException
from utils.logger import get_logger

logger = get_logger(__name__)

class ValidationManager:
    """
    Central manager for all validation operations.
    
    This class handles:
    - Registration of validators
    - Automatic validator selection
    - Validation orchestration
    - Result aggregation
    """
    
    def __init__(self):
        """Initialize the validation manager"""
        self.validators: Dict[str, BaseValidator] = {}
        self.format_mapping: Dict[str, str] = {}  # format -> validator_name
        self.default_validator = None
        
        # Load default validators
        self._load_default_validators()
    
    def register_validator(self, validator: BaseValidator, 
                         is_default: bool = False) -> None:
        """
        Register a new validator
        
        Args:
            validator: The validator instance to register
            is_default: Whether this should be the default validator
        """
        validator_name = validator.validator_type
        self.validators[validator_name] = validator
        
        # Map supported formats to this validator
        for format_type in validator.get_supported_formats():
            self.format_mapping[format_type] = validator_name
        
        if is_default:
            self.default_validator = validator_name
        
        logger.info(f"Registered validator: {validator_name} for formats: {validator.get_supported_formats()}")
    
    def get_validator(self, validator_name: str) -> Optional[BaseValidator]:
        """
        Get a specific validator by name
        
        Args:
            validator_name: Name of the validator to retrieve
            
        Returns:
            The validator instance or None if not found
        """
        return self.validators.get(validator_name)
    
    def auto_select_validator(self, target_path: str, 
                             format_hint: str = None) -> Optional[BaseValidator]:
        """
        Automatically select the best validator for a target
        
        Args:
            target_path: Path to the target for validation
            format_hint: Optional hint about the expected format
            
        Returns:
            The best validator or None if none suitable
        """
        # If format hint provided, try to use that
        if format_hint and format_hint in self.format_mapping:
            validator_name = self.format_mapping[format_hint]
            return self.validators.get(validator_name)
        
        # Try to detect format from path structure
        detected_format = self._detect_format(target_path)
        if detected_format and detected_format in self.format_mapping:
            validator_name = self.format_mapping[detected_format]
            return self.validators.get(validator_name)
        
        # Fall back to default validator
        if self.default_validator:
            return self.validators.get(self.default_validator)
        
        return None
    
    def validate(self, target_path: str, 
                validation_level: ValidationLevel = ValidationLevel.STANDARD,
                validator_name: str = None,
                format_hint: str = None) -> ValidationResult:
        """
        Perform validation using the most appropriate validator
        
        Args:
            target_path: Path to validate
            validation_level: Strictness level for validation
            validator_name: Specific validator to use (optional)
            format_hint: Hint about expected format (optional)
            
        Returns:
            ValidationResult: Complete validation results
        """
        if not os.path.exists(target_path):
            raise ValidationException(f"Target path does not exist: {target_path}")
        
        # Select validator
        if validator_name:
            validator = self.get_validator(validator_name)
            if not validator:
                raise ValidationException(f"Validator not found: {validator_name}")
        else:
            validator = self.auto_select_validator(target_path, format_hint)
            if not validator:
                raise ValidationException("No suitable validator found for target")
        
        logger.info(f"Using validator: {validator.validator_type} for {target_path}")
        
        try:
            # 对于MetaCam格式，执行流水线式验证
            if validator.validator_type == "MetaCamValidator":
                result = self._perform_pipeline_validation(target_path, validation_level)
            else:
                # 其他验证器使用单独验证
                result = validator.validate(target_path, validation_level)
            
            # Add manager metadata
            if not result.metadata:
                result.metadata = {}
            result.metadata['manager_version'] = '1.0'
            result.metadata['selected_validator'] = validator.validator_type
            result.metadata['auto_selected'] = validator_name is None
            
            logger.info(f"Validation completed: {result.summary}")
            return result
            
        except Exception as e:
            logger.error(f"Validation failed with {validator.validator_type}: {e}")
            raise ValidationException(f"Validation failed: {e}", validator.validator_type)
    
    def get_available_validators(self) -> List[str]:
        """
        Get list of available validator names
        
        Returns:
            List of validator names
        """
        return list(self.validators.keys())
    
    def get_supported_formats(self) -> Dict[str, str]:
        """
        Get mapping of supported formats to validators
        
        Returns:
            Dictionary mapping format names to validator names
        """
        return self.format_mapping.copy()
    
    def validate_multiple(self, targets: List[str],
                         validation_level: ValidationLevel = ValidationLevel.STANDARD) -> Dict[str, ValidationResult]:
        """
        Validate multiple targets
        
        Args:
            targets: List of paths to validate
            validation_level: Validation strictness level
            
        Returns:
            Dictionary mapping target paths to validation results
        """
        results = {}
        
        for target in targets:
            try:
                result = self.validate(target, validation_level)
                results[target] = result
            except Exception as e:
                logger.error(f"Failed to validate {target}: {e}")
                # Create a failed result
                results[target] = ValidationResult(
                    is_valid=False,
                    validation_level=validation_level,
                    score=0.0,
                    errors=[str(e)],
                    warnings=[],
                    missing_files=[],
                    missing_directories=[],
                    extra_files=[],
                    file_details={},
                    summary=f"Validation failed: {e}",
                    validator_type="unknown",
                    metadata={'error': str(e)}
                )
        
        return results
    
    def _load_default_validators(self):
        """Load default validators"""
        try:
            # Import and register MetaCam validator
            from .metacam import MetaCamValidator
            
            metacam_validator = MetaCamValidator()
            self.register_validator(metacam_validator, is_default=True)
            
            # Import and register Transient validator (with fallback)
            try:
                from .transient_validator import TransientValidator
                
                transient_validator = TransientValidator()
                self.register_validator(transient_validator)
                logger.info("Full TransientValidator loaded successfully")
            except ImportError as e:
                logger.warning(f"Full TransientValidator not available due to missing imports: {e}")
                self._try_fallback_transient_validator()
            except Exception as e:
                logger.warning(f"Full TransientValidator failed to initialize: {e}")
                self._try_fallback_transient_validator()
            
        except ImportError as e:
            logger.warning(f"Could not load default validators: {e}")
    
    def _try_fallback_transient_validator(self):
        """尝试加载fallback版本的TransientValidator"""
        try:
            from .transient_validator_fallback import TransientValidatorFallback
            
            fallback_validator = TransientValidatorFallback()
            self.register_validator(fallback_validator)
            logger.info("Fallback TransientValidator loaded successfully")
        except Exception as e:
            logger.warning(f"Even fallback TransientValidator failed to load: {e}")
            logger.info("Transient validation will be completely skipped")
    
    def _detect_format(self, target_path: str) -> Optional[str]:
        """
        Detect format from path structure
        
        Args:
            target_path: Path to analyze
            
        Returns:
            Detected format or None
        """
        target_path = Path(target_path)
        
        # Check for camera images - multiple possible structures
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        
        def check_metacam_structure(path: Path) -> bool:
            """Check if a path contains MetaCam structure (按照schema标准)"""
            metacam_indicators = ['metadata.yaml', 'camera', 'data', 'info']
            found_indicators = 0
            
            if path.is_dir():
                for indicator in metacam_indicators:
                    if (path / indicator).exists():
                        found_indicators += 1
            
            return found_indicators >= 2
        
        
        # Check for MetaCam structure first (这是唯一的标准格式)
        if check_metacam_structure(target_path):
            return 'metacam'
        
        # Check subdirectories for MetaCam structure
        if target_path.is_dir():
            for item in target_path.iterdir():
                if item.is_dir() and check_metacam_structure(item):
                    return 'metacam'
        
        return None
    
    def _perform_pipeline_validation(self, target_path: str, validation_level: ValidationLevel) -> ValidationResult:
        """
        Perform pipeline validation for MetaCam data packages.
        
        This method orchestrates a multi-stage validation process:
        1. Basic format validation (MetaCamValidator) - validates directory structure, files, metadata
        2. Transient object detection (TransientValidator) - analyzes camera images for moving obstacles
        
        The pipeline ensures comprehensive data quality assessment while maintaining flexibility.
        If basic validation fails, the pipeline stops early. If transient detection fails,
        the pipeline continues with warnings since basic format compliance is sufficient.
        
        Args:
            target_path: Path to the MetaCam data package directory
            validation_level: Validation strictness level (STRICT/STANDARD/LENIENT)
            
        Returns:
            Combined validation result with weighted scoring:
            - Basic validation: 70% weight
            - Transient detection: 30% weight
        """
        logger.info(f"Starting pipeline validation for MetaCam data: {target_path}")
        
        # Stage 1: Basic format validation using MetaCamValidator
        # This stage validates directory structure, required files, and metadata compliance
        metacam_validator = self.validators.get("MetaCamValidator")
        if not metacam_validator:
            raise ValidationException("MetaCamValidator not available")
        
        logger.info("Step 1/2: Basic format validation (MetaCamValidator)")
        base_result = metacam_validator.validate(target_path, validation_level)
        
        # Early termination if basic validation fails
        # Basic format compliance is mandatory - without it, data package is unusable
        if not base_result.is_valid:
            logger.warning(f"Basic format validation failed: {base_result.summary}")
            base_result.metadata['pipeline_stage'] = 'basic_format'
            base_result.metadata['pipeline_completed'] = False
            return base_result
        
        logger.info(f"Basic format validation passed: {base_result.summary}")
        
        # Stage 2: Transient object detection validation (if camera directory exists)
        # This stage analyzes camera images for moving obstacles using YOLO11 models
        transient_validator = self.validators.get("TransientValidator")
        camera_path = os.path.join(target_path, "camera")
        
        # Search for camera directory - could be in root or subdirectory after extraction
        actual_camera_path = None
        if os.path.exists(camera_path):
            actual_camera_path = camera_path
        else:
            # Recursive search in subdirectories for camera directory
            # This handles cases where data is nested in additional folders after extraction
            try:
                for item in os.listdir(target_path):
                    item_path = os.path.join(target_path, item)
                    if os.path.isdir(item_path):
                        sub_camera_path = os.path.join(item_path, "camera")
                        if os.path.exists(sub_camera_path):
                            actual_camera_path = sub_camera_path
                            break
            except:
                pass
        
        # Execute transient detection if both validator and camera directory are available
        if transient_validator and actual_camera_path:
            logger.info("Step 2/2: Transient object detection validation (TransientValidator)")
            try:
                # Run transient detection analysis on camera images
                transient_result = transient_validator.validate(target_path, validation_level)
                
                # Combine results from both validation stages
                # This creates a comprehensive result with weighted scoring
                combined_result = self._combine_validation_results(base_result, transient_result)
                combined_result.metadata['pipeline_stage'] = 'transient_detection'
                combined_result.metadata['pipeline_completed'] = True
                
                logger.info(f"Pipeline validation completed: {combined_result.summary}")
                return combined_result
                
            except Exception as e:
                logger.warning(f"Transient validation failed: {e}")
                # Graceful degradation: transient detection failure doesn't invalidate basic format
                # Add warning but keep the basic validation result as valid
                base_result.warnings.append(f"Transient detection failed: {e}")
                base_result.metadata['pipeline_stage'] = 'basic_format'
                base_result.metadata['pipeline_completed'] = False
                base_result.metadata['transient_detection_error'] = str(e)
                return base_result
        else:
            # Skip transient detection if prerequisites are missing
            # This is not an error - many valid data packages may not have camera images
            logger.info("Step 2/2: Skipping transient validation (no camera directory or validator unavailable)")
            base_result.metadata['pipeline_stage'] = 'basic_format'
            base_result.metadata['pipeline_completed'] = True
            base_result.metadata['transient_detection_skipped'] = 'No camera directory found or TransientValidator unavailable'
            
        logger.info(f"Pipeline validation completed: {base_result.summary}")
        return base_result
    
    def _combine_validation_results(self, base_result: ValidationResult, 
                                   transient_result: ValidationResult) -> ValidationResult:
        """
        Combine results from basic format validation and transient object detection.
        
        This method merges two validation results into a comprehensive assessment with
        weighted scoring. The combination logic prioritizes basic format compliance
        while incorporating transient detection insights.
        
        Scoring Logic:
        - Basic validation: 70% weight (fundamental data package integrity)
        - Transient detection: 30% weight (quality enhancement for reconstruction)
        
        Validity Logic:
        - Overall validation passes only if basic validation passes
        - Transient detection enhances quality but doesn't block processing
        
        Args:
            base_result: Result from MetaCamValidator (directory structure, files, metadata)
            transient_result: Result from TransientValidator (moving obstacle analysis)
            
        Returns:
            Combined validation result with merged errors, warnings, and metadata
        """
        from .base import ValidationResult
        
        # Merge error and warning lists from both validation stages
        combined_errors = base_result.errors + transient_result.errors
        combined_warnings = base_result.warnings + transient_result.warnings
        
        # Merge file-related information, removing duplicates
        combined_missing_files = list(set(base_result.missing_files + transient_result.missing_files))
        combined_missing_directories = list(set(base_result.missing_directories + transient_result.missing_directories))
        combined_extra_files = list(set(base_result.extra_files + transient_result.extra_files))
        
        # Merge file detail dictionaries (transient details override base if conflicts)
        combined_file_details = {}
        combined_file_details.update(base_result.file_details)
        combined_file_details.update(transient_result.file_details)
        
        # Calculate weighted combined score
        # 70% weight for basic format validation (fundamental requirement)
        # 30% weight for transient detection (quality enhancement)
        combined_score = base_result.score * 0.7 + transient_result.score * 0.3
        
        # Combined validity: basic validation must pass, transient is enhancement only
        # This ensures that format compliance is mandatory while transient analysis is optional
        combined_is_valid = base_result.is_valid and transient_result.is_valid
        
        # 生成综合摘要
        combined_summary = f"Pipeline Validation: Basic({base_result.score:.1f}) + Transient({transient_result.score:.1f}) = {combined_score:.1f}/100"
        if combined_is_valid:
            combined_summary += " - PASS"
        else:
            combined_summary += " - FAIL"
        
        # 合并元数据
        combined_metadata = {}
        combined_metadata.update(base_result.metadata)
        
        # 添加transient检测结果到metadata
        if transient_result.metadata:
            combined_metadata['transient_validation'] = transient_result.metadata
        
        combined_metadata['validation_pipeline'] = {
            'base_validation': {
                'score': base_result.score,
                'is_valid': base_result.is_valid,
                'summary': base_result.summary,
                'errors': len(base_result.errors),
                'warnings': len(base_result.warnings)
            },
            'transient_validation': {
                'score': transient_result.score,
                'is_valid': transient_result.is_valid,
                'summary': transient_result.summary,
                'errors': len(transient_result.errors),
                'warnings': len(transient_result.warnings)
            },
            'combined_score': combined_score,
            'weights': {'base': 0.7, 'transient': 0.3}
        }
        
        return ValidationResult(
            is_valid=combined_is_valid,
            validation_level=base_result.validation_level,
            score=combined_score,
            errors=combined_errors,
            warnings=combined_warnings,
            missing_files=combined_missing_files,
            missing_directories=combined_missing_directories,
            extra_files=combined_extra_files,
            file_details=combined_file_details,
            summary=combined_summary,
            validator_type="Pipeline(MetaCam+Transient)",
            metadata=combined_metadata
        )