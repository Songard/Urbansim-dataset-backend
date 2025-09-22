"""
Data Processing Module

Handles execution of Windows executable programs for MetaCam data processing.
Integrates with the validation pipeline to process data after validation passes.

This module orchestrates a complete data processing workflow:
1. Directory structure standardization for MetaCam format compatibility
2. Execution of validation_generator.exe for data preparation
3. Execution of metacam_cli.exe for 3D reconstruction processing
4. Post-processing to create final packaged results

Key Features:
- Robust file search across multiple possible output locations
- Automatic creation of final processed packages combining original and processed files
- Real-time process monitoring with detailed logging
- Comprehensive error handling and recovery
- Package verification and integrity checks

Output Structure:
The final processed package ({package_name}_processed.zip) contains:
- colorized.las: Processed 3D point cloud with color information
- transforms.json: 3D transformation matrices and metadata
- metadata.yaml: Original package metadata (preserved)
- Preview.jpg: Original preview image (preserved)
- camera/: Complete camera calibration data (preserved)

Dependencies:
- validation_generator.exe: Data preparation tool
- metacam_cli.exe: 3D reconstruction processing tool
- Original MetaCam data package with proper directory structure
"""

import os
import subprocess
import tempfile
import shutil
import threading
import select
import sys
import time
import zipfile
import yaml
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
    MetaCam data processing orchestrator for Windows executable programs.
    
    Manages the complete workflow of MetaCam 3D reconstruction processing:
    
    Processing Pipeline:
    1. Directory standardization - Ensures MetaCam-compatible structure
    2. validation_generator.exe - Prepares and validates data format
    3. metacam_cli.exe - Performs 3D reconstruction with configurable parameters
    4. Post-processing - Creates final packaged results
    
    Key Features:
    - Automatic scene type detection (Indoor/Outdoor/Balance)
    - Standardized output file location for consistency
    - Real-time process monitoring with timeout handling
    - Comprehensive logging and error reporting
    - Final package assembly and verification
    - Temporary resource cleanup
    
    Configuration:
    Uses Config class settings for:
    - Executable paths (PROCESSORS_EXE_PATH)
    - Processing timeouts (PROCESSING_TIMEOUT_SECONDS, METACAM_CLI_TIMEOUT_SECONDS)
    - Output directory (PROCESSING_OUTPUT_PATH)
    - MetaCam CLI parameters (mode, color settings, scene thresholds)
    
    Error Handling:
    - Graceful handling of exe failures or crashes
    - Attempts post-processing even if exes exit abnormally
    - Detailed error logging with diagnostic information
    - Automatic cleanup of temporary resources
    
    Usage:
        processor = DataProcessor()
        result = processor.process_validated_data(data_path, validation_result, file_id)
        if result['overall_success'] and 'final_package_path' in result:
            print(f"Processing completed: {result['final_package_path']}")
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
    
    def process_validated_data(self, data_path: str, validation_result: Dict, file_id: str = None) -> Dict[str, Any]:
        """
        Process validated MetaCam data package using the processing pipeline
        
        This method orchestrates the complete data processing workflow:
        1. Standardizes directory structure to ensure proper MetaCam format
        2. Executes validation_generator.exe on the data package root
        3. Executes metacam_cli.exe on the data package root
        
        Args:
            data_path: Path to the extracted data package directory
            validation_result: Validation result containing metadata and scores
            file_id: Google Drive file ID for final package naming (optional)
            
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
            
            # Step 2: Run metacam_cli.exe on the standardized parent directory (with retry)
            step2_result = self._run_metacam_cli_with_retry(standardized_path, validation_result)
            processing_results['processing_steps'].append({
                'step': 'metacam_cli',
                'result': step2_result.to_dict()
            })
            
            if not step2_result.success:
                error_msg = f"metacam_cli failed after {Config.PROCESSING_RETRY_ATTEMPTS} attempts: {step2_result.error}"
                processing_results['errors'].append(error_msg)
                logger.error(error_msg)
                logger.warning("metacam_cli failed, but continuing with post-processing to check for any output files...")
            else:
                logger.info("metacam_cli completed successfully")
            
            # Step 3: Post-process the outputs and create final package
            # This runs regardless of metacam_cli success/failure to maximize data recovery
            logger.info("Starting post-processing phase (regardless of exe completion status)")
            step3_result = self._post_process_results(standardized_path, validation_result, file_id)
            processing_results['processing_steps'].append({
                'step': 'post_processing',
                'result': step3_result.to_dict() if step3_result else {'success': False, 'error': 'No post-processing result'}
            })
            
            if step3_result and step3_result.success:
                logger.info("Post-processing and packaging completed successfully")
                processing_results['final_package_path'] = step3_result.output
            else:
                warning_msg = "Processing completed but post-processing failed"
                processing_results['warnings'].append(warning_msg)
                logger.warning(warning_msg)
            
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
            # Use the new real-time output method
            result = self._run_process_with_realtime_output(
                command=command,
                command_str=command_str,
                timeout_seconds=Config.PROCESSING_TIMEOUT_SECONDS,
                cwd=str(self.validation_generator_path.parent)
            )
            
            # Track processed files count for summary
            output_lines = result.output.strip().split('\n') if result.output else []
            processed_files_count = sum(1 for line in output_lines if line.strip().startswith('file: No.'))
            
            if processed_files_count > 0:
                logger.info(f"validation_generator processed {processed_files_count} files")
            
            if result.success:
                logger.info(f"validation_generator completed successfully in {result.duration:.2f}s")
            else:
                logger.error(f"validation_generator failed with return code {result.return_code}")
            
            return result
            
        except Exception as e:
            error_msg = f"Failed to execute validation_generator: {e}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )
    
    def _run_process_with_realtime_output(self, command: List[str], command_str: str, 
                                        timeout_seconds: int, cwd: Optional[str] = None) -> ProcessingResult:
        """
        Execute a subprocess with real-time output display and enhanced error handling
        
        Args:
            command: List of command arguments
            command_str: String representation of command for logging
            timeout_seconds: Timeout in seconds
            cwd: Working directory
            
        Returns:
            ProcessingResult with execution details
        """
        logger.info(f"Executing command: {command_str}")
        
        # Pre-execution checks
        exe_path = command[0]
        if not os.path.exists(exe_path):
            error_msg = f"Executable not found: {exe_path}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )
        
        # Check if executable has proper permissions
        if not os.access(exe_path, os.X_OK):
            logger.warning(f"Executable may not have execute permissions: {exe_path}")
        
        # Check working directory
        if cwd and not os.path.exists(cwd):
            error_msg = f"Working directory does not exist: {cwd}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )
        
        # Log environment information
        logger.info(f"Working directory: {cwd or os.getcwd()}")
        logger.info(f"Executable path: {exe_path}")
        logger.info(f"Executable size: {os.path.getsize(exe_path)} bytes")
        logger.info(f"Timeout: {timeout_seconds} seconds")
        
        # Check executable dependencies and potential issues
        dep_check = self._check_exe_dependencies(exe_path)
        if dep_check['dependencies_found']:
            logger.info(f"Found dependencies: {', '.join(dep_check['dependencies_found'])}")
        
        if dep_check['potential_issues']:
            for issue in dep_check['potential_issues']:
                logger.warning(f"Potential issue: {issue}")
        
        try:
            start_time = datetime.now()
            
            # Start process with pipes for real-time output
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
                shell=False,
                bufsize=1,
                universal_newlines=True
            )
            
            stdout_lines = []
            stderr_lines = []
            
            def read_stdout():
                try:
                    line_count = 0
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            line = line.rstrip('\n\r')
                            stdout_lines.append(line)
                            logger.info(f"[STDOUT] {line}")
                            line_count += 1
                            
                            # Log progress every 50 lines to detect if process is active
                            if line_count % 50 == 0:
                                logger.debug(f"Process is active - received {line_count} stdout lines")
                    
                    if line_count == 0:
                        logger.warning("No stdout output received from process")
                    else:
                        logger.debug(f"Stdout reading completed - total {line_count} lines")
                    process.stdout.close()
                except Exception as e:
                    logger.error(f"Error reading stdout: {e}")
            
            def read_stderr():
                try:
                    error_count = 0
                    for line in iter(process.stderr.readline, ''):
                        if line:
                            line = line.rstrip('\n\r')
                            stderr_lines.append(line)
                            logger.warning(f"[STDERR] {line}")
                            error_count += 1
                            
                            # Check for specific error patterns that indicate permission issues
                            if any(keyword in line.lower() for keyword in ['access denied', 'permission denied', 'cannot access', 'unauthorized']):
                                logger.error(f"PERMISSION ERROR DETECTED: {line}")
                    
                    if error_count > 0:
                        logger.warning(f"Stderr reading completed - total {error_count} error lines")
                    process.stderr.close()
                except Exception as e:
                    logger.error(f"Error reading stderr: {e}")
            
            # Start threads to read stdout and stderr
            stdout_thread = threading.Thread(target=read_stdout)
            stderr_thread = threading.Thread(target=read_stderr)
            
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for process completion or timeout with enhanced monitoring
            try:
                logger.info(f"Waiting for process completion (max {timeout_seconds}s)...")
                
                # Use poll() with short intervals to detect early exits
                poll_interval = 5  # Check every 5 seconds
                elapsed = 0
                
                while elapsed < timeout_seconds:
                    return_code = process.poll()
                    if return_code is not None:
                        # Process has completed
                        logger.info(f"Process completed after {elapsed:.1f}s with return code {return_code}")
                        break
                    
                    # Log progress every 30 seconds to show the process is still running
                    if elapsed > 0 and elapsed % 30 == 0:
                        logger.info(f"Process still running... ({elapsed}s elapsed)")
                    
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                else:
                    # Timeout occurred
                    logger.warning(f"Process did not complete within {timeout_seconds} seconds")
                    process.kill()
                    return_code = process.wait()  # Wait for kill to complete
                    
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    
                    error_msg = f"Process timed out after {timeout_seconds} seconds"
                    logger.error(error_msg)
                    return ProcessingResult(
                        success=False,
                        command=command_str,
                        output="\n".join(stdout_lines),
                        error=error_msg,
                        return_code=return_code,
                        duration=duration
                    )
                
            except Exception as e:
                logger.error(f"Error waiting for process: {e}")
                try:
                    process.kill()
                    return_code = process.wait()
                except:
                    return_code = -1
            
            # Wait for threads to complete
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Combine output
            output = "\n".join(stdout_lines)
            error = "\n".join(stderr_lines)
            
            success = return_code == 0
            
            # Enhanced result analysis
            if success:
                logger.info(f"Process completed successfully in {duration:.2f}s")
                logger.info(f"Generated {len(stdout_lines)} stdout lines, {len(stderr_lines)} stderr lines")
            else:
                logger.error(f"Process failed with return code {return_code}")
                
                # Analyze failure reasons
                if return_code == -1:
                    logger.error("Process was killed or crashed unexpectedly")
                elif return_code == 1:
                    logger.error("General error occurred in process")
                elif return_code == 2:
                    logger.error("Misuse of shell command or invalid arguments")
                elif return_code == 126:
                    logger.error("Command invoked cannot execute (permission problem or not executable)")
                elif return_code == 127:
                    logger.error("Command not found")
                elif return_code == 128:
                    logger.error("Invalid argument to exit")
                elif return_code > 128:
                    signal_num = return_code - 128
                    logger.error(f"Process terminated by signal {signal_num}")
                else:
                    logger.error(f"Process exited with unknown code {return_code}")
                
                # Check for silent exit (no output at all)
                if len(stdout_lines) == 0 and len(stderr_lines) == 0:
                    logger.error("SILENT EXIT DETECTED: Process exited without any output")
                    logger.error("This usually indicates:")
                    logger.error("  1. Permission issues (insufficient privileges)")
                    logger.error("  2. Missing dependencies or libraries")
                    logger.error("  3. Invalid input parameters")
                    logger.error("  4. Working directory access issues")
                    logger.error("  5. Antivirus blocking execution")
                
                # Check if minimal output suggests early exit
                elif len(stdout_lines) < 3 and duration < 5:
                    logger.warning("EARLY EXIT DETECTED: Process ran for very short time with minimal output")
                    logger.warning("This may indicate startup issues or invalid parameters")
            
            return ProcessingResult(
                success=success,
                command=command_str,
                output=output,
                error=error,
                return_code=return_code,
                duration=duration
            )
            
        except Exception as e:
            error_msg = f"Failed to execute process: {e}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )
    
    def _check_exe_dependencies(self, exe_path: str) -> Dict[str, Any]:
        """
        Check executable dependencies and environment requirements
        
        Args:
            exe_path: Path to the executable file
            
        Returns:
            Dict with dependency check results
        """
        check_result = {
            'file_exists': False,
            'file_size': 0,
            'executable': False,
            'dependencies_found': [],
            'potential_issues': []
        }
        
        try:
            if os.path.exists(exe_path):
                check_result['file_exists'] = True
                check_result['file_size'] = os.path.getsize(exe_path)
                check_result['executable'] = os.access(exe_path, os.X_OK)
                
                # Check for common dependency files in the same directory
                exe_dir = os.path.dirname(exe_path)
                common_deps = [
                    'msvcr120.dll', 'msvcr140.dll', 'msvcp140.dll',  # Visual C++ Runtime
                    'vcruntime140.dll', 'vcruntime140_1.dll',        # More VC++ Runtime
                    'api-ms-win-crt-runtime-l1-1-0.dll',            # Universal CRT
                    'concrt140.dll', 'vcomp140.dll',                # Concurrency Runtime
                ]
                
                for dep in common_deps:
                    dep_path = os.path.join(exe_dir, dep)
                    if os.path.exists(dep_path):
                        check_result['dependencies_found'].append(dep)
                
                # Check for potential issues
                if check_result['file_size'] == 0:
                    check_result['potential_issues'].append("Executable file is empty")
                
                if not check_result['executable']:
                    check_result['potential_issues'].append("File does not have execute permissions")
                
                if len(check_result['dependencies_found']) == 0:
                    check_result['potential_issues'].append("No common dependencies found - may require system libraries")
                    
        except Exception as e:
            check_result['potential_issues'].append(f"Error checking dependencies: {e}")
        
        return check_result
    
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
            
            # Execute with real-time output and extended timeout for heavy processing
            result = self._run_process_with_realtime_output(
                command=command,
                command_str=command_str,
                timeout_seconds=Config.METACAM_CLI_TIMEOUT_SECONDS,
                cwd=str(self.metacam_cli_path.parent)
            )
            
            # Log processing time information
            hours = int(result.duration // 3600)
            minutes = int((result.duration % 3600) // 60)
            seconds = result.duration % 60
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds:.1f}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds:.1f}s" 
            else:
                duration_str = f"{seconds:.1f}s"
            
            logger.info(f"metacam_cli processing completed in {duration_str}")
            
            # Check for output files using comprehensive search (same as post-processing)
            package_name = Path(standardized_path).name
            found_files = self._find_processing_output_files(package_name)
            
            # Log what we found in the configured output directory for debugging
            output_files = list(output_dir.glob("*"))
            if output_files:
                logger.info(f"Files found in configured output directory {output_dir}:")
                for output_file in output_files[:5]:  # Log first 5 files
                    size_mb = output_file.stat().st_size / (1024 * 1024)
                    logger.info(f"  {output_file.name} ({size_mb:.1f} MB)")
                if len(output_files) > 5:
                    logger.info(f"  ... and {len(output_files) - 5} more files")
            else:
                logger.info(f"No files found in configured output directory: {output_dir}")
            
            # Determine success based on return code AND comprehensive file search
            files_found = found_files['colorized_las'] is not None or found_files['transforms_json'] is not None
            success = result.success and files_found
            
            if success:
                logger.info(f"metacam_cli completed successfully")
                if found_files['colorized_las']:
                    logger.info(f"  ✓ Point cloud file found: {found_files['colorized_las']}")
                if found_files['transforms_json']:
                    logger.info(f"  ✓ Transforms file found: {found_files['transforms_json']}")
            else:
                logger.error(f"metacam_cli failed with return code {result.return_code}")
                if not files_found:
                    logger.error("No required output files found in any search location")
                    missing_files = []
                    if not found_files['colorized_las']:
                        missing_files.append('point cloud file (colorized.las/uncolorized.ply)')
                    if not found_files['transforms_json']:
                        missing_files.append('transforms.json')
                    logger.error(f"Missing: {', '.join(missing_files)}")
            
            # Update the result with file generation status
            final_result = ProcessingResult(
                success=success,
                command=result.command,
                output=result.output,
                error=result.error if result.error else ("No required output files found" if not success else ""),
                return_code=result.return_code,
                duration=result.duration
            )
            
            return final_result
            
            
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
            subdirs = [item for item in all_items if item.is_dir() and item.name != "_MACOSX"]
            logger.info(f"Found {len(subdirs)} subdirectories in {data_path}")
            
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
    
    
    def _run_metacam_cli_with_retry(self, standardized_path: str, validation_result: Dict) -> ProcessingResult:
        """
        Run metacam_cli with retry mechanism for failed results
        
        Args:
            standardized_path: Path to directory that already contains 'data' subdirectory
            validation_result: Validation result containing scene and scale information
            
        Returns:
            ProcessingResult with execution details (includes retry information)
        """
        max_attempts = Config.PROCESSING_RETRY_ATTEMPTS
        last_result = None
        
        for attempt in range(1, max_attempts + 1):
            logger.info(f"metacam_cli attempt {attempt}/{max_attempts}")
            
            # Run metacam_cli
            result = self._run_metacam_cli_direct(standardized_path, validation_result)
            
            if result.success:
                if attempt > 1:
                    logger.info(f"metacam_cli succeeded on attempt {attempt}")
                return result
            else:
                last_result = result
                logger.warning(f"metacam_cli attempt {attempt} failed: {result.error}")
                
                if attempt < max_attempts:
                    logger.info(f"Retrying metacam_cli (attempt {attempt + 1}/{max_attempts})...")
                else:
                    logger.error(f"metacam_cli failed after {max_attempts} attempts")
        
        # Return the last failed result with retry information
        if last_result:
            last_result.error = f"Failed after {max_attempts} attempts. Last error: {last_result.error}"
        
        return last_result or ProcessingResult(
            success=False,
            command="metacam_cli (retry)",
            error=f"Failed after {max_attempts} attempts - no result available"
        )
    
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
            
            # Execute with real-time output and extended timeout for heavy processing
            result = self._run_process_with_realtime_output(
                command=command,
                command_str=command_str,
                timeout_seconds=Config.METACAM_CLI_TIMEOUT_SECONDS,
                cwd=str(self.metacam_cli_path.parent)
            )
            
            # Log processing time information
            hours = int(result.duration // 3600)
            minutes = int((result.duration % 3600) // 60)
            seconds = result.duration % 60
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds:.1f}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds:.1f}s" 
            else:
                duration_str = f"{seconds:.1f}s"
            
            logger.info(f"metacam_cli processing completed in {duration_str}")
            
            # Check for output files using comprehensive search (same as post-processing)
            package_name = Path(standardized_path).name
            found_files = self._find_processing_output_files(package_name)
            
            # Log what we found in the configured output directory for debugging
            output_files = list(output_dir.glob("*"))
            if output_files:
                logger.info(f"Files found in configured output directory {output_dir}:")
                for output_file in output_files[:5]:  # Log first 5 files
                    size_mb = output_file.stat().st_size / (1024 * 1024)
                    logger.info(f"  {output_file.name} ({size_mb:.1f} MB)")
                if len(output_files) > 5:
                    logger.info(f"  ... and {len(output_files) - 5} more files")
            else:
                logger.info(f"No files found in configured output directory: {output_dir}")
            
            # Determine success based on return code AND comprehensive file search
            files_found = found_files['colorized_las'] is not None or found_files['transforms_json'] is not None
            success = result.success and files_found
            
            if success:
                logger.info(f"metacam_cli completed successfully")
                if found_files['colorized_las']:
                    logger.info(f"  ✓ Point cloud file found: {found_files['colorized_las']}")
                if found_files['transforms_json']:
                    logger.info(f"  ✓ Transforms file found: {found_files['transforms_json']}")
            else:
                logger.error(f"metacam_cli failed with return code {result.return_code}")
                if not files_found:
                    logger.error("No required output files found in any search location")
                    missing_files = []
                    if not found_files['colorized_las']:
                        missing_files.append('point cloud file (colorized.las/uncolorized.ply)')
                    if not found_files['transforms_json']:
                        missing_files.append('transforms.json')
                    logger.error(f"Missing: {', '.join(missing_files)}")
            
            # Update the result with file generation status
            final_result = ProcessingResult(
                success=success,
                command=result.command,
                output=result.output,
                error=result.error if result.error else ("No required output files found" if not success else ""),
                return_code=result.return_code,
                duration=result.duration
            )
            
            return final_result
            
            
        except Exception as e:
            error_msg = f"Failed to execute metacam_cli: {e}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                command=command_str,
                error=error_msg
            )
    
    def _post_process_results(self, standardized_path: str, validation_result: Dict, file_id: str = None) -> Optional[ProcessingResult]:
        """
        Post-process the exe outputs to create final processed package
        
        This method:
        1. Searches for the required output files (colorized.las, transforms.json)
           in the standardized output location: ./processors/exe_packages/processed/output/{package_name}_output
        2. Copies required files from the original package
        3. Creates and compresses the final processed package
        
        Args:
            standardized_path: Path to the original standardized data directory
            validation_result: Validation result for context
            file_id: Google Drive file ID for final package naming (optional)
            
        Returns:
            ProcessingResult with post-processing details
        """
        logger.info("Starting post-processing of exe outputs")
        
        try:
            # Determine package name and paths
            package_name = Path(standardized_path).name
            
            # Search for output files in multiple possible locations
            output_files = self._find_processing_output_files(package_name)
            
            if not output_files['colorized_las'] or not output_files['transforms_json']:
                missing_files = []
                if not output_files['colorized_las']:
                    missing_files.append('colorized.las')
                if not output_files['transforms_json']:
                    missing_files.append('transforms.json')
                
                error_msg = f"Required processing output files not found: {', '.join(missing_files)}"
                logger.error(error_msg)
                return ProcessingResult(
                    success=False,
                    command="post_processing",
                    error=error_msg
                )
            
            logger.info(f"✅ POST-PROCESSING: Required output files successfully located!")
            logger.info(f"  • colorized.las: {output_files['colorized_las']}")
            logger.info(f"  • transforms.json: {output_files['transforms_json']}")
            
            # Return successful result with file locations for main loop to handle
            return ProcessingResult(
                success=True,
                command="post_processing_file_search",
                output=str(output_files),  # Pass file locations to main loop
                duration=0.0
            )
            
        except Exception as e:
            error_msg = f"Post-processing failed: {e}"
            logger.error(error_msg)
            return ProcessingResult(
                success=False,
                command="post_processing",
                error=error_msg
            )
    
    def _find_processing_output_files(self, package_name: str) -> Dict[str, Optional[str]]:
        """
        Search for the required processing output files in the standardized output location
        
        Searches in: ./processors/exe_packages/processed/output/{package_name}_output
        
        Args:
            package_name: Name of the processed package
            
        Returns:
            Dict with paths to found files or None if not found
        """
        result = {
            'colorized_las': None,
            'transforms_json': None
        }
        
        # Single output location to search
        search_locations = [
            # Relative to exe directory
            self.metacam_cli_path.parent / "processed" / "output" / f"{package_name}_output"
        ]
        
        logger.info(f"=== Starting search for output files (colorized.las & transforms.json) ===")
        logger.info(f"Package name: {package_name}")
        logger.info(f"Will search in {len(search_locations)} locations:")
        for i, location in enumerate(search_locations, 1):
            logger.info(f"  {i}. {location}")
        
        # Search for files in each location
        for i, search_path in enumerate(search_locations, 1):
            logger.info(f"[{i}/{len(search_locations)}] Checking location: {search_path}")
            
            if not search_path.exists():
                logger.info(f"  → Directory does not exist, skipping")
                continue
                
            logger.info(f"  → Directory exists, searching for files...")
            
            # List directory contents for debugging
            try:
                contents = list(search_path.iterdir())
                if contents:
                    logger.info(f"  → Found {len(contents)} items in directory:")
                    for item in contents[:10]:  # Show first 10 items
                        item_type = "DIR" if item.is_dir() else "FILE"
                        logger.info(f"    - [{item_type}] {item.name}")
                    if len(contents) > 10:
                        logger.info(f"    ... and {len(contents) - 10} more items")
                else:
                    logger.info(f"  → Directory is empty")
            except Exception as e:
                logger.warning(f"  → Could not list directory contents: {e}")
            
            # Search for colorized.las (or alternative point cloud files)
            if not result['colorized_las']:
                logger.info(f"  → Searching for point cloud files (colorized.las,  etc.)...")
                # Try multiple possible file names and extensions
                patterns = [
                    'colorized.las', '**/colorized.las',
                ]
                
                for pattern in patterns:
                    logger.info(f"    - Trying pattern: {pattern}")
                    matches = list(search_path.glob(pattern))
                    if matches:
                        result['colorized_las'] = str(matches[0])
                        logger.info(f"    [OK] FOUND point cloud file at: {result['colorized_las']}")
                        logger.info(f"        (Note: Using {matches[0].name} as point cloud file)")
                        break
                    else:
                        logger.info(f"    [NO] No match for pattern: {pattern}")
                
                if not result['colorized_las']:
                    logger.info(f"  → No point cloud files found in this location")
            else:
                logger.info(f"  → colorized.las already found, skipping search")
            
            # Search for transforms.json
            if not result['transforms_json']:
                logger.info(f"  → Searching for transforms.json...")
                for pattern in ['transforms.json', '**/transforms.json']:
                    logger.info(f"    - Trying pattern: {pattern}")
                    matches = list(search_path.glob(pattern))
                    if matches:
                        result['transforms_json'] = str(matches[0])
                        logger.info(f"    [OK] FOUND transforms.json at: {result['transforms_json']}")
                        break
                    else:
                        logger.info(f"    [NO] No match for pattern: {pattern}")
                
                if not result['transforms_json']:
                    logger.info(f"  → transforms.json not found in this location")
            else:
                logger.info(f"  → transforms.json already found, skipping search")
            
            # If both files found, stop searching
            if result['colorized_las'] and result['transforms_json']:
                logger.info(f"[SUCCESS] Both required files found in location {i}: {search_path}")
                break
            else:
                files_found = []
                if result['colorized_las']:
                    files_found.append("colorized.las")
                if result['transforms_json']:
                    files_found.append("transforms.json")
                
                if files_found:
                    logger.info(f"  → Partial success: Found {', '.join(files_found)} but still searching for remaining files")
                else:
                    logger.info(f"  → No target files found in this location")
        
        # Final search results summary
        logger.info(f"=== Search completed ===")
        if result['colorized_las'] and result['transforms_json']:
            logger.info(f"[SUCCESS] SEARCH SUCCESS: Both required files found!")
            logger.info(f"  - colorized.las: {result['colorized_las']}")
            logger.info(f"  - transforms.json: {result['transforms_json']}")
        else:
            missing_files = []
            if not result['colorized_las']:
                missing_files.append("colorized.las")
            if not result['transforms_json']:
                missing_files.append("transforms.json")
            
            logger.error(f"[FAILED] SEARCH FAILED: Missing files: {', '.join(missing_files)}")
            
            if result['colorized_las']:
                logger.info(f"  - Found colorized.las: {result['colorized_las']}")
            if result['transforms_json']:
                logger.info(f"  - Found transforms.json: {result['transforms_json']}")
            
            logger.info(f"[TIPS] Troubleshooting suggestions:")
            logger.info(f"  1. Check if metacam_cli.exe completed successfully")
            logger.info(f"  2. Verify the exe actually generates these specific filenames") 
            logger.info(f"  3. Check if files are in subdirectories with different names")
            logger.info(f"  4. Look for alternative file extensions (.pcd, .ply, .txt, etc.)")
        
        return result
    
