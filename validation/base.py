"""
Base Validation Framework

Defines the core interfaces and base classes for the validation system.
This provides a foundation for implementing different validation strategies
and scoring algorithms.
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
    """Standardized validation result structure"""
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
    metadata: Dict[str, Any] = None
    
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
        base_score = 100.0
        
        # Default scoring weights (can be customized per validator)
        error_weight = self.config.get('error_weight', 15)
        warning_weight = self.config.get('warning_weight', 3)
        missing_weight = self.config.get('missing_weight', 10)
        
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
            critical_errors = [e for e in errors if self._is_critical_error(e)]
            return len(critical_errors) == 0 and len(missing_files) <= 2
        
        else:  # LENIENT
            return len(errors) <= 5
    
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