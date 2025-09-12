# MetaCam Data Validation Documentation

This document describes all validation checks performed by the MetaCam Data Processing System. This comprehensive validation ensures data quality and integrity before processing 3D reconstruction datasets. This documentation is maintained alongside the validation code and updated whenever validation logic changes.

## Overview

The validation system performs comprehensive checks on MetaCam data packages to ensure data quality and integrity before processing. The system uses a **pipeline validation approach** where multiple validators work in sequence to provide comprehensive data quality assessment.

### Validation Pipeline Architecture

**Single Data Format**: All data packages follow the MetaCam format as defined by `data_schemas/metacam_schema.yaml`

**Pipeline Stages**:
1. **Basic Format Validation** (MetaCamValidator): Validates directory structure, required files, and metadata
2. **Transient Object Detection** (TransientValidator): Analyzes camera images for moving obstacles (if camera directory exists)

**Result Combination**: 
- Combined score = Basic Format (70%) + Transient Detection (30%)
- Overall validation passes only if basic format validation passes
- Transient detection enhances the validation but doesn't block processing if unavailable

## Validation Checks

### Pipeline Stage 1: Basic Format Validation (MetaCamValidator)

This stage validates the fundamental structure and files of MetaCam data packages according to the schema definition.

#### 1.1 Directory Structure Validation

**Required Directories** (per `metacam_schema.yaml`):
- `images/` - Camera image data directory
- `data/` - Raw sensor data directory
- `info/` - Device information and configuration directory

**Validation Rules**:
- All required directories must exist
- Missing required directories result in validation failure
- Missing optional subdirectories generate warnings

#### 1.2 Required Files Validation

**Root Directory Files**:
- `colorized-realtime.las` - Colored point cloud data (1MB-1GB)
- `metadata.yaml` - Recording metadata (100B-10KB)
- `Preview.jpg` - Preview image (1KB-10MB)
- `Preview.pcd` - Preview point cloud (1KB-100MB)

**Data Directory Files**:
- `data/data_0` - Primary sensor data file (1MB-2GB)
  - Supports flexible naming: `data_0` (no extension) or `data_0.bag` (ROS bag format)
  - Automatic detection and validation of both formats

**Info Directory Files**:
- `info/calibration.json` - Camera calibration parameters
- `info/device_info.json` - Device information and metadata
  - Contains device model, serial number, hardware configuration
  - Used for automatic device ID generation (`{model}-{SN}`)
- `info/rtk_info.json` - RTK positioning data

#### 1.3 Metadata File Validation

**File**: `metadata.yaml`

**Purpose**: Validates the presence and content of the metadata file that describes the entire dataset.

**Required Fields**:
- `record.start_time`: Start time of data recording
- `record.duration`: Duration of data recording session  
- `record.location.lat`: Latitude coordinate
- `record.location.lon`: Longitude coordinate

**Validation Rules**:

#### Duration Validation
- **Optimal Range**: 4.5-7 minutes
- **Warning Conditions**: 
  - Duration 3-4.5 minutes: Issues warning for potentially insufficient data
  - Duration > 7 minutes: Issues warning for potentially excessive data
- **Error Conditions**:
  - Duration < 3 minutes: Fails validation (insufficient data)
  - Duration > 9 minutes: Fails validation (excessive data that may indicate recording issues)

#### Data Upload
The following metadata information is automatically uploaded to Google Sheets:
- **Start Time**: Recording start time from metadata
- **Duration**: Recording duration (HH:MM:SS format) with color-coded background:
  - 🟢 **Green**: Optimal range (4.5-7 minutes)
  - 🟡 **Yellow**: Warning range (3-4.5 min or >7 min)  
  - 🔴 **Red**: Error range (<3 min or >9 min)
  - ⚪ **Gray**: Parse error or unknown
- **Location**: Combined coordinates (latitude, longitude)
- **Device ID**: Automatically extracted device identifier ({model}-{SN})
- **Validation Score**: Overall validation score (0-100)
- **Validation Status**: Pass/warning/error with specific, actionable error messages

### 2. File Structure Validation

**Purpose**: Ensures proper file organization and presence of required files.

**Checks**:
- Presence of required directory structure
- Existence of mandatory files
- File naming conventions
- File size validations

### 3. PCD Point Cloud Scale Validation

**File**: `Preview.pcd`

**Purpose**: Validates the spatial scale of point cloud data to ensure it's within reasonable ranges for scene reconstruction.

**Detection Strategy**:
- Searches for `Preview.pcd` file (case-insensitive)
- First checks root directory, then recursively searches subdirectories
- Parses up to 100,000 points to avoid memory issues

**Scale Validation Rules**:

#### Optimal Range
- **Target Scale**: ~100m × 100m (typical urban scene)
- **Acceptable Range**: 50m - 200m in any dimension
- **Status**: `optimal` - Green indicator in sheets

#### Warning Conditions
- **Small Scale**: 10m - 50m
  - Status: `warning_small` - Yellow indicator
  - Typical for indoor scenes or small areas
- **Large Scale**: 200m - 500m  
  - Status: `warning_large` - Yellow indicator
  - Typical for large outdoor areas
- **Narrow Shape**: One dimension < 25m while other is acceptable
  - Status: `warning_narrow` - Yellow indicator
  - Indicates elongated scene coverage

#### Error Conditions
- **Too Small**: < 10m
  - Status: `error_too_small` - Red indicator
  - May indicate object-level scanning instead of scene
- **Too Large**: > 500m
  - Status: `error_too_large` - Red indicator  
  - May indicate aerial/satellite data or processing errors

#### Data Upload
The following PCD scale information is automatically uploaded to Google Sheets:
- **PCD Scale**: Scale validation status with color coding:
  - 🟢 **Green**: Optimal range (50m-200m)
  - 🟡 **Yellow**: Warning range (10m-50m or 200m-500m)
  - 🔴 **Red**: Error range (<10m or >500m)
  - ℹ️ **Gray**: File not found or parsing error

**Technical Implementation**:
- Supports PCD v0.7 format in both ASCII and binary encoding
- Parses X, Y, Z coordinates to calculate bounding box
- Binary format uses 32-bit little-endian floats
- Computes width, height, depth, and coverage area
- Warning-level validation (doesn't block processing)
- Detailed logging for troubleshooting
- Note: Binary compressed format is not yet supported

### Pipeline Stage 2: Transient Object Detection (TransientValidator)

This stage analyzes camera image sequences for moving obstacles (people, dogs, etc.) using YOLO11 AI models. This validation only runs if the `camera/` directory structure exists and contains image files.

#### 2.1 Camera Directory Detection

**Search Strategy**:
1. Check for `camera/` directory in the target path
2. If not found, recursively search subdirectories (max depth: 2)
3. Verify presence of `camera/left/` and/or `camera/right/` subdirectories
4. Confirm image files exist in camera subdirectories

**Supported Image Formats**: `.jpg`, `.jpeg`, `.png`, `.bmp`

#### 2.2 YOLO Model Validation

**Purpose**: Validates the availability and integrity of YOLO detection and segmentation models for computer vision tasks.

**Models Required**:
- **Detection Model**: `yolo11n.pt` (primary model for object detection)
- **Segmentation Model**: `yolo11n-seg.pt` (enhanced model for instance segmentation)

**Validation Process**:

#### Model Loading Strategy
1. **Detection Model Loading**:
   - Attempts to load specified detection model (default: `yolo11n.pt`)
   - If model file doesn't exist, YOLO will automatically download it
   - Model is moved to specified device (CPU/GPU)
   - **Critical Failure**: If detection model fails to load, system cannot proceed

2. **Segmentation Model Loading**:
   - Attempts to load corresponding segmentation model (e.g., `yolo11n-seg.pt`)
   - If not found locally, automatically attempts to download
   - Falls back to detection model if segmentation model unavailable
   - **Warning Level**: Segmentation failure doesn't block processing but reduces accuracy

#### Validation Status Levels
- **SUCCESS**: Both detection and segmentation models loaded successfully
- **WARNING**: Detection model loaded, segmentation model failed (reduced functionality)
- **CRITICAL ERROR**: Detection model failed to load (system cannot function)

#### Error Handling
- **Model Download Failure**: 
  - Level: `ERROR` (Critical)
  - Message: "CRITICAL: Failed to download segmentation model: {error_details}"
  - System continues with detection-only mode
  
- **Segmentation Fallback**:
  - Level: `ERROR` (Critical but non-blocking)
  - Message: "CRITICAL: Segmentation model not available, falling back to detection model - this may impact accuracy"
  - Each segmentation request triggers this warning

#### Technical Implementation
- **Model Detection**: Automatic generation of segmentation model name from detection model
- **Auto-Download**: Leverages ultralytics YOLO auto-download capability
- **Device Management**: Proper GPU/CPU allocation for loaded models
- **Graceful Degradation**: System continues functioning with reduced capability when segmentation unavailable

#### Monitoring and Alerting
- **Model Status**: Tracked in validation results
- **Performance Impact**: Segmentation failures logged as critical issues affecting accuracy
- **System Health**: Model availability monitored for operational status

#### 2.3 Moving Obstacle Detection Process

**Target Objects**: People (class 0) and dogs (class 16) from COCO dataset

**Processing Pipeline**:
1. **Adaptive Sampling**: Calculate optimal frame sampling rates based on total frame count
2. **Batch Processing**: Process images in batches for efficiency
3. **Detection Analysis**: Use YOLO11 detection model for object identification
4. **Segmentation Analysis**: Use YOLO11 segmentation model for precise object boundaries (if available)
5. **Metrics Calculation**: Compute quality metrics for validation decision

**Quality Metrics**:
- **WDD (Weighted Detection Density)**: Density of detected moving obstacles
- **WPO (Weighted Person Occupancy)**: Percentage of frames with people detected  
- **SAI (Scene Activity Index)**: Overall scene activity level

**Decision Thresholds**:
- **PASS**: Low obstacle density, suitable for reconstruction
- **NEED_REVIEW**: Moderate obstacle presence, manual review recommended
- **REJECT**: High obstacle density, unsuitable for quality reconstruction

#### 2.4 Pipeline Result Combination

**Score Calculation**:
```
Combined Score = (Basic Format Score × 0.7) + (Transient Detection Score × 0.3)
```

**Overall Validation Logic**:
- **PASS**: Basic format validation passes (regardless of transient detection)
- **Enhanced PASS**: Both basic format and transient detection pass
- **FAIL**: Basic format validation fails

**Metadata Integration**:
- Transient detection results added to validation metadata
- Quality metrics (WDD, WPO, SAI) uploaded to Google Sheets
- Detection decision recorded for tracking

### 5. Data Quality Checks

**Purpose**: Validates the quality and integrity of data content.

**Checks**:
- Data format validation
- Content completeness checks
- Data consistency verification
- Schema compliance validation

## Validation Results & Error Handling

### Status Levels
- **PASS**: All critical validations successful, data ready for processing
- **WARNING**: Minor issues detected, manual review recommended but processing can continue
- **ERROR**: Critical issues detected, data rejected and processing halted

### Enhanced Error Messaging

The system provides clear, actionable error messages instead of technical jargon:

**Old Format (Technical)**:
```
Data format validation failed: Pipeline Validation: Basic(19.0) + Transient(10.0) = 16.3/100 - FAIL
```

**New Format (User-Friendly)**:
```
Missing file: info/device_info.json; file metadata.yaml is smaller than required: 45 < 100; Missing folder: camera/left
```

### Error Categorization

Errors are automatically categorized by type for easier troubleshooting:

| Category | Description | Examples |
|----------|-------------|----------|
| **Missing Files** | Required files not found | `Missing file: metadata.yaml` |
| **Missing Directories** | Required folders not found | `Missing folder: camera/left` |
| **File Size Issues** | Files outside acceptable size ranges | `file data_0 is larger than allowed: 3GB > 2GB` |
| **Format Issues** | Invalid file formats or content | `Invalid format in Preview.pcd` |
| **Validation Failures** | Specific validation checks failed | `Duration too short (2.5 min): Less than 3 minutes` |

### Warning Categorization

Warnings provide specific details about potential issues:

| Category | Description | Examples |
|----------|-------------|----------|
| **Scene Naming** | File naming convention issues | `Scene naming does not follow standard convention` |
| **File Size** | Size outside recommended ranges | `File size larger than recommended: Preview.jpg is 15MB` |
| **PCD Scale** | Point cloud dimensions unusual | `PCD scale point cloud dimensions are unusual` |
| **Duration** | Recording time concerns | `Duration recording is only 2.5 minutes` |
| **Location** | GPS/positioning issues | `Location data missing from metadata` |
| **Device Info** | Device metadata problems | `Device info missing model field` |

### Reporting

All validation results are:
1. **Logged to system logs** with detailed technical information
2. **Uploaded to Google Sheets** with color-coded status and user-friendly messages
3. **Available through validation API** for programmatic access
4. **Included in email notifications** (if configured) with actionable summaries

## Usage

### Automatic Pipeline Validation

The validation system runs automatically when processing MetaCam data packages. The system detects MetaCam format and triggers pipeline validation:

```python
from validation.manager import ValidationManager

validator = ValidationManager()
# Automatically detects MetaCam format and runs pipeline validation
results = validator.validate("/path/to/metacam/data")
```

### Manual Validator Selection

You can also run individual validators manually:

```python
# Run only basic format validation
results = validator.validate("/path/to/data", validator_name="MetaCamValidator")

# Run only transient detection (requires camera directory)
results = validator.validate("/path/to/data", validator_name="TransientValidator")
```

### Pipeline Validation Results

Pipeline validation returns enhanced results with combined metrics:

```python
if results.validator_type == "Pipeline(MetaCam+Transient)":
    # Access pipeline-specific metadata
    pipeline_info = results.metadata['validation_pipeline']
    base_score = pipeline_info['base_validation']['score']
    transient_score = pipeline_info['transient_validation']['score']
    combined_score = pipeline_info['combined_score']
```

## Maintenance

This documentation should be updated whenever:
- New validation checks are added
- Existing validation logic is modified
- Validation thresholds are changed
- New data fields are added to sheets upload

---

*Last Updated: 2025-08-15 - Enhanced Error Handling and Device ID Extraction*
*Version: 3.0 - Complete validation pipeline with improved error messaging, device ID extraction, and flexible file naming support*