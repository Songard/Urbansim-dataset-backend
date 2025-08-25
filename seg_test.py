import cv2
import numpy as np
from ultralytics import YOLO
import matplotlib.pyplot as plt
import argparse
import os


def segment_and_visualize(image_path, model_path):
    """
    Segment and visualize specified image using YOLO11n segmentation model
    
    Args:
        image_path (str): Input image path
        model_path (str): YOLO model path
    """
    # Load YOLO model
    model = YOLO(model_path)
    
    # Read image
    if not os.path.exists(image_path):
        print(f"Error: Cannot find image file {image_path}")
        return
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Cannot read image file {image_path}")
        return
    
    # Convert to RGB format (OpenCV uses BGR by default)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Perform segmentation
    print("Performing image segmentation...")
    results = model(image_path)
    
    # Create visualization
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    
    # Display original image
    axes[0].imshow(image_rgb)
    axes[0].set_title('Original Image')
    axes[0].axis('off')
    
    # Display segmentation results
    if results[0].masks is not None and results[0].boxes is not None:
        # Get segmentation masks and class information
        masks = results[0].masks.data.cpu().numpy()
        classes = results[0].boxes.cls.cpu().numpy()
        confidences = results[0].boxes.conf.cpu().numpy()
        
        # Filter for person class only (class ID 0 in COCO dataset)
        person_indices = [i for i, cls in enumerate(classes) if int(cls) == 0]
        
        if person_indices:
            # Filter masks and confidences for person class
            person_masks = [masks[i] for i in person_indices]
            person_confidences = [confidences[i] for i in person_indices]
            
            # Create colored mask
            colored_mask = np.zeros_like(image_rgb)
            colors = plt.cm.Set3(np.linspace(0, 1, len(person_masks)))
            
            for i, (mask, color) in enumerate(zip(person_masks, colors)):
                # Resize mask to match original image
                mask_resized = cv2.resize(mask.astype(np.uint8), 
                                        (image_rgb.shape[1], image_rgb.shape[0]))
                
                # Apply color
                for c in range(3):
                    colored_mask[:, :, c] = np.where(mask_resized > 0.5, 
                                                   color[c] * 255, 
                                                   colored_mask[:, :, c])
            
            # Display segmentation mask
            axes[1].imshow(colored_mask.astype(np.uint8))
            axes[1].set_title(f'Person Segmentation ({len(person_masks)} persons)')
            axes[1].axis('off')
            
            # Display overlay result
            overlay = cv2.addWeighted(image_rgb, 0.6, colored_mask.astype(np.uint8), 0.4, 0)
            axes[2].imshow(overlay)
            axes[2].set_title('Person Overlay Result')
            axes[2].axis('off')
            
            # Print detection information
            print(f"Detected {len(person_masks)} person(s)")
            class_names = model.names
            for i, conf in enumerate(person_confidences):
                print(f"Person {i+1}: {class_names[0]} (confidence: {conf:.2f})")
        else:
            axes[1].text(0.5, 0.5, 'No persons detected', ha='center', va='center', transform=axes[1].transAxes)
            axes[1].set_title('No Persons Found')
            axes[1].axis('off')
            axes[2].imshow(image_rgb)
            axes[2].set_title('No Person Results')
            axes[2].axis('off')
            print("No persons detected")
    else:
        axes[1].text(0.5, 0.5, 'No segmentation objects detected', ha='center', va='center', transform=axes[1].transAxes)
        axes[1].axis('off')
        axes[2].imshow(image_rgb)
        axes[2].set_title('No Segmentation Results')
        axes[2].axis('off')
        print("No objects detected")
    
    plt.tight_layout()
    plt.show()
    
    # Save results
    output_path = os.path.splitext(image_path)[0] + '_person_segmented.jpg'
    if results[0].masks is not None and results[0].boxes is not None:
        classes = results[0].boxes.cls.cpu().numpy()
        person_indices = [i for i, cls in enumerate(classes) if int(cls) == 0]
        if person_indices:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"Person segmentation results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Segment and visualize images using YOLO11n segmentation model')
    parser.add_argument('--image', '-i', type=str, required=True, help='Input image path')
    parser.add_argument('--model', '-m', type=str, 
                       default=r'C:\Users\15436\Documents\MyPrograms\Urbansim\yolo11n-seg.pt',
                       help='YOLO model path')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.model):
        print(f"Error: Cannot find model file {args.model}")
        return
    
    segment_and_visualize(args.image, args.model)


if __name__ == "__main__":
    main()