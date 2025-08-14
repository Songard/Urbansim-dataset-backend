"""
Unified Error Formatting System

This module provides standardized error message formatting across all validators
to ensure consistent and readable error reporting in the sheets.
"""

from typing import List, Dict, Any, Union, Optional
from enum import Enum


class ErrorSeverity(Enum):
    """Standardized error severity levels"""
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"  
    WARNING = "WARNING"
    INFO = "INFO"


class ErrorCategory(Enum):
    """Standardized error categories"""
    FILE_STRUCTURE = "FILE_STRUCTURE"
    DATA_VALIDATION = "DATA_VALIDATION"
    SIZE_VALIDATION = "SIZE_VALIDATION"
    FORMAT_VALIDATION = "FORMAT_VALIDATION"
    METADATA_EXTRACTION = "METADATA_EXTRACTION"
    TRANSIENT_DETECTION = "TRANSIENT_DETECTION"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class StandardizedError:
    """Standardized error object"""
    
    def __init__(self, 
                 severity: ErrorSeverity, 
                 category: ErrorCategory,
                 message: str,
                 details: Optional[str] = None,
                 file_path: Optional[str] = None,
                 validator: Optional[str] = None):
        self.severity = severity
        self.category = category
        self.message = message
        self.details = details
        self.file_path = file_path
        self.validator = validator
    
    def to_string(self) -> str:
        """Convert to human-readable string format"""
        parts = [f"[{self.severity.value}]"]
        
        if self.validator:
            parts.append(f"({self.validator})")
            
        parts.append(self.message)
        
        if self.file_path:
            parts.append(f"File: {self.file_path}")
            
        if self.details:
            parts.append(f"Details: {self.details}")
            
        return " ".join(parts)


class ErrorFormatter:
    """Unified error message formatter for all validators"""
    
    @classmethod
    def format_validation_summary(cls, 
                                errors: List[StandardizedError], 
                                warnings: List[StandardizedError],
                                file_name: str = "",
                                validator_name: str = "") -> str:
        """
        Create a standardized validation summary message
        
        Args:
            errors: List of standardized errors
            warnings: List of standardized warnings  
            file_name: Name of the file being validated
            validator_name: Name of the validator
            
        Returns:
            Formatted summary string
        """
        if not errors and not warnings:
            return f"Validation PASSED: No issues found"
        
        summary_parts = []
        
        if errors:
            error_count = len(errors)
            summary_parts.append(f"{error_count} error{'s' if error_count != 1 else ''}")
            
        if warnings:
            warning_count = len(warnings)
            summary_parts.append(f"{warning_count} warning{'s' if warning_count != 1 else ''}")
        
        status = "FAILED" if errors else "WARNING"
        summary = f"Validation {status}: {', '.join(summary_parts)}"
        
        if file_name:
            summary += f" in {file_name}"
            
        return summary
    
    @classmethod
    def format_error_list(cls, 
                         errors: List[StandardizedError], 
                         max_errors: int = 5) -> str:
        """
        Format a list of errors into a readable string
        
        Args:
            errors: List of standardized errors
            max_errors: Maximum number of errors to display
            
        Returns:
            Formatted error list string
        """
        if not errors:
            return ""
        
        error_strings = []
        displayed_errors = errors[:max_errors]
        
        for error in displayed_errors:
            error_strings.append(error.to_string())
        
        result = "; ".join(error_strings)
        
        if len(errors) > max_errors:
            remaining = len(errors) - max_errors
            result += f"; ... and {remaining} more error{'s' if remaining != 1 else ''}"
        
        return result
    
    @classmethod
    def create_file_error(cls, message: str, file_path: str, validator: str = "") -> StandardizedError:
        """Create a file-related error"""
        return StandardizedError(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.FILE_STRUCTURE,
            message=message,
            file_path=file_path,
            validator=validator
        )
    
    @classmethod
    def create_size_error(cls, message: str, details: str = "", validator: str = "") -> StandardizedError:
        """Create a size validation error"""
        return StandardizedError(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.SIZE_VALIDATION,
            message=message,
            details=details,
            validator=validator
        )
    
    @classmethod
    def create_size_warning(cls, message: str, details: str = "", validator: str = "") -> StandardizedError:
        """Create a size validation warning"""
        return StandardizedError(
            severity=ErrorSeverity.WARNING,
            category=ErrorCategory.SIZE_VALIDATION,
            message=message,
            details=details,
            validator=validator
        )
    
    @classmethod
    def create_format_error(cls, message: str, file_path: str = "", validator: str = "") -> StandardizedError:
        """Create a format validation error"""
        return StandardizedError(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.FORMAT_VALIDATION,
            message=message,
            file_path=file_path,
            validator=validator
        )
    
    @classmethod
    def create_data_error(cls, message: str, details: str = "", validator: str = "") -> StandardizedError:
        """Create a data validation error"""
        return StandardizedError(
            severity=ErrorSeverity.ERROR,
            category=ErrorCategory.DATA_VALIDATION,
            message=message,
            details=details,
            validator=validator
        )
    
    @classmethod
    def create_system_error(cls, message: str, details: str = "", validator: str = "") -> StandardizedError:
        """Create a system error"""
        return StandardizedError(
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.SYSTEM_ERROR,
            message=message,
            details=details,
            validator=validator
        )
    
    @classmethod
    def translate_legacy_errors(cls, 
                               legacy_errors: List[str], 
                               validator_name: str = "") -> List[StandardizedError]:
        """
        Convert legacy string-based errors to standardized format
        
        Args:
            legacy_errors: List of legacy error strings
            validator_name: Name of the validator that generated the errors
            
        Returns:
            List of standardized errors
        """
        standardized_errors = []
        
        for error_msg in legacy_errors:
            error_msg_lower = error_msg.lower()
            
            # Categorize based on error content
            if any(keyword in error_msg_lower for keyword in ['file', 'directory', 'missing', 'not found']):
                category = ErrorCategory.FILE_STRUCTURE
            elif any(keyword in error_msg_lower for keyword in ['size', 'too small', 'too large']):
                category = ErrorCategory.SIZE_VALIDATION
            elif any(keyword in error_msg_lower for keyword in ['format', 'invalid', 'corrupted']):
                category = ErrorCategory.FORMAT_VALIDATION
            elif any(keyword in error_msg_lower for keyword in ['metadata', 'extraction']):
                category = ErrorCategory.METADATA_EXTRACTION
            elif any(keyword in error_msg_lower for keyword in ['transient', 'detection']):
                category = ErrorCategory.TRANSIENT_DETECTION
            else:
                category = ErrorCategory.DATA_VALIDATION
            
            # Determine severity
            if any(keyword in error_msg_lower for keyword in ['critical', 'fatal', 'corruption']):
                severity = ErrorSeverity.CRITICAL
            elif any(keyword in error_msg_lower for keyword in ['warning']):
                severity = ErrorSeverity.WARNING
            elif any(keyword in error_msg_lower for keyword in ['missing required key', 'missing key', 'json file']):
                # JSON validation issues are warnings, not errors
                severity = ErrorSeverity.WARNING
            else:
                severity = ErrorSeverity.ERROR
            
            standardized_error = StandardizedError(
                severity=severity,
                category=category,
                message=error_msg,
                validator=validator_name
            )
            
            standardized_errors.append(standardized_error)
        
        return standardized_errors
    
    @classmethod
    def create_extract_status_message(cls, 
                                    errors: List[StandardizedError], 
                                    warnings: List[StandardizedError],
                                    validation_score: float) -> str:
        """
        Create standardized extract status message in English
        
        Args:
            errors: List of standardized errors
            warnings: List of standardized warnings
            validation_score: Validation score (0-100)
            
        Returns:
            Standardized extract status message
        """
        # Only treat critical and error-level issues as failures
        critical_errors = [e for e in errors if e.severity == ErrorSeverity.CRITICAL or e.severity == ErrorSeverity.ERROR]
        
        if critical_errors:
            return f"Failed (Validation: {validation_score:.1f}/100)"
        elif errors or warnings:
            return f"Success with Warnings (Validation: {validation_score:.1f}/100)"
        else:
            return f"Success (Validation: {validation_score:.1f}/100)"
    
    @classmethod
    def format_duration_seconds(cls, duration_seconds: float) -> str:
        """
        Format duration from decimal seconds to MM:SS format
        
        Args:
            duration_seconds: Duration in seconds (decimal)
            
        Returns:
            Formatted duration string in MM:SS format
        """
        if duration_seconds < 0:
            return "00:00"
        
        total_seconds = int(round(duration_seconds))
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        return f"{minutes:02d}:{seconds:02d}"