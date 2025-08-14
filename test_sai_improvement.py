#!/usr/bin/env python3
"""
Test script to validate the improved SAI calculation

This script tests the new Scene Activity Index calculation to ensure
it provides better discrimination than the previous version.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from detection.region_manager import RegionManager
from detection.metrics_calculator import MetricsCalculator, FrameMetrics

def test_sai_improvement():
    """Test the improved SAI calculation with various scenarios"""
    
    print("Testing Improved SAI Calculation")
    print("=" * 50)
    
    # Initialize components
    region_manager = RegionManager(1920, 1080)  # 1080p video
    calculator = MetricsCalculator(1920, 1080)
    
    # Test scenarios
    test_scenarios = [
        {
            "name": "No person detections",
            "detections": []
        },
        {
            "name": "Small person in upper area", 
            "detections": [
                {"bbox": [800, 200, 900, 300], "class_name": "person", "confidence": 0.8}
            ]
        },
        {
            "name": "Medium person in bottom center",
            "detections": [
                {"bbox": [860, 700, 1060, 1000], "class_name": "person", "confidence": 0.9}
            ]
        },
        {
            "name": "Large person in bottom left",
            "detections": [
                {"bbox": [50, 600, 400, 1050], "class_name": "person", "confidence": 0.95}
            ]
        },
        {
            "name": "Very large person covering bottom",
            "detections": [
                {"bbox": [200, 500, 1200, 1080], "class_name": "person", "confidence": 0.92}
            ]
        },
        {
            "name": "Multiple people, one likely self",
            "detections": [
                {"bbox": [100, 100, 200, 300], "class_name": "person", "confidence": 0.7},
                {"bbox": [700, 650, 1000, 1000], "class_name": "person", "confidence": 0.9}
            ]
        }
    ]
    
    print(f"Testing {len(test_scenarios)} scenarios:")
    print()
    
    results = []
    
    for i, scenario in enumerate(test_scenarios):
        print(f"Scenario {i+1}: {scenario['name']}")
        
        # Create detection frame data
        detection_data = {
            "detections": scenario["detections"]
        }
        
        # Process the frame
        frame_metrics = calculator.process_detection_frame(i, detection_data)
        
        # Calculate individual self-appearance scores for each person
        person_scores = []
        for detection in scenario["detections"]:
            if detection["class_name"] == "person":
                bbox = tuple(detection["bbox"])
                score = region_manager.calculate_self_appearance_score(bbox)
                person_scores.append(score)
                
                print(f"  Person {detection['bbox']}: Self-score = {score:.3f}")
        
        print(f"  Frame self-appearance score: {frame_metrics.self_appearance_score:.3f}")
        print(f"  Traditional has_self_appearance: {frame_metrics.has_self_appearance}")
        print()
        
        results.append({
            "scenario": scenario["name"],
            "self_score": frame_metrics.self_appearance_score,
            "has_self": frame_metrics.has_self_appearance,
            "person_count": len([d for d in scenario["detections"] if d["class_name"] == "person"])
        })
    
    # Calculate final SAI using multiple frames
    print("Final SAI Calculation:")
    print("-" * 30)
    
    final_metrics = calculator.calculate_final_metrics(
        total_frames=len(test_scenarios), 
        sampling_rates={"detection": 1, "segmentation": 1}
    )
    
    print(f"Traditional SAI (binary): {final_metrics.SAI:.2f}%")
    print(f"Frames with self-appearance: {len([r for r in results if r['has_self']])}/{len(results)}")
    print()
    
    # Show score distribution
    print("Score Distribution:")
    for result in results:
        status = "PASS" if result["self_score"] > 0.1 else "FAIL"
        print(f"  [{status}] {result['scenario']}: {result['self_score']:.3f}")
    
    print()
    print("Test completed! The new SAI calculation should show:")
    print("  - Better discrimination between scenarios")
    print("  - Non-zero values for realistic self-appearance cases")
    print("  - Graduated scores rather than binary 0/1 results")
    
    # Validation
    non_zero_scores = [r for r in results if r["self_score"] > 0.0]
    print(f"\nValidation: {len(non_zero_scores)}/{len(results)} scenarios have non-zero SAI scores")
    
    if len(non_zero_scores) >= 3:
        print("SUCCESS: Improved SAI provides better discrimination!")
    else:
        print("NEEDS WORK: SAI still not discriminative enough")

if __name__ == "__main__":
    test_sai_improvement()