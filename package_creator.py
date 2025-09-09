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
        
        # Copy processing output files
        logger.info("Copying processing output files...")
        
        # Copy point cloud file keeping original filename
        original_pc_file = Path(output_files['colorized_las'])
        final_pc_name = original_pc_file.name  # Keep original filename exactly
        
        shutil.copy2(output_files['colorized_las'], temp_package_dir / final_pc_name)
        logger.info(f"Copied point cloud file: {final_pc_name}")
        
        shutil.copy2(output_files['transforms_json'], temp_package_dir / "transforms.json")
        
        # Copy required files from original package (递归搜索解压目录)
        original_path = Path(original_path)
        logger.info(f"Recursively searching for original files in: {original_path}")
        
        # Copy metadata.yaml (递归搜索)
        metadata_files = list(original_path.rglob("metadata.yaml"))
        if metadata_files:
            metadata_file = metadata_files[0]  # 使用找到的第一个
            logger.info(f"Found metadata.yaml at: {metadata_file}")
            shutil.copy2(metadata_file, temp_package_dir / "metadata.yaml")
            logger.info("✓ Copied metadata.yaml")
        else:
            logger.warning(f"metadata.yaml not found in: {original_path} (searched recursively)")
        
        # Copy Preview.jpg (递归搜索)
        preview_files = list(original_path.rglob("Preview.jpg"))
        if preview_files:
            preview_file = preview_files[0]  # 使用找到的第一个
            logger.info(f"Found Preview.jpg at: {preview_file}")
            shutil.copy2(preview_file, temp_package_dir / "Preview.jpg")
            logger.info("✓ Copied Preview.jpg")
        else:
            logger.warning(f"Preview.jpg not found in: {original_path} (searched recursively)")
        
        # Copy camera directory (递归搜索)
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
        
        # Generate COLMAP format files if enabled
        transforms_json_path = temp_package_dir / "transforms.json"
        if transforms_json_path.exists():
            logger.info("Generating COLMAP format files (sparse/0/, images/)...")
            
            # Find colorized.las file in the package
            colorized_las_files = list(temp_package_dir.glob("colorized*.las"))
            colorized_las_path = None
            if colorized_las_files:
                colorized_las_path = str(colorized_las_files[0])
                logger.info(f"Found point cloud file: {Path(colorized_las_path).name}")
            else:
                logger.info("No colorized.las file found, will generate COLMAP files without points3D.txt")
            
            colmap_success, split_info = generate_colmap_format(
                output_dir=str(temp_package_dir),
                transforms_json_path=str(transforms_json_path),
                original_data_path=str(temp_package_dir),  # Use temp_package_dir where camera/ is already copied
                colorized_las_path=colorized_las_path
            )
            if colmap_success:
                logger.info("✓ COLMAP format generation completed")
                logger.info(f"Train/Val split: {split_info['train_count']}/{split_info['val_count']} ({split_info['split_quality']})")
            else:
                logger.warning("COLMAP format generation failed, continuing without COLMAP files")
        else:
            logger.warning("transforms.json not found, skipping COLMAP format generation")
        
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
    Verify the final package contains all required files
    
    Args:
        package_path: Path to the created package
        
    Returns:
        bool: True if verification passes
    """
    try:
        logger.info(f"Verifying package contents: {package_path}")
        
        # Schema-compliant required files with flexible point cloud naming
        base_required_files = [
            'transforms.json',    # Transform matrices
            'metadata.yaml'       # Original metadata
        ]
        
        with zipfile.ZipFile(package_path, 'r') as zipf:
            file_list = zipf.namelist()
            
            # Check base required files
            missing_files = []
            for required_file in base_required_files:
                if required_file not in file_list:
                    missing_files.append(required_file)
            
            # Check for any point cloud file with supported extensions
            point_cloud_found = False
            found_point_cloud_file = None
            
            for file_name in file_list:
                file_ext = Path(file_name).suffix.lower()
                if file_ext in Config.SUPPORTED_POINT_CLOUD_EXTENSIONS:
                    point_cloud_found = True
                    found_point_cloud_file = file_name
                    logger.info(f"Found point cloud file: {file_name}")
                    break
            
            if not point_cloud_found:
                missing_files.append(f"point cloud file (with supported extensions: {', '.join(Config.SUPPORTED_POINT_CLOUD_EXTENSIONS)})")
            
            # Check camera directory exists
            has_camera_files = any(filename.startswith('camera/') for filename in file_list)
            if not has_camera_files:
                logger.warning("No camera/ directory found in package")
            
            if missing_files:
                logger.error(f"Package verification failed - missing files: {', '.join(missing_files)}")
                return False
            
            logger.info(f"✅ Package verification passed - found {len(file_list)} files total")
            if has_camera_files:
                camera_file_count = sum(1 for f in file_list if f.startswith('camera/'))
                logger.info(f"   Including {camera_file_count} camera files")
            
            return True
            
    except Exception as e:
        logger.error(f"Package verification failed with exception: {e}")
        return False