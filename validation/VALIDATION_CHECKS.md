# Validation Checks Documentation

This document describes all validation checks performed by the Urban Simulation validation system. This documentation is maintained alongside the validation code and will be updated whenever validation logic changes.

## Overview

The validation system performs comprehensive checks on data files and directories to ensure data quality and integrity before processing. All validation results are automatically uploaded to Google Sheets for tracking and monitoring.

## Validation Checks

### 1. Metadata File Validation

**File**: `metadata.yaml`

**Purpose**: Validates the presence and content of the metadata file that describes the entire dataset.

**Required Fields**:
- `record.start_time`: Start time of data recording
- `record.duration`: Duration of data recording session  
- `record.location.lat`: Latitude coordinate
- `record.location.lon`: Longitude coordinate

**Validation Rules**:

#### Duration Validation
- **Optimal Range**: 5-7 minutes
- **Warning Conditions**: 
  - Duration < 5 minutes: Issues warning for potentially insufficient data
  - Duration > 7 minutes: Issues warning for potentially excessive data
- **Error Conditions**:
  - Duration < 3 minutes: Fails validation (insufficient data)
  - Duration > 9 minutes: Fails validation (excessive data that may indicate recording issues)

#### Data Upload
The following metadata information is automatically uploaded to Google Sheets:
- **Start Time**: Recording start time from metadata
- **Duration**: Recording duration (HH:MM:SS format) with color-coded background:
  - 🟢 **Green**: Optimal range (5-7 minutes)
  - 🟡 **Yellow**: Warning range (<5 min or >7 min)  
  - 🔴 **Red**: Error range (<3 min or >9 min)
  - ⚪ **Gray**: Parse error or unknown
- **Location**: Combined coordinates (latitude, longitude)
- **Validation Score**: Overall validation score
- **Validation Status**: Pass/warning/error with detailed messages

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

### 4. Data Quality Checks

**Purpose**: Validates the quality and integrity of data content.

**Checks**:
- Data format validation
- Content completeness checks
- Data consistency verification
- Schema compliance validation

## Validation Results

### Status Levels
- **PASS**: All validations successful
- **WARNING**: Minor issues detected, but processing can continue
- **ERROR**: Critical issues detected, processing should be halted

### Reporting
All validation results are:
1. Logged to the system log
2. Uploaded to Google Sheets with timestamp and details
3. Available through the validation API
4. Included in email notifications (if configured)

## Usage

The validation system runs automatically when processing files. Manual validation can be triggered using:

```python
from validation.manager import ValidationManager

validator = ValidationManager()
results = validator.validate_directory("/path/to/data")
```

## Maintenance

This documentation should be updated whenever:
- New validation checks are added
- Existing validation logic is modified
- Validation thresholds are changed
- New data fields are added to sheets upload

---

*Last Updated: [Auto-generated timestamp]*
*Version: 1.0*