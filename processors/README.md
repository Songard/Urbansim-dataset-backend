# Processors Directory

This directory contains Windows executable packages for data processing.

## Structure

- `exe_packages/` - Contains Windows .exe files for data processing
  - Place your Windows executable programs here
  - These files are excluded from git tracking

## Required Executables

### 1. validation_generator.exe
**Purpose**: Initial data validation and file listing
**Usage**: `validation_generator.exe <data_path>`
**Output**: Lists processed data files in format `file: No.X: <path>`

### 2. metacam_cli.exe
**Purpose**: Main 3D reconstruction processing
**Usage**: `metacam_cli.exe -i <input> -o <output> -s <scene> -color <0|1> -mode <0|1>`
**Parameters**:
- `-i`: Input data path
- `-o`: Output directory path  
- `-s`: Scene type (0=Balance, 1=Open/Outdoor, 2=Narrow/Indoor)
- `-color`: Enable coloring (0=No, 1=Yes)
- `-mode`: Processing mode (0=Fast, 1=Precision)

## Automatic Scene Detection

The system automatically determines scene type based on validation results:

- **Open (1)**: Detected outdoor scenes
- **Narrow (2)**: Indoor scenes with max dimension < 30m
- **Balance (0)**: All other cases (default)

## Configuration

Set processing parameters in `config.py` or environment variables:

```python
# Processing mode (0=fast, 1=precision)
METACAM_CLI_MODE = "0"  

# Enable coloring (0=no, 1=yes)
METACAM_CLI_COLOR = "1"

# Processing timeout (1 hour default)
METACAM_CLI_TIMEOUT_SECONDS = 3600

# Scale threshold for narrow scenes  
INDOOR_SCALE_THRESHOLD_M = 30.0
```

## Processing Flow

1. **Data Validation**: System validates uploaded data
2. **Automatic Processing**: If validation passes:
   - Extract data to temporary directory
   - Run `validation_generator.exe` first
   - Run `metacam_cli.exe` with determined scene type
   - Monitor processing time and resource usage
   - Log detailed results

## Output

Processed results are saved to:
```
processed/output/<dataset_name>_output/
├── processed_pointcloud.ply
├── reconstruction_mesh.obj
├── camera_poses.txt
└── processing_log.txt
```

## Installation

1. Copy your Windows executables to `exe_packages/`:
   ```
   processors/exe_packages/
   ├── validation_generator.exe
   └── metacam_cli.exe
   ```

2. Ensure executables are compatible with your Windows environment

3. The system will automatically detect and use them

## Notes

- All .exe files in this directory are ignored by git
- Processing can take significant time (hours for large datasets)
- System includes timeout protection and detailed logging
- Failed processing attempts are logged with full error details