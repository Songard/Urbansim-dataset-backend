#!/usr/bin/env python3
"""
A simple utility script to load and visualize a Point Cloud Data (PCD) file.

This script uses the open3d library to open a window and display the point cloud.
It works for both ASCII and binary PCD files.

Usage:
python visualize_pcd.py --file "/path/to/your/file.pcd"

If no file is provided, it will use the default path specified in the script.
"""

import open3d as o3d
import os
import argparse

def visualize_pcd(pcd_path: str):
    """
    Loads and visualizes a PCD file in an interactive window.
    """
    # 1. Check if the file exists
    if not os.path.exists(pcd_path):
        print(f"Error: File not found at '{pcd_path}'")
        return

    print(f"Loading point cloud from: {pcd_path}")
    try:
        # 2. Read the point cloud file. open3d automatically handles the binary format.
        pcd = o3d.io.read_point_cloud(pcd_path)
    except Exception as e:
        print(f"Error loading PCD file: {e}")
        return

    # 3. Check if the point cloud is empty
    if not pcd.has_points():
        print("Error: The point cloud is empty or could not be loaded correctly.")
        return

    print(f"Successfully loaded point cloud with {len(pcd.points):,} points.")
    print("--> Opening visualization window. Press 'Q' in the window to close.")
    # 4. Visualize the point cloud
    o3d.visualization.draw_geometries([pcd], window_name="PCD Visualization")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize a PCD file.")
    parser.add_argument('--file', type=str, 
                        default=r"F:\2025-08-20_15-23-34\Preview.pcd",
                        help="Path to the PCD file to visualize.")
    args = parser.parse_args()
    
    visualize_pcd(args.file)
