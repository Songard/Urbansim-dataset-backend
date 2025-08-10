#!/usr/bin/env python3
"""
Diagnostic script to analyze extracted archive structure
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from processors.archive_handler import ArchiveHandler
from validation.metacam import MetaCamValidator

def analyze_archive_structure(archive_path):
    """Analyze what's inside an extracted archive"""
    
    print(f"Analyzing archive: {archive_path}")
    print("=" * 60)
    
    if not os.path.exists(archive_path):
        print(f"Archive not found: {archive_path}")
        return
    
    # Extract archive to temp directory
    archive_handler = ArchiveHandler()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Extracting to: {temp_dir}")
        
        if archive_handler.extract_archive(archive_path, temp_dir):
            print("Extraction successful")
            
            # Analyze directory structure
            print("\nDirectory structure:")
            for root, dirs, files in os.walk(temp_dir):
                level = root.replace(temp_dir, '').count(os.sep)
                indent = ' ' * 2 * level
                print(f"{indent}{os.path.basename(root)}/")
                sub_indent = ' ' * 2 * (level + 1)
                for file in files[:10]:  # Limit to first 10 files per directory
                    print(f"{sub_indent}{file}")
                if len(files) > 10:
                    print(f"{sub_indent}... and {len(files) - 10} more files")
            
            # Test MetaCam detection
            print("\nTesting MetaCam detection:")
            validator = MetaCamValidator()
            
            # Test direct path
            print(f"Testing direct path: {temp_dir}")
            is_metacam_root = validator._is_metacam_root(temp_dir)
            print(f"Is MetaCam root: {is_metacam_root}")
            
            # Test _find_actual_root
            print(f"\nTesting _find_actual_root:")
            actual_root = validator._find_actual_root(temp_dir)
            print(f"Found root: {actual_root}")
            
            # Check subdirectories
            try:
                subdirs = [d for d in os.listdir(temp_dir) if os.path.isdir(os.path.join(temp_dir, d))]
                print(f"\nSubdirectories: {subdirs}")
                
                for subdir in subdirs[:3]:  # Check first 3 subdirectories
                    subdir_path = os.path.join(temp_dir, subdir)
                    print(f"Testing {subdir}: {validator._is_metacam_root(subdir_path)}")
                    
            except Exception as e:
                print(f"Error checking subdirectories: {e}")
                
        else:
            print("Extraction failed")

if __name__ == "__main__":
    # Check processed directory first
    processed_dir = "processed"
    if os.path.exists(processed_dir):
        files = [f for f in os.listdir(processed_dir) if f.endswith('.zip')]
        if files:
            # Analyze the center0710.zip that had validation score
            target_file = "center0710.zip"  # This one had validation score 0.0/100
            if target_file in files:
                file_path = os.path.join(processed_dir, target_file)
                print(f"Analyzing failed file: {file_path}")
                analyze_archive_structure(file_path)
            else:
                # Analyze the most recent file
                latest_file = max([os.path.join(processed_dir, f) for f in files], key=os.path.getctime)
                print(f"Analyzing latest file: {latest_file}")
                analyze_archive_structure(latest_file)
        else:
            print("No zip files found in processed directory")
    else:
        # Check for recent downloads
        downloads_dir = "downloads"
        if os.path.exists(downloads_dir):
            files = [f for f in os.listdir(downloads_dir) if f.endswith('.zip')]
            if files:
                # Analyze the most recent file
                latest_file = max([os.path.join(downloads_dir, f) for f in files], key=os.path.getctime)
                print(f"Analyzing latest file: {latest_file}")
                analyze_archive_structure(latest_file)
            else:
                print("No zip files found in downloads directory")
        else:
            print("No directories found")