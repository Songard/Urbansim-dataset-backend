# colmap_utils.py
"""
COLMAP format generation utilities for MetaCam processing pipeline.

This module provides functions to generate COLMAP-compatible formats from 
processed MetaCam data, including:
- cameras.txt: Camera intrinsic parameters
- images.txt: Image information with poses  
- images_val.txt: Validation set images
- Directory structure creation

Based on the reference implementation in metacam.py
"""

import os
import json
import shutil
import numpy as np
from scipy.spatial.transform import Rotation as R
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import random

from config import Config
from utils.logger import get_logger

logger = get_logger(__name__)

# Import tqdm with fallback
try:
    from tqdm import tqdm
except ImportError:
    # Simple fallback for progress display
    def tqdm(iterable, desc=None, **kwargs):
        if desc:
            logger.info(f"Processing {desc}...")
        return iterable

# Import visualization libraries
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    logger.warning("Matplotlib not available, visualization will be disabled")
    HAS_MATPLOTLIB = False

# Import point cloud processing libraries
try:
    import laspy
    import open3d as o3d
    HAS_POINTCLOUD_LIBS = True
except ImportError as e:
    logger.warning(f"Point cloud libraries not available: {e}")
    logger.warning("Points3D.txt generation will be disabled")
    HAS_POINTCLOUD_LIBS = False


def split_frames_by_origin(
    frames: List[Dict],
    global_trans: np.ndarray,
    global_rot: np.ndarray,
    dist_thresh: float = 0.30,
    min_run: int = 3,
) -> Tuple[List[Dict], List[Dict], Dict]:
    """
    Split camera frames into train/validation sets based on proximity to origin.
    
    This function identifies periods where the camera is near the origin (pause periods)
    and splits the trajectory accordingly for better train/validation separation.
    
    Args:
        frames: List of frame data with transform matrices
        global_trans: Global transformation matrix (4x4)
        global_rot: Global rotation matrix (3x3)  
        dist_thresh: Distance threshold to consider as "near origin" (meters)
        min_run: Minimum consecutive frames required for a valid pause period
        
    Returns:
        Tuple of (train_frames, validation_frames, split_info)
    """
    logger.info(f"Splitting {len(frames)} frames using distance threshold {dist_thresh}m")
    
    n_total = len(frames)
    n_half = n_total // 2
    camA = frames[:n_half]  # First half (camera A)
    camB = frames[n_half:]  # Second half (camera B)

    def cam_centers(frm_list):
        """Extract camera centers from frame list"""
        c = []
        for frm in frm_list:
            T = np.array(frm["transform_matrix"])
            T[:3, :3] = T[:3, :3] @ global_rot
            T = global_trans @ T
            cam_pose = np.linalg.inv(T)
            c.append(cam_pose[:3, 3])
        return np.vstack(c)

    # Calculate distances from origin for camera A trajectory
    radii_A = np.linalg.norm(cam_centers(camA), axis=1)
    radii_B = np.linalg.norm(cam_centers(camB), axis=1)

    # Find longest sequence of frames near origin
    best_len = best_end = 0
    cur_len = 0
    for i, r in enumerate(radii_A):
        if r < dist_thresh:
            cur_len += 1
            if cur_len > best_len:
                best_len, best_end = cur_len, i
        else:
            cur_len = 0

    # Multi-level threshold detection
    split_info = {
        "status": "FAILED",
        "train_count": 0,
        "val_count": 0,
        "split_quality": "FAILED",
        "distance_used": dist_thresh,
        "pause_frames": best_len
    }
    
    if best_len < min_run:
        # Try with warning threshold (1.0m)
        if dist_thresh < Config.COLMAP_SPLIT_DISTANCE_WARNING:
            logger.info(f"Trying with warning threshold: {Config.COLMAP_SPLIT_DISTANCE_WARNING}m")
            
            # Recalculate with warning threshold
            best_len_warn = best_end_warn = 0
            cur_len = 0
            for i, r in enumerate(radii_A):
                if r < Config.COLMAP_SPLIT_DISTANCE_WARNING:
                    cur_len += 1
                    if cur_len > best_len_warn:
                        best_len_warn, best_end_warn = cur_len, i
                else:
                    cur_len = 0
            
            if best_len_warn >= min_run:
                # Use warning threshold split
                split_start = best_end_warn - best_len_warn + 1
                split_end = best_end_warn
                split_start_B = min(split_start, len(radii_B))
                split_end_B = min(split_end, len(radii_B) - 1)
                
                train_frames = camA[:split_start] + camB[:split_start_B]
                val_frames = camA[split_end + 1:] + camB[split_end_B + 1:]
                
                # Check if either train or validation set is empty - mark as failed even with warning threshold
                if len(train_frames) == 0 or len(val_frames) == 0:
                    logger.error(f"WARNING threshold split FAILED: Empty set detected - train={len(train_frames)}, val={len(val_frames)}")
                    
                    # Fall through to failed section below
                else:
                    split_info.update({
                        "status": "WARNING", 
                        "split_quality": "WARNING",
                        "train_count": len(train_frames),
                        "val_count": len(val_frames),
                        "distance_used": Config.COLMAP_SPLIT_DISTANCE_WARNING,
                        "pause_frames": best_len_warn
                    })
                    
                    logger.warning(f"Split with WARNING quality: train={len(train_frames)}, val={len(val_frames)}, pause={best_len_warn}")
                    return train_frames, val_frames, split_info
        
        # Both thresholds failed - use fallback split
        logger.error(f"Split FAILED: No adequate near-origin segment detected (best: {best_len}, required: {min_run})")
        logger.error("Cannot perform reliable train/validation split")
        
        # Return fallback 80-20 split but mark as failed
        split_idx = int(0.8 * len(frames))
        train_frames = frames[:split_idx]
        val_frames = frames[split_idx:]
        
        split_info.update({
            "status": "FAILED",
            "split_quality": "FAILED", 
            "train_count": len(train_frames),
            "val_count": len(val_frames),
            "distance_used": dist_thresh,
            "pause_frames": best_len
        })
        
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
        
        split_info.update({
            "status": "FAILED",
            "split_quality": "FAILED", 
            "train_count": len(train_frames),
            "val_count": len(val_frames),
            "distance_used": dist_thresh,
            "pause_frames": best_len
        })
        
        return train_frames, val_frames, split_info

    # Determine split quality
    if dist_thresh <= Config.COLMAP_SPLIT_DISTANCE_GOOD:
        split_quality = "GOOD"
        status = "SUCCESS"
    else:
        split_quality = "WARNING" 
        status = "WARNING"
    
    split_info.update({
        "status": status,
        "split_quality": split_quality,
        "train_count": len(train_frames),
        "val_count": len(val_frames),
        "distance_used": dist_thresh,
        "pause_frames": best_len
    })

    logger.info(
        f"Frame split result ({split_quality}): train={len(train_frames)}, "
        f"val={len(val_frames)}, pause_len={best_len}"
    )

    return train_frames, val_frames, split_info


def write_images_txt(
    frames: List[Dict],
    src_dir: str,
    sparse_dir: str,
    images_dir: str,
    global_trans: np.ndarray,
    global_rot: np.ndarray,
    start_id: int = 0,
    out_name: str = "images.txt",
) -> bool:
    """
    Write COLMAP images.txt file and copy corresponding images.
    
    Args:
        frames: List of frame data with transforms and image paths
        src_dir: Source directory containing original images
        sparse_dir: Output sparse directory for images.txt
        images_dir: Output directory for copied images
        global_trans: Global transformation matrix
        global_rot: Global rotation matrix
        start_id: Starting image ID
        out_name: Output filename (images.txt or images_val.txt)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        images_txt = os.path.join(sparse_dir, out_name)
        logger.info(f"Writing {out_name} with {len(frames)} frames")
        
        with open(images_txt, "w") as f:
            for idx, frame in enumerate(tqdm(frames, desc=f"Processing {out_name}")):
                img_id = start_id + idx
                
                # Apply transformations
                trans = np.array(frame['transform_matrix'])
                trans[:3, :3] = trans[:3, :3] @ global_rot
                trans = global_trans @ trans
                cam_pose = np.linalg.inv(trans)

                # Extract pose with coordinate system alignment
                # Apply R_x(-90°) rotation to align coordinate systems
                Rx_m90 = np.array([[1, 0, 0],
                                   [0, 0, 1],
                                   [0,-1, 0]], dtype=float)  # R_x(-90°)
                
                R_wc_fixed = cam_pose[:3, :3] @ Rx_m90
                tvec = cam_pose[:3, 3]                      # Translation unchanged
                
                q = R.from_matrix(R_wc_fixed).as_quat()     # [x,y,z,w]
                qvec = [q[3], q[0], q[1], q[2]]             # Convert to COLMAP [w,x,y,z]

                # Process image path and copy file
                src_name = frame['file_path'].replace('\\', '/')
                dst_name = src_name.replace('/', '_')
                
                # Use correct camera path as per schema
                # src_name format is like "left/1757025812332602000.jpg" or "right/1757025977217852000.jpg"
                src_path = os.path.join(src_dir, 'camera', src_name)
                
                try:
                    shutil.copy(src_path, os.path.join(images_dir, dst_name))
                except FileNotFoundError:
                    logger.error(f"Image file not found: {src_path}")
                    return False
                except Exception as e:
                    logger.error(f"Failed to copy image {src_path}: {e}")
                    return False

                # Determine camera ID (1=left, 2=right)
                cam_id = 1 if 'left' in src_name else 2
                
                # Write COLMAP format: IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID IMAGE_NAME
                elems = [img_id] + qvec + tvec.tolist() + [cam_id, dst_name]
                f.write(" ".join(map(str, elems)) + "\n\n")
        
        logger.info(f"Successfully wrote {images_txt}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write {out_name}: {e}")
        return False


def write_cameras_txt(frames: List[Dict], sparse_dir: str) -> bool:
    """
    Write COLMAP cameras.txt file with fisheye camera parameters.
    
    Args:
        frames: List of frame data containing camera parameters
        sparse_dir: Output directory for cameras.txt
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cam_file = os.path.join(sparse_dir, 'cameras.txt')
        logger.info("Writing cameras.txt")
        
        # Find left and right camera parameters
        left_cam = right_cam = None
        for frm in frames:
            path = frm['file_path']
            if path.startswith('left') and left_cam is None:
                left_cam = frm
            elif path.startswith('right') and right_cam is None:
                right_cam = frm
            if left_cam and right_cam:
                break

        with open(cam_file, 'w') as f:
            # Write left camera (ID=1)
            if left_cam:
                f.write(
                    f"1 OPENCV_FISHEYE {left_cam['w']} {left_cam['h']} "
                    f"{left_cam['fl_x']} {left_cam['fl_y']} {left_cam['cx']} {left_cam['cy']} "
                    f"{left_cam['k1']} {left_cam['k2']} {left_cam['k3']} {left_cam['k4']}\n"
                )
                logger.info(f"Added left camera: {left_cam['w']}x{left_cam['h']}")
            
            # Write right camera (ID=2)  
            if right_cam:
                f.write(
                    f"2 OPENCV_FISHEYE {right_cam['w']} {right_cam['h']} "
                    f"{right_cam['fl_x']} {right_cam['fl_y']} {right_cam['cx']} {right_cam['cy']} "
                    f"{right_cam['k1']} {right_cam['k2']} {right_cam['k3']} {right_cam['k4']}\n"
                )
                logger.info(f"Added right camera: {right_cam['w']}x{right_cam['h']}")

        logger.info(f"Successfully wrote {cam_file}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write cameras.txt: {e}")
        return False


def setup_colmap_directories(output_dir: str) -> Dict[str, str]:
    """
    Create COLMAP directory structure.
    
    Creates:
    - sparse/0/ - COLMAP sparse reconstruction directory
    - images/ - Image directory
    
    Args:
        output_dir: Base output directory
        
    Returns:
        Dictionary with created directory paths
    """
    sparse_dir = os.path.join(output_dir, "sparse/0")
    images_dir = os.path.join(output_dir, "images")
    
    directories = {
        "sparse_dir": sparse_dir,
        "images_dir": images_dir,
    }
    
    for name, path in directories.items():
        os.makedirs(path, exist_ok=True)
        logger.info(f"Created {name}: {path}")
    
    return directories


def generate_colmap_format(
    output_dir: str,
    transforms_json_path: str,
    original_data_path: str,
    colorized_las_path: str = None
) -> Tuple[bool, Dict]:
    """
    Generate COLMAP format files from transforms.json and optional point cloud.
    
    Args:
        output_dir: Directory where COLMAP files will be created
        transforms_json_path: Path to transforms.json file
        original_data_path: Path to directory containing camera/ folder with images
        colorized_las_path: Optional path to colorized.las file for points3D.txt generation
        
    Returns:
        Tuple of (success: bool, split_info: dict)
    """
    try:
        logger.info("=== Starting COLMAP format generation ===")
        
        if not Config.ENABLE_COLMAP_GENERATION:
            logger.info("COLMAP generation disabled in config")
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
        dirs = setup_colmap_directories(output_dir)
        
        # Global transformations from config
        global_trans = np.array(Config.COLMAP_GLOBAL_TRANSFORM)
        global_rot = np.array(Config.COLMAP_GLOBAL_ROTATION)
        
        # Split frames into train/validation
        train_frames, val_frames, split_info = split_frames_by_origin(
            frames, global_trans, global_rot,
            dist_thresh=Config.COLMAP_SPLIT_DISTANCE_GOOD,
            min_run=Config.COLMAP_MIN_PAUSE_FRAMES
        )
        
        # Generate COLMAP files
        success = True
        
        # Write training images.txt
        if not write_images_txt(
            train_frames, original_data_path, dirs["sparse_dir"], dirs["images_dir"],
            global_trans, global_rot, start_id=0, out_name="images.txt"
        ):
            success = False
            
        # Write validation images_val.txt
        if not write_images_txt(
            val_frames, original_data_path, dirs["sparse_dir"], dirs["images_dir"],
            global_trans, global_rot, start_id=len(train_frames), out_name="images_val.txt"
        ):
            success = False
            
        # Write cameras.txt
        if not write_cameras_txt(frames, dirs["sparse_dir"]):
            success = False
        
        # Generate points3D.txt from colorized.las if available
        pcd = None
        if colorized_las_path and os.path.exists(colorized_las_path) and HAS_POINTCLOUD_LIBS:
            logger.info("=== Starting point cloud processing ===")
            
            # Load and process point cloud
            pcd = load_pointcloud_from_las(colorized_las_path)
            if pcd is not None:
                # Downsample point cloud
                pcd = downsample_pointcloud(pcd)
                
                # Write points3D.txt
                points3d_path = os.path.join(dirs["sparse_dir"], "points3D.txt")
                if write_colmap_points3d_txt(pcd, points3d_path):
                    logger.info("✓ Generated points3D.txt")
                else:
                    logger.warning("Failed to generate points3D.txt")
                    success = False
            else:
                logger.warning("Failed to load point cloud from LAS file")
        elif colorized_las_path:
            if not os.path.exists(colorized_las_path):
                logger.warning(f"Point cloud file not found: {colorized_las_path}")
            elif not HAS_POINTCLOUD_LIBS:
                logger.warning("Point cloud libraries not available, skipping points3D.txt generation")
        
        # Generate visualization if we have both point cloud and camera poses
        if pcd is not None and success:
            logger.info("=== Creating alignment visualization ===")
            
            # Load camera centers
            images_train_path = os.path.join(dirs["sparse_dir"], "images.txt")
            images_val_path = os.path.join(dirs["sparse_dir"], "images_val.txt")
            
            cams_train = load_camera_centers(images_train_path, 800)
            cams_val = load_camera_centers(images_val_path, 800)
            
            # Sample points for visualization
            vis_points = sample_points_for_visualization(
                pcd, Config.COLMAP_VISUALIZATION_SAMPLE_POINTS
            )
            
            # Create visualization
            vis_path = os.path.join(output_dir, "camera_pointcloud_alignment.png")
            if plot_three_views(vis_points, cams_train, cams_val, vis_path):
                logger.info("✓ Created alignment visualization")
            else:
                logger.warning("Failed to create alignment visualization")
            
        if success:
            logger.info("=== COLMAP format generation completed successfully ===")
            logger.info(f"Files created in: {dirs['sparse_dir']}")
            logger.info("- cameras.txt")
            logger.info("- images.txt") 
            logger.info("- images_val.txt")
            if pcd is not None:
                logger.info("- points3D.txt")
            logger.info(f"Images copied to: {dirs['images_dir']}")
            if pcd is not None:
                logger.info(f"Visualization saved: camera_pointcloud_alignment.png")
        else:
            logger.error("COLMAP format generation failed")
            
        return success, split_info
        
    except Exception as e:
        logger.error(f"COLMAP format generation error: {e}")
        return False, {"status": "ERROR", "split_quality": "FAILED", "train_count": 0, "val_count": 0}


def load_pointcloud_from_las(las_path: str):
    """
    Load point cloud from colorized.las file with coordinate transformation.
    
    Args:
        las_path: Path to colorized.las file
        
    Returns:
        Open3D point cloud object or None if failed
    """
    if not HAS_POINTCLOUD_LIBS:
        logger.error("Point cloud libraries not available")
        return None
        
    try:
        logger.info(f"Loading point cloud from: {las_path}")
        
        # Read LAS file
        las = laspy.read(las_path)
        
        # Extract coordinates and colors
        pts = np.vstack([las.x, las.y, las.z]).T
        
        # Color data in LAS is typically 16-bit, convert to 0-1 range
        if hasattr(las, 'red') and hasattr(las, 'green') and hasattr(las, 'blue'):
            red = (las.red / 65535.0).astype(np.float32)
            green = (las.green / 65535.0).astype(np.float32) 
            blue = (las.blue / 65535.0).astype(np.float32)
            cols = np.vstack([red, green, blue]).T
        else:
            logger.warning("No color information found in LAS file, using white")
            cols = np.ones((len(pts), 3), dtype=np.float32)
        
        logger.info(f"Loaded {len(pts)} points from LAS file")
        
        # Apply coordinate transformation to match camera pose transformation R_x(-90°)
        # R_x(-90°) transforms [x,y,z] -> [x,z,-y]
        pts_transformed = np.stack([pts[:, 1], -1 * pts[:, 2], -1 * pts[:, 0]], axis=1)

        # Create Open3D point cloud
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pts_transformed)
        pcd.colors = o3d.utility.Vector3dVector(cols)
        
        logger.info("Point cloud coordinate transformation applied: [x, z, -y] to match camera R_x(-90°)")
        
        return pcd
        
    except Exception as e:
        logger.error(f"Failed to load point cloud from LAS: {e}")
        return None


def downsample_pointcloud(pcd):
    """
    Downsample point cloud using configured method.
    
    Args:
        pcd: Input point cloud
        
    Returns:
        Downsampled point cloud
    """
    if not HAS_POINTCLOUD_LIBS:
        return pcd
        
    try:
        method = Config.COLMAP_POINTCLOUD_DOWNSAMPLE_METHOD
        original_count = len(pcd.points)
        
        if method == 'voxel':
            voxel_size = Config.COLMAP_POINTCLOUD_VOXEL_SIZE
            pcd_ds = pcd.voxel_down_sample(voxel_size)
            logger.info(f"Voxel downsampling: {original_count} -> {len(pcd_ds.points)} points (voxel_size={voxel_size})")
        elif method == 'uniform':
            every_k = Config.COLMAP_POINTCLOUD_EVERY_K_POINTS
            pcd_ds = pcd.uniform_down_sample(every_k)
            logger.info(f"Uniform downsampling: {original_count} -> {len(pcd_ds.points)} points (every_k={every_k})")
        else:
            logger.warning(f"Unknown downsample method: {method}, using original point cloud")
            pcd_ds = pcd
            
        return pcd_ds
        
    except Exception as e:
        logger.error(f"Point cloud downsampling failed: {e}")
        return pcd


def write_colmap_points3d_txt(pcd, output_path: str) -> bool:
    """
    Write point cloud to COLMAP points3D.txt format.
    
    COLMAP format:
    POINT3D_ID X Y Z R G B ERROR TRACK[] as (IMAGE_ID, POINT2D_IDX)
    
    Args:
        pcd: Open3D point cloud
        output_path: Output path for points3D.txt
        
    Returns:
        True if successful, False otherwise
    """
    if not HAS_POINTCLOUD_LIBS:
        return False
        
    try:
        logger.info(f"Writing COLMAP points3D.txt with {len(pcd.points)} points")
        
        points = np.asarray(pcd.points)
        colors = np.asarray(pcd.colors)
        
        # Convert colors from 0-1 to 0-255 range
        colors_255 = (colors * 255).astype(np.uint8)
        
        with open(output_path, 'w') as f:
            # Write header comment
            f.write("# 3D point list with one line of data per point:\n")
            f.write("# POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[] as (IMAGE_ID, POINT2D_IDX)\n")
            
            for i, (pt, col) in enumerate(zip(points, colors_255)):
                point_id = i + 1  # COLMAP uses 1-based indexing
                x, y, z = pt
                r, g, b = col
                error = 1.0  # Default reprojection error
                
                # No track information available from point cloud alone
                # Write minimal COLMAP format
                f.write(f"{point_id} {x:.6f} {y:.6f} {z:.6f} {r} {g} {b} {error:.6f}\n")
        
        logger.info(f"Successfully wrote {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write points3D.txt: {e}")
        return False


def load_camera_centers(images_txt_path: str, num_samples: int = 500) -> np.ndarray:
    """
    Load camera centers from COLMAP images.txt file.
    
    Args:
        images_txt_path: Path to images.txt file
        num_samples: Maximum number of cameras to sample
        
    Returns:
        Array of camera centers (N x 3)
    """
    try:
        if not os.path.exists(images_txt_path):
            logger.warning(f"Images file not found: {images_txt_path}")
            return np.empty((0, 3))
            
        centers = []
        lines = []
        
        with open(images_txt_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    lines.append(line)
        
        # Sample lines if too many
        if len(lines) > num_samples:
            lines = random.sample(lines, num_samples)
        
        for line in lines:
            parts = line.split()
            if len(parts) < 10:
                continue
                
            # Parse quaternion and translation
            qw, qx, qy, qz = map(float, parts[1:5])
            tx, ty, tz = map(float, parts[5:8])
            
            # Convert to camera center
            R_wc = R.from_quat([qx, qy, qz, qw]).as_matrix()
            t_wc = np.array([tx, ty, tz])
            C = -R_wc.T @ t_wc
            centers.append(C)
        
        if centers:
            return np.asarray(centers, dtype=float)
        else:
            logger.warning(f"No valid camera poses found in {images_txt_path}")
            return np.empty((0, 3))
        
    except Exception as e:
        logger.error(f"Failed to load camera centers: {e}")
        return np.empty((0, 3))


def sample_points_for_visualization(pcd, num_pts: int = 4000) -> np.ndarray:
    """
    Sample points from point cloud for visualization.
    
    Args:
        pcd: Input point cloud
        num_pts: Number of points to sample
        
    Returns:
        Sampled points array (N x 3)
    """
    if not HAS_POINTCLOUD_LIBS:
        return np.empty((0, 3))
        
    try:
        points = np.asarray(pcd.points)
        if len(points) <= num_pts:
            return points
        
        # Random sampling
        indices = np.random.choice(len(points), num_pts, replace=False)
        return points[indices]
        
    except Exception as e:
        logger.error(f"Point sampling failed: {e}")
        return np.empty((0, 3))


def plot_three_views(points: np.ndarray, cams_train: np.ndarray, cams_val: np.ndarray, save_path: str) -> bool:
    """
    Create three-view visualization plot (Front X-Z, Side Y-Z, Top X-Y).
    
    Args:
        points: Point cloud coordinates (N x 3)
        cams_train: Training camera centers (M x 3)  
        cams_val: Validation camera centers (K x 3)
        save_path: Output path for visualization
        
    Returns:
        True if successful, False otherwise
    """
    if not HAS_MATPLOTLIB:
        logger.warning("Matplotlib not available, skipping visualization")
        return False
        
    try:
        logger.info("Creating three-view visualization...")
        
        plt.figure(figsize=(15, 5))

        def _subplot(idx, x, y, title):
            ax = plt.subplot(1, 3, idx)
            if len(points) > 0:
                ax.scatter(points[:, x], points[:, y], s=3, c='tab:red', alpha=0.6, label='Points')
            if len(cams_train) > 0:
                ax.scatter(cams_train[:, x], cams_train[:, y], s=6, c='tab:green', label='Cams (train)')
            if len(cams_val) > 0:
                ax.scatter(cams_val[:, x], cams_val[:, y], s=6, c='tab:blue', label='Cams (val)')
            ax.set_xlabel(['X','Y','Z'][x])
            ax.set_ylabel(['X','Y','Z'][y])
            ax.set_title(title)
            ax.axis('equal')
            ax.grid(True, alpha=0.3)
            ax.legend()

        _subplot(1, 0, 2, 'Front  (X–Z)')
        _subplot(2, 1, 2, 'Side   (Y–Z)')
        _subplot(3, 0, 1, 'Top    (X–Y)')

        # Create output directory if needed
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=160, bbox_inches='tight')
        plt.close()
        
        logger.info(f'Visualization saved: {save_path}')
        return True
        
    except Exception as e:
        logger.error(f"Visualization creation failed: {e}")
        return False