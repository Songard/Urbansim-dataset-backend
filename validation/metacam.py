"""
MetaCam Data Package Validator

Specialized validator for MetaCam 3D reconstruction data packages.
Implements the base validator interface with MetaCam-specific logic.
"""

import os
import json
import yaml
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from .base import BaseValidator, ValidationResult, ValidationLevel
from utils.logger import get_logger

logger = get_logger(__name__)

class MetaCamValidator(BaseValidator):
    """
    Validator for MetaCam data packages.
    
    Validates the structure, files, and content of MetaCam
    3D reconstruction data packages according to the schema.
    """
    
    def __init__(self, schema_file: str = None):
        """
        Initialize MetaCam validator
        
        Args:
            schema_file: Path to schema file (optional)
        """
        super().__init__()
        self.schema_file = schema_file or self._get_default_schema_file()
        self.schema = None
        self.validator_type = "MetaCamValidator"
        
        # Load schema
        if not self.load_schema():
            raise ValueError(f"Failed to load schema from: {self.schema_file}")
    
    def get_supported_formats(self) -> List[str]:
        """Get supported format types"""
        return ['metacam', 'metacam_3d', 'reconstruction_data']
    
    def validate(self, target_path: str, 
                validation_level: ValidationLevel = ValidationLevel.STANDARD) -> ValidationResult:
        """
        Validate MetaCam data package
        
        Args:
            target_path: Path to the data package directory
            validation_level: Validation strictness level
            
        Returns:
            ValidationResult: Complete validation results
        """
        logger.info(f"Starting MetaCam validation: {target_path} (level: {validation_level.value})")
        
        # Find actual root directory (handle wrapper folders)
        actual_root = self._find_actual_root(target_path)
        if not actual_root:
            return self._create_failed_result(
                validation_level, 
                ["Unable to find valid MetaCam data root directory"]
            )
        
        logger.info(f"Actual data root: {actual_root}")
        
        # Initialize validation tracking
        errors = []
        warnings = []
        missing_files = []
        missing_directories = []
        extra_files = []
        file_details = {}
        
        # Perform validation steps
        self._validate_directory_structure(actual_root, errors, warnings, missing_directories)
        self._validate_required_files(actual_root, errors, warnings, missing_files, file_details)
        self._validate_optional_files(actual_root, warnings, file_details)
        
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
        
        logger.info(f"MetaCam validation completed: {summary}")
        return result
    
    def load_schema(self) -> bool:
        """Load validation schema from file"""
        try:
            if not os.path.exists(self.schema_file):
                logger.error(f"Schema file not found: {self.schema_file}")
                return False
            
            with open(self.schema_file, 'r', encoding='utf-8') as f:
                self.schema = yaml.safe_load(f)
            
            schema_name = self.schema.get('schema_name', 'Unknown')
            schema_version = self.schema.get('schema_version', '1.0')
            logger.info(f"Loaded schema: {schema_name} v{schema_version}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load schema: {e}")
            return False
    
    def _get_default_schema_file(self) -> str:
        """Get default schema file path"""
        current_dir = Path(__file__).parent
        return str(current_dir.parent / 'data_schemas' / 'metacam_schema.yaml')
    
    def _find_actual_root(self, directory_path: str) -> Optional[str]:
        """Find the actual MetaCam data root directory"""
        directory_path = os.path.abspath(directory_path)
        
        # Check if current directory contains MetaCam indicators
        if self._is_metacam_root(directory_path):
            return directory_path
        
        # Check subdirectories for MetaCam root
        try:
            items = os.listdir(directory_path)
            directories = [item for item in items if os.path.isdir(os.path.join(directory_path, item))]
            
            # If only one directory, check if it's the root
            if len(directories) == 1:
                potential_root = os.path.join(directory_path, directories[0])
                if self._is_metacam_root(potential_root):
                    return potential_root
            
            # Check all subdirectories
            for directory in directories:
                potential_root = os.path.join(directory_path, directory)
                if self._is_metacam_root(potential_root):
                    return potential_root
                    
        except Exception as e:
            logger.error(f"Error searching for root directory: {e}")
        
        return None
    
    def _is_metacam_root(self, path: str) -> bool:
        """Check if path contains MetaCam indicators"""
        indicators = ['metadata.yaml', 'camera', 'data', 'info']
        found_count = 0
        
        for indicator in indicators:
            indicator_path = os.path.join(path, indicator)
            if os.path.exists(indicator_path):
                found_count += 1
        
        return found_count >= 2  # Require at least 2 indicators
    
    def _validate_directory_structure(self, root_path: str, errors: List[str], 
                                    warnings: List[str], missing_directories: List[str]):
        """Validate required directory structure"""
        required_dirs = self.schema.get('required_directories', [])
        
        for dir_info in required_dirs:
            dir_path = os.path.join(root_path, dir_info['path'])
            
            if not os.path.exists(dir_path):
                error_msg = f"Missing required directory: {dir_info['path']}"
                errors.append(error_msg)
                missing_directories.append(dir_info['path'])
                logger.warning(error_msg)
            else:
                logger.debug(f"Found directory: {dir_info['path']}")
                
                # Check subdirectories
                subdirs = dir_info.get('subdirectories', [])
                for subdir_info in subdirs:
                    subdir_path = os.path.join(root_path, subdir_info['path'])
                    
                    if not os.path.exists(subdir_path):
                        if not subdir_info.get('optional', False):
                            error_msg = f"Missing required subdirectory: {subdir_info['path']}"
                            errors.append(error_msg)
                            missing_directories.append(subdir_info['path'])
                        else:
                            warnings.append(f"Missing optional subdirectory: {subdir_info['path']}")
    
    def _validate_required_files(self, root_path: str, errors: List[str], 
                                warnings: List[str], missing_files: List[str], 
                                file_details: Dict[str, Dict[str, Any]]):
        """Validate required files"""
        # Validate root required files
        self._validate_file_list(root_path, self.schema.get('required_files', []), 
                                errors, warnings, missing_files, file_details, True)
        
        # Validate data directory files
        self._validate_file_list(root_path, self.schema.get('data_directory_files', []),
                                errors, warnings, missing_files, file_details, True)
        
        # Validate info directory files  
        self._validate_file_list(root_path, self.schema.get('info_directory_files', []),
                                errors, warnings, missing_files, file_details, True)
    
    def _validate_optional_files(self, root_path: str, warnings: List[str], 
                                file_details: Dict[str, Dict[str, Any]]):
        """Validate optional files"""
        optional_files = self.schema.get('optional_files', [])
        self._validate_file_list(root_path, optional_files, [], warnings, [], file_details, False)
    
    def _validate_file_list(self, root_path: str, file_list: List[Dict], 
                           errors: List[str], warnings: List[str], missing_files: List[str],
                           file_details: Dict[str, Dict[str, Any]], is_required: bool):
        """Validate a list of files"""
        for file_info in file_list:
            file_path = os.path.join(root_path, file_info['path'])
            relative_path = file_info['path']
            
            # Check for flexible naming (for files like data_0 that can have .bag extension or no extension)
            if file_info.get('flexible_naming', False):
                actual_file_path, actual_relative_path = self._find_flexible_file(root_path, file_info)
                if actual_file_path:
                    file_path = actual_file_path
                    relative_path = actual_relative_path
                    logger.debug(f"Found flexible file: {relative_path}")
            
            if not os.path.exists(file_path):
                if is_required:
                    error_msg = f"Missing required file: {relative_path}"
                    errors.append(error_msg)
                    missing_files.append(relative_path)
                    logger.warning(error_msg)
                else:
                    warnings.append(f"Missing optional file: {relative_path}")
                continue
            
            # Validate file details
            file_detail = self._validate_single_file(file_path, file_info, errors, warnings)
            file_details[relative_path] = file_detail
            logger.debug(f"Validated file: {relative_path} - {file_detail['status']}")
    
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
                # Handle empty extension case (when file has no extension)
                if file_ext == '' and '' not in expected_extensions:
                    warning_msg = f"File {file_info['path']} extension mismatch: no extension, expected one of {expected_extensions}"
                    warnings.append(warning_msg)
                    detail['status'] = 'wrong_extension'
                elif file_ext != '' and file_ext not in expected_extensions:
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
        for dir_info in self.schema.get('required_directories', []):
            expected_items.add(dir_info['path'])
            for subdir_info in dir_info.get('subdirectories', []):
                expected_items.add(subdir_info['path'])
        
        for file_list in ['required_files', 'optional_files', 'data_directory_files', 'info_directory_files']:
            for file_info in self.schema.get(file_list, []):
                expected_items.add(file_info['path'])
        
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
        """Extract and validate metadata.yaml and device_info.json information"""
        metadata_info = {
            'start_time': None,
            'duration': None,
            'location': None,
            'parsed_successfully': False,
            'duration_status': None,
            'duration_seconds': None,
            'device_id': None
        }
        
        metadata_file = os.path.join(root_path, 'metadata.yaml')
        
        if not os.path.exists(metadata_file):
            errors.append("metadata.yaml file not found")
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
            else:
                errors.append("metadata.yaml missing required field: record.start_time")
            
            # Extract duration and validate
            duration_str = record_info.get('duration')
            if duration_str:
                metadata_info['duration'] = str(duration_str)
                duration_seconds = self._parse_duration_to_seconds(duration_str)
                
                if duration_seconds is not None:
                    metadata_info['duration_seconds'] = duration_seconds
                    duration_minutes = duration_seconds / 60
                    
                    # Duration validation logic
                    if duration_seconds < 180:  # Less than 3 minutes
                        errors.append(f"Duration too short ({duration_minutes:.1f} min): Less than 3 minutes indicates insufficient data")
                        metadata_info['duration_status'] = 'error_too_short'
                    elif duration_seconds > 540:  # More than 9 minutes  
                        errors.append(f"Duration too long ({duration_minutes:.1f} min): More than 9 minutes may indicate recording issues")
                        metadata_info['duration_status'] = 'error_too_long'
                    elif duration_seconds < 270:  # Less than 4.5 minutes
                        warnings.append(f"Duration potentially short ({duration_minutes:.1f} min): Less than 4.5 minutes may be insufficient")
                        metadata_info['duration_status'] = 'warning_short'
                    elif duration_seconds > 420:  # More than 7 minutes
                        warnings.append(f"Duration potentially long ({duration_minutes:.1f} min): More than 7 minutes may be excessive")
                        metadata_info['duration_status'] = 'warning_long'
                    else:
                        metadata_info['duration_status'] = 'optimal'
                        logger.info(f"Duration is optimal: {duration_minutes:.1f} minutes")
                else:
                    errors.append(f"Unable to parse duration format: {duration_str}")
                    metadata_info['duration_status'] = 'parse_error'
            else:
                errors.append("metadata.yaml missing required field: record.duration")
            
            # Extract location
            location_info = record_info.get('location', {})
            if location_info:
                lat = location_info.get('lat')
                lon = location_info.get('lon') 
                
                # Check if location data is available (not null/None/empty)
                if lat and lon and str(lat).lower() != 'null' and str(lon).lower() != 'null':
                    # Clean up encoding issues with degree symbols
                    lat_str = str(lat).replace('\xB0', '°').replace('°°', '°')
                    lon_str = str(lon).replace('\xB0', '°').replace('°°', '°')
                    
                    metadata_info['location'] = {
                        'latitude': lat_str,
                        'longitude': lon_str
                    }
                    logger.info(f"Extracted location: {lat_str}, {lon_str}")
                else:
                    # Location is null/None - this is acceptable, just log it as info
                    logger.info("Location data not available (lat/lon are null)")
                    metadata_info['location'] = None
            else:
                # No location section at all
                warnings.append("metadata.yaml missing location section (optional)")
                metadata_info['location'] = None
                
        except yaml.YAMLError as e:
            errors.append(f"Error parsing metadata.yaml: {e}")
        except Exception as e:
            errors.append(f"Error reading metadata.yaml: {e}")
        
        # Extract device information from device_info.json
        self._extract_device_info(root_path, metadata_info, errors, warnings)
        
        return metadata_info
    
    def _find_flexible_file(self, root_path: str, file_info: Dict[str, Any]) -> tuple:
        """
        Find files with flexible naming (e.g., data_0 or data_0.bag)
        
        Returns:
            tuple: (actual_file_path, actual_relative_path) or (None, None) if not found
        """
        base_path = file_info['path']
        base_filename = os.path.basename(base_path)
        directory = os.path.dirname(base_path)
        
        # Get allowed extensions from schema
        extensions = file_info.get('extensions', [''])
        
        # Try each extension
        for ext in extensions:
            if ext == '':
                # Try without extension (original path)
                test_path = os.path.join(root_path, base_path)
                test_relative = base_path
            else:
                # Try with extension
                test_filename = base_filename + ext
                test_relative = os.path.join(directory, test_filename) if directory else test_filename
                test_path = os.path.join(root_path, test_relative)
            
            if os.path.exists(test_path):
                logger.debug(f"Flexible file found: {test_relative} (extension: '{ext}')")
                return test_path, test_relative
        
        # Also try pattern matching in the directory for similar files
        try:
            search_dir = os.path.join(root_path, directory) if directory else root_path
            if os.path.exists(search_dir):
                for filename in os.listdir(search_dir):
                    # Check if filename starts with the base name
                    if filename.startswith(base_filename):
                        # Check if it matches one of the allowed extensions
                        file_ext = os.path.splitext(filename)[1]
                        if file_ext in extensions or (file_ext == '' and '' in extensions):
                            found_relative = os.path.join(directory, filename) if directory else filename
                            found_path = os.path.join(root_path, found_relative)
                            logger.debug(f"Pattern-matched flexible file: {found_relative}")
                            return found_path, found_relative
        except Exception as e:
            logger.warning(f"Error during flexible file search: {e}")
        
        return None, None
    
    def _extract_device_info(self, root_path: str, metadata_info: Dict[str, Any], errors: List[str], warnings: List[str]):
        """Extract device information from info/device_info.json"""
        device_info_file = os.path.join(root_path, 'info', 'device_info.json')
        
        if not os.path.exists(device_info_file):
            warnings.append("device_info.json file not found")
            return
        
        try:
            with open(device_info_file, 'r', encoding='utf-8') as f:
                device_data = json.load(f)
            
            # Extract model and SN to create device ID
            model = device_data.get('model', '')
            sn = device_data.get('SN', '')
            
            if model and sn:
                device_id = f"{model}-{sn}"
                metadata_info['device_id'] = device_id
                logger.info(f"Extracted device ID: {device_id}")
            else:
                if not model:
                    warnings.append("device_info.json missing 'model' field")
                if not sn:
                    warnings.append("device_info.json missing 'SN' field")
                
                # Fallback: use whatever is available
                if model or sn:
                    device_id = f"{model}{'-' if model and sn else ''}{sn}"
                    metadata_info['device_id'] = device_id
                    logger.info(f"Extracted partial device ID: {device_id}")
                else:
                    warnings.append("Unable to create device ID: both model and SN are missing")
                    
        except json.JSONDecodeError as e:
            errors.append(f"Error parsing device_info.json: {e}")
        except Exception as e:
            errors.append(f"Error reading device_info.json: {e}")
    
    def _parse_duration_to_seconds(self, duration_str: str) -> Optional[int]:
        """Parse duration string (HH:MM:SS format) to seconds"""
        try:
            # Handle format like "00:06:56"
            if ':' in duration_str:
                parts = duration_str.split(':')
                if len(parts) == 3:
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])
                    return hours * 3600 + minutes * 60 + seconds
                elif len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    return minutes * 60 + seconds
            
            # Handle other potential formats
            # Try to extract numbers using regex
            numbers = re.findall(r'\d+', duration_str)
            if len(numbers) >= 2:
                if len(numbers) >= 3:
                    # Assume H:M:S
                    hours, minutes, seconds = int(numbers[0]), int(numbers[1]), int(numbers[2])
                    return hours * 3600 + minutes * 60 + seconds
                else:
                    # Assume M:S
                    minutes, seconds = int(numbers[0]), int(numbers[1])
                    return minutes * 60 + seconds
                    
        except (ValueError, IndexError) as e:
            logger.warning(f"Could not parse duration '{duration_str}': {e}")
        
        return None
    
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
            summary=f"Validation failed: {'; '.join(errors)}",
            validator_type=self.validator_type,
            metadata={'schema_file': self.schema_file}
        )