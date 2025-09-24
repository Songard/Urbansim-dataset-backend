"""
Processed MetaCam Data Package Validator

Specialized validator for processed MetaCam 3D reconstruction data packages.
Implements the base validator interface with processed package-specific logic.
"""

import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any

from .base import BaseValidator, ValidationResult, ValidationLevel
from utils.logger import get_logger

logger = get_logger(__name__)

class ProcessedMetaCamValidator(BaseValidator):
    """
    Validator for processed MetaCam data packages.
    
    Validates the structure, files, and content of processed MetaCam
    3D reconstruction data packages according to the processed schema.
    """
    
    def __init__(self, schema_file: str = None):
        """
        Initialize Processed MetaCam validator
        
        Args:
            schema_file: Path to processed schema file (optional)
        """
        super().__init__()
        self.schema_file = schema_file or self._get_default_schema_file()
        self.schema = None
        self.validator_type = "ProcessedMetaCamValidator"
        
        # Load schema
        if not self.load_schema():
            raise ValueError(f"Failed to load processed schema from: {self.schema_file}")
    
    def get_supported_formats(self) -> List[str]:
        """Get supported format types"""
        return ['processed_metacam', 'processed_metacam_3d', 'processed_reconstruction_data']
    
    def validate(self, target_path: str, 
                validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
        """
        Validate processed MetaCam data package
        
        Args:
            target_path: Path to the processed data package directory
            validation_level: Validation strictness level
            
        Returns:
            ValidationResult: Complete validation results
        """
        logger.info(f"Starting Processed MetaCam validation: {target_path} (level: {validation_level.value})")
        
        # Find actual root directory (handle wrapper folders)
        actual_root = self._find_actual_root(target_path)
        if not actual_root:
            return self._create_failed_result(
                validation_level, 
                ["Unable to find valid processed MetaCam data root directory"]
            )
        
        logger.info(f"Actual processed data root: {actual_root}")
        
        # Initialize validation tracking
        errors = []
        warnings = []
        missing_files = []
        missing_directories = []
        extra_files = []
        file_details = {}
        
        # Perform validation steps
        self._validate_preserved_files(actual_root, errors, warnings, missing_files, file_details)
        self._validate_preserved_directories(actual_root, errors, warnings, missing_directories)
        self._validate_processing_output_files(actual_root, errors, warnings, missing_files, file_details)
        self._validate_optional_processing_files(actual_root, warnings, file_details)
        
        # Check for extra files (only in non-lenient modes)
        if validation_level != ValidationLevel.LENIENT:
            self._validate_extra_files(actual_root, warnings, extra_files)
        
        # Validate file contents
        self._validate_file_contents(actual_root, errors, warnings, file_details)
        
        # Extract and validate metadata
        metadata_info = self._extract_and_validate_metadata(actual_root, errors, warnings)
        
        # Calculate score and determine validity
        score = self.calculate_score(errors, warnings, missing_files, missing_directories)
        is_valid = self.determine_validity(validation_level, errors, missing_files, missing_directories)
        summary = self.generate_summary(is_valid, score, len(errors), len(warnings))
        
        # Create result
        result = ValidationResult(
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
            metadata={
                'actual_root': actual_root,
                'schema_version': self.schema.get('schema_version', 'unknown'),
                'total_files_checked': len(file_details),
                'extracted_metadata': metadata_info
            }
        )
        
        logger.info(f"Processed MetaCam validation completed: {summary}")
        return result
    
    def load_schema(self) -> bool:
        """Load validation schema from file"""
        try:
            if not os.path.exists(self.schema_file):
                logger.error(f"Processed schema file not found: {self.schema_file}")
                return False
            
            with open(self.schema_file, 'r', encoding='utf-8') as f:
                self.schema = yaml.safe_load(f)
            
            schema_name = self.schema.get('schema_name', 'Unknown')
            schema_version = self.schema.get('schema_version', '1.0')
            logger.info(f"Loaded processed schema: {schema_name} v{schema_version}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load processed schema: {e}")
            return False
    
    def _get_default_schema_file(self) -> str:
        """Get default processed schema file path"""
        current_dir = Path(__file__).parent
        return str(current_dir.parent / 'data_schemas' / 'processed_metacam_schema.yaml')
    
    def _find_actual_root(self, directory_path: str) -> Optional[str]:
        """Find the actual processed MetaCam data root directory"""
        directory_path = os.path.abspath(directory_path)
        
        # Check if current directory contains processed MetaCam indicators
        if self._is_processed_metacam_root(directory_path):
            return directory_path
        
        # Check subdirectories for processed MetaCam root
        try:
            items = os.listdir(directory_path)
            directories = [item for item in items if os.path.isdir(os.path.join(directory_path, item))]
            
            # If only one directory, check if it's the root
            if len(directories) == 1:
                potential_root = os.path.join(directory_path, directories[0])
                if self._is_processed_metacam_root(potential_root):
                    return potential_root
            
            # Check all subdirectories
            for directory in directories:
                potential_root = os.path.join(directory_path, directory)
                if self._is_processed_metacam_root(potential_root):
                    return potential_root
                    
        except Exception as e:
            logger.error(f"Error searching for processed root directory: {e}")
        
        return None
    
    def _is_processed_metacam_root(self, path: str) -> bool:
        """Check if path contains processed MetaCam indicators"""
        # Look for key processed package indicators
        indicators = ['metadata.yaml', 'transforms.json', 'data']
        found_count = 0
        
        for indicator in indicators:
            indicator_path = os.path.join(path, indicator)
            if os.path.exists(indicator_path):
                found_count += 1
        
        # Also check for processed point cloud files
        point_cloud_files = ['colorized.las', 'processed_pointcloud.ply']
        for pcd_file in point_cloud_files:
            pcd_path = os.path.join(path, pcd_file)
            if os.path.exists(pcd_path):
                found_count += 1
                break
        
        # Need at least 2 indicators to be considered a valid processed package
        return found_count >= 2
    
    def _validate_preserved_files(self, root_path: str, errors: List[str], 
                                 warnings: List[str], missing_files: List[str], 
                                 file_details: Dict[str, Dict[str, Any]]):
        """Validate preserved files from original package"""
        preserved_files = self.schema.get('preserved_files', [])
        self._validate_file_list(root_path, preserved_files, errors, warnings, missing_files, file_details, True)
    
    def _validate_preserved_directories(self, root_path: str, errors: List[str], 
                                      warnings: List[str], missing_directories: List[str]):
        """Validate preserved directories from original package"""
        preserved_dirs = self.schema.get('preserved_directories', [])
        
        for dir_info in preserved_dirs:
            dir_path = os.path.join(root_path, dir_info['path'])
            
            if not os.path.exists(dir_path):
                if not dir_info.get('optional', False):
                    error_msg = f"Missing required preserved directory: {dir_info['path']}"
                    errors.append(error_msg)
                    missing_directories.append(dir_info['path'])
                    logger.warning(error_msg)
                else:
                    warnings.append(f"Missing optional preserved directory: {dir_info['path']}")
            else:
                logger.debug(f"Found preserved directory: {dir_info['path']}")
    
    def _validate_processing_output_files(self, root_path: str, errors: List[str], 
                                        warnings: List[str], missing_files: List[str], 
                                        file_details: Dict[str, Dict[str, Any]]):
        """Validate processing output files"""
        processing_files = self.schema.get('processing_output_files', [])
        self._validate_file_list(root_path, processing_files, errors, warnings, missing_files, file_details, True)
    
    def _validate_optional_processing_files(self, root_path: str, warnings: List[str], 
                                          file_details: Dict[str, Dict[str, Any]]):
        """Validate optional processing files"""
        optional_files = self.schema.get('optional_processing_files', [])
        self._validate_file_list(root_path, optional_files, [], warnings, [], file_details, False)
    
    def _validate_file_list(self, root_path: str, file_list: List[Dict], 
                           errors: List[str], warnings: List[str], missing_files: List[str],
                           file_details: Dict[str, Dict[str, Any]], is_required: bool):
        """Validate a list of files"""
        for file_info in file_list:
            file_path = os.path.join(root_path, file_info['path'])
            relative_path = file_info['path']
            
            # Handle wildcard paths (like "*" for point cloud files)
            if file_info['path'] == "*":
                # Look for point cloud files with allowed extensions
                extensions = file_info.get('extensions', ['.las'])
                found_pointcloud = False
                
                for ext in extensions:
                    # Look for common point cloud filenames
                    common_names = ['colorized.las', 'processed_pointcloud.ply', 'pointcloud.ply']
                    for name in common_names:
                        test_path = os.path.join(root_path, name)
                        if os.path.exists(test_path):
                            file_path = test_path
                            relative_path = name
                            found_pointcloud = True
                            break
                    if found_pointcloud:
                        break
                
                if not found_pointcloud:
                    if is_required:
                        error_msg = f"Missing required point cloud file (expected one of: {extensions})"
                        errors.append(error_msg)
                        missing_files.append("point_cloud_file")
                        logger.warning(error_msg)
                    continue
            
            if not os.path.exists(file_path):
                if is_required:
                    error_msg = f"Missing required processing output file: {relative_path}"
                    errors.append(error_msg)
                    missing_files.append(relative_path)
                    logger.warning(error_msg)
                else:
                    warnings.append(f"Missing optional processing file: {relative_path}")
                continue
            
            # Validate file details
            file_detail = self._validate_single_file(file_path, file_info, errors, warnings)
            file_details[relative_path] = file_detail
            logger.debug(f"Validated processing file: {relative_path} - {file_detail['status']}")
    
    def _validate_single_file(self, file_path: str, file_info: Dict[str, Any],
                             errors: List[str], warnings: List[str]) -> Dict[str, Any]:
        """Validate individual file"""
        detail = {
            'path': file_path,
            'exists': True,
            'size': 0,
            'status': 'valid'
        }
        
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            detail['size'] = file_size
            
            min_size = file_info.get('min_size', 0)
            max_size = file_info.get('max_size', float('inf'))
            
            if file_size < min_size:
                error_msg = f"File {file_info['path']} too small: {file_size} < {min_size}"
                errors.append(error_msg)
                detail['status'] = 'too_small'
            elif file_size > max_size:
                error_msg = f"File {file_info['path']} too large: {file_size} > {max_size}"
                errors.append(error_msg)
                detail['status'] = 'too_large'
            
            # Check file extension
            expected_extensions = file_info.get('extensions', [])
            if expected_extensions:
                file_ext = Path(file_path).suffix.lower()
                if file_ext not in expected_extensions:
                    warning_msg = f"File {file_info['path']} extension mismatch: {file_ext} not in {expected_extensions}"
                    warnings.append(warning_msg)
                    detail['status'] = 'wrong_extension'
            
        except Exception as e:
            error_msg = f"Error validating file {file_info['path']}: {e}"
            errors.append(error_msg)
            detail['status'] = 'error'
        
        return detail
    
    def _validate_extra_files(self, root_path: str, warnings: List[str], extra_files: List[str]):
        """Check for unexpected extra files"""
        expected_items = set()
        
        # Collect all expected items from schema
        for file_list in ['preserved_files', 'processing_output_files', 'optional_processing_files']:
            for file_info in self.schema.get(file_list, []):
                if file_info['path'] != "*":  # Skip wildcard entries
                    expected_items.add(file_info['path'])
        
        for dir_info in self.schema.get('preserved_directories', []):
            expected_items.add(dir_info['path'])
        
        # Find extra files
        try:
            for root, dirs, files in os.walk(root_path):
                for item in files + dirs:
                    relative_path = os.path.relpath(os.path.join(root, item), root_path)
                    relative_path = relative_path.replace('\\\\', '/')  # Normalize path separators
                    
                    if relative_path not in expected_items:
                        extra_files.append(relative_path)
            
            if extra_files:
                warnings.append(f"Found extra files: {', '.join(extra_files[:10])}")
                
        except Exception as e:
            logger.error(f"Error checking for extra files: {e}")
    
    def _validate_file_contents(self, root_path: str, errors: List[str], 
                               warnings: List[str], file_details: Dict[str, Dict[str, Any]]):
        """Validate file contents"""
        content_validation = self.schema.get('content_validation', {})
        
        # Validate JSON files
        for json_file_info in content_validation.get('json_files', []):
            file_path = os.path.join(root_path, json_file_info['path'])
            if os.path.exists(file_path):
                self._validate_json_content(file_path, json_file_info, errors, warnings)
        
        # Validate YAML files
        for yaml_file_info in content_validation.get('yaml_files', []):
            file_path = os.path.join(root_path, yaml_file_info['path'])
            if os.path.exists(file_path):
                self._validate_yaml_content(file_path, yaml_file_info, errors, warnings)
    
    def _validate_json_content(self, file_path: str, validation_info: Dict,
                              errors: List[str], warnings: List[str]):
        """Validate JSON file content"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for key in validation_info.get('required_keys', []):
                if key not in data:
                    error_msg = f"JSON file {validation_info['path']} missing required key: {key}"
                    errors.append(error_msg)
                    
        except json.JSONDecodeError as e:
            error_msg = f"JSON file {validation_info['path']} format error: {e}"
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"Error validating JSON file {validation_info['path']}: {e}"
            errors.append(error_msg)
    
    def _validate_yaml_content(self, file_path: str, validation_info: Dict,
                              errors: List[str], warnings: List[str]):
        """Validate YAML file content"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            for key in validation_info.get('required_keys', []):
                if key not in data:
                    error_msg = f"YAML file {validation_info['path']} missing required key: {key}"
                    errors.append(error_msg)
                    
        except yaml.YAMLError as e:
            error_msg = f"YAML file {validation_info['path']} format error: {e}"
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"Error validating YAML file {validation_info['path']}: {e}"
            errors.append(error_msg)
    
    def _extract_and_validate_metadata(self, root_path: str, errors: List[str], warnings: List[str]) -> Dict[str, Any]:
        """Extract and validate metadata.yaml information"""
        metadata_info = {
            'parsed_successfully': False,
            'start_time': None,
            'duration': None,
            'location': None
        }
        
        metadata_file = os.path.join(root_path, 'metadata.yaml')
        
        if not os.path.exists(metadata_file):
            errors.append("metadata.yaml file not found in processed package")
            return metadata_info
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = yaml.safe_load(f)
            
            metadata_info['parsed_successfully'] = True
            
            # Extract record information
            record_info = metadata.get('record', {})
            
            # Extract start_time
            start_time = record_info.get('start_time')
            if start_time:
                metadata_info['start_time'] = str(start_time)
                logger.info(f"Extracted start_time: {start_time}")
            
            # Extract duration
            duration_str = record_info.get('duration')
            if duration_str:
                metadata_info['duration'] = str(duration_str)
                logger.info(f"Extracted duration: {duration_str}")
            
            # Extract location
            location_info = record_info.get('location', {})
            if location_info:
                lat = location_info.get('lat')
                lon = location_info.get('lon') 
                
                if lat and lon and str(lat).lower() != 'null' and str(lon).lower() != 'null':
                    metadata_info['location'] = {
                        'latitude': str(lat),
                        'longitude': str(lon)
                    }
                    logger.info(f"Extracted location: {lat}, {lon}")
                else:
                    metadata_info['location'] = None
            else:
                metadata_info['location'] = None
                
        except yaml.YAMLError as e:
            errors.append(f"Error parsing metadata.yaml: {e}")
        except Exception as e:
            errors.append(f"Error reading metadata.yaml: {e}")
        
        return metadata_info
    
    def _create_failed_result(self, validation_level: ValidationLevel, errors: List[str]) -> ValidationResult:
        """Create a failed validation result"""
        return ValidationResult(
            is_valid=False,
            validation_level=validation_level,
            score=0.0,
            errors=errors,
            warnings=[],
            missing_files=[],
            missing_directories=[],
            extra_files=[],
            file_details={},
            summary=f"Processed validation failed: {'; '.join(errors)}",
            validator_type=self.validator_type,
            metadata={'schema_file': self.schema_file}
        )
