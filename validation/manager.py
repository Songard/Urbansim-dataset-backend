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
            # Perform validation
            result = validator.validate(target_path, validation_level)
            
            # Add manager metadata
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
            
        except ImportError as e:
            logger.warning(f"Could not load default validators: {e}")
    
    def _detect_format(self, target_path: str) -> Optional[str]:
        """
        Detect format from path structure
        
        Args:
            target_path: Path to analyze
            
        Returns:
            Detected format or None
        """
        target_path = Path(target_path)
        
        # Check for MetaCam indicators
        metacam_indicators = ['metadata.yaml', 'camera', 'data', 'info']
        found_indicators = 0
        
        if target_path.is_dir():
            for indicator in metacam_indicators:
                if (target_path / indicator).exists():
                    found_indicators += 1
        
        if found_indicators >= 2:
            return 'metacam'
        
        return None