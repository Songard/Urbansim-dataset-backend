"""
Package creation utilities for processed MetaCam data

This module handles the creation and assembly of final processed packages,
combining exe outputs with original data files into compressed archives.
"""

import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from config import Config
from utils.logger import get_logger
from utils.colmap_utils import generate_colmap_format

logger = get_logger(__name__)


def create_final_package(
    original_path: str, 
    output_files: Dict[str, str], 
    package_name: str, 
    file_id: str = None,
    output_dir: str = "./processed",
    scene_type: str = "outdoor"
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
        
        # Copy camera directory (if enabled)
        if Config.PACKAGE_INCLUDE_CAMERA_IMAGES:
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
                
        logger.info(f"File copying configuration summary:")
        logger.info(f"  - Include original files: {Config.PACKAGE_INCLUDE_ORIGINAL_FILES}")
        logger.info(f"  - Include processing outputs: {Config.PACKAGE_INCLUDE_PROCESSING_OUTPUTS}")
        logger.info(f"  - Include COLMAP files: {Config.PACKAGE_INCLUDE_COLMAP_FILES}")
        logger.info(f"  - Include camera images: {Config.PACKAGE_INCLUDE_CAMERA_IMAGES}")
        logger.info(f"  - Include preview image: {Config.PACKAGE_INCLUDE_PREVIEW_IMAGE}")
        logger.info(f"  - Include visualization: {Config.PACKAGE_INCLUDE_VISUALIZATION}")
        
        # Generate COLMAP format files if enabled
        colmap_success = False
        split_info = {}
        
        if Config.PACKAGE_INCLUDE_COLMAP_FILES:
            # For COLMAP generation, we need transforms.json
            transforms_json_path = temp_package_dir / "transforms.json"
            
            # If transforms.json is not in package, try to copy from processing outputs
            if not transforms_json_path.exists() and 'transforms_json' in output_files:
                logger.info("Copying transforms.json for COLMAP generation...")
                shutil.copy2(output_files['transforms_json'], transforms_json_path)
            
            if transforms_json_path.exists():
                logger.info("Generating COLMAP format files (sparse/0/, images/)...")
                
                # Find colorized.las file in the package or from processing outputs
                colorized_las_path = None
                
                # First look in temp package
                colorized_las_files = list(temp_package_dir.glob("colorized*.las"))
                if colorized_las_files:
                    colorized_las_path = str(colorized_las_files[0])
                    logger.info(f"Found point cloud file: {Path(colorized_las_path).name}")
                elif 'colorized_las' in output_files:
                    # Use processing output file directly
                    colorized_las_path = output_files['colorized_las']
                    logger.info(f"Using point cloud file from processing outputs: {Path(colorized_las_path).name}")
                else:
                    logger.info("No colorized.las file found, will generate COLMAP files without points3D.txt")
                
                # Ensure camera directory is available for COLMAP generation
                if not (temp_package_dir / "camera").exists():
                    logger.info("Camera directory not in package, copying for COLMAP generation...")
                    camera_dirs = [d for d in Path(original_path).rglob("camera") if d.is_dir()]
                    if camera_dirs:
                        shutil.copytree(camera_dirs[0], temp_package_dir / "camera")
                        logger.info("✓ Temporary camera directory copied for COLMAP")
                
                colmap_success, split_info = generate_colmap_format(
                    output_dir=str(temp_package_dir),
                    transforms_json_path=str(transforms_json_path),
                    original_data_path=str(temp_package_dir),  # Use temp_package_dir where camera/ is available
                    colorized_las_path=colorized_las_path
                )
                
                if colmap_success:
                    logger.info("✓ COLMAP format generation completed")
                    logger.info(f"Train/Val split: {split_info['train_count']}/{split_info['val_count']} ({split_info['split_quality']})")
                    
                    # Clean up temporary files if they weren't supposed to be included
                    if not Config.PACKAGE_INCLUDE_PROCESSING_OUTPUTS and (temp_package_dir / "transforms.json").exists():
                        (temp_package_dir / "transforms.json").unlink()
                        logger.info("Removed temporary transforms.json")
                    
                    if not Config.PACKAGE_INCLUDE_CAMERA_IMAGES and (temp_package_dir / "camera").exists():
                        shutil.rmtree(temp_package_dir / "camera")
                        logger.info("Removed temporary camera/ directory")
                        
                    # Remove visualization file if not enabled
                    if not Config.PACKAGE_INCLUDE_VISUALIZATION:
                        vis_file = temp_package_dir / "camera_pointcloud_alignment.png"
                        if vis_file.exists():
                            vis_file.unlink()
                            logger.info("Removed visualization file (not enabled in config)")
                        
                else:
                    logger.warning("COLMAP format generation failed, continuing without COLMAP files")
            else:
                logger.warning("transforms.json not found, skipping COLMAP format generation")
        else:
            logger.info("COLMAP files disabled in configuration, skipping generation")
        
        # Create scene-specific subdirectory and file naming
        scene_subdir = "outdoor" if scene_type.lower() == "outdoor" else "indoor"
        output_with_scene = Path(output_dir) / scene_subdir
        
        # Use file_id for naming without _processed suffix
        if file_id:
            final_package_name = f"{file_id}.zip"
            logger.info(f"Using Google Drive file ID for package name: {file_id}")
        else:
            final_package_name = f"{package_name}.zip"
            logger.info(f"Using package name for final package: {package_name}")
        
        final_package_path = output_with_scene / final_package_name
        logger.info(f"Final package will be saved to: {final_package_path}")
        logger.info(f"Scene type: {scene_type} -> subdirectory: {scene_subdir}")
        
        # Ensure output directory exists
        final_package_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Count total files to compress for progress tracking
        all_files = [f for f in temp_package_dir.rglob('*') if f.is_file()]
        total_files_to_compress = len(all_files)
        
        logger.info(f"Compressing final package: {final_package_path}")
        logger.info(f"Compressing {total_files_to_compress} files... This may take several minutes")
        
        compression_start = datetime.now()
        
        with zipfile.ZipFile(final_package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, file_path in enumerate(all_files, 1):
                arcname = file_path.relative_to(temp_package_dir)
                zipf.write(file_path, arcname)
                
                # Log progress every 50 files to avoid spam
                if i % 50 == 0 or i == total_files_to_compress:
                    progress_pct = (i / total_files_to_compress) * 100
                    logger.info(f"Compression progress: {i}/{total_files_to_compress} files ({progress_pct:.1f}%)")
        
        compression_duration = (datetime.now() - compression_start).total_seconds()
        logger.info(f"✓ Compression completed in {compression_duration:.1f}s")
        
        # Get package info
        package_size = final_package_path.stat().st_size
        package_size_mb = package_size / (1024 * 1024)
        
        # Cleanup temporary directory
        shutil.rmtree(temp_package_dir)
        
        logger.success(f"Final processed package created: {final_package_path}")
        logger.info(f"Package size: {package_size_mb:.1f} MB")
        
        # Verify package contents
        verification_result = _verify_final_package(final_package_path)
        if not verification_result:
            logger.warning("Package verification failed, but package was created")
        
        # Prepare COLMAP result info for metadata
        colmap_result_info = {}
        if 'colmap_success' in locals() and colmap_success and split_info:
            colmap_result_info = {
                'train_count': split_info.get('train_count', 0),
                'val_count': split_info.get('val_count', 0), 
                'split_quality': split_info.get('split_quality', 'FAILED')
            }
        
        return {
            'success': True,
            'package_path': str(final_package_path),
            'package_size_mb': package_size_mb,
            'compression_duration': compression_duration,
            'colmap_result': colmap_result_info
        }
        
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
            
            # COLMAP files verification (if enabled)
            if Config.PACKAGE_INCLUDE_COLMAP_FILES:
                # Check for sparse/0/ directory structure
                has_sparse = any(f.startswith('sparse/0/') for f in file_list)
                if not has_sparse:
                    missing_files.append("sparse/0/ directory (COLMAP structure)")
                else:
                    # Check for required COLMAP files
                    colmap_files = ['cameras.txt', 'cameras.bin', 'images.txt', 'images.bin', 'images_val.txt', 'images_val.bin']
                    found_colmap_files = []
                    for f in file_list:
                        if f.startswith('sparse/0/'):
                            filename = f.split('/')[-1]
                            if filename in colmap_files:
                                found_colmap_files.append(filename)
                    
                    # Need at least cameras and images files (either .txt or .bin format)
                    has_cameras = any(f.startswith('cameras.') for f in found_colmap_files)
                    has_images = any(f.startswith('images.') for f in found_colmap_files)
                    
                    if not has_cameras:
                        missing_files.append("cameras file in sparse/0/")
                    if not has_images:
                        missing_files.append("images file in sparse/0/")
                
                # Check for images/ directory
                has_images_dir = any(f.startswith('images/') for f in file_list)
                if not has_images_dir:
                    missing_files.append("images/ directory")
            
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