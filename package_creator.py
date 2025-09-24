"""
Package creation utilities for processed MetaCam data

This module handles the creation and assembly of final processed packages,
combining exe outputs with original data files into compressed archives.
"""

import os
import sys
import subprocess
import time
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

from config import Config
from utils.logger import get_logger
from utils.colmap_utils import generate_nvs_format

logger = get_logger(__name__)


def _log_scene_name(scene_type: str, file_id: str, package_name: str, output_dir: str):
    """
    Log scene name to appropriate text file (indoor.txt or outdoor.txt)
    
    Args:
        scene_type: Scene type (indoor/outdoor)
        file_id: Google Drive file ID
        package_name: Package name
        output_dir: Output directory where log files are stored
    """
    try:
        # Determine log file name
        log_filename = "indoor.txt" if scene_type.lower() == "indoor" else "outdoor.txt"
        log_file_path = Path(output_dir) / "data" / log_filename
        
        # Ensure the data directory exists
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use file_id if available, otherwise use package_name
        scene_name = file_id if file_id else package_name
        
        # Append to log file
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(f"{scene_name}\n")
        
        logger.info(f"Logged scene name '{scene_name}' to {log_filename}")
        
    except Exception as e:
        logger.warning(f"Failed to log scene name to {log_filename}: {e}")


def create_final_package(
    original_path: str, 
    output_files: Dict[str, str], 
    package_name: str, 
    file_id: str = None,
    output_dir: str = "./processed",
    scene_type: str = "outdoor",
    exclude_unmasked_images: bool = False,
    processing_output_path: str = None
) -> Dict[str, any]:
    """
    Create the final processed package by combining original files with processing outputs
    
    Args:
        original_path: Path to original standardized data directory
        output_files: Dict with paths to processing output files
        package_name: Name for the final package
        file_id: Google Drive file ID for package naming (optional)
        output_dir: Directory to save the final package (default: ./processed)
        scene_type: Scene type (indoor/outdoor) for subdirectory organization
        exclude_unmasked_images: If True, exclude original unmasked camera/ and undistorted/ directories
        processing_output_path: Path to processing output directory containing masked images (optional)
        
    Returns:
        Dict containing success status, package path, and any errors
    """
    logger.info("Creating final processed package")
    logger.info(f"Scene type parameter received: '{scene_type}'")
    
    try:
        # Create temporary directory for package assembly
        temp_package_dir = Path(tempfile.mkdtemp(prefix=f"processed_{package_name}_"))
        logger.info(f"Assembling package in: {temp_package_dir}")
        
        # Copy files based on configuration
        logger.info("Copying files based on package configuration...")
        original_path = Path(original_path)
        
        # Copy processing output files (if enabled)
        if Config.PACKAGE_INCLUDE_PROCESSING_OUTPUTS:
            logger.info("Copying processing output files...")
            
            # Copy point cloud file keeping original filename
            original_pc_file = Path(output_files['colorized_las'])
            final_pc_name = original_pc_file.name  # Keep original filename exactly
            
            shutil.copy2(output_files['colorized_las'], temp_package_dir / final_pc_name)
            logger.info(f"✓ Copied point cloud file: {final_pc_name}")
            
            shutil.copy2(output_files['transforms_json'], temp_package_dir / "transforms.json")
            logger.info("✓ Copied transforms.json")
        
        # Copy original metadata and other files (if enabled)
        if Config.PACKAGE_INCLUDE_ORIGINAL_FILES:
            logger.info("Copying original files...")
            
            # Copy metadata.yaml (递归搜索)
            metadata_files = list(original_path.rglob("metadata.yaml"))
            if metadata_files:
                metadata_file = metadata_files[0]  # 使用找到的第一个
                logger.info(f"Found metadata.yaml at: {metadata_file}")
                shutil.copy2(metadata_file, temp_package_dir / "metadata.yaml")
                logger.info("✓ Copied metadata.yaml")
            else:
                logger.warning(f"metadata.yaml not found in: {original_path} (searched recursively)")
        
        # Copy Preview.jpg (if enabled)
        if Config.PACKAGE_INCLUDE_PREVIEW_IMAGE:
            logger.info("Looking for Preview.jpg...")
            preview_files = list(original_path.rglob("Preview.jpg"))
            if preview_files:
                preview_file = preview_files[0]  # 使用找到的第一个
                logger.info(f"Found Preview.jpg at: {preview_file}")
                shutil.copy2(preview_file, temp_package_dir / "Preview.jpg")
                logger.info("✓ Copied Preview.jpg")
            else:
                logger.warning(f"Preview.jpg not found in: {original_path} (searched recursively)")
        
        # Copy camera directory (if enabled and not excluding unmasked images)
        if Config.PACKAGE_INCLUDE_CAMERA_IMAGES and not exclude_unmasked_images:
            logger.info("Looking for camera directory...")
            camera_dirs = [d for d in original_path.rglob("camera") if d.is_dir()]
            if camera_dirs:
                camera_dir = camera_dirs[0]  # 使用找到的第一个
                logger.info(f"Found camera/ directory at: {camera_dir}")
                # Count files first to show progress
                total_files = sum(1 for _ in camera_dir.rglob('*') if _.is_file())
                logger.info(f"Copying camera/ directory ({total_files} files)... This may take a moment")
                
                start_time = datetime.now()
                shutil.copytree(camera_dir, temp_package_dir / "camera")
                end_time = datetime.now()
                
                duration = (end_time - start_time).total_seconds()
                logger.info(f"✓ Copied camera/ directory ({total_files} files) in {duration:.1f}s")
            else:
                logger.warning(f"camera/ directory not found in: {original_path} (searched recursively)")
        elif Config.PACKAGE_INCLUDE_CAMERA_IMAGES and exclude_unmasked_images:
            logger.info("Skipping camera/ directory (unmasked images excluded)")
        
        # Copy masked image directories (if they exist and we're excluding unmasked images)
        if exclude_unmasked_images:
            logger.info("Looking for masked image directories...")
            
            # Search locations for masked images (original path and processing output path)
            search_paths = []
            
            # Add original path data directories
            original_path = Path(original_path)
            data_dirs = [d for d in original_path.rglob("data") if d.is_dir()]
            search_paths.extend(data_dirs)
            
            # Add processing output path data directories if provided
            if processing_output_path:
                processing_path = Path(processing_output_path)
                if processing_path.exists():
                    logger.info(f"Also searching for masked images in processing output: {processing_path}")
                    # Look for data directory in processing output
                    processing_data_dirs = [d for d in processing_path.rglob("data") if d.is_dir()]
                    search_paths.extend(processing_data_dirs)
                    
                    # Also check if processing output path itself contains image directories
                    if (processing_path / "fisheye_mask").exists() or (processing_path / "images_mask").exists():
                        search_paths.append(processing_path)
            
            if search_paths:
                logger.info(f"Searching for masked images in {len(search_paths)} locations")
                
                # Track which directories we've already copied to avoid duplicates
                copied_dirs = set()
                
                for data_dir in search_paths:
                    logger.info(f"Checking for masked images in: {data_dir}")
                
                    # Copy fisheye masked images (fisheye_mask directory)
                    fisheye_mask_dir = data_dir / "fisheye_mask"
                    if fisheye_mask_dir.exists() and "fisheye_mask" not in copied_dirs:
                        logger.info(f"Found fisheye_mask/ directory at: {fisheye_mask_dir}")
                        total_files = sum(1 for _ in fisheye_mask_dir.rglob('*') if _.is_file())
                        logger.info(f"Copying fisheye_mask/ directory ({total_files} files)...")
                        
                        start_time = datetime.now()
                        shutil.copytree(fisheye_mask_dir, temp_package_dir / "fisheye_mask")
                        end_time = datetime.now()
                        
                        duration = (end_time - start_time).total_seconds()
                        logger.info(f"✓ Copied fisheye_mask/ directory ({total_files} files) in {duration:.1f}s")
                        copied_dirs.add("fisheye_mask")
                    
                    # Copy undistorted masked images (images_mask directory)
                    images_mask_dir = data_dir / "images_mask"
                    if images_mask_dir.exists() and "images_mask" not in copied_dirs:
                        logger.info(f"Found images_mask/ directory at: {images_mask_dir}")
                        total_files = sum(1 for _ in images_mask_dir.rglob('*') if _.is_file())
                        logger.info(f"Copying images_mask/ directory ({total_files} files)...")
                        
                        start_time = datetime.now()
                        shutil.copytree(images_mask_dir, temp_package_dir / "images_mask")
                        end_time = datetime.now()
                        
                        duration = (end_time - start_time).total_seconds()
                        logger.info(f"✓ Copied images_mask/ directory ({total_files} files) in {duration:.1f}s")
                        copied_dirs.add("images_mask")
                    
                    # Copy the masked images from fisheye and images directories (these contain the masked versions)
                    fisheye_dir = data_dir / "fisheye"
                    if fisheye_dir.exists() and "fisheye" not in copied_dirs:
                        logger.info(f"Found fisheye/ directory (masked) at: {fisheye_dir}")
                        total_files = sum(1 for _ in fisheye_dir.rglob('*') if _.is_file())
                        logger.info(f"Copying fisheye/ directory ({total_files} masked files)...")
                        
                        start_time = datetime.now()
                        shutil.copytree(fisheye_dir, temp_package_dir / "fisheye")
                        end_time = datetime.now()
                        
                        duration = (end_time - start_time).total_seconds()
                        logger.info(f"✓ Copied fisheye/ directory ({total_files} files) in {duration:.1f}s")
                        copied_dirs.add("fisheye")
                    
                    images_dir = data_dir / "images"
                    if images_dir.exists() and "images" not in copied_dirs:
                        logger.info(f"Found images/ directory (masked) at: {images_dir}")
                        total_files = sum(1 for _ in images_dir.rglob('*') if _.is_file())
                        logger.info(f"Copying images/ directory ({total_files} masked files)...")
                        
                        start_time = datetime.now()
                        shutil.copytree(images_dir, temp_package_dir / "images")
                        end_time = datetime.now()
                        
                        duration = (end_time - start_time).total_seconds()
                        logger.info(f"✓ Copied images/ directory ({total_files} files) in {duration:.1f}s")
                        copied_dirs.add("images")
                
                if not copied_dirs:
                    logger.warning("No masked image directories found in any search location")
                else:
                    logger.info(f"Successfully copied masked image directories: {', '.join(copied_dirs)}")
            else:
                logger.warning("No data/ directories found for masked images")
                
        logger.info(f"File copying configuration summary:")
        logger.info(f"  - Include original files: {Config.PACKAGE_INCLUDE_ORIGINAL_FILES}")
        logger.info(f"  - Include processing outputs: {Config.PACKAGE_INCLUDE_PROCESSING_OUTPUTS}")
        logger.info(f"  - Include COLMAP files: {Config.PACKAGE_INCLUDE_COLMAP_FILES}")
        logger.info(f"  - Include camera images: {Config.PACKAGE_INCLUDE_CAMERA_IMAGES}")
        logger.info(f"  - Include preview image: {Config.PACKAGE_INCLUDE_PREVIEW_IMAGE}")
        logger.info(f"  - Include visualization: {Config.PACKAGE_INCLUDE_VISUALIZATION}")
        logger.info(f"  - Exclude unmasked images: {exclude_unmasked_images}")
        
        # Generate NVS split and images via COLMAP if enabled (without retaining sparse/)
        split_info = {}
        if Config.PACKAGE_INCLUDE_COLMAP_FILES:
            transforms_json_path = temp_package_dir / "transforms.json"
            if not transforms_json_path.exists() and 'transforms_json' in output_files:
                logger.info("Copying transforms.json for NVS generation...")
                shutil.copy2(output_files['transforms_json'], transforms_json_path)
            if transforms_json_path.exists():
                logger.info("Generating NVS images and splits...")
                colorized_las_path = None
                colorized_las_files = list(temp_package_dir.glob("colorized*.las"))
                if colorized_las_files:
                    colorized_las_path = str(colorized_las_files[0])
                elif 'colorized_las' in output_files:
                    colorized_las_path = output_files['colorized_las']
                if not (temp_package_dir / "camera").exists():
                    camera_dirs = [d for d in Path(original_path).rglob("camera") if d.is_dir()]
                    if camera_dirs:
                        shutil.copytree(camera_dirs[0], temp_package_dir / "camera")
                nvs_success, split_info = generate_nvs_format(
                    output_dir=str(temp_package_dir),
                    transforms_json_path=str(transforms_json_path),
                    original_data_path=str(temp_package_dir),
                    colorized_las_path=colorized_las_path
                )
                if nvs_success:
                    train_count = split_info.get('train_count', 0)
                    val_count = split_info.get('val_count', 0)
                    split_quality = split_info.get('split_quality', 'UNKNOWN')
                    logger.info(f"NVS split: {train_count}/{val_count} ({split_quality})")
                    # Mask NVS images to fisheye/ and fisheye_mask/
                    try:
                        images_dir = temp_package_dir / "images"
                        if images_dir.exists() and images_dir.is_dir():
                            if getattr(Config, 'IMAGE_MASKING_ENABLED', True):
                                script_path = Path(__file__).resolve().parent / 'processors' / 'image_masker.py'
                                if script_path.exists():
                                    output_dir_for_masked = temp_package_dir / "fisheye"
                                    output_dir_for_masked.mkdir(parents=True, exist_ok=True)
                                    masks_dir = temp_package_dir / "fisheye_mask"
                                    masks_dir.mkdir(parents=True, exist_ok=True)
                                    cmd = [
                                        sys.executable,
                                        str(script_path),
                                        '--input_dir', str(images_dir.resolve()),
                                        '--output_dir', str(output_dir_for_masked.resolve()),
                                        '--mask_dir', str(masks_dir.resolve()),
                                        '--face_model_score_threshold', str(Config.IMAGE_MASK_FACE_MODEL_SCORE_THRESHOLD),
                                        '--lp_model_score_threshold', str(Config.IMAGE_MASK_LP_MODEL_SCORE_THRESHOLD),
                                        '--nms_iou_threshold', str(Config.IMAGE_MASK_NMS_IOU_THRESHOLD),
                                        '--scale_factor_detections', str(Config.IMAGE_MASK_SCALE_FACTOR_DETECTIONS)
                                    ]
                                    if getattr(Config, 'IMAGE_MASK_FACE_MODEL_PATH', None):
                                        cmd += ['--face_model_path', Config.IMAGE_MASK_FACE_MODEL_PATH]
                                    if getattr(Config, 'IMAGE_MASK_LP_MODEL_PATH', None):
                                        cmd += ['--lp_model_path', Config.IMAGE_MASK_LP_MODEL_PATH]
                                    subprocess.run(cmd, check=False)
                                else:
                                    logger.warning("image_masker.py not found; skipping masking")
                        # Remove sparse/ and images/ from processed package workspace
                        sparse_dir = temp_package_dir / "sparse"
                        if sparse_dir.exists():
                            shutil.rmtree(sparse_dir)
                        images_dir_clean = temp_package_dir / "images"
                        if images_dir_clean.exists():
                            shutil.rmtree(images_dir_clean)

                        # Ensure processed package contains all archive contents except images/
                        try:
                            # metadata.yaml
                            if not (temp_package_dir / "metadata.yaml").exists():
                                metadata_files = list(Path(original_path).rglob("metadata.yaml"))
                                if metadata_files:
                                    shutil.copy2(metadata_files[0], temp_package_dir / "metadata.yaml")
                                    logger.info("Added metadata.yaml to processed package")
                            # Preview.jpg
                            if not (temp_package_dir / "Preview.jpg").exists():
                                preview_files = list(Path(original_path).rglob("Preview.jpg"))
                                if preview_files:
                                    shutil.copy2(preview_files[0], temp_package_dir / "Preview.jpg")
                                    logger.info("Added Preview.jpg to processed package")
                            # camera/
                            if not (temp_package_dir / "camera").exists():
                                camera_dirs2 = [d for d in Path(original_path).rglob("camera") if d.is_dir()]
                                if camera_dirs2:
                                    shutil.copytree(camera_dirs2[0], temp_package_dir / "camera")
                                    logger.info("Added camera/ to processed package")
                            # data/
                            if not (temp_package_dir / "data").exists():
                                data_dirs2 = [d for d in Path(original_path).rglob("data") if d.is_dir()]
                                if data_dirs2:
                                    shutil.copytree(data_dirs2[0], temp_package_dir / "data")
                                    logger.info("Added data/ to processed package")
                            # transforms.json
                            if not (temp_package_dir / "transforms.json").exists() and output_files.get('transforms_json'):
                                shutil.copy2(output_files['transforms_json'], temp_package_dir / "transforms.json")
                                logger.info("Added transforms.json to processed package")
                            # colorized point cloud
                            pc_present = any(p.suffix.lower() in Config.SUPPORTED_POINT_CLOUD_EXTENSIONS for p in temp_package_dir.iterdir())
                            if not pc_present and output_files.get('colorized_las'):
                                src_pc = Path(output_files['colorized_las'])
                                shutil.copy2(src_pc, temp_package_dir / src_pc.name)
                                logger.info(f"Added {src_pc.name} to processed package")
                        except Exception as e:
                            logger.warning(f"Failed to backfill processed package contents: {e}")
                    except Exception as e:
                        logger.warning(f"Masking/NVS cleanup error: {e}")
            else:
                logger.warning("transforms.json not found, skipping NVS generation")
        
        # Use single "data" folder instead of scene-specific subdirectories
        output_with_data = Path(output_dir) / "data"
        
        # Use file_id for naming without _processed suffix
        if file_id:
            base_name = file_id
            final_package_name = f"{file_id}.zip"
            logger.info(f"Using Google Drive file ID for package name: {file_id}")
        else:
            base_name = package_name
            final_package_name = f"{package_name}.zip"
            logger.info(f"Using package name for final package: {package_name}")
        
        final_package_path = output_with_data / final_package_name
        logger.info(f"Final package will be saved to: {final_package_path}")
        logger.info(f"Scene type: {scene_type} -> using data folder")
        
        # Ensure output directory exists
        final_package_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create processed and archive packages from the same assembled temp directory
        # Processed: exclude images/ and camera/
        compression_start = datetime.now()
        compression_duration = _create_zip_with_folder_structure(
            temp_package_dir, final_package_path, base_name, "final package", exclude_dirs=["images", "camera"]
        )
        archive_path = None
        if Config.ENABLE_ARCHIVE_CREATION:
            # Archive: include everything except camera/
            archive_output_with_data = Path(Config.ARCHIVE_OUTPUT_PATH) / "data"
            archive_output_with_data.mkdir(parents=True, exist_ok=True)
            archive_zip_name = f"{base_name}_archive.zip"
            archive_zip_path = archive_output_with_data / archive_zip_name
            _ = _create_zip_with_folder_structure(
                temp_package_dir, archive_zip_path, f"{base_name}_archive", "archive package", exclude_dirs=["camera"]
            )
            archive_path = str(archive_zip_path)
        logger.info(f"✓ Compression completed in {compression_duration:.1f}s")
        
        # Get package info
        package_size = final_package_path.stat().st_size
        package_size_mb = package_size / (1024 * 1024)
        
        # Log scene name to appropriate text file
        _log_scene_name(scene_type, file_id, package_name, output_dir)
        
        # Cleanup temporary directory
        shutil.rmtree(temp_package_dir)
        
        logger.success(f"Final processed package created: {final_package_path}")
        logger.info(f"Package size: {package_size_mb:.1f} MB")
        
        # Verify package contents
        verification_result = _verify_final_package(final_package_path)
        if not verification_result:
            logger.warning("Package verification failed, but package was created")
        
        # Prepare NVS result info for metadata
        nvs_result_info = {}
        if 'nvs_success' in locals() and nvs_success and split_info:
            nvs_result_info = {
                'train_count': split_info.get('train_count', 0),
                'val_count': split_info.get('val_count', 0), 
                'split_quality': split_info.get('split_quality', 'FAILED')
            }
        
        result = {
            'success': True,
            'package_path': str(final_package_path),
            'package_size_mb': package_size_mb,
            'compression_duration': compression_duration,
            'colmap_result': nvs_result_info  # Keep key name for backward compatibility
        }
        
        # Add archive path if created
        if archive_path:
            result['archive_path'] = archive_path
            logger.info(f"Archive package also created: {archive_path}")
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to create final package: {e}"
        logger.error(error_msg)
        
        # Cleanup temp directory if it exists
        if 'temp_package_dir' in locals() and temp_package_dir.exists():
            try:
                shutil.rmtree(temp_package_dir)
            except:
                pass
        
        return {
            'success': False,
            'error': error_msg
        }


def _verify_final_package(package_path: Path) -> bool:
    """
    Verify the final package contains required files based on configuration
    
    Args:
        package_path: Path to the created package
        
    Returns:
        bool: True if verification passes
    """
    try:
        logger.info(f"Verifying package contents: {package_path}")
        
        with zipfile.ZipFile(package_path, 'r') as zipf:
            file_list = zipf.namelist()
            missing_files = []
            
            # NVS split verification (if enabled): require nvs_split/ with train.txt and val.txt
            if Config.PACKAGE_INCLUDE_COLMAP_FILES:
                has_nvs_split_dir = any(f.startswith('nvs_split/') for f in file_list)
                if not has_nvs_split_dir:
                    missing_files.append("nvs_split/ directory")
                else:
                    has_train = 'nvs_split/train.txt' in file_list
                    has_val = 'nvs_split/val.txt' in file_list
                    if not has_train:
                        missing_files.append("nvs_split/train.txt")
                    if not has_val:
                        missing_files.append("nvs_split/val.txt")

            # No longer require sparse/ or images/ in the processed package
            
            # Original files verification (if enabled)
            if Config.PACKAGE_INCLUDE_ORIGINAL_FILES:
                if 'metadata.yaml' not in file_list:
                    missing_files.append("metadata.yaml")
            
            # Processing outputs verification (if enabled)
            if Config.PACKAGE_INCLUDE_PROCESSING_OUTPUTS:
                # Check for point cloud file
                point_cloud_found = False
                for file_name in file_list:
                    file_ext = Path(file_name).suffix.lower()
                    if file_ext in Config.SUPPORTED_POINT_CLOUD_EXTENSIONS:
                        point_cloud_found = True
                        logger.info(f"Found point cloud file: {file_name}")
                        break
                
                if not point_cloud_found:
                    missing_files.append(f"point cloud file (extensions: {', '.join(Config.SUPPORTED_POINT_CLOUD_EXTENSIONS)})")
                
                if 'transforms.json' not in file_list:
                    missing_files.append("transforms.json")
            
            # Camera images verification (if enabled)
            if Config.PACKAGE_INCLUDE_CAMERA_IMAGES:
                has_camera_files = any(f.startswith('camera/') for f in file_list)
                if not has_camera_files:
                    missing_files.append("camera/ directory")

            # Masked images verification (if masking likely ran during NVS)
            # We expect fisheye/ (masked images) and fisheye_mask/ when IMAGE_MASKING_ENABLED
            if getattr(Config, 'IMAGE_MASKING_ENABLED', False):
                has_fisheye = any(f.startswith('fisheye/') for f in file_list)
                has_fisheye_mask = any(f.startswith('fisheye_mask/') for f in file_list)
                if not has_fisheye:
                    missing_files.append("fisheye/ directory")
                if not has_fisheye_mask:
                    missing_files.append("fisheye_mask/ directory")
            
            # Preview image verification (if enabled)
            if Config.PACKAGE_INCLUDE_PREVIEW_IMAGE:
                if 'Preview.jpg' not in file_list:
                    missing_files.append("Preview.jpg")
            
            # Visualization verification (if enabled)
            if Config.PACKAGE_INCLUDE_VISUALIZATION:
                if 'camera_pointcloud_alignment.png' not in file_list:
                    missing_files.append("camera_pointcloud_alignment.png")
            
            if missing_files:
                logger.error(f"Package verification failed - missing files: {', '.join(missing_files)}")
                return False
            
            logger.info(f"✅ Package verification passed - found {len(file_list)} files total")
            
            # Log what was included based on configuration
            logger.info("Package contents based on configuration:")
            if Config.PACKAGE_INCLUDE_COLMAP_FILES:
                colmap_file_count = sum(1 for f in file_list if f.startswith('sparse/') or f.startswith('images/'))
                logger.info(f"  - COLMAP files: {colmap_file_count} files")
            if Config.PACKAGE_INCLUDE_CAMERA_IMAGES:
                camera_file_count = sum(1 for f in file_list if f.startswith('camera/'))
                logger.info(f"  - Camera images: {camera_file_count} files")
            if getattr(Config, 'IMAGE_MASKING_ENABLED', False):
                fisheye_file_count = sum(1 for f in file_list if f.startswith('fisheye/'))
                fisheye_mask_file_count = sum(1 for f in file_list if f.startswith('fisheye_mask/'))
                logger.info(f"  - Masked images: fisheye/ {fisheye_file_count}, fisheye_mask/ {fisheye_mask_file_count}")
            if Config.PACKAGE_INCLUDE_PROCESSING_OUTPUTS:
                processing_files = [f for f in file_list if f.endswith(tuple(Config.SUPPORTED_POINT_CLOUD_EXTENSIONS)) or f == 'transforms.json']
                logger.info(f"  - Processing outputs: {len(processing_files)} files")
            if Config.PACKAGE_INCLUDE_PREVIEW_IMAGE and 'Preview.jpg' in file_list:
                logger.info("  - Preview image: included")
            if Config.PACKAGE_INCLUDE_VISUALIZATION and 'camera_pointcloud_alignment.png' in file_list:
                logger.info("  - Visualization: included")
            
            return True
            
    except Exception as e:
        logger.error(f"Package verification failed with exception: {e}")
        return False


def _create_zip_with_folder_structure(source_dir: Path, zip_path: Path, folder_name: str, package_type: str, exclude_dirs: Optional[List[str]] = None) -> float:
    """
    Create a zip file with proper folder structure (creates a top-level folder when unzipped)
    
    Args:
        source_dir: Source directory containing files to zip
        zip_path: Output zip file path
        folder_name: Name of the top-level folder to create in the zip
        package_type: Type of package for logging (e.g., "final package", "archive package")
        
    Returns:
        Compression duration in seconds
    """
    # Count total files to compress for progress tracking
    exclude_dirs = exclude_dirs or []
    all_files = []
    for f in source_dir.rglob('*'):
        if not f.is_file():
            continue
        # Skip excluded directories
        relative_parent_parts = f.relative_to(source_dir).parts
        if relative_parent_parts:
            top_level_dir = relative_parent_parts[0]
            if top_level_dir in exclude_dirs:
                continue
        all_files.append(f)
    total_files_to_compress = len(all_files)
    
    logger.info(f"Compressing {package_type}: {zip_path}")
    logger.info(f"Compressing {total_files_to_compress} files into folder '{folder_name}'... This may take several minutes")
    
    compression_start = datetime.now()
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for i, file_path in enumerate(all_files, 1):
            # Create archive name with top-level folder
            relative_path = file_path.relative_to(source_dir)
            arcname = Path(folder_name) / relative_path
            zipf.write(file_path, str(arcname))
            
            # Log progress every 50 files to avoid spam
            if i % 50 == 0 or i == total_files_to_compress:
                progress_pct = (i / total_files_to_compress) * 100
                logger.info(f"Compression progress: {i}/{total_files_to_compress} files ({progress_pct:.1f}%)")
    
    compression_duration = (datetime.now() - compression_start).total_seconds()
    return compression_duration


def _create_archive_package(original_path: str, output_files: Dict[str, str], base_name: str, 
                           scene_type: str, processing_output_path: str = None) -> Optional[str]:
    """
    Create an archive package containing all files including unmasked images
    
    Args:
        original_path: Path to original standardized data directory
        output_files: Dict with paths to processing output files
        base_name: Base name for the archive package
        scene_type: Scene type (indoor/outdoor)
        processing_output_path: Path to processing output directory
        
    Returns:
        Path to created archive package or None if failed
    """
    try:
        import tempfile
        
        # Create temporary directory for archive assembly
        temp_archive_dir = Path(tempfile.mkdtemp(prefix=f"archive_{base_name}_"))
        logger.info(f"Assembling archive package in: {temp_archive_dir}")
        
        original_path = Path(original_path)
        
        # Copy ALL original files (including unmasked images)
        logger.info("Copying all original files for archive...")
        
        # Copy processing output files
        if output_files.get('colorized_las') and output_files.get('transforms_json'):
            # Copy point cloud file keeping original filename
            original_pc_file = Path(output_files['colorized_las'])
            final_pc_name = original_pc_file.name
            shutil.copy2(output_files['colorized_las'], temp_archive_dir / final_pc_name)
            shutil.copy2(output_files['transforms_json'], temp_archive_dir / "transforms.json")
            logger.info("✓ Copied processing output files to archive")
        
        # Copy metadata.yaml
        metadata_files = list(original_path.rglob("metadata.yaml"))
        if metadata_files:
            shutil.copy2(metadata_files[0], temp_archive_dir / "metadata.yaml")
            logger.info("✓ Copied metadata.yaml to archive")
        
        # Copy Preview.jpg
        preview_files = list(original_path.rglob("Preview.jpg"))
        if preview_files:
            shutil.copy2(preview_files[0], temp_archive_dir / "Preview.jpg")
            logger.info("✓ Copied Preview.jpg to archive")
        
        # Copy ALL camera directories (including unmasked images)
        camera_dirs = [d for d in original_path.rglob("camera") if d.is_dir()]
        if camera_dirs:
            camera_dir = camera_dirs[0]
            total_files = sum(1 for _ in camera_dir.rglob('*') if _.is_file())
            logger.info(f"Copying complete camera/ directory ({total_files} files)...")
            
            start_time = datetime.now()
            shutil.copytree(camera_dir, temp_archive_dir / "camera")
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"✓ Copied camera/ directory ({total_files} files) in {duration:.1f}s")
        
        # Copy all data directories (both masked and unmasked images)
        data_dirs = [d for d in original_path.rglob("data") if d.is_dir()]
        if data_dirs:
            data_dir = data_dirs[0]
            logger.info(f"Copying complete data/ directory...")
            
            start_time = datetime.now()
            shutil.copytree(data_dir, temp_archive_dir / "data")
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"✓ Copied data/ directory in {duration:.1f}s")
        
        # Also copy any processed images from processing output path if it exists
        if processing_output_path:
            processing_path = Path(processing_output_path)
            if processing_path.exists():
                logger.info("Copying processed images from processing output...")
                
                # Look for processed data directories
                processing_data_dirs = [d for d in processing_path.rglob("data") if d.is_dir()]
                for proc_data_dir in processing_data_dirs:
                    # Copy any additional processed images
                    for subdir in proc_data_dir.iterdir():
                        if subdir.is_dir() and not (temp_archive_dir / "data" / subdir.name).exists():
                            shutil.copytree(subdir, temp_archive_dir / "data" / subdir.name)
                            logger.info(f"✓ Copied processed {subdir.name}/ from processing output")

        # Ensure NVS images/ are included in ARCHIVE package (but not in processed one)
        try:
            images_dir = (Path(output_files.get('transforms_json', '')).parent if output_files.get('transforms_json') else Path('.'))
            # If temp_package_dir created earlier exists with images, reuse. Otherwise, search original_path for generated images
            # Here, we only ensure images/ exists under archive for completeness if present next to temp work
            # No-op if not found
        except Exception:
            pass
        
        # Generate COLMAP format files for archive (to create images/), but do not require sparse/ later
        transforms_json_path = temp_archive_dir / "transforms.json"
        if transforms_json_path.exists():
            logger.info("Generating COLMAP format files for archive...")
            
            # Find colorized.las file
            colorized_las_path = None
            colorized_las_files = list(temp_archive_dir.glob("colorized*.las"))
            if colorized_las_files:
                colorized_las_path = str(colorized_las_files[0])
            elif output_files.get('colorized_las'):
                colorized_las_path = output_files['colorized_las']
            
            nvs_success, split_info = generate_nvs_format(
                output_dir=str(temp_archive_dir),
                transforms_json_path=str(transforms_json_path),
                original_data_path=str(temp_archive_dir),
                colorized_las_path=colorized_las_path
            )
            
            if nvs_success:
                logger.info("✓ COLMAP images/NVS generation completed for archive")
                # Run masking on archive images/ as well to produce fisheye/ and fisheye_mask/
                try:
                    images_dir = temp_archive_dir / "images"
                    if images_dir.exists() and images_dir.is_dir() and getattr(Config, 'IMAGE_MASKING_ENABLED', True):
                        script_path = Path(__file__).resolve().parent / 'processors' / 'image_masker.py'
                        if script_path.exists():
                            output_dir_for_masked = temp_archive_dir / "fisheye"
                            output_dir_for_masked.mkdir(parents=True, exist_ok=True)
                            masks_dir = temp_archive_dir / "fisheye_mask"
                            masks_dir.mkdir(parents=True, exist_ok=True)
                            cmd = [
                                sys.executable,
                                str(script_path),
                                '--input_dir', str(images_dir.resolve()),
                                '--output_dir', str(output_dir_for_masked.resolve()),
                                '--mask_dir', str(masks_dir.resolve()),
                                '--face_model_score_threshold', str(Config.IMAGE_MASK_FACE_MODEL_SCORE_THRESHOLD),
                                '--lp_model_score_threshold', str(Config.IMAGE_MASK_LP_MODEL_SCORE_THRESHOLD),
                                '--nms_iou_threshold', str(Config.IMAGE_MASK_NMS_IOU_THRESHOLD),
                                '--scale_factor_detections', str(Config.IMAGE_MASK_SCALE_FACTOR_DETECTIONS)
                            ]
                            if getattr(Config, 'IMAGE_MASK_FACE_MODEL_PATH', None):
                                cmd += ['--face_model_path', Config.IMAGE_MASK_FACE_MODEL_PATH]
                            if getattr(Config, 'IMAGE_MASK_LP_MODEL_PATH', None):
                                cmd += ['--lp_model_path', Config.IMAGE_MASK_LP_MODEL_PATH]
                            subprocess.run(cmd, check=False)
                        else:
                            logger.warning("image_masker.py not found; skipping archive masking")
                except Exception as e:
                    logger.warning(f"Archive masking error: {e}")
                # Remove sparse/ from ARCHIVE as it's no longer needed
                try:
                    sparse_dir_arch = temp_archive_dir / "sparse"
                    if sparse_dir_arch.exists():
                        shutil.rmtree(sparse_dir_arch)
                        logger.info("Removed sparse/ directory from archive")
                except Exception as e:
                    logger.warning(f"Failed to remove sparse/ from archive: {e}")
            else:
                logger.warning("COLMAP format generation failed for archive")
        
        # Create archive zip file in data folder
        archive_output_with_data = Path(Config.ARCHIVE_OUTPUT_PATH) / "data"
        archive_output_with_data.mkdir(parents=True, exist_ok=True)
        
        archive_zip_name = f"{base_name}_archive.zip"
        archive_zip_path = archive_output_with_data / archive_zip_name
        
        # Create archive zip with folder structure
        compression_duration = _create_zip_with_folder_structure(
            temp_archive_dir, archive_zip_path, f"{base_name}_archive", "archive package"
        )
        
        # Get archive package info
        archive_size = archive_zip_path.stat().st_size
        archive_size_mb = archive_size / (1024 * 1024)
        
        # Cleanup temporary directory
        shutil.rmtree(temp_archive_dir)
        
        logger.success(f"Archive package created: {archive_zip_path}")
        logger.info(f"Archive size: {archive_size_mb:.1f} MB (compressed in {compression_duration:.1f}s)")
        
        return str(archive_zip_path)
        
    except Exception as e:
        logger.error(f"Failed to create archive package: {e}")
        return None