import argparse
import os
from typing import List

import cv2
import numpy as np
import torch
import torchvision
from tqdm import tqdm


def parse_args():
    parser = argparse.ArgumentParser(description="Batch face/plate masking on CUDA")

    parser.add_argument(
        "--face_model_path",
        required=False,
        type=str,
        default=None,
        help="Absolute EgoBlur face model file path",
    )

    parser.add_argument(
        "--lp_model_path",
        required=False,
        type=str,
        default=None,
        help="Absolute EgoBlur license plate model file path",
    )

    parser.add_argument(
        "--face_model_score_threshold",
        required=False,
        type=float,
        default=0.5,
        help="Face model score threshold to filter out low confidence detections",
    )

    parser.add_argument(
        "--lp_model_score_threshold",
        required=False,
        type=float,
        default=0.5,
        help="License plate model score threshold to filter out low confidence detections",
    )

    parser.add_argument(
        "--nms_iou_threshold",
        required=False,
        type=float,
        default=0.3,
        help="NMS IoU threshold to filter out overlapping boxes",
    )

    parser.add_argument(
        "--input_dir",
        required=True,
        type=str,
        help="Absolute path to directory containing images to process",
    )

    parser.add_argument(
        "--output_dir",
        required=True,
        type=str,
        help="Absolute path to directory where processed images will be saved",
    )

    parser.add_argument(
        "--mask_dir",
        required=True,
        type=str,
        help="Absolute path to directory where masks will be saved",
    )

    parser.add_argument(
        "--scale_factor_detections",
        required=False,
        type=float,
        default=1.1,
        help="Scale detections by the given factor to allow masking more area, 1.15 would mean 15% scaling",
    )

    return parser.parse_args()


def get_cuda_device() -> str:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA device is required but not available.")
    return f"cuda:{torch.cuda.current_device()}"


def create_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_image(image_path: str) -> np.ndarray:
    bgr_image = cv2.imread(image_path)
    if bgr_image is None:
        raise ValueError(f"Failed to read image: {image_path}")
    if len(bgr_image.shape) == 2:
        bgr_image = cv2.cvtColor(bgr_image, cv2.COLOR_GRAY2BGR)
    return bgr_image


def write_image(image: np.ndarray, image_path: str) -> None:
    cv2.imwrite(image_path, image)


def get_image_tensor(bgr_image: np.ndarray, device: str) -> torch.Tensor:
    return torch.from_numpy(np.transpose(bgr_image, (2, 0, 1))).to(device)


@torch.no_grad()
def get_detections(
    detector: torch.jit._script.RecursiveScriptModule,
    image_tensor: torch.Tensor,
    score_threshold: float,
    nms_threshold: float,
) -> List[List[float]]:
    boxes, _, scores, _ = detector(image_tensor)
    keep = torchvision.ops.nms(boxes, scores, nms_threshold)
    boxes, scores = boxes[keep].cpu().numpy(), scores[keep].cpu().numpy()
    return boxes[scores > score_threshold].tolist()


def scale_box(box: List[float], max_width: int, max_height: int, scale: float) -> List[float]:
    x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
    w, h = x2 - x1, y2 - y1
    xc, yc = x1 + w / 2, y1 + h / 2
    w, h = scale * w, scale * h
    
    x1 = max(xc - w / 2, 0)
    y1 = max(yc - h / 2, 0)
    x2 = min(xc + w / 2, max_width)
    y2 = min(yc + h / 2, max_height)
    
    return [x1, y1, x2, y2]


def build_and_save_outputs(
    bgr_image: np.ndarray,
    detections: List[List[float]],
    output_image_path: str,
    output_mask_path: str,
    scale_factor: float = 1.0,
) -> None:
    h, w = bgr_image.shape[:2]
    mask = np.full((h, w), 255, dtype=np.uint8)
    ellipse_mask = np.zeros((h, w), dtype=np.uint8)
    masked_image = bgr_image.copy()

    for box in detections:
        if scale_factor != 1.0:
            box = scale_box(box, w, h, scale_factor)
            
        x1, y1, x2, y2 = map(int, box)
        box_w, box_h = x2 - x1, y2 - y1

        if box_w <= 0 or box_h <= 0:
            continue

        center = ((x1 + x2) // 2, (y1 + y2) // 2)
        cv2.ellipse(ellipse_mask, center, (box_w, box_h), 0, 0, 360, 255, -1)

    mask[ellipse_mask == 255] = 0
    masked_image[ellipse_mask == 255] = 0

    write_image(masked_image, output_image_path)
    write_image(mask, output_mask_path)


def process_directory(
    input_dir: str,
    output_dir: str,
    mask_dir: str,
    face_detector: torch.jit._script.RecursiveScriptModule,
    lp_detector: torch.jit._script.RecursiveScriptModule,
    face_threshold: float,
    lp_threshold: float,
    nms_threshold: float,
    device: str,
    scale_factor: float = 1.0,
) -> None:
    # Create output directories - images go to output_dir, masks go to mask_dir
    create_dir(output_dir)
    create_dir(mask_dir)

    supported_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
    image_files = [
        f
        for f in os.listdir(input_dir)
        if any(f.lower().endswith(ext) for ext in supported_extensions)
    ]

    if not image_files:
        print(f"No supported image files found in {input_dir}")
        return

    for filename in tqdm(image_files, desc="Processing images", unit="image"):
        input_path = os.path.join(input_dir, filename)
        bgr_image = read_image(input_path)
        image_tensor = get_image_tensor(bgr_image, device)

        detections = []
        if face_detector is not None:
            detections.extend(get_detections(face_detector, image_tensor, face_threshold, nms_threshold))
        if lp_detector is not None:
            detections.extend(get_detections(lp_detector, image_tensor.clone(), lp_threshold, nms_threshold))

        name, _ = os.path.splitext(filename)
        output_image_path = os.path.join(output_dir, f"{name}.jpg")
        output_mask_path = os.path.join(mask_dir, f"{name}.png")

        try:
            build_and_save_outputs(bgr_image, detections, output_image_path, output_mask_path, scale_factor)
        except Exception as e:
            tqdm.write(f"Error processing {filename}: {str(e)}")
            continue


def main():
    args = parse_args()

    if args.face_model_path is None and args.lp_model_path is None:
        raise ValueError("Please provide either --face_model_path or --lp_model_path or both")
    if not os.path.exists(args.input_dir):
        raise ValueError(f"Input directory does not exist: {args.input_dir}")
    
    create_dir(args.output_dir)
    device = get_cuda_device()
    face_detector = None
    if args.face_model_path is not None:
        if not os.path.exists(args.face_model_path):
            raise ValueError(f"Face model path does not exist: {args.face_model_path}")
        face_detector = torch.jit.load(args.face_model_path, map_location="cpu").to(device)
        face_detector.eval()

    lp_detector = None
    if args.lp_model_path is not None:
        if not os.path.exists(args.lp_model_path):
            raise ValueError(f"License plate model path does not exist: {args.lp_model_path}")
        lp_detector = torch.jit.load(args.lp_model_path, map_location="cpu").to(device)
        lp_detector.eval()

    process_directory(
        args.input_dir,
        args.output_dir,
        args.mask_dir,
        face_detector,
        lp_detector,
        args.face_model_score_threshold,
        args.lp_model_score_threshold,
        args.nms_iou_threshold,
        device,
        args.scale_factor_detections,
    )


if __name__ == "__main__":
    main()