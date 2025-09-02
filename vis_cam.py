import cv2
import os
import numpy as np
from pathlib import Path

# Define the base path and subfolders
base_path = r"C:\Users\15436\Documents\MyPrograms\Urbansim\processed\i_370jay2F\i_370jay2F\camera"
left_path = os.path.join(base_path, "left")
right_path = os.path.join(base_path, "right")
output_filename = 'output_stereo.mp4'

# Get sorted lists of image files from both folders
left_image_files = sorted([f for f in os.listdir(left_path) if f.endswith(('.jpg', '.png'))])
right_image_files = sorted([f for f in os.listdir(right_path) if f.endswith(('.jpg', '.png'))])

# Determine the number of frames to process (minimum of both lists)
num_frames = min(len(left_image_files), len(right_image_files))

if num_frames == 0:
    print("No matching image pairs found in the specified directories.")
    exit()

# Get first image to determine dimensions
first_left = cv2.imread(os.path.join(left_path, left_image_files[0]))
height, width = first_left.shape[:2]

# Create video writer
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(output_filename, fourcc, 5.0, (width*2, height))

# Text properties
font = cv2.FONT_HERSHEY_SIMPLEX
font_scale = 1.2
font_color = (255, 255, 255)  # White color
thickness = 2
position = (30, 50)  # Top-left position

# Process each pair of images
for i in range(num_frames):
    # Read left and right images
    left_img = cv2.imread(os.path.join(left_path, left_image_files[i]))
    right_img = cv2.imread(os.path.join(right_path, right_image_files[i]))

    # Check if images were loaded correctly
    if left_img is None or right_img is None:
        print(f"Warning: Could not read frame {i+1}. Skipping.")
        continue

    # Add text labels to each image
    cv2.putText(left_img, 'Left', position, font, font_scale, font_color, thickness, cv2.LINE_AA)
    cv2.putText(right_img, 'Right', position, font, font_scale, font_color, thickness, cv2.LINE_AA)

    # Combine images horizontally
    combined_img = np.hstack((left_img, right_img))
    
    # Write frame to video
    out.write(combined_img)
    
    # Optional: display progress
    print(f"Processing frame {i+1}/{num_frames}: {left_image_files[i]} and {right_image_files[i]}")

# Release video writer
out.release()
print(f"\nVideo creation completed: {output_filename}")