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
                    logger.info("No colorized.las file found, will generate NVS split files only")
                
                # Ensure camera directory is available for NVS generation
                if not (temp_package_dir / "camera").exists():
                    logger.info("Camera directory not in package, copying for NVS generation...")
                    camera_dirs = [d for d in Path(original_path).rglob("camera") if d.is_dir()]
                    if camera_dirs:
                        shutil.copytree(camera_dirs[0], temp_package_dir / "camera")
                        logger.info("✓ Temporary camera directory copied for NVS")
                
                nvs_success, split_info = generate_colmap_format(
                    output_dir=str(temp_package_dir),
                    transforms_json_path=str(transforms_json_path),
                    original_data_path=str(temp_package_dir),  # Use temp_package_dir where camera/ is available
                    colorized_las_path=colorized_las_path
                )
                
                if nvs_success:
                    logger.info("✓ NVS format generation completed")
                    logger.info(f"Train/Val split: {split_info['train_count']}/{split_info['val_count']} ({split_info['split_quality']})")
                    
                    # Clean up temporary files if they weren't supposed to be included
                    if not Config.PACKAGE_INCLUDE_PROCESSING_OUTPUTS and (temp_package_dir / "transforms.json").exists():
                        (temp_package_dir / "transforms.json").unlink()
                        logger.info("Removed temporary transforms.json")
                    
                    if (not Config.PACKAGE_INCLUDE_CAMERA_IMAGES or exclude_unmasked_images) and (temp_package_dir / "camera").exists():
                        shutil.rmtree(temp_package_dir / "camera")
                        logger.info("Removed temporary camera/ directory")
                        
                    # Remove visualization file if not enabled
                    if not Config.PACKAGE_INCLUDE_VISUALIZATION:
                        vis_file = temp_package_dir / "camera_pointcloud_alignment.png"
                        if vis_file.exists():
                            vis_file.unlink()
                            logger.info("Removed visualization file (not enabled in config)")
                        
                else:
                    logger.warning("NVS format generation failed, continuing without NVS files")
            else:
                logger.warning("transforms.json not found, skipping NVS format generation")
        else:
            logger.info("NVS files disabled in configuration, skipping generation")
        
        # Create scene-specific subdirectory and file naming
        scene_subdir = "outdoor" if scene_type.lower() == "outdoor" else "indoor"
        output_with_scene = Path(output_dir) / scene_subdir
        
        # Use file_id for naming without _processed suffix
        if file_id:
            base_name = file_id
            final_package_name = f"{file_id}.zip"
            logger.info(f"Using Google Drive file ID for package name: {file_id}")
        else:
            base_name = package_name
            final_package_name = f"{package_name}.zip"
            logger.info(f"Using package name for final package: {package_name}")
        
        final_package_path = output_with_scene / final_package_name
        logger.info(f"Final package will be saved to: {final_package_path}")
        logger.info(f"Scene type: {scene_type} -> subdirectory: {scene_subdir}")
        
        # Ensure output directory exists
        final_package_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create the final package with proper folder structure
        compression_start = datetime.now()
        compression_duration = _create_zip_with_folder_structure(
            temp_package_dir, final_package_path, base_name, "final package"
        )
        
        # Create archive package if enabled
        archive_path = None
        if Config.ENABLE_ARCHIVE_CREATION:
            logger.info("Creating archive package with all files (including unmasked images)...")
            archive_path = _create_archive_package(
                original_path, output_files, base_name, scene_type, processing_output_path
            )
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


def _create_zip_with_folder_structure(source_dir: Path, zip_path: Path, folder_name: str, package_type: str) -> float:
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
    all_files = [f for f in source_dir.rglob('*') if f.is_file()]
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
        
        # Generate COLMAP format files for archive
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
            
            nvs_success, split_info = generate_colmap_format(
                output_dir=str(temp_archive_dir),
                transforms_json_path=str(transforms_json_path),
                original_data_path=str(temp_archive_dir),
                colorized_las_path=colorized_las_path
            )
            
            if nvs_success:
                logger.info("✓ COLMAP format generation completed for archive")
            else:
                logger.warning("COLMAP format generation failed for archive")
        
        # Create archive zip file
        scene_subdir = "outdoor" if scene_type.lower() == "outdoor" else "indoor"
        archive_output_with_scene = Path(Config.ARCHIVE_OUTPUT_PATH) / scene_subdir
        archive_output_with_scene.mkdir(parents=True, exist_ok=True)
        
        archive_zip_name = f"{base_name}_archive.zip"
        archive_zip_path = archive_output_with_scene / archive_zip_name
        
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