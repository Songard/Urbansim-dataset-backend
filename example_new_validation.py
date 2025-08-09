#!/usr/bin/env python3
"""
New Validation System Example

Demonstrates the new extensible validation framework:
1. Validation Manager with multiple validators
2. Automatic validator selection
3. Extensible scoring and validation logic
4. Future-ready architecture
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import get_logger, log_system_startup
from validation import ValidationManager, ValidationLevel, MetaCamValidator
from processors.archive_handler import ArchiveHandler

logger = get_logger(__name__)

class NewValidationDemo:
    """New validation system demonstration"""
    
    def __init__(self):
        self.validation_manager = ValidationManager()
        self.archive_handler = ArchiveHandler()
        
    def demonstrate_validation_manager(self):
        """Demonstrate the new validation manager capabilities"""
        logger.info("=== New Validation System Demo ===")
        
        # Show available validators
        available_validators = self.validation_manager.get_available_validators()
        logger.info(f"Available validators: {available_validators}")
        
        # Show supported formats
        supported_formats = self.validation_manager.get_supported_formats()
        logger.info(f"Supported formats: {supported_formats}")
        
        # Create test structure
        temp_dir = self._create_test_structure()
        if not temp_dir:
            logger.error("Failed to create test structure")
            return
        
        try:
            # Test 1: Automatic validator selection
            logger.info("\n--- Test 1: Automatic Validator Selection ---")
            result = self.validation_manager.validate(temp_dir, ValidationLevel.STANDARD)
            self._print_result("Auto-selection", result)
            
            # Test 2: Explicit validator selection
            logger.info("\n--- Test 2: Explicit Validator Selection ---")
            result = self.validation_manager.validate(
                temp_dir, 
                ValidationLevel.STRICT,
                validator_name="MetaCamValidator"
            )
            self._print_result("Explicit MetaCam", result)
            
            # Test 3: Format hint usage
            logger.info("\n--- Test 3: Format Hint Usage ---")
            result = self.validation_manager.validate(
                temp_dir,
                ValidationLevel.LENIENT, 
                format_hint='metacam'
            )
            self._print_result("Format hint", result)
            
            # Test 4: Multiple validation levels
            logger.info("\n--- Test 4: Multiple Validation Levels ---")
            for level in [ValidationLevel.STRICT, ValidationLevel.STANDARD, ValidationLevel.LENIENT]:
                result = self.validation_manager.validate(temp_dir, level)
                logger.info(f"{level.value}: Score={result.score:.1f}, Valid={result.is_valid}")
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def demonstrate_archive_integration(self):
        """Demonstrate integration with archive handler"""
        logger.info("\n=== Archive Handler Integration ===")
        
        # This demonstrates how the new system integrates
        logger.info("Archive handler now uses ValidationManager instead of DataFormatValidator")
        logger.info("Benefits:")
        logger.info("  1. Pluggable validators - easy to add new data types")
        logger.info("  2. Consistent validation interface across all validators")  
        logger.info("  3. Centralized validation management")
        logger.info("  4. Automatic validator selection based on data type")
        logger.info("  5. Extensible scoring algorithms")
        logger.info("  6. Better error handling and reporting")
        
        # Show current validation flow
        logger.info("\nCurrent validation flow in archive processing:")
        logger.info("  1. Extract archive -> temporary directory")
        logger.info("  2. ValidationManager.validate(directory, level, format_hint)")
        logger.info("  3. Manager selects appropriate validator (MetaCamValidator)")
        logger.info("  4. Validator performs comprehensive validation")
        logger.info("  5. Return structured ValidationResult with score")
        logger.info("  6. Archive handler processes result and updates sheet")
    
    def demonstrate_extensibility(self):
        """Show how to extend the validation system"""
        logger.info("\n=== Extensibility Examples ===")
        
        logger.info("Adding new validators is straightforward:")
        logger.info("""
# Example: Adding a new LiDAR data validator
class LiDARValidator(BaseValidator):
    def get_supported_formats(self):
        return ['lidar', 'las', 'point_cloud']
    
    def validate(self, target_path, validation_level):
        # Custom LiDAR validation logic
        # Return ValidationResult
        pass

# Register with manager
manager = ValidationManager()
manager.register_validator(LiDARValidator())
        """)
        
        logger.info("Custom scoring algorithms:")
        logger.info("""
# Override scoring in validator
def calculate_score(self, errors, warnings, missing_files, missing_dirs):
    # Custom scoring logic for specific data type
    score = 100.0
    # Apply domain-specific penalties
    return max(0.0, score - penalties)
        """)
        
        logger.info("Future extensibility options:")
        logger.info("  - Plugin system for external validators")
        logger.info("  - Machine learning-based validation scoring") 
        logger.info("  - Real-time validation result caching")
        logger.info("  - Validation rule configuration via external files")
        logger.info("  - Multi-threaded validation for large datasets")
    
    def _create_test_structure(self) -> str:
        """Create a test MetaCam structure"""
        temp_base = tempfile.gettempdir()
        test_dir = os.path.join(temp_base, f"test_new_validation_{datetime.now().strftime('%H%M%S')}")
        
        try:
            os.makedirs(test_dir, exist_ok=True)
            
            # Create basic MetaCam structure
            directories = ["camera", "camera/left", "camera/right", "data", "info"]
            for directory in directories:
                os.makedirs(os.path.join(test_dir, directory), exist_ok=True)
            
            # Create key files
            files = [
                ("colorized-realtime.las", 2 * 1024 * 1024),
                ("points3D.ply", 5 * 1024 * 1024), 
                ("Preview.jpg", 500 * 1024),
                ("Preview.pcd", 10 * 1024 * 1024),
                ("data/data_0", 20 * 1024 * 1024)
            ]
            
            for file_path, size in files:
                full_path = os.path.join(test_dir, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'wb') as f:
                    f.write(b'0' * size)
            
            # Create metadata.yaml
            metadata_content = """
data_type: "MetaCam 3D Reconstruction"
timestamp: "2025-01-08T12:00:00Z"
location: 
  latitude: 39.9042
  longitude: 116.4074
"""
            with open(os.path.join(test_dir, "metadata.yaml"), 'w') as f:
                f.write(metadata_content)
            
            # Create JSON files
            import json
            json_files = {
                "info/calibration.json": {
                    "camera_matrix": [[1000, 0, 320], [0, 1000, 240], [0, 0, 1]],
                    "distortion_coeffs": [0.1, -0.2, 0, 0, 0]
                },
                "info/device_info.json": {
                    "device_id": "METACAM_001",
                    "firmware_version": "v1.2.3"
                },
                "info/rtk_info.json": {
                    "status": "active"
                }
            }
            
            for file_path, content in json_files.items():
                full_path = os.path.join(test_dir, file_path)
                with open(full_path, 'w') as f:
                    json.dump(content, f, indent=2)
            
            logger.info(f"Created test structure: {test_dir}")
            return test_dir
            
        except Exception as e:
            logger.error(f"Failed to create test structure: {e}")
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir, ignore_errors=True)
            return None
    
    def _print_result(self, test_name: str, result):
        """Print validation result in a clean format"""
        logger.info(f"\n{test_name} Result:")
        logger.info(f"  Status: {'PASS' if result.is_valid else 'FAIL'}")
        logger.info(f"  Score: {result.score:.1f}/100")
        logger.info(f"  Level: {result.validation_level.value}")
        logger.info(f"  Validator: {result.validator_type}")
        
        if result.errors:
            logger.info(f"  Errors ({len(result.errors)}): {result.errors[:2]}")
        
        if result.warnings:
            logger.info(f"  Warnings ({len(result.warnings)}): {result.warnings[:2]}")
        
        logger.info(f"  Summary: {result.summary}")

def main():
    """Main demonstration function"""
    try:
        # Initialize logging
        log_system_startup()
        
        # Run demonstrations
        demo = NewValidationDemo()
        demo.demonstrate_validation_manager()
        demo.demonstrate_archive_integration() 
        demo.demonstrate_extensibility()
        
        logger.success("New validation system demonstration completed!")
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())