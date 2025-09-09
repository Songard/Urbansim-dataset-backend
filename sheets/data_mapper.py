"""
Data Mapper - Unified processing of ValidationResult to Sheets data conversion

This module is responsible for:
1. Defining standard data contracts
2. Unified processing of various ValidationResult formats
3. Providing consistent sheets data format
4. Reducing data transfer errors
"""

from typing import Dict, Any, Optional, Union
from datetime import datetime
from validation.base import ValidationResult
from utils.error_formatter import ErrorFormatter, StandardizedError, ErrorSeverity


class SheetsDataMapper:
    """Unified mapping of ValidationResult to Sheets record format"""
    
    # Define standard sheets field mapping
    SHEETS_FIELDS = {
        # Basic fields
        'file_id': str,
        'file_name': str,
        'upload_time': str,
        'device_id': str,
        'owner_name': str,
        'uploader_email': str,
        'file_size': int,
        'file_type': str,
        'extract_status': str,
        'file_count': str,
        'file_collection_status': str,
        'process_time': datetime,
        
        # Validation fields
        'validation_score': str,
        'start_time': str,
        'duration': str,
        'location': str,
        
        # Scene fields
        'scene_type': str,
        'size_status': str,
        'pcd_scale': str,
        
        # Transient detection fields
        'transient_decision': str,
        'wdd': str,  # 平均每帧人数 (Avg Persons/Frame)
        'wpo': str,  # 平均每帧面积占比 (Avg Area Occupied)
        'sai': str,  # 自身入镜指数 (Self Appearance Index)
        
        # Processing and upload fields  
        'train_val_split': str,
        'hf_upload_status': str,
        
        # Other fields
        'error_message': str,
        'warning_message': str,
        'notes': str
    }
    
    @classmethod
    def map_validation_result(cls, validation_result: Union[ValidationResult, Dict], 
                            base_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map ValidationResult to standard sheets record
        
        Args:
            validation_result: ValidationResult object or dictionary
            base_record: Basic record information (file info, etc.)
            
        Returns:
            Standardized sheets record
        """
        # Copy basic record
        sheets_record = base_record.copy()
        
        if not validation_result:
            return cls._fill_default_values(sheets_record)
        
        # Extract basic validation information
        sheets_record.update(cls._extract_basic_validation(validation_result))
        
        # Extract scene information
        sheets_record.update(cls._extract_scene_info(validation_result))
        
        # Extract transient detection information
        sheets_record.update(cls._extract_transient_info(validation_result))
        
        # Extract file collection information
        sheets_record.update(cls._extract_file_collection_info(validation_result))
        
        # Extract train/val split information
        sheets_record.update(cls._extract_train_val_split_info(validation_result))
        
        # Extract metadata information
        metadata_info = cls._extract_metadata_info(validation_result)
        sheets_record.update(metadata_info)
        
        # Extract owner information
        sheets_record.update(cls._extract_owner_info(base_record))
        
        # Extract Hugging Face upload status
        sheets_record.update(cls._extract_hf_upload_status(validation_result))
        
        # Standardize error messages
        sheets_record.update(cls._standardize_error_messages(validation_result, sheets_record))
        
        return sheets_record
    
    @classmethod
    def _extract_basic_validation(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """Extract basic validation information"""
        if isinstance(validation_result, dict):
            return {
                'validation_score': f"{validation_result.get('score', 0):.1f}/100",
            }
        else:
            return {
                'validation_score': f"{getattr(validation_result, 'score', 0):.1f}/100",
            }
    
    @classmethod
    def _extract_scene_info(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """Extract scene-related information - needs adjustment based on actual archive_handler implementation"""
        # This needs to be extracted based on actual validation_result structure
        # Currently handled by main.py, temporarily return empty
        return {}
    
    @classmethod
    def _extract_transient_info(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """Extract transient detection information with user-friendly metrics"""
        transient_info = {
            'transient_decision': 'N/A',
            'wdd': 'N/A',    # 平均每帧人数 (Avg Persons/Frame)
            'wpo': 'N/A',    # 平均每帧面积占比 (Avg Area Occupied)  
            'sai': 'N/A'     # 自身入镜指数 (Self Appearance Index)
        }
        
        try:
            # Get metadata
            if isinstance(validation_result, dict):
                metadata = validation_result.get('metadata', {})
            else:
                metadata = getattr(validation_result, 'metadata', {})
            
            if not metadata:
                return transient_info
            
            # Follow correct data path: metadata -> transient_validation -> transient_detection
            transient_validation = metadata.get('transient_validation', {})
            transient_detection = transient_validation.get('transient_detection', {})
            
            if transient_detection:
                transient_info['transient_decision'] = transient_detection.get('decision', 'N/A')
                
                metrics = transient_detection.get('metrics', {})
                if metrics:
                    wdd = metrics.get('WDD')  # Weighted Detection Density
                    wpo = metrics.get('WPO')  # Weighted Pixel Occupancy
                    sai = metrics.get('SAI')  # Self-Appearance Index
                    
                    # Format WDD as average persons per frame (clean number format)
                    transient_info['wdd'] = f"{wdd:.2f}" if wdd is not None else 'N/A'
                    
                    # Format WPO as percentage (clean number format)
                    transient_info['wpo'] = f"{wpo:.1f}" if wpo is not None else 'N/A'
                    
                    # Format SAI as percentage (clean number format)
                    transient_info['sai'] = f"{sai:.1f}" if sai is not None else 'N/A'
        
        except Exception as e:
            print(f"Warning: Failed to extract transient info: {e}")
        
        return transient_info
    
    @classmethod
    def _extract_file_collection_info(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """Extract file collection status information from processing results"""
        collection_info = {
            'file_collection_status': 'NOT_CHECKED'
        }
        
        try:
            # Get metadata to check for processing results
            if isinstance(validation_result, dict):
                metadata = validation_result.get('metadata', {})
            else:
                metadata = getattr(validation_result, 'metadata', {})
            
            if not metadata:
                return collection_info
            
            # Check for processing pipeline results in metadata
            processing_pipeline = metadata.get('processing_pipeline', {})
            if processing_pipeline:
                # Check if post-processing step exists and has results
                processing_steps = processing_pipeline.get('processing_steps', [])
                post_processing_step = None
                
                for step in processing_steps:
                    if step.get('step') == 'post_processing':
                        post_processing_step = step
                        break
                
                if post_processing_step:
                    step_result = post_processing_step.get('result', {})
                    step_success = step_result.get('success', False)
                    
                    if step_success:
                        # Post-processing succeeded, files were collected successfully
                        collection_info['file_collection_status'] = 'PASS'
                    else:
                        # Post-processing failed, check error for missing files
                        error_msg = step_result.get('error', '').lower()
                        if 'required processing output files not found' in error_msg or 'missing files' in error_msg:
                            collection_info['file_collection_status'] = 'MISSING_FILES'
                        else:
                            collection_info['file_collection_status'] = 'FAILED'
                else:
                    # Check if overall processing was successful but no post-processing found
                    overall_success = processing_pipeline.get('overall_success', False)
                    if overall_success:
                        # Processing ran but no post-processing step - might have final package
                        final_package_path = processing_pipeline.get('final_package_path')
                        if final_package_path:
                            collection_info['file_collection_status'] = 'PASS'
                        else:
                            collection_info['file_collection_status'] = 'PARTIAL'
                    else:
                        collection_info['file_collection_status'] = 'NOT_CHECKED'
            
            # Also check for any package creation results in the metadata
            final_package_info = metadata.get('final_package_info', {})
            if final_package_info:
                # If final package was created successfully, mark as PASS
                if final_package_info.get('success', False):
                    collection_info['file_collection_status'] = 'PASS'
                elif 'missing' in final_package_info.get('error', '').lower():
                    collection_info['file_collection_status'] = 'MISSING_FILES'
        
        except Exception as e:
            print(f"Warning: Failed to extract file collection info: {e}")
        
        return collection_info
    
    @classmethod
    def _extract_train_val_split_info(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """Extract train/validation split information from COLMAP processing results"""
        split_info = {
            'train_val_split': 'NOT_PROCESSED'
        }
        
        try:
            # Get metadata to check for processing results
            if isinstance(validation_result, dict):
                metadata = validation_result.get('metadata', {})
            else:
                metadata = getattr(validation_result, 'metadata', {})
            
            if not metadata:
                return split_info
            
            # Check for COLMAP processing results in final package info (legacy path)
            final_package_info = metadata.get('final_package_info', {})
            if final_package_info:
                colmap_result = final_package_info.get('colmap_result', {})
                if colmap_result:
                    train_count = colmap_result.get('train_count', 0)
                    val_count = colmap_result.get('val_count', 0)
                    split_quality = colmap_result.get('split_quality', 'FAILED')
                    
                    if train_count > 0 and val_count > 0:
                        # Format as "train_count|val_count (quality)"
                        split_info['train_val_split'] = f"{train_count}|{val_count} ({split_quality})"
                    else:
                        split_info['train_val_split'] = f"FAILED ({split_quality})"
                    return split_info
            
            # Check processing pipeline for COLMAP results - new path via final_package_result
            processing_pipeline = metadata.get('processing_pipeline', {})
            if processing_pipeline:
                # Check for final_package_result containing COLMAP information
                final_package_result = processing_pipeline.get('final_package_result', {})
                if final_package_result:
                    colmap_result = final_package_result.get('colmap_result', {})
                    if colmap_result:
                        train_count = colmap_result.get('train_count', 0)
                        val_count = colmap_result.get('val_count', 0)
                        split_quality = colmap_result.get('split_quality', 'FAILED')
                        
                        if train_count > 0 and val_count > 0:
                            split_info['train_val_split'] = f"{train_count}|{val_count} ({split_quality})"
                        else:
                            split_info['train_val_split'] = f"FAILED ({split_quality})"
                        return split_info
                
                # Legacy check for processing steps (keep for backward compatibility)
                processing_steps = processing_pipeline.get('processing_steps', [])
                post_processing_step = None
                
                for step in processing_steps:
                    if step.get('step') == 'post_processing':
                        post_processing_step = step
                        break
                
                if post_processing_step:
                    step_result = post_processing_step.get('result', {})
                    colmap_info = step_result.get('colmap_info', {})
                    
                    if colmap_info:
                        train_count = colmap_info.get('train_count', 0)
                        val_count = colmap_info.get('val_count', 0)
                        split_quality = colmap_info.get('split_quality', 'FAILED')
                        
                        if train_count > 0 and val_count > 0:
                            split_info['train_val_split'] = f"{train_count}|{val_count} ({split_quality})"
                        else:
                            split_info['train_val_split'] = f"FAILED ({split_quality})"
        
        except Exception as e:
            print(f"Warning: Failed to extract train/val split info: {e}")
        
        return split_info
    
    @classmethod
    def _extract_metadata_info(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """Extract other information from metadata (such as time, location, etc.)"""
        metadata_info = {
            'start_time': '',
            'duration': '',
            'location': '',
            'device_id': ''
        }
        
        try:
            # Get metadata
            if isinstance(validation_result, dict):
                metadata = validation_result.get('metadata', {})
            else:
                metadata = getattr(validation_result, 'metadata', {})
            
            if not metadata:
                return metadata_info
            
            # Extract time and location information
            extracted_metadata = metadata.get('extracted_metadata', {})
            if extracted_metadata:
                metadata_info['start_time'] = extracted_metadata.get('start_time', '')
                # Convert duration from decimal seconds to MM:SS format
                duration_raw = extracted_metadata.get('duration', '')
                if duration_raw:
                    # Try to format the duration, handle both string and numeric values
                    try:
                        formatted_duration = cls._format_duration(duration_raw)
                        metadata_info['duration'] = formatted_duration
                    except Exception as e:
                        # If formatting fails, keep the original value
                        metadata_info['duration'] = str(duration_raw)
                else:
                    metadata_info['duration'] = ''
                
                location = extracted_metadata.get('location', {})
                if location:
                    lat = location.get('latitude', '')
                    lon = location.get('longitude', '')
                    if lat and lon:
                        metadata_info['location'] = f"{lat}, {lon}"
                
                # Extract device ID
                device_id = extracted_metadata.get('device_id', '')
                if device_id:
                    metadata_info['device_id'] = device_id
        
        except Exception as e:
            print(f"Warning: Failed to extract metadata info: {e}")
        
        return metadata_info
    
    @classmethod
    def _extract_owner_info(cls, base_record: Dict[str, Any]) -> Dict[str, Any]:
        """Extract owner/uploader information from file metadata
        
        【字段添加问题分析 - 本次修复的关键环节】
        这个方法是本次Owner/Uploader字段添加过程中的关键组件。
        
        问题发生过程：
        1. 最初这个方法被正确创建 ✓
        2. 在map_validation_result中被正确调用 ✓  
        3. 但是当validation_result=None时，代码走_fill_default_values分支 ✗
        4. _fill_default_values最初没有调用这个方法 ✗
        
        修复方案：
        1. 确保_fill_default_values也调用此方法提取owner信息
        2. 确保main.py传递owners数据到base_record
        
        Google Drive API owners字段结构：
        owners: [
            {
                'kind': 'drive#user',
                'displayName': 'username',  -> owner_name
                'emailAddress': 'email@domain.com',  -> uploader_email
                'photoLink': '...',
                'me': false,
                'permissionId': '...'
            }
        ]
        """
        owner_info = {
            'owner_name': '',
            'uploader_email': ''
        }
        
        try:
            # Get owners information from the base_record (file metadata)
            owners = base_record.get('owners', [])
            if owners and len(owners) > 0:
                # Use the first owner (primary owner) - typically the file uploader
                first_owner = owners[0]
                owner_info['owner_name'] = first_owner.get('displayName', '')
                owner_info['uploader_email'] = first_owner.get('emailAddress', '')
        
        except Exception as e:
            print(f"Warning: Failed to extract owner info: {e}")
        
        return owner_info
    
    @classmethod
    def _extract_hf_upload_status(cls, validation_result: Union[ValidationResult, Dict]) -> Dict[str, Any]:
        """Extract Hugging Face upload status information from processing results"""
        hf_info = {
            'hf_upload_status': 'NOT_PROCESSED'
        }
        
        try:
            # Check for processing pipeline containing HF upload result
            if isinstance(validation_result, dict):
                metadata = validation_result.get('metadata', {})
                processing_pipeline = metadata.get('processing_pipeline', {})
            else:
                metadata = getattr(validation_result, 'metadata', {}) if validation_result else {}
                processing_pipeline = metadata.get('processing_pipeline', {})
            
            if processing_pipeline:
                # Check for HF upload result in processing pipeline
                hf_upload_result = processing_pipeline.get('hf_upload_result', {})
                
                if hf_upload_result:
                    if hf_upload_result.get('success'):
                        # Extract URL information from upload result
                        file_url = hf_upload_result.get('file_url', '')
                        repo_url = hf_upload_result.get('repo_url', '')
                        upload_path = hf_upload_result.get('upload_path', '')
                        
                        # Create status with URL
                        if file_url:
                            hf_info['hf_upload_status'] = f"UPLOADED: {file_url}"
                        elif repo_url and upload_path:
                            hf_info['hf_upload_status'] = f"UPLOADED: {repo_url}/blob/main/{upload_path}"
                        else:
                            hf_info['hf_upload_status'] = 'UPLOADED'
                    elif hf_upload_result.get('skipped'):
                        reason = hf_upload_result.get('reason', '')
                        if 'disabled' in reason.lower():
                            hf_info['hf_upload_status'] = 'DISABLED'
                        else:
                            hf_info['hf_upload_status'] = 'SKIPPED'
                    else:
                        error = hf_upload_result.get('error', '')
                        hf_info['hf_upload_status'] = f"FAILED: {error[:50]}..." if len(error) > 50 else f"FAILED: {error}"
                else:
                    # If there's processing pipeline but no HF result, it might be processing without upload
                    hf_info['hf_upload_status'] = 'NOT_PROCESSED'
        
        except Exception as e:
            print(f"Warning: Failed to extract HF upload status: {e}")
            hf_info['hf_upload_status'] = 'ERROR'
        
        return hf_info
    
    @classmethod
    def _format_duration(cls, duration_value: Union[str, float, int]) -> str:
        """Convert duration from decimal seconds to MM:SS format"""
        try:
            # Handle empty or None values
            if not duration_value:
                return ''
            
            # Convert to float
            if isinstance(duration_value, str):
                # Remove any whitespace and handle empty strings
                duration_value = duration_value.strip()
                if not duration_value:
                    return ''
                
                # Check if it's already in MM:SS format
                if ':' in duration_value:
                    # Already formatted, return as is
                    return duration_value
                
                duration_seconds = float(duration_value)
            else:
                duration_seconds = float(duration_value)
            
            # Convert to minutes and seconds
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            
            return f"{minutes:02d}:{seconds:02d}"
        
        except (ValueError, TypeError) as e:
            # If conversion fails, return original value as string
            print(f"Warning: Failed to format duration '{duration_value}': {e}")
            return str(duration_value) if duration_value else ''
    
    @classmethod
    def _standardize_error_messages(cls, 
                                  validation_result: Union[ValidationResult, Dict],
                                  sheets_record: Dict[str, Any]) -> Dict[str, Any]:
        """Standardize error messages to English with unified format"""
        standardized_info = {}
        
        try:
            # Get errors from validation result
            errors = []
            warnings = []
            
            if isinstance(validation_result, dict):
                errors = validation_result.get('errors', [])
                warnings = validation_result.get('warnings', [])
            else:
                errors = getattr(validation_result, 'errors', [])
                warnings = getattr(validation_result, 'warnings', [])
            
            # Convert to standardized format
            standardized_errors = ErrorFormatter.translate_legacy_errors(errors, "DataValidator")
            standardized_warnings = ErrorFormatter.translate_legacy_errors(warnings, "DataValidator")
            
            # Get validation score
            validation_score = 0
            validation_score_str = sheets_record.get('validation_score', '0')
            if isinstance(validation_score_str, str) and '/' in validation_score_str:
                validation_score = float(validation_score_str.split('/')[0])
            
            # Create standardized extract status
            extract_status = ErrorFormatter.create_extract_status_message(
                standardized_errors, 
                standardized_warnings, 
                validation_score
            )
            
            # Enhanced error and warning categorization
            # ERRORS: Critical issues that prevent successful processing
            critical_errors = []
            # WARNINGS: Issues that don't prevent processing but should be reviewed
            review_warnings = []
            
            for error in standardized_errors:
                if error.severity == ErrorSeverity.CRITICAL or error.severity == ErrorSeverity.ERROR:
                    critical_errors.append(error)
                else:
                    review_warnings.append(error)
            
            for warning in standardized_warnings:
                if warning.severity == ErrorSeverity.WARNING:
                    review_warnings.append(warning)
            
            # Create clear, specific error message showing actual problems
            error_message = ""
            if critical_errors:
                # Show actual error details instead of just categories
                error_details = []
                for error in critical_errors[:5]:  # Show up to 5 specific errors
                    # Handle StandardizedError objects properly
                    if hasattr(error, 'message'):
                        error_text = error.message.strip()
                    else:
                        error_text = str(error).strip()
                    
                    # Clean up and format error text
                    if error_text:
                        # Remove redundant prefixes
                        error_text = error_text.replace("Error:", "").replace("error:", "").strip()
                        # Make it more readable
                        error_text = cls._format_error_for_display(error_text)
                        error_details.append(error_text)
                
                if error_details:
                    error_message = "; ".join(error_details)
                    if len(critical_errors) > 5:
                        error_message += f" (and {len(critical_errors) - 5} more issues)"
            
            # Create clear, specific warning message
            warning_message = ""
            if review_warnings:
                # Show actual warning details instead of just categories
                warning_details = []
                for warning in review_warnings[:5]:  # Show up to 5 specific warnings
                    # Handle StandardizedError objects properly
                    if hasattr(warning, 'message'):
                        warning_text = warning.message.strip()
                    else:
                        warning_text = str(warning).strip()
                    
                    # Clean up and format warning text
                    if warning_text:
                        # Remove redundant prefixes
                        warning_text = warning_text.replace("warning:", "").replace("Warning:", "").strip()
                        warning_details.append(warning_text)
                
                if warning_details:
                    warning_message = "; ".join(warning_details)
                    if len(review_warnings) > 5:
                        warning_message += f" (and {len(review_warnings) - 5} more)"
            
            standardized_info['extract_status'] = extract_status
            # Only override error_message if it's empty or not already set
            existing_error_message = sheets_record.get('error_message', '')
            if existing_error_message and existing_error_message not in ['', 'N/A']:
                # Keep the existing error message from main.py
                standardized_info['error_message'] = existing_error_message
            elif error_message:
                standardized_info['error_message'] = error_message
            else:
                standardized_info['error_message'] = ""
            
            # Handle warning message
            existing_warning_message = sheets_record.get('warning_message', '')
            if existing_warning_message and existing_warning_message not in ['', 'N/A']:
                # Keep the existing warning message
                standardized_info['warning_message'] = existing_warning_message
            elif warning_message:
                standardized_info['warning_message'] = warning_message
            else:
                standardized_info['warning_message'] = ""
                
        except Exception as e:
            print(f"Warning: Failed to standardize error messages: {e}")
            # Fallback to existing values
            standardized_info['extract_status'] = sheets_record.get('extract_status', 'Unknown')
            standardized_info['error_message'] = sheets_record.get('error_message', '')
            standardized_info['warning_message'] = sheets_record.get('warning_message', '')
        
        return standardized_info
    
    @classmethod
    def _fill_default_values(cls, sheets_record: Dict[str, Any]) -> Dict[str, Any]:
        """Fill default values for missing validation_result"""
        defaults = {
            'validation_score': 'N/A (Not Validated)',
            'start_time': '',
            'duration': '',
            'location': '',
            'device_id': '',
            'owner_name': '',
            'uploader_email': '',
            'scene_type': 'unknown',
            'size_status': 'unknown',
            'pcd_scale': 'unknown',
            'file_collection_status': 'NOT_CHECKED',
            'train_val_split': 'NOT_PROCESSED',
            'hf_upload_status': 'NOT_PROCESSED',
            'transient_decision': 'N/A',
            'wdd': 'N/A',
            'wpo': 'N/A',
            'sai': 'N/A',
            'error_message': '',
            'warning_message': ''
        }
        
        sheets_record.update(defaults)
        
        # 【关键修复】Extract owner information even when validation_result is None
        # 这是本次问题的第二个修复点：
        # 原本只有在validation_result存在时才提取owner信息，
        # 但当validation_result=None时，代码走这个分支，导致owner信息丢失
        # 解决方案：无论validation_result是否存在都要提取owner信息
        owner_info = cls._extract_owner_info(sheets_record)
        sheets_record.update(owner_info)
        
        return sheets_record
    
    @classmethod
    def _format_error_for_display(cls, error_text: str) -> str:
        """Format error text to be more user-friendly and specific, including detailed missing file information"""
        # Common formatting improvements
        error_text = error_text.replace("Missing required file:", "Missing file:")
        error_text = error_text.replace("Missing required directory:", "Missing folder:")
        error_text = error_text.replace("File", "file")
        error_text = error_text.replace("too small:", "is smaller than required:")
        error_text = error_text.replace("too large:", "is larger than allowed:")
        
        # Handle specific validation messages
        if "validation failed" in error_text.lower():
            error_text = error_text.replace("validation failed", "validation failed")
        if "invalid" in error_text.lower() and "format" in error_text.lower():
            error_text = error_text.replace("Invalid", "Invalid format in")
        
        # Enhanced missing file error formatting
        if "required processing output files not found" in error_text.lower():
            # Extract specific missing files from the error message
            if "colorized.las" in error_text and "transforms.json" in error_text:
                error_text = "Missing processing output files: colorized.las, transforms.json"
            elif "colorized.las" in error_text:
                error_text = "Missing processing output file: colorized.las"
            elif "transforms.json" in error_text:
                error_text = "Missing processing output file: transforms.json"
            else:
                error_text = "Missing required processing output files"
        
        # Handle package verification failures with missing file details
        if "package verification failed" in error_text.lower() and "missing files" in error_text.lower():
            error_text = error_text.replace("Package verification failed - missing files:", "Package missing files:")
        
        return error_text
    
    @classmethod
    def _categorize_error(cls, error_text: str) -> str:
        """Categorize errors for better readability"""
        error_text_lower = error_text.lower()
        
        if "missing" in error_text_lower:
            if "file" in error_text_lower:
                return "Missing Files"
            elif "directory" in error_text_lower:
                return "Missing Directories"
            else:
                return "Missing Data"
        elif "invalid" in error_text_lower or "format" in error_text_lower:
            return "Format Issues"
        elif "size" in error_text_lower:
            return "Size Issues"
        elif "validation" in error_text_lower:
            return "Validation Failures"
        elif "transient" in error_text_lower:
            return "Transient Detection"
        elif "basic" in error_text_lower:
            return "Basic Validation"
        else:
            return "Other Issues"
    
    @classmethod
    def _categorize_warning(cls, warning_text: str) -> str:
        """Categorize warnings for better readability"""
        warning_text_lower = warning_text.lower()
        
        if "scene" in warning_text_lower or "naming" in warning_text_lower:
            return "Scene Naming"
        elif "size" in warning_text_lower:
            return "File Size"
        elif "pcd" in warning_text_lower or "scale" in warning_text_lower:
            return "PCD Scale"
        elif "duration" in warning_text_lower:
            return "Duration"
        elif "location" in warning_text_lower:
            return "Location"
        elif "device" in warning_text_lower:
            return "Device Info"
        else:
            return "General Warnings"
    
    @classmethod
    def validate_record(cls, record: Dict[str, Any]) -> bool:
        """Validate whether record contains all required fields"""
        required_fields = ['file_id', 'file_name']
        return all(field in record for field in required_fields)