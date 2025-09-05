"""
Data Processing Module

Handles execution of Windows executable programs for data processing.
Integrates with the validation pipeline to process data after validation passes.
"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class ProcessingResult:
    """Processing result container"""
    
    def __init__(self, success: bool, command: str, output: str = "", 
                 error: str = "", return_code: int = 0, duration: float = 0.0):
        self.success = success
        self.command = command
        self.output = output
        self.error = error
        self.return_code = return_code
        self.duration = duration
        self.timestamp = datetime.now().isoformat()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            'success': self.success,
            'command': self.command,
            'output': self.output,
            'error': self.error,
            'return_code': self.return_code,
            'duration': self.duration,
            'timestamp': self.timestamp
        }


class DataProcessor:
    """
    Data processing orchestrator for Windows executable programs.
    
    Manages execution of data processing tools in a controlled environment
    with proper error handling, logging, and integration with the validation system.
    """
    
    def __init__(self):
        """Initialize data processor"""
        self.exe_base_path = Path(Config.PROCESSORS_EXE_PATH)
        self.validation_generator_path = self.exe_base_path / "validation_generator.exe"
        self.metacam_cli_path = self.exe_base_path / "metacam_cli.exe"
        self.temp_processing_dir = None
        
        logger.info(f"DataProcessor initialized, exe path: {self.exe_base_path}")
        
    def validate_executables(self) -> Dict[str, bool]:
        """
        Validate that required executables exist and are accessible
        
        Returns:
            Dict mapping executable names to their availability status
        """
        executables = {
            'validation_generator': self.validation_generator_path,
            'metacam_cli': self.metacam_cli_path
        }
        
        status = {}
        for name, path in executables.items():
            exists = path.exists() and path.is_file()
            status[name] = exists
            
            if exists:
                logger.info(f"[OK] Found executable: {name} at {path}")
            else:
                logger.warning(f"[MISSING] Executable not found: {name} at {path}")
        
        return status
    
    def process_validated_data(self, data_path: str, validation_result: Dict) -> Dict[str, Any]:
        """
        Process validated MetaCam data package using the processing pipeline
        
        This method orchestrates the complete data processing workflow:
        1. Standardizes directory structure to ensure proper MetaCam format
        2. Executes validation_generator.exe on the data package root
        3. Executes metacam_cli.exe on the data package root
        
        Args:
            data_path: Path to the extracted data package directory
            validation_result: Validation result containing metadata and scores
            
        Returns:
            Dict containing processing results, status, and detailed step information
        """
        logger.info(f"Starting data processing for: {data_path}")
        
        processing_results = {
            'overall_success': False,
            'data_path': data_path,
            'validation_score': validation_result.get('score', 0),
            'processing_steps': [],
            'errors': [],
            'warnings': [],
            'start_time': datetime.now().isoformat()
        }
        
        try:
            # Validate executables are available
            exe_status = self.validate_executables()
            if not all(exe_status.values()):
                missing_exes = [name for name, status in exe_status.items() if not status]
                error_msg = f"Missing required executables: {', '.join(missing_exes)}"
                processing_results['errors'].append(error_msg)
                logger.error(error_msg)
                return processing_results
            
            # Standardize directory structure to ensure proper MetaCam format
            standardized_path = self._standardize_directory_structure(data_path)
            if not standardized_path:
                error_msg = "Failed to standardize directory structure"
                processing_results['errors'].append(error_msg)
                logger.error(error_msg)
                return processing_results
            
            package_name = Path(standardized_path).name
            logger.info(f"Processing MetaCam data package: {package_name}")
            
            if not os.path.exists(standardized_path):
                error_msg = f"Standardized directory does not exist: {standardized_path}"
                processing_results['errors'].append(error_msg)
                logger.error(error_msg)
                return processing_results
            
            # Step 1: Run validation_generator.exe on the package root directory
            step1_result = self._run_validation_generator(standardized_path)
            processing_results['processing_steps'].append({
                'step': 'validation_generator',
                'result': step1_result.to_dict()
            })
            
            if not step1_result.success:
                error_msg = f"validation_generator failed: {step1_result.error}"
                processing_results['errors'].append(error_msg)
                logger.error(error_msg)
                return processing_results
            
            logger.info("validation_generator completed successfully")
            
            # Step 2: Run metacam_cli.exe on the standardized parent directory
            step2_result = self._run_metacam_cli_direct(standardized_path, validation_result)
            processing_results['processing_steps'].append({
                'step': 'metacam_cli',
                'result': step2_result.to_dict()
            })
            
            if not step2_result.success:
                error_msg = f"metacam_cli failed: {step2_result.error}"
                processing_results['errors'].append(error_msg)
                logger.error(error_msg)
                return processing_results
            
            logger.info("metacam_cli completed successfully")
            
            # Future processing steps (e.g., result validation, cleanup) can be added here
            
            # Mark overall success
            processing_results['overall_success'] = True
            processing_results['end_time'] = datetime.now().isoformat()
            
            logger.success(f"Data processing completed successfully for: {data_path}")
            
        except Exception as e:
            error_msg = f"Processing pipeline exception: {e}"
            processing_results['errors'].append(error_msg)
            logger.error(error_msg)
        
        finally:
            # Cleanup temporary directories if created
            self._cleanup_temp_directories()
        
        return processing_results
    
    def _run_validation_generator(self, data_path: str) -> ProcessingResult:
        """
        Execute validation_generator.exe on the provided data path
        
        Args:
            data_path: Path to the data directory to process
            
        Returns:
            ProcessingResult with execution details
        """
        logger.info(f"Running validation_generator on: {data_path}")
        
        # Ensure data path exists and is absolute
        data_path = os.path.abspath(data_path)
        if not os.path.exists(data_path):
            return ProcessingResult(
                success=False,
                command=f'validation_generator.exe "{data_path}"',
                error=f"Data path does not exist: {data_path}"
            )
        
        # Prepare command
        command = [str(self.validation_generator_path), data_path]
        command_str = f'"{self.validation_generator_path}" "{data_path}"'
        
        logger.info(f"Executing command: {command_str}")
        
        try:
            start_time = datetime.now()
            
            # Execute with controlled environment
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=Config.PROCESSING_TIMEOUT_SECONDS,
                cwd=self.validation_generator_path.parent,  # Set working directory to exe location
                shell=False
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Track processed files count for summary
            output_lines = result.stdout.strip().split('\n') if result.stdout else []
            processed_files_count = sum(1 for line in output_lines if line.strip().startswith('file: No.'))
            
            if processed_files_count > 0:
                logger.info(f"validation_generator processed {processed_files_count} files")
            
            # Log any errors from stderr
            if result.stderr and result.stderr.strip():
                logger.warning(f"validation_generator warnings/errors: {result.stderr.strip()}")
            
            # Determine success based on return code and output
            success = result.returncode == 0
            
            if success:
                logger.info(f"validation_generator completed successfully in {duration:.2f}s")
            else:
                logger.error(f"validation_generator failed with return code {result.returncode}")
            
            return ProcessingResult(
                success=success,
                command=command_str,
                output=result.stdout or "",
                error=result.stderr or "",
                return_code=result.returncode,
                duration=duration
            )
            
        except subprocess.TimeoutExpired:
            error_msg = f"validation_generator timed out after {Config.PROCESSING_TIMEOUT_SECONDS} seconds"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )
            
        except Exception as e:
            error_msg = f"Failed to execute validation_generator: {e}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )
    
    def _cleanup_temp_directories(self):
        """Clean up any temporary directories created during processing"""
        if self.temp_processing_dir and os.path.exists(self.temp_processing_dir):
            try:
                shutil.rmtree(self.temp_processing_dir)
                logger.debug(f"Cleaned up temporary directory: {self.temp_processing_dir}")
                self.temp_processing_dir = None
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")
    
    def get_processing_status(self) -> Dict[str, Any]:
        """
        Get current processing system status
        
        Returns:
            Dict with system status information
        """
        exe_status = self.validate_executables()
        
        return {
            'exe_base_path': str(self.exe_base_path),
            'executables': exe_status,
            'ready': all(exe_status.values()),
            'missing_executables': [name for name, status in exe_status.items() if not status]
        }
    
    def _run_metacam_cli(self, data_path: str, validation_result: Dict) -> ProcessingResult:
        """
        Execute metacam_cli.exe on the provided data path
        
        Args:
            data_path: Path to the data directory to process
            validation_result: Validation result containing scene and scale information
            
        Returns:
            ProcessingResult with execution details
        """
        logger.info(f"Running metacam_cli on: {data_path}")
        
        # Ensure data path exists and is absolute
        data_path = os.path.abspath(data_path)
        if not os.path.exists(data_path):
            return ProcessingResult(
                success=False,
                command=f'metacam_cli.exe "{data_path}"',
                error=f"Data path does not exist: {data_path}"
            )
        
        # Standardize directory structure for metacam_cli
        standardized_path = self._standardize_directory_structure(data_path)
        if not standardized_path:
            return ProcessingResult(
                success=False,
                command=f'metacam_cli.exe "{data_path}"',
                error="Failed to standardize directory structure for metacam_cli"
            )
        
        # Create output directory for this processing session
        output_base_name = Path(data_path).name
        output_dir = Path(Config.PROCESSING_OUTPUT_PATH) / f"{output_base_name}_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine scene type based on validation result
        scene_type = self._determine_scene_type(validation_result)
        
        # Prepare metacam_cli command with all parameters using standardized path
        command = [
            str(self.metacam_cli_path),
            "-i", standardized_path,
            "-o", str(output_dir),
            "-s", str(scene_type),
            "-color", Config.METACAM_CLI_COLOR,
            "-mode", Config.METACAM_CLI_MODE
        ]
        
        command_str = " ".join([f'"{arg}"' if " " in str(arg) else str(arg) for arg in command])
        
        logger.info(f"Executing metacam_cli with parameters:")
        logger.info(f"  Input: {standardized_path}")
        logger.info(f"  Output: {output_dir}")
        logger.info(f"  Scene: {scene_type} ({self._get_scene_description(scene_type)})")
        logger.info(f"  Color: {Config.METACAM_CLI_COLOR}")
        logger.info(f"  Mode: {Config.METACAM_CLI_MODE} ({'fast' if Config.METACAM_CLI_MODE == '0' else 'precision'})")
        logger.info(f"Full command: {command_str}")
        
        try:
            start_time = datetime.now()
            logger.info(f"Starting metacam_cli processing at {start_time.strftime('%H:%M:%S')}")
            
            # Execute with extended timeout for heavy processing
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=Config.METACAM_CLI_TIMEOUT_SECONDS,
                cwd=self.metacam_cli_path.parent,
                shell=False
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Log processing time information
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = duration % 60
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds:.1f}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds:.1f}s" 
            else:
                duration_str = f"{seconds:.1f}s"
            
            logger.info(f"metacam_cli processing completed in {duration_str}")
            
            # Check for output files to verify success
            output_files = list(output_dir.glob("*"))
            if output_files:
                logger.info(f"Generated {len(output_files)} output files in: {output_dir}")
                for output_file in output_files[:5]:  # Log first 5 files
                    size_mb = output_file.stat().st_size / (1024 * 1024)
                    logger.info(f"  {output_file.name} ({size_mb:.1f} MB)")
                if len(output_files) > 5:
                    logger.info(f"  ... and {len(output_files) - 5} more files")
            
            # Log any important output or errors
            if result.stderr and result.stderr.strip():
                logger.warning(f"metacam_cli warnings/errors: {result.stderr.strip()}")
            
            # Determine success based on return code and output presence
            success = result.returncode == 0 and len(output_files) > 0
            
            if success:
                logger.info(f"metacam_cli completed successfully")
            else:
                logger.error(f"metacam_cli failed with return code {result.returncode}")
                if not output_files:
                    logger.error("No output files generated")
            
            return ProcessingResult(
                success=success,
                command=command_str,
                output=result.stdout or "",
                error=result.stderr or ("No output files generated" if not success and not result.stderr else ""),
                return_code=result.returncode,
                duration=duration
            )
            
        except subprocess.TimeoutExpired:
            # Handle timeout - this is expected for very large datasets
            timeout_hours = Config.METACAM_CLI_TIMEOUT_SECONDS / 3600
            error_msg = f"metacam_cli timed out after {timeout_hours:.1f} hours"
            logger.error(error_msg)
            logger.warning("Consider increasing METACAM_CLI_TIMEOUT_SECONDS for large datasets")
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )
            
        except Exception as e:
            error_msg = f"Failed to execute metacam_cli: {e}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )
    
    def _determine_scene_type(self, validation_result: Dict) -> int:
        """
        Determine scene type for metacam_cli based on validation metadata
        
        Scene types:
        0 - Balance (default)
        1 - Open (outdoor scenes)  
        2 - Narrow (indoor small scale scenes)
        
        Args:
            validation_result: Validation result with metadata
            
        Returns:
            int: Scene type (0, 1, or 2)
        """
        try:
            metadata = validation_result.get('metadata', {})
            
            # Extract scene information from validation
            extracted_metadata = metadata.get('extracted_metadata', {})
            
            # First, check if we have scene type from validation
            scene_validation = None
            if 'scene_validation' in extracted_metadata:
                scene_validation = extracted_metadata['scene_validation']
            elif 'scene_type' in extracted_metadata:
                scene_type_str = str(extracted_metadata['scene_type']).lower()
                scene_validation = {'scene_type': scene_type_str}
            
            # Extract PCD scale information for size-based decisions
            pcd_validation = None
            if 'pcd_validation' in extracted_metadata:
                pcd_validation = extracted_metadata['pcd_validation']
            
            # Scene type decision logic
            if scene_validation:
                scene_type_str = scene_validation.get('scene_type', '').lower()
                
                if scene_type_str == 'outdoor':
                    logger.info("Scene type: Open (outdoor scene detected)")
                    return 1  # Open
                    
                elif scene_type_str == 'indoor':
                    # For indoor scenes, check scale to decide between Balance and Narrow
                    if pcd_validation:
                        width_m = pcd_validation.get('width_m', 0)
                        height_m = pcd_validation.get('height_m', 0)
                        max_dimension = max(width_m, height_m)
                        
                        if max_dimension > 0 and max_dimension < Config.INDOOR_SCALE_THRESHOLD_M:
                            logger.info(f"Scene type: Narrow (indoor scene, max dimension: {max_dimension:.1f}m)")
                            return 2  # Narrow
                        else:
                            logger.info(f"Scene type: Balance (indoor scene, max dimension: {max_dimension:.1f}m)")
                            return 0  # Balance
                    else:
                        logger.info("Scene type: Balance (indoor scene, no scale info)")
                        return 0  # Balance
            
            # Default fallback
            logger.info("Scene type: Balance (default - no clear scene indicators)")
            return 0  # Balance
            
        except Exception as e:
            logger.warning(f"Error determining scene type: {e}, using Balance as default")
            return 0  # Balance
    
    def _get_scene_description(self, scene_type: int) -> str:
        """Get human-readable description of scene type"""
        descriptions = {
            0: "Balance",
            1: "Open", 
            2: "Narrow"
        }
        return descriptions.get(scene_type, "Unknown")
    
    def _standardize_directory_structure(self, data_path: str) -> Optional[str]:
        """
        Standardize directory structure to ensure proper MetaCam data package format
        
        MetaCam processing tools expect the input directory to be the data package root
        containing subdirectories like 'data/', 'camera/', etc. This method:
        1. Detects if the directory structure is already properly formatted
        2. Creates the proper structure if needed by organizing files appropriately
        3. Returns the path that both validation_generator.exe and metacam_cli.exe should use
        
        Args:
            data_path: Path to extracted data package directory
            
        Returns:
            str: Path to standardized data package root directory, or None if failed
        """
        try:
            data_path = Path(data_path)
            data_subdir = data_path / "data"
            
            # Check if data subdirectory already exists
            if data_subdir.exists() and data_subdir.is_dir():
                logger.info(f"Found existing data/ subdirectory in {data_path}")
                return str(data_path)
            
            # Get all files and directories in the source path
            all_items = list(data_path.iterdir())
            
            if not all_items:
                logger.warning(f"No files found in {data_path}")
                return None
            
            # Check if there's already a single subdirectory that might be the data directory
            subdirs = [item for item in all_items if item.is_dir()]
            files = [item for item in all_items if item.is_file()]
            
            # If we have exactly one subdirectory and no files, check if it contains a data subdirectory
            if len(subdirs) == 1 and len(files) == 0:
                single_subdir = subdirs[0]
                data_subdir_in_single = single_subdir / "data"
                
                # Check if this subdirectory contains a 'data' subdirectory (proper MetaCam structure)
                if data_subdir_in_single.exists() and data_subdir_in_single.is_dir():
                    logger.info(f"Found proper MetaCam structure: {single_subdir.name}/data/")
                    # Return the path to the subdirectory that contains the data/ folder
                    return str(single_subdir)
                
                # If no data subdirectory, check if it directly contains data files
                subdir_contents = list(single_subdir.iterdir())
                has_data_files = any(self._is_data_file(item) for item in subdir_contents)
                
                if has_data_files:
                    logger.info(f"Found data files directly in subdirectory: {single_subdir.name}")
                    return str(data_path)
            
            # Create data/ subdirectory and move files into it
            logger.info(f"Creating standardized data/ subdirectory in {data_path}")
            data_subdir.mkdir(exist_ok=True)
            
            # Move all items into the data subdirectory
            moved_count = 0
            for item in all_items:
                try:
                    destination = data_subdir / item.name
                    
                    # Avoid moving if destination already exists
                    if destination.exists():
                        logger.warning(f"Destination already exists: {destination}, skipping {item.name}")
                        continue
                    
                    if item.is_file():
                        shutil.move(str(item), str(destination))
                    elif item.is_dir():
                        shutil.move(str(item), str(destination))
                    
                    moved_count += 1
                    logger.debug(f"Moved {item.name} to data/")
                    
                except Exception as e:
                    logger.warning(f"Failed to move {item.name}: {e}")
                    continue
            
            logger.info(f"Successfully moved {moved_count} items to data/ subdirectory")
            
            # Verify the data directory now contains files
            data_contents = list(data_subdir.iterdir())
            if not data_contents:
                logger.error("data/ directory is empty after standardization")
                return None
            
            logger.info(f"Standardized directory structure created: {data_subdir}")
            return str(data_path)
            
        except Exception as e:
            logger.error(f"Failed to standardize directory structure: {e}")
            return None
    
    def _is_data_file(self, file_path: Path) -> bool:
        """
        Check if a file is a data file that should be processed
        
        Args:
            file_path: Path to file to check
            
        Returns:
            bool: True if this appears to be a data file
        """
        if not file_path.is_file():
            return False
            
        # Common data file extensions
        data_extensions = {
            '.pcd', '.ply', '.las', '.laz', '.xyz',  # Point cloud files
            '.jpg', '.jpeg', '.png', '.tiff', '.tif',  # Image files
            '.bin', '.data', '.raw',  # Binary data files
            '.txt', '.csv', '.json', '.xml', '.yaml', '.yml',  # Text data files
            '.bag', '.mcap',  # ROS/robotics data
            '.h5', '.hdf5', '.mat'  # Scientific data formats
        }
        
        extension = file_path.suffix.lower()
        return extension in data_extensions
    
    
    def _run_metacam_cli_direct(self, standardized_path: str, validation_result: Dict) -> ProcessingResult:
        """
        Execute metacam_cli.exe on a pre-standardized directory path
        
        This method assumes the directory structure is already standardized and contains
        a 'data' subdirectory with the actual data files.
        
        Args:
            standardized_path: Path to directory that already contains 'data' subdirectory
            validation_result: Validation result containing scene and scale information
            
        Returns:
            ProcessingResult with execution details
        """
        logger.info(f"Running metacam_cli on pre-standardized path: {standardized_path}")
        
        # Ensure path exists and is absolute
        standardized_path = os.path.abspath(standardized_path)
        if not os.path.exists(standardized_path):
            return ProcessingResult(
                success=False,
                command=f'metacam_cli.exe "{standardized_path}"',
                error=f"Standardized path does not exist: {standardized_path}"
            )
        
        # Verify data directory exists
        data_dir = Path(standardized_path) / "data"
        if not data_dir.exists():
            return ProcessingResult(
                success=False,
                command=f'metacam_cli.exe "{standardized_path}"',
                error=f"Data subdirectory not found: {data_dir}"
            )
        
        # Create output directory for this processing session
        output_base_name = Path(standardized_path).name
        output_dir = Path(Config.PROCESSING_OUTPUT_PATH) / f"{output_base_name}_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine scene type based on validation result
        scene_type = self._determine_scene_type(validation_result)
        
        # Prepare metacam_cli command with all parameters
        command = [
            str(self.metacam_cli_path),
            "-i", standardized_path,
            "-o", str(output_dir),
            "-s", str(scene_type),
            "-color", Config.METACAM_CLI_COLOR,
            "-mode", Config.METACAM_CLI_MODE
        ]
        
        command_str = " ".join([f'"{arg}"' if " " in str(arg) else str(arg) for arg in command])
        
        logger.info(f"Executing metacam_cli with parameters:")
        logger.info(f"  Input: {standardized_path}")
        logger.info(f"  Output: {output_dir}")
        logger.info(f"  Scene: {scene_type} ({self._get_scene_description(scene_type)})")
        logger.info(f"  Color: {Config.METACAM_CLI_COLOR}")
        logger.info(f"  Mode: {Config.METACAM_CLI_MODE} ({'fast' if Config.METACAM_CLI_MODE == '0' else 'precision'})")
        logger.info(f"Full command: {command_str}")
        
        try:
            start_time = datetime.now()
            logger.info(f"Starting metacam_cli processing at {start_time.strftime('%H:%M:%S')}")
            
            # Execute with extended timeout for heavy processing
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=Config.METACAM_CLI_TIMEOUT_SECONDS,
                cwd=self.metacam_cli_path.parent,
                shell=False
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Log processing time information
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = duration % 60
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds:.1f}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds:.1f}s" 
            else:
                duration_str = f"{seconds:.1f}s"
            
            logger.info(f"metacam_cli processing completed in {duration_str}")
            
            # Check for output files to verify success
            output_files = list(output_dir.glob("*"))
            if output_files:
                logger.info(f"Generated {len(output_files)} output files in: {output_dir}")
                for output_file in output_files[:5]:  # Log first 5 files
                    size_mb = output_file.stat().st_size / (1024 * 1024)
                    logger.info(f"  {output_file.name} ({size_mb:.1f} MB)")
                if len(output_files) > 5:
                    logger.info(f"  ... and {len(output_files) - 5} more files")
            
            # Log any important output or errors
            if result.stderr and result.stderr.strip():
                logger.warning(f"metacam_cli warnings/errors: {result.stderr.strip()}")
            
            # Determine success based on return code and output presence
            success = result.returncode == 0 and len(output_files) > 0
            
            if success:
                logger.info(f"metacam_cli completed successfully")
            else:
                logger.error(f"metacam_cli failed with return code {result.returncode}")
                if not output_files:
                    logger.error("No output files generated")
            
            return ProcessingResult(
                success=success,
                command=command_str,
                output=result.stdout or "",
                error=result.stderr or ("No output files generated" if not success and not result.stderr else ""),
                return_code=result.returncode,
                duration=duration
            )
            
        except subprocess.TimeoutExpired:
            # Handle timeout - this is expected for very large datasets
            timeout_hours = Config.METACAM_CLI_TIMEOUT_SECONDS / 3600
            error_msg = f"metacam_cli timed out after {timeout_hours:.1f} hours"
            logger.error(error_msg)
            logger.warning("Consider increasing METACAM_CLI_TIMEOUT_SECONDS for large datasets")
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )
            
        except Exception as e:
            error_msg = f"Failed to execute metacam_cli: {e}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )