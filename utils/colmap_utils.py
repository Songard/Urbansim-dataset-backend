# nvs_utils.py
"""
NVS (Novel View Synthesis) format generation utilities for MetaCam processing pipeline.

This module provides functions to generate NVS train/val split files from 
processed MetaCam data, including:
- train.txt: Training image names
- val.txt: Validation image names  
- Directory structure creation
- Image copying and organization

Based on the reference implementation in metacam.py
"""

import os
import json
import shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import List, Dict, Tuple
from pathlib import Path

from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

# Import tqdm with fallback
try:
    from tqdm import tqdm
except ImportError:
    # Simple fallback for progress display
    def tqdm(iterable, desc=None, **kwargs):
        return iterable


def split_frames_by_origin(
    frames: List[Dict],
    global_trans: np.ndarray,
    global_rot: np.ndarray,
    dist_thresh: float = 0.30,
    min_run: int = 3,
) -> Tuple[List[Dict], List[Dict], Dict]:
    """
    Split frames into train/validation sets based on camera movement patterns.
    
    This function analyzes camera trajectories to find natural pause points
    where the camera remains relatively stationary, then uses these points
    to create meaningful train/validation splits.
    
    Args:
        frames: List of frame dictionaries with transform matrices
        global_trans: Global transformation matrix
        global_rot: Global rotation matrix  
        dist_thresh: Distance threshold for detecting pauses (meters)
        min_run: Minimum number of consecutive frames for a valid pause
        
    Returns:
        Tuple of (train_frames, val_frames, split_info)
    """
    if len(frames) < 6:
        logger.warning(f"Too few frames ({len(frames)}) for intelligent splitting, using simple 80-20 split")
        split_idx = max(1, int(0.8 * len(frames)))
        train_frames = frames[:split_idx]
        val_frames = frames[split_idx:]
        
        split_info = {
            "status": "FALLBACK",
            "split_quality": "SIMPLE", 
            "train_count": len(train_frames),
            "val_count": len(val_frames),
            "distance_used": 0,
            "pause_frames": 0
        }
        
        return train_frames, val_frames, split_info

    # Separate frames by camera (left/right)
    camA, camB = [], []
    for frame in frames:
        file_path = frame['file_path']
        if 'left' in file_path.lower():
            camA.append(frame)
        else:
            camB.append(frame)
    
    # Extract camera positions for both cameras
    def extract_positions(cam_frames):
        positions = []
        for frame in cam_frames:
            trans = np.array(frame['transform_matrix'])
            trans[:3, :3] = trans[:3, :3] @ global_rot
            trans = global_trans @ trans
            cam_pose = np.linalg.inv(trans)
            positions.append(cam_pose[:3, 3])
        return np.array(positions)
    
    posA = extract_positions(camA) if camA else np.array([])
    posB = extract_positions(camB) if camB else np.array([])
    
    # Calculate movement distances
    def calc_radii(positions):
        if len(positions) < 2:
            return []
        diffs = np.diff(positions, axis=0)
        distances = np.linalg.norm(diffs, axis=1)
        return distances
    
    radii_A = calc_radii(posA)
    radii_B = calc_radii(posB)
    
    # Find best pause region
    def find_best_pause(radii, min_run, dist_thresh):
        best_len, best_end = 0, -1
        current_len, current_end = 0, -1
        
        for i, r in enumerate(radii):
            if r <= dist_thresh:
                if current_len == 0:
                    current_end = i
                current_len += 1
            else:
                if current_len >= min_run and current_len > best_len:
                    best_len, best_end = current_len, current_end
                current_len = 0
        
        # Check final run
        if current_len >= min_run and current_len > best_len:
            best_len, best_end = current_len, current_end
            
        return best_len, best_end
    
    # Try to find pauses with increasing distance thresholds
    best_len = 0
    best_end = -1
    current_thresh = dist_thresh
    
    while best_len < min_run and current_thresh <= 2.0:
        if len(radii_A) > 0:
            len_A, end_A = find_best_pause(radii_A, min_run, current_thresh)
            if len_A > best_len:
                best_len, best_end = len_A, end_A
        
        if len(radii_B) > 0:
            len_B, end_B = find_best_pause(radii_B, min_run, current_thresh)
            if len_B > best_len:
                best_len, best_end = len_B, end_B
        
        if best_len >= min_run:
            break
            
        current_thresh += 0.10
    
    # If no good pause found, fall back to simple split
    if best_len < min_run:
        logger.warning(f"No suitable pause region found, using 80-20 split")
        
        split_idx = int(0.8 * len(frames))
        train_frames = frames[:split_idx]
        val_frames = frames[split_idx:]
        
        split_info = {
            "status": "FAILED",
            "split_quality": "FAILED", 
            "train_count": len(train_frames),
            "val_count": len(val_frames),
            "distance_used": current_thresh,
            "pause_frames": best_len
        }
        
        return train_frames, val_frames, split_info

    # Calculate split points
    split_start = best_end - best_len + 1
    split_end = best_end

    split_start_B = min(split_start, len(radii_B))
    split_end_B = min(split_end, len(radii_B) - 1)

    # Create train/validation splits
    train_frames = camA[:split_start] + camB[:split_start_B]
    val_frames = camA[split_end + 1:] + camB[split_end_B + 1:]

    # Check if either train or validation set is empty - mark as failed
    if len(train_frames) == 0 or len(val_frames) == 0:
        logger.error(f"Split FAILED: Empty set detected - train={len(train_frames)}, val={len(val_frames)}")
        
        # Return fallback 80-20 split but mark as failed
        split_idx = int(0.8 * len(frames))
        train_frames = frames[:split_idx]
        val_frames = frames[split_idx:]
        
        split_info = {
            "status": "FAILED",
            "split_quality": "FAILED", 
            "train_count": len(train_frames),
            "val_count": len(val_frames),
            "distance_used": current_thresh,
            "pause_frames": best_len
        }
        
        return train_frames, val_frames, split_info

    # Determine split quality
    if current_thresh <= Config.COLMAP_SPLIT_DISTANCE_GOOD:
        split_quality = "GOOD"
        status = "SUCCESS"
    else:
        split_quality = "WARNING" 
        status = "WARNING"
    
    split_info = {
        "status": status,
        "split_quality": split_quality,
        "train_count": len(train_frames),
        "val_count": len(val_frames),
        "distance_used": current_thresh,
        "pause_frames": best_len
    }

    logger.info(
        f"Frame split result ({split_quality}): train={len(train_frames)}, val={len(val_frames)}, "
        f"pause_frames={best_len}, distance_thresh={current_thresh:.2f}m"
    )
    
    return train_frames, val_frames, split_info


def setup_nvs_directories(output_dir: str) -> Dict[str, str]:
    """
    Create NVS (Novel View Synthesis) directory structure.
    
    Creates:
    - nvs_split/ - Directory for train/val split files
    - images/ - Image directory
    
    Args:
        output_dir: Base output directory
        
    Returns:
        Dictionary with created directory paths
    """
    nvs_split_dir = os.path.join(output_dir, "nvs_split")
    images_dir = os.path.join(output_dir, "images")
    
    directories = {
        "nvs_split_dir": nvs_split_dir,
        "images_dir": images_dir,
    }
    
    for name, path in directories.items():
        os.makedirs(path, exist_ok=True)
        logger.info(f"Created {name}: {path}")
    
    return directories


def write_nvs_split_files(
    train_frames: List[Dict],
    val_frames: List[Dict],
    src_dir: str,
    nvs_split_dir: str,
    images_dir: str
) -> bool:
    """
    Write NVS split files (train.txt and val.txt) with image names and copy images.
    
    Args:
        train_frames: List of training frame data
        val_frames: List of validation frame data
        src_dir: Source directory containing original images
        nvs_split_dir: Output directory for split files
        images_dir: Output directory for copied images
        
    Returns:
        True if successful, False otherwise
    """
    try:
        train_file = os.path.join(nvs_split_dir, "train.txt")
        val_file = os.path.join(nvs_split_dir, "val.txt")
        
        logger.info(f"Writing NVS split files: train.txt ({len(train_frames)} images), val.txt ({len(val_frames)} images)")
        
        # Process training frames
        train_image_names = []
        for frame in tqdm(train_frames, desc="Processing training images"):
            # Process image path and copy file
            src_name = frame['file_path'].replace('\\', '/')
            dst_name = src_name.replace('/', '_')
            
            # Use correct camera path as per schema
            src_path = os.path.join(src_dir, 'camera', src_name)
            dst_path = os.path.join(images_dir, dst_name)
            
            try:
                shutil.copy(src_path, dst_path)
                train_image_names.append(dst_name)
            except FileNotFoundError:
                logger.error(f"Training image file not found: {src_path}")
                return False
            except Exception as e:
                logger.error(f"Failed to copy training image {src_path}: {e}")
                return False
        
        # Process validation frames
        val_image_names = []
        for frame in tqdm(val_frames, desc="Processing validation images"):
            # Process image path and copy file
            src_name = frame['file_path'].replace('\\', '/')
            dst_name = src_name.replace('/', '_')
            
            # Use correct camera path as per schema
            src_path = os.path.join(src_dir, 'camera', src_name)
            dst_path = os.path.join(images_dir, dst_name)
            
            try:
                shutil.copy(src_path, dst_path)
                val_image_names.append(dst_name)
            except FileNotFoundError:
                logger.error(f"Validation image file not found: {src_path}")
                return False
            except Exception as e:
                logger.error(f"Failed to copy validation image {src_path}: {e}")
                return False
        
        # Write train.txt
        with open(train_file, 'w') as f:
            for image_name in train_image_names:
                f.write(f"{image_name}\n")
        
        # Write val.txt
        with open(val_file, 'w') as f:
            for image_name in val_image_names:
                f.write(f"{image_name}\n")
        
        logger.info(f"Successfully wrote {train_file} with {len(train_image_names)} images")
        logger.info(f"Successfully wrote {val_file} with {len(val_image_names)} images")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write NVS split files: {e}")
        return False


def generate_nvs_format(
    output_dir: str,
    transforms_json_path: str,
    original_data_path: str,
    colorized_las_path: str = None
) -> Tuple[bool, Dict]:
    """
    Generate NVS format files from transforms.json with train/val split.
    
    Args:
        output_dir: Directory where NVS files will be created
        transforms_json_path: Path to transforms.json file
        original_data_path: Path to directory containing camera/ folder with images
        colorized_las_path: Optional path to colorized.las file (unused in NVS format)
        
    Returns:
        Tuple of (success: bool, split_info: dict)
    """
    try:
        logger.info("=== Starting NVS format generation ===")
        
        if not Config.ENABLE_COLMAP_GENERATION:
            logger.info("NVS generation disabled in config")
            return True, {"status": "DISABLED", "split_quality": "N/A", "train_count": 0, "val_count": 0}
        
        # Load transforms.json
        if not os.path.exists(transforms_json_path):
            logger.error(f"transforms.json not found: {transforms_json_path}")
            return False, {"status": "ERROR", "split_quality": "FAILED", "train_count": 0, "val_count": 0}
            
        with open(transforms_json_path, 'r') as f:
            data = json.load(f)
            
        frames = data.get('frames', [])
        if not frames:
            logger.error("No frames found in transforms.json")
            return False, {"status": "ERROR", "split_quality": "FAILED", "train_count": 0, "val_count": 0}
            
        logger.info(f"Loaded {len(frames)} frames from transforms.json")
        
        # Setup directories
        dirs = setup_nvs_directories(output_dir)
        
        # Global transformations from config
        global_trans = np.array(Config.COLMAP_GLOBAL_TRANSFORM)
        global_rot = np.array(Config.COLMAP_GLOBAL_ROTATION)
        
        # Split frames into train/validation
        train_frames, val_frames, split_info = split_frames_by_origin(
            frames, global_trans, global_rot,
            dist_thresh=Config.COLMAP_SPLIT_DISTANCE_GOOD,
            min_run=Config.COLMAP_MIN_PAUSE_FRAMES
        )
        
        # Generate NVS split files
        success = write_nvs_split_files(
            train_frames, val_frames, original_data_path, 
            dirs["nvs_split_dir"], dirs["images_dir"]
        )
        
        if success:
            logger.info("=== NVS format generation completed successfully ===")
            logger.info(f"Split files created in: {dirs['nvs_split_dir']}")
            logger.info(f"- train.txt ({len(train_frames)} images)")
            logger.info(f"- val.txt ({len(val_frames)} images)")
            logger.info(f"Images copied to: {dirs['images_dir']}")
        else:
            logger.error("NVS format generation failed")
            
        return success, split_info
        
    except Exception as e:
        logger.error(f"NVS format generation error: {e}")
        return False, {"status": "ERROR", "split_quality": "FAILED", "train_count": 0, "val_count": 0}


# Legacy function alias for backward compatibility
def generate_colmap_format(
    output_dir: str,
    transforms_json_path: str,
    original_data_path: str,
    colorized_las_path: str = None
) -> Tuple[bool, Dict]:
    """
    Legacy function - use generate_nvs_format() instead.
    Generates NVS format files for backward compatibility.
    """
    logger.warning("generate_colmap_format() is deprecated, use generate_nvs_format() instead")
    return generate_nvs_format(output_dir, transforms_json_path, original_data_path, colorized_las_path)