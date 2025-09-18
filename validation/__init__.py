"""
MetaCam Validation Module

Simple, direct validation functions for MetaCam data packages.
Each function is independent and performs specific validation tasks.
"""

from .base import ValidationResult, ValidationLevel
from .metacam import MetaCamValidator
from .archive_metacam import ArchiveMetaCamValidator
from .processed_metacam import ProcessedMetaCamValidator

# Import transient validator with fallback
try:
    from .transient_validator import TransientValidator
except ImportError:
    try:
        from .transient_validator_fallback import TransientValidatorFallback as TransientValidator
    except ImportError:
        TransientValidator = None

from utils.logger import get_logger
logger = get_logger(__name__)


def validate_metacam(target_path: str, validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
    """
    Validate original MetaCam data package with pipeline validation.

    Combines basic format validation with transient object detection.

    Args:
        target_path: Path to the MetaCam data directory
        validation_level: Validation strictness level

    Returns:
        ValidationResult: Complete validation results
    """
    logger.info(f"Starting MetaCam pipeline validation: {target_path}")

    # Stage 1: Basic format validation
    metacam_validator = MetaCamValidator()
    base_result = metacam_validator.validate(target_path, validation_level)

    # Early termination if basic validation fails
    if not base_result.is_valid:
        logger.warning(f"Basic format validation failed: {base_result.summary}")
        base_result.metadata['pipeline_stage'] = 'basic_format'
        base_result.metadata['pipeline_completed'] = False
        return base_result

    logger.info(f"Basic format validation passed: {base_result.summary}")

    # Stage 2: Transient object detection (if available and images exist)
    if TransientValidator is None:
        logger.info("TransientValidator not available, skipping transient detection")
        base_result.metadata['pipeline_stage'] = 'basic_format'
        base_result.metadata['pipeline_completed'] = True
        base_result.metadata['transient_detection_skipped'] = 'TransientValidator not available'
        return base_result

    # Check for images directory
    import os
    images_path = os.path.join(target_path, "images")
    actual_images_path = None

    if os.path.exists(images_path):
        actual_images_path = images_path
    else:
        # Search in subdirectories
        try:
            for item in os.listdir(target_path):
                item_path = os.path.join(target_path, item)
                if os.path.isdir(item_path):
                    sub_images_path = os.path.join(item_path, "images")
                    if os.path.exists(sub_images_path):
                        actual_images_path = sub_images_path
                        break
        except:
            pass

    if actual_images_path:
        logger.info("Running transient object detection")
        try:
            transient_validator = TransientValidator()
            transient_result = transient_validator.validate(target_path, validation_level)

            # Combine results
            combined_result = _combine_validation_results(base_result, transient_result)
            combined_result.metadata['pipeline_stage'] = 'transient_detection'
            combined_result.metadata['pipeline_completed'] = True

            logger.info(f"Pipeline validation completed: {combined_result.summary}")
            return combined_result

        except Exception as e:
            logger.warning(f"Transient validation failed: {e}")
            base_result.warnings.append(f"Transient detection failed: {e}")
            base_result.metadata['pipeline_stage'] = 'basic_format'
            base_result.metadata['pipeline_completed'] = False
            base_result.metadata['transient_detection_error'] = str(e)
    else:
        logger.info("No images directory found, skipping transient detection")
        base_result.metadata['transient_detection_skipped'] = 'No images directory found'

    base_result.metadata['pipeline_stage'] = 'basic_format'
    base_result.metadata['pipeline_completed'] = True
    logger.info(f"Pipeline validation completed: {base_result.summary}")
    return base_result


def validate_archive_metacam(target_path: str, validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
    """
    Validate archive MetaCam data package.

    Args:
        target_path: Path to the archive MetaCam data directory
        validation_level: Validation strictness level

    Returns:
        ValidationResult: Complete validation results
    """
    logger.info(f"Starting Archive MetaCam validation: {target_path}")

    validator = ArchiveMetaCamValidator()
    result = validator.validate(target_path, validation_level)

    logger.info(f"Archive MetaCam validation completed: {result.summary}")
    return result


def validate_processed_metacam(target_path: str, validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
    """
    Validate processed MetaCam data package.

    Args:
        target_path: Path to the processed MetaCam data directory
        validation_level: Validation strictness level

    Returns:
        ValidationResult: Complete validation results
    """
    logger.info(f"Starting Processed MetaCam validation: {target_path}")

    validator = ProcessedMetaCamValidator()
    result = validator.validate(target_path, validation_level)

    logger.info(f"Processed MetaCam validation completed: {result.summary}")
    return result


def validate_transient_only(target_path: str, validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
    """
    Run only transient object detection validation.

    Args:
        target_path: Path to the data directory
        validation_level: Validation strictness level

    Returns:
        ValidationResult: Transient detection results
    """
    if TransientValidator is None:
        raise ImportError("TransientValidator not available")

    logger.info(f"Starting transient-only validation: {target_path}")

    validator = TransientValidator()
    result = validator.validate(target_path, validation_level)

    logger.info(f"Transient validation completed: {result.summary}")
    return result


def _combine_validation_results(base_result: ValidationResult, transient_result: ValidationResult) -> ValidationResult:
    """
    Combine results from basic format validation and transient object detection.

    Args:
        base_result: Result from MetaCamValidator
        transient_result: Result from TransientValidator

    Returns:
        Combined validation result with weighted scoring
    """
    # Merge error and warning lists
    combined_errors = base_result.errors + transient_result.errors
    combined_warnings = base_result.warnings + transient_result.warnings

    # Merge file-related information
    combined_missing_files = list(set(base_result.missing_files + transient_result.missing_files))
    combined_missing_directories = list(set(base_result.missing_directories + transient_result.missing_directories))
    combined_extra_files = list(set(base_result.extra_files + transient_result.extra_files))

    # Merge file details
    combined_file_details = {}
    combined_file_details.update(base_result.file_details)
    combined_file_details.update(transient_result.file_details)

    # Calculate weighted combined score (70% base + 30% transient)
    combined_score = base_result.score * 0.7 + transient_result.score * 0.3

    # Combined validity: base validation must pass
    combined_is_valid = base_result.is_valid and transient_result.is_valid

    # Generate combined summary
    combined_summary = f"Pipeline Validation: Basic({base_result.score:.1f}) + Transient({transient_result.score:.1f}) = {combined_score:.1f}/100"
    if combined_is_valid:
        combined_summary += " - PASS"
    else:
        combined_summary += " - FAIL"

    # Merge metadata
    combined_metadata = {}
    combined_metadata.update(base_result.metadata)

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


# Export the main validation functions
__all__ = [
    'validate_metacam',
    'validate_archive_metacam',
    'validate_processed_metacam',
    'validate_transient_only',
    'ValidationResult',
    'ValidationLevel'
]